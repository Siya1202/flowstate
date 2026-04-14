import hashlib
import json
import os
import redis
from typing import List
from flowstate.models import Task
from automation.calendar import create_calendar_event

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def already_processed(task_hash: str) -> bool:
    """Check if task has already been triggered."""
    return r.sismember("flowstate:processed_hashes", task_hash)

def mark_processed(task_hash: str):
    """Mark task as processed."""
    r.sadd("flowstate:processed_hashes", task_hash)

def trigger_task(task: Task):
    """Trigger real-world actions for an approved task."""
    owner = task.owner or task.inferred_owner or "Unassigned"
    deadline = task.deadline or ""

    # Idempotency check
    task_hash = hashlib.sha256(f"{task.task_id}:{owner}:{deadline}".encode()).hexdigest()
    if already_processed(task_hash):
        print(f"Already processed: {task.task}")
        return

    # Create calendar event if deadline exists
    if task.deadline:
        try:
            create_calendar_event(task.task, owner, task.deadline)
        except Exception as e:
            print(f"  ⚠️ Calendar error: {e}")

    mark_processed(task_hash)
    print(f"Triggered: {task.task}")

def trigger_approved_tasks(tasks: List[Task]):
    """Trigger actions for all approved tasks."""
    print(f"Phase 8: Triggering actions for {len(tasks)} tasks...")
    for task in tasks:
        trigger_task(task)