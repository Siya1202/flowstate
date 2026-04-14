from typing import Dict, List, Optional

from sqlalchemy import desc

from flowstate.infra.db import SessionLocal
from flowstate.infra.models import SourceRef, Task


def get_historical_ownership(team_id: str, task_description: str) -> Optional[str]:
    """Retrieve a likely owner for a similar task title within a team."""
    with SessionLocal() as db:
        task = (
            db.query(Task)
            .filter(Task.team_id == team_id, Task.title.ilike(task_description), Task.owner.is_not(None))
            .order_by(desc(Task.updated_at), desc(Task.created_at))
            .first()
        )
        return task.owner if task else None


def get_speaker_activity(team_id: str, source_ref: str) -> Optional[List[Dict[str, str]]]:
    """Return source-aware activity hints.

    Speaker telemetry is not persisted yet; keeping the shape for compatibility.
    """
    if not source_ref:
        return None

    with SessionLocal() as db:
        source = (
            db.query(SourceRef)
            .filter(
                SourceRef.team_id == team_id,
                (SourceRef.external_id == source_ref) | (SourceRef.url == source_ref),
            )
            .first()
        )
        if not source:
            return None

    return None


def get_task_by_id(task_id: str, team_id: str) -> Optional[Task]:
    """Retrieve a task by id scoped to a team."""
    with SessionLocal() as db:
        return db.query(Task).filter(Task.id == task_id, Task.team_id == team_id).first()