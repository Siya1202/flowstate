import json
import redis
import os
import time
import uuid
from backend.ml import model
from backend.preprocessing.normalizer import normalize
from backend.extraction.extractor import extract_tasks
from backend.enrichment.pipeline import enrich_task
from backend.graph.dag import get_dag_summary
from backend.vector_db import store_tasks_batch
from backend.models import Task
from backend.governance.router import route_tasks

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

# Step 1.5 — Warm up model on startup
print("[worker] Warming up model...")
_warmup_t0 = time.perf_counter()
model.encode(["warmup"], show_progress_bar=False)
_warmup_elapsed = time.perf_counter() - _warmup_t0
print(f"[worker] Model warmup complete in {_warmup_elapsed:.2f}s")

def process_job(job: dict):
    print(f"\nProcessing job: {job['job_id']}")

    # Phase 2 — Normalize
    print("Phase 2: Normalizing...")
    _t0_phase2 = time.perf_counter()
    chunks = normalize(job["file_path"], job["file_type"])
    print(f"Phase 2 done in {time.perf_counter() - _t0_phase2:.2f}s — got {len(chunks)} chunks")

    # Phase 3 — Extract tasks
    print("Phase 3: Sending to Mistral... (this may take 1-2 mins)")
    _t0_phase3 = time.perf_counter()
    tasks = extract_tasks(chunks)
    print(f"Phase 3 done in {time.perf_counter() - _t0_phase3:.2f}s — extracted {len(tasks)} tasks")

    # Phase 4 — Pass 1: enrich all tasks
    print("Phase 4a: Enriching tasks...")
    _t0_phase4a = time.perf_counter()
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
    print(f"Phase 4a done in {time.perf_counter() - _t0_phase4a:.2f}s")

    # Phase 4 — Pass 2: batch encode
    print("Phase 4b: Batch encoding embeddings...")
    _t0_phase4b = time.perf_counter()
    if enriched_tasks:
        texts = [t.task for t in enriched_tasks]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        print(f"Phase 4b done in {time.perf_counter() - _t0_phase4b:.2f}s")

        # Phase 4 — Pass 3: batch store in ChromaDB
        print("Phase 4c: Batch storing in ChromaDB...")
        _t0_phase4c = time.perf_counter()
        store_tasks_batch(enriched_tasks, embeddings)
        print(f"Phase 4c done in {time.perf_counter() - _t0_phase4c:.2f}s")
    else:
        print("Phase 4b/4c skipped — no tasks to encode or store")

    # Phase 5 — Build DAG
    print("Phase 5: Building DAG...")
    _t0_phase5 = time.perf_counter()
    dag_summary = get_dag_summary(enriched_tasks)
    print(f"Phase 5 done in {time.perf_counter() - _t0_phase5:.2f}s")
    print(f"\nDAG Summary:")
    print(f"  Total tasks: {dag_summary['total_tasks']}")
    print(f"  Critical path: {dag_summary['critical_path']}")
    print(f"  Bottlenecks: {dag_summary['bottlenecks']}")
    print("\n✅ Job complete!")

    return enriched_tasks

    # Phase 6 — Governance
    print("Phase 6: Routing tasks...")
    routing = route_tasks(enriched_tasks)
    print(f"  ✅ Auto-approved: {len(routing['approved'])} tasks")
    print(f"  👀 Needs review: {len(routing['review'])} tasks")
    for t in routing['review']:
        print(f"    - {t}")

def run_worker():
    print("Worker is listening for jobs...")
    while True:
        _, data = r.brpop("flowstate:jobs")
        job = json.loads(data)
        process_job(job)

if __name__ == "__main__":
    run_worker()