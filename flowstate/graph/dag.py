import networkx as nx
from typing import List, Dict, Optional
from backend.models import Task

def build_dag(tasks: List[Task]) -> nx.DiGraph:
    """
    Build a directed acyclic graph from a list of tasks.
    Edges represent dependencies between tasks.
    """
    G = nx.DiGraph()

    for task in tasks:
        G.add_node(task.task_id or task.task, label=task.task, deadline=task.deadline, owner=task.owner)

    # Add edges based on dependencies
    for task in tasks:
        if task.dependencies:
            for dep in task.dependencies:
                G.add_edge(dep, task.task_id or task.task)

    return G

def get_critical_path(G: nx.DiGraph) -> List[str]:
    """Return the longest path in the DAG — the critical path."""
    return nx.dag_longest_path(G)

def get_bottlenecks(G: nx.DiGraph) -> List[str]:
    """Return nodes with more than 2 incoming edges — bottleneck tasks."""
    return [n for n in G.nodes if G.in_degree(n) > 2]

def get_dag_summary(tasks: List[Task]) -> Dict:
    """Build DAG and return summary with critical path and bottlenecks."""
    G = build_dag(tasks)
    return {
        "total_tasks": G.number_of_nodes(),
        "total_dependencies": G.number_of_edges(),
        "critical_path": get_critical_path(G),
        "bottlenecks": get_bottlenecks(G),
    }