from datetime import datetime, timezone
from typing import Dict, List

import networkx as nx

from flowstate.graph.dag import FlowstateDAG


def get_critical_path(dag: FlowstateDAG) -> List[str]:
    """Return the longest dependency chain (task IDs in order)."""
    return nx.dag_longest_path(dag.G)


def get_bottlenecks(dag: FlowstateDAG, top_n: int = 5) -> List[dict]:
    """Nodes blocking the most other nodes."""
    centrality = nx.betweenness_centrality(dag.G)
    results = [{"task_id": task_id, "score": score} for task_id, score in centrality.items()]
    return sorted(results, key=lambda x: -x["score"])[:top_n]


def get_do_first_tasks(dag: FlowstateDAG, limit: int = 10) -> List[dict]:
    """
    Score = (urgency × impact) / (1 + num_blockers)
    urgency: 1/days_to_deadline
    impact: number of tasks this unblocks
    """
    now = datetime.now(timezone.utc)
    results: List[Dict] = []

    for node_id, data in dag.G.nodes(data=True):
        deadline = data.get("deadline")
        if deadline and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        if deadline:
            days_to_deadline = max((deadline - now).days, 1)
            urgency = 1 / days_to_deadline
        else:
            urgency = 0.1

        impact = len(list(dag.G.successors(node_id)))
        blockers = len(
            [
                pred
                for pred in dag.G.predecessors(node_id)
                if dag.G.nodes[pred].get("status") != "done"
            ]
        )

        score = (urgency * impact) / (1 + blockers)
        results.append({"task_id": node_id, "score": score, **data})

    return sorted(results, key=lambda x: -x["score"])[:limit]


def get_stale_blockers(dag: FlowstateDAG, stale_days: int = 3) -> List[str]:
    """Tasks untouched for N days that are actively blocking something."""
    now = datetime.now(timezone.utc)
    stale: List[str] = []

    for node_id, data in dag.G.nodes(data=True):
        if data.get("status") not in ("open", "in_progress"):
            continue

        updated = data.get("updated_at")
        if not updated:
            continue

        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)

        if (now - updated).days >= stale_days and dag.G.out_degree(node_id) > 0:
            stale.append(node_id)

    return stale
