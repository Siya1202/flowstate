import os
import redis
import json
from typing import List
from backend.models import Task

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

CONFIDENCE_THRESHOLD = float(os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.75"))
OWNERSHIP_THRESHOLD = float(os.getenv("OWNERSHIP_INFERENCE_THRESHOLD", "0.70"))

def route_task(task: Task) -> str:
    """
    Route task to auto-approve or human review queue.
    Returns 'approved' or 'review'
    """
    needs_review = False

    # Low extraction confidence
    if task.confidence < CONFIDENCE_THRESHOLD:
        needs_review = True

    # Low ownership inference confidence
    if task.inference_confidence and task.inference_confidence < OWNERSHIP_THRESHOLD:
        needs_review = True

    # Has duplicate candidates
    if task.duplicate_candidates:
        needs_review = True

    # No owner at all
    if not task.owner and not task.inferred_owner:
        needs_review = True

    if needs_review:
        r.lpush("flowstate:review", json.dumps(task.dict()))
        return "review"
    else:
        r.lpush("flowstate:approved", json.dumps(task.dict()))
        return "approved"

def route_tasks(tasks: List[Task]) -> dict:
    """Route a list of tasks and return summary."""
    results = {"approved": [], "review": []}
    for task in tasks:
        status = route_task(task)
        results[status].append(task.task)
    return results