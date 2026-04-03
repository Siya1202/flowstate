import os
import redis
import json
import logging
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


# --- Config ---
class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    EXTRACTION_CONFIDENCE_THRESHOLD: float = 0.75
    OWNERSHIP_INFERENCE_THRESHOLD: float = 0.70

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
r = redis.from_url(settings.REDIS_URL)
logging.basicConfig(level=logging.INFO)

# --- Task Model ---
class Task(BaseModel):
    task: str
    confidence: float
    inference_confidence: Optional[float] = None
    owner: Optional[str] = None
    inferred_owner: Optional[str] = None
    duplicate_candidates: Optional[List[str]] = None

# --- Routing Logic ---
def route_task(task: Task) -> str:
    """Route task to auto-approve or human review queue."""
    try:
        needs_review = (
            task.confidence < settings.EXTRACTION_CONFIDENCE_THRESHOLD
            or (task.inference_confidence or 0) < settings.OWNERSHIP_INFERENCE_THRESHOLD
            or task.duplicate_candidates
            or (not task.owner and not task.inferred_owner)
        )

        queue = "flowstate:review" if needs_review else "flowstate:approved"
        r.lpush(queue, json.dumps(task.dict()))
        logging.info(f"Task routed to {queue}: {task.task}")
        return "review" if needs_review else "approved"
    except Exception as e:
        logging.error(f"Error routing task: {e}")
        raise

def route_tasks(tasks: List[Task]) -> dict:
    """Route a list of tasks and return summary."""
    results = {"approved": [], "review": []}
    for task in tasks:
        status = route_task(task)
        results[status].append(task.task)
    return results