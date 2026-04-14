from typing import Dict, Optional
from flowstate.models import Task
from flowstate.enrichment.deadlines import normalize_deadline
from flowstate.enrichment.duplicates import detect_duplicates
from flowstate.enrichment.ownership import infer_owner
from flowstate.infra.task_store import get_task_by_id

def enrich_task(task: Task, team_id: str) -> Task:
    """
    Run the full enrichment pipeline:
    1. Infer owner if missing
    2. Normalize deadline
    3. Detect duplicates
    """
    # Step 1: Infer owner
    if not task.owner:
        task.owner = infer_owner(task, team_id)

    # Step 2: Normalize deadline
    if task.deadline and not task.deadline.startswith("20"):
        task.deadline = normalize_deadline(task.deadline)

    # Step 3: Detect duplicates
    duplicates = detect_duplicates(task, team_id)
    if duplicates:
        task.duplicate_candidates = duplicates if duplicates else []

    return task

# CLI entry point for testing
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True, help="Task ID to enrich")
    parser.add_argument("--team-id", required=True, help="Team ID for tenancy-scoped lookup")
    args = parser.parse_args()

    # Fetch task from DB
    task = get_task_by_id(args.task_id, args.team_id)
    if task:
        enriched_task = enrich_task(task, task.team_id)
        payload = enriched_task.dict() if hasattr(enriched_task, "dict") else str(enriched_task)
        print(f"Enriched task: {payload}")
    else:
        print(f"Task {args.task_id} not found for team {args.team_id}.")