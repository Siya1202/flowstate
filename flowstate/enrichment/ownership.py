from typing import Optional, Dict, List
from datetime import datetime
from backend.models import Task, Chunk
from backend.db import get_historical_ownership, get_speaker_activity

def infer_owner(task: Task, team_id: str) -> Optional[str]:
    """
    Infer task owner if not explicitly set.
    Uses historical ownership and speaker activity frequency.
    """
    if task.owner:
        return task.owner

    # Get historical ownership data for similar tasks
    historical_owner = get_historical_ownership(team_id, task.task)
    if historical_owner:
        task.inferred_owner = historical_owner
        task.inference_confidence = 0.85  # Default confidence for historical match
        return historical_owner

    # Fallback: Use most active speaker in the chunk's conversation
    speaker_activity = get_speaker_activity(team_id, task.source_ref)
    if speaker_activity:
        most_active_speaker = max(speaker_activity, key=lambda x: x["frequency"])
        task.inferred_owner = most_active_speaker["speaker"]
        task.inference_confidence = 0.70  # Lower confidence for activity-based inference
        return most_active_speaker["speaker"]

    return None