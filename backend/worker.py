import json
import os
import time
import uuid
from typing import Optional

import redis
from redis import exceptions as redis_exceptions

from automation.trigger import trigger_approved_tasks
from flowstate.enrichment.pipeline import enrich_task
from flowstate.extraction.extractor import extract_tasks
from flowstate.graph.dag import FlowstateDAG
from flowstate.graph.intelligence import get_bottlenecks, get_critical_path
from flowstate.governance.router import route_tasks
from flowstate.ml import model
from flowstate.models import Task
from flowstate.preprocessing.normalizer import normalize
from flowstate.vector_db import store_tasks_batch

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_RETRY_SECONDS = int(os.getenv("WORKER_REDIS_RETRY_SECONDS", "5"))
SERVICE_RETRY_SECONDS = int(os.getenv("WORKER_SERVICE_RETRY_SECONDS", "3"))
MAX_SERVICE_RETRIES = int(os.getenv("WORKER_MAX_SERVICE_RETRIES", "3"))

_model_warmed = False


def get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL)


def ensure_model_warm() -> bool:
    global _model_warmed
    if _model_warmed:
        return True

    for attempt in range(1, MAX_SERVICE_RETRIES + 1):
        try:
            print(f"[worker] Warming up model (attempt {attempt}/{MAX_SERVICE_RETRIES})...")
            _warmup_t0 = time.perf_counter()
            model.encode(["warmup"], show_progress_bar=False)
            print(f"[worker] Model warmup complete in {time.perf_counter() - _warmup_t0:.2f}s")
            _model_warmed = True
            return True
        except Exception as exc:
            print(f"[worker] Model warmup failed: {exc}")
            time.sleep(SERVICE_RETRY_SECONDS)

    print("[worker] Model unavailable after retries; job will be skipped until dependencies recover.")
    return False


def extract_tasks_with_retry(chunks):
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_SERVICE_RETRIES + 1):
        try:
            return extract_tasks(chunks)
        except Exception as exc:
            last_exc = exc
            print(f"[worker] Extraction attempt {attempt}/{MAX_SERVICE_RETRIES} failed: {exc}")
            time.sleep(SERVICE_RETRY_SECONDS)

    if last_exc:
        raise last_exc
    return []


def store_embeddings_with_retry(tasks, embeddings) -> bool:
    for attempt in range(1, MAX_SERVICE_RETRIES + 1):
        try:
            store_tasks_batch(tasks, embeddings)
            return True
        except Exception as exc:
            print(f"[worker] Vector store attempt {attempt}/{MAX_SERVICE_RETRIES} failed: {exc}")
            time.sleep(SERVICE_RETRY_SECONDS)

    print("[worker] ChromaDB unavailable; continuing without vector persistence for this job.")
    return False


def merge_into_persistent_dag(team_id: str, tasks: list[Task]):
    dag = FlowstateDAG(team_id=team_id)
    dag.load_from_db()

    new_tasks_payload = []
    new_deps_payload = []
    task_ids_by_title: dict[str, str] = {}

    for task in tasks:
        new_tasks_payload.append(
            {
                "id": task.task_id,
                "title": task.task,
                "owner": task.owner,
                "deadline": task.deadline,
            }
        )
        task_ids_by_title[task.task] = task.task_id

    for task in tasks:
        for dep in task.dependencies or []:
            new_deps_payload.append(
                {
                    "from_task_id": task_ids_by_title.get(dep, dep),
                    "to_task_id": task.task_id,
                    "dep_type": "blocks",
                }
            )

    merge_result = dag.merge_new_tasks(new_tasks_payload, new_deps_payload)
    snapshot_id = dag.save_snapshot()

    return {
        "dag": dag,
        "snapshot_id": snapshot_id,
        "created_tasks": len(merge_result.created_task_ids),
        "created_dependencies": len(merge_result.created_dependency_ids),
    }

def process_job(job: dict):
    print(f"\nProcessing job: {job['job_id']}")

    if not ensure_model_warm():
        print("[worker] Skipping job because model service is unavailable.")
        return []

    # Phase 2 — Normalize
    print("Phase 2: Normalizing...")
    _t0 = time.perf_counter()
    try:
        chunks = normalize(job["file_path"], job["file_type"])
    except Exception as exc:
        print(f"[worker] Normalization failed: {exc}")
        return []
    print(f"Phase 2 done in {time.perf_counter() - _t0:.2f}s — got {len(chunks)} chunks")

    # Phase 3 — Extract tasks
    print("Phase 3: Sending to Mistral... (this may take 1-2 mins)")
    _t0 = time.perf_counter()
    try:
        tasks = extract_tasks_with_retry(chunks)
    except Exception as exc:
        print(f"[worker] Extraction failed after retries: {exc}")
        return []
    print(f"Phase 3 done in {time.perf_counter() - _t0:.2f}s — extracted {len(tasks)} tasks")

    # Phase 4a — Enrich
    print("Phase 4a: Enriching tasks...")
    _t0 = time.perf_counter()
    enriched_tasks = []
    for task in tasks:
        owner = task.owner
        if isinstance(owner, list):
            owner = ", ".join(owner)

        t = Task(
            task_id=str(uuid.uuid4()),
            task=task.title,
            owner=owner,
            deadline=task.deadline,
            confidence=task.confidence,
            source_ref=job["filename"],
            team_id=job["team_id"],
            dependencies=task.dependencies if task.dependencies else []
        )

        enriched = enrich_task(t, job["team_id"])
        enriched_tasks.append(enriched)
        print(f"  ✅ {enriched.task} | owner: {enriched.owner or enriched.inferred_owner} | deadline: {enriched.deadline}")
    print(f"Phase 4a done in {time.perf_counter() - _t0:.2f}s")

    # Phase 4b — Batch encode
    print("Phase 4b: Batch encoding embeddings...")
    _t0 = time.perf_counter()
    if enriched_tasks:
        texts = [t.task for t in enriched_tasks]
        try:
            embeddings = model.encode(texts, show_progress_bar=False).tolist()
        except Exception as exc:
            print(f"[worker] Embedding generation failed: {exc}")
            embeddings = None
        print(f"Phase 4b done in {time.perf_counter() - _t0:.2f}s")

        # Phase 4c — Batch store
        print("Phase 4c: Batch storing in ChromaDB...")
        _t0 = time.perf_counter()
        if embeddings is not None:
            store_embeddings_with_retry(enriched_tasks, embeddings)
            print(f"Phase 4c done in {time.perf_counter() - _t0:.2f}s")
        else:
            print("Phase 4c skipped — no embeddings generated")
    else:
        print("Phase 4b/4c skipped — no tasks")

    # Phase 5 — Build DAG
    print("Phase 5: Building and persisting DAG...")
    _t0 = time.perf_counter()
    dag_state = merge_into_persistent_dag(job["team_id"], enriched_tasks)
    dag = dag_state["dag"]
    print(f"Phase 5 done in {time.perf_counter() - _t0:.2f}s")
    print(f"\nDAG Summary:")
    print(f"  Total tasks: {dag.G.number_of_nodes()}")
    print(f"  Total dependencies: {dag.G.number_of_edges()}")
    print(f"  Critical path: {get_critical_path(dag)}")
    print(f"  Bottlenecks: {[x['task_id'] for x in get_bottlenecks(dag)]}")
    print(f"  Snapshot ID: {dag_state['snapshot_id']}")

    # Phase 6 — Governance
    print("Phase 6: Routing tasks...")
    routing = route_tasks(enriched_tasks)
    print(f"   Auto-approved: {len(routing['approved'])} tasks")
    print(f"   Needs review: {len(routing['review'])} tasks")
    for t in routing['review']:
        print(f"    - {t}")

    # Phase 8 — Automation
    print("Phase 8: Triggering calendar events...")
    approved_tasks = [t for t in enriched_tasks if t.deadline]
    trigger_approved_tasks(approved_tasks)

    print("\n✅ Job complete!")
    return enriched_tasks

def run_worker():
    print("Worker is listening for jobs...")
    r: Optional[redis.Redis] = None

    while True:
        try:
            if r is None:
                r = get_redis_client()
                r.ping()
                print("[worker] Connected to Redis")

            item = r.brpop("flowstate:jobs", timeout=15)
            if not item:
                continue

            _, data = item
            job = json.loads(data)
            process_job(job)
        except (redis_exceptions.ConnectionError, redis_exceptions.TimeoutError) as exc:
            print(f"[worker] Redis unavailable: {exc}. Retrying in {REDIS_RETRY_SECONDS}s...")
            r = None
            time.sleep(REDIS_RETRY_SECONDS)
        except json.JSONDecodeError as exc:
            print(f"[worker] Invalid job payload, skipping: {exc}")
        except Exception as exc:
            print(f"[worker] Unexpected worker error: {exc}")
            time.sleep(SERVICE_RETRY_SECONDS)

if __name__ == "__main__":
    run_worker()