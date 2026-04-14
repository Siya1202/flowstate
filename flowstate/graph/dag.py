from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence
import uuid

import networkx as nx

from flowstate.infra import get_db_session
from flowstate.infra.models import Dependency, GraphSnapshot, Task, Team


@dataclass
class MergeResult:
    created_task_ids: List[str]
    deduped_task_ids: List[str]
    created_dependency_ids: List[str]


class FlowstateDAG:
    def __init__(self, team_id: str):
        self.team_id = team_id
        self.G = nx.DiGraph()

    def load_from_db(self):
        """Load the live graph for this team from Postgres."""
        self.G.clear()
        with get_db_session() as db:
            tasks = db.query(Task).filter_by(team_id=self.team_id).all()
            deps = (
                db.query(Dependency)
                .join(Task, Dependency.from_task_id == Task.id)
                .filter(Task.team_id == self.team_id)
                .all()
            )

        for task in tasks:
            self.G.add_node(
                task.id,
                title=task.title,
                owner=task.owner,
                deadline=task.deadline,
                status=task.status.value if hasattr(task.status, "value") else task.status,
                updated_at=task.updated_at,
                created_at=task.created_at,
                team_id=task.team_id,
            )
        for dep in deps:
            self.G.add_edge(dep.from_task_id, dep.to_task_id, type=dep.dep_type)

    def merge_new_tasks(self, new_tasks: Sequence[Any], new_deps: Sequence[Dict[str, Any]]) -> MergeResult:
        """Merge extraction output into the live graph with tenant-safe deduping."""
        created_task_ids: List[str] = []
        deduped_task_ids: List[str] = []
        created_dependency_ids: List[str] = []

        with get_db_session() as db:
            self._ensure_team_exists(db)
            existing_tasks = db.query(Task).filter(Task.team_id == self.team_id).all()
            dedupe_index = {
                self._dedupe_key(t.title, t.owner): t.id
                for t in existing_tasks
                if t.title
            }

            resolved_task_id_by_label: Dict[str, str] = {}

            for raw_task in new_tasks:
                title = self._read_field(raw_task, "title") or self._read_field(raw_task, "task")
                owner = self._read_owner(raw_task)
                deadline = self._parse_deadline(self._read_field(raw_task, "deadline"))
                label = self._read_field(raw_task, "id") or title

                if not title:
                    continue

                key = self._dedupe_key(title, owner)
                task_id = dedupe_index.get(key)

                if not task_id:
                    similar_task_id = self._find_similar_existing_id(title, owner, existing_tasks)
                    task_id = similar_task_id

                if task_id:
                    deduped_task_ids.append(task_id)
                else:
                    created = Task(
                        id=str(uuid.uuid4()),
                        title=title,
                        owner=owner,
                        deadline=deadline,
                        team_id=self.team_id,
                    )
                    db.add(created)
                    db.flush()
                    task_id = created.id
                    existing_tasks.append(created)
                    dedupe_index[key] = task_id
                    created_task_ids.append(task_id)

                if label:
                    resolved_task_id_by_label[str(label)] = task_id
                resolved_task_id_by_label[title] = task_id

            for dep in new_deps:
                from_ref = dep.get("from_task_id") or dep.get("from") or dep.get("source")
                to_ref = dep.get("to_task_id") or dep.get("to") or dep.get("target")
                dep_type = dep.get("dep_type") or dep.get("type") or "blocks"

                from_task_id = self._resolve_task_ref(from_ref, resolved_task_id_by_label)
                to_task_id = self._resolve_task_ref(to_ref, resolved_task_id_by_label)
                if not from_task_id or not to_task_id:
                    continue

                existing_dep = (
                    db.query(Dependency)
                    .filter(
                        Dependency.from_task_id == from_task_id,
                        Dependency.to_task_id == to_task_id,
                    )
                    .first()
                )
                if existing_dep:
                    continue

                created_dep = Dependency(
                    id=str(uuid.uuid4()),
                    from_task_id=from_task_id,
                    to_task_id=to_task_id,
                    dep_type=dep_type,
                )
                db.add(created_dep)
                db.flush()
                created_dependency_ids.append(created_dep.id)

            db.commit()

        self.load_from_db()
        return MergeResult(
            created_task_ids=created_task_ids,
            deduped_task_ids=deduped_task_ids,
            created_dependency_ids=created_dependency_ids,
        )

    def save_snapshot(self) -> str:
        """Persist a versioned snapshot with a diff summary from last snapshot."""
        now = datetime.now(timezone.utc)
        payload = self._make_json_safe(nx.node_link_data(self.G))

        with get_db_session() as db:
            self._ensure_team_exists(db)
            previous = (
                db.query(GraphSnapshot)
                .filter(GraphSnapshot.team_id == self.team_id)
                .order_by(GraphSnapshot.created_at.desc())
                .first()
            )

            previous_graph = nx.DiGraph()
            if previous and previous.payload:
                previous_graph = nx.node_link_graph(previous.payload)

            diff_summary = {
                "added_nodes": max(self.G.number_of_nodes() - previous_graph.number_of_nodes(), 0),
                "removed_nodes": max(previous_graph.number_of_nodes() - self.G.number_of_nodes(), 0),
                "added_edges": max(self.G.number_of_edges() - previous_graph.number_of_edges(), 0),
                "removed_edges": max(previous_graph.number_of_edges() - self.G.number_of_edges(), 0),
            }

            snapshot = GraphSnapshot(
                id=str(uuid.uuid4()),
                team_id=self.team_id,
                created_at=now,
                node_count=self.G.number_of_nodes(),
                edge_count=self.G.number_of_edges(),
                payload=payload,
                diff_summary=diff_summary,
            )
            db.add(snapshot)
            db.commit()
            return snapshot.id

    def _ensure_team_exists(self, db):
        team = db.query(Team).filter(Team.id == self.team_id).first()
        if team:
            return
        db.add(Team(id=self.team_id, name=self.team_id))
        db.flush()

    @staticmethod
    def _read_field(obj: Any, key: str):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def _read_owner(self, obj: Any):
        owner = self._read_field(obj, "owner")
        if isinstance(owner, list):
            return ", ".join(str(item) for item in owner)
        return owner

    @staticmethod
    def _dedupe_key(title: str, owner: Optional[str]) -> str:
        normalized_title = " ".join(title.lower().split())
        normalized_owner = (owner or "").strip().lower()
        return f"{normalized_title}::{normalized_owner}"

    def _find_similar_existing_id(self, title: str, owner: Optional[str], existing_tasks: Iterable[Task]) -> Optional[str]:
        normalized_title = " ".join(title.lower().split())
        normalized_owner = (owner or "").strip().lower()

        # Primary path: use vector similarity from ChromaDB when available.
        try:
            from flowstate.ml import model
            from flowstate.vector_db import query_similar_tasks

            embedding = model.encode(title, show_progress_bar=False).tolist()
            results = query_similar_tasks(self.team_id, embedding, top_k=3)
            ids = (results or {}).get("ids", [])
            if ids and ids[0]:
                candidate_ids = {str(item) for item in ids[0]}
                for task in existing_tasks:
                    if task.id in candidate_ids:
                        task_owner = (task.owner or "").strip().lower()
                        if not normalized_owner or task_owner == normalized_owner:
                            return task.id
        except Exception:
            # Fall back to lightweight matching if model/vector infra is unavailable.
            pass

        # Lightweight fuzzy fallback until vector similarity is integrated deeply.
        for task in existing_tasks:
            task_owner = (task.owner or "").strip().lower()
            if task_owner != normalized_owner:
                continue
            candidate_title = " ".join((task.title or "").lower().split())
            if candidate_title == normalized_title:
                return task.id
        return None

    @staticmethod
    def _resolve_task_ref(ref: Any, resolved_task_id_by_label: Dict[str, str]) -> Optional[str]:
        if ref is None:
            return None
        as_str = str(ref)
        return resolved_task_id_by_label.get(as_str)

    @staticmethod
    def _parse_deadline(deadline: Any):
        if deadline is None or isinstance(deadline, datetime):
            return deadline
        if isinstance(deadline, str):
            value = deadline.strip()
            if not value:
                return None
            try:
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _make_json_safe(value: Any):
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "value"):
            # Handles enum values without importing enum type explicitly.
            return value.value
        if isinstance(value, dict):
            return {k: FlowstateDAG._make_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [FlowstateDAG._make_json_safe(item) for item in value]
        return value


def build_dag(tasks: List[Any]) -> nx.DiGraph:
    """Compatibility helper for transient in-memory DAG computation."""
    G = nx.DiGraph()
    for task in tasks:
        task_id = getattr(task, "task_id", None) or getattr(task, "id", None) or getattr(task, "task", None)
        title = getattr(task, "task", None) or getattr(task, "title", None)
        if not task_id:
            continue
        G.add_node(task_id, title=title, deadline=getattr(task, "deadline", None), owner=getattr(task, "owner", None))

    for task in tasks:
        task_id = getattr(task, "task_id", None) or getattr(task, "id", None) or getattr(task, "task", None)
        deps = getattr(task, "dependencies", None) or []
        for dep in deps:
            G.add_edge(dep, task_id)

    return G


def get_critical_path(G: nx.DiGraph) -> List[str]:
    return nx.dag_longest_path(G)


def get_bottlenecks(G: nx.DiGraph) -> List[str]:
    return [n for n in G.nodes if G.in_degree(n) > 2]


def get_dag_summary(tasks: List[Any]) -> Dict[str, Any]:
    G = build_dag(tasks)
    return {
        "total_tasks": G.number_of_nodes(),
        "total_dependencies": G.number_of_edges(),
        "critical_path": get_critical_path(G),
        "bottlenecks": get_bottlenecks(G),
    }