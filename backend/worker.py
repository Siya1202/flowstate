import json
import redis
import os
import uuid
from sentence_transformers import SentenceTransformer
from backend.preprocessing.normalizer import normalize
from backend.extraction.extractor import extract_tasks
from backend.enrichment.pipeline import enrich_task
from backend.graph.dag import get_dag_summary
from backend.vector_db import store_task
from backend.models import Task

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)
model = SentenceTransformer("all-MiniLM-L6-v2")

def process_job(job: dict):
    print(f"\nProcessing job: {job['job_id']}")

    # Phase 2 — Normalize
    print("Phase 2: Normalizing...")
    chunks = normalize(job["file_path"], job["file_type"])
    print(f"Got {len(chunks)} chunks")

    # Phase 3 — Extract tasks
    print("Phase 3: Sending to Mistral... (this may take 1-2 mins)")
    tasks = extract_tasks(chunks)
    print(f"Phase 3 done. Extracted {len(tasks)} tasks")

    # Phase 4 — Enrich + store in ChromaDB
    print("Phase 4: Enriching tasks...")
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

        embedding = model.encode(enriched.task).tolist()
        store_task(enriched, embedding)

        print(f"  ✅ {enriched.task} | owner: {enriched.owner or enriched.inferred_owner} | deadline: {enriched.deadline}")

    # Phase 5 — Build DAG
    print("Phase 5: Building DAG...")
    dag_summary = get_dag_summary(enriched_tasks)
    print(f"\nDAG Summary:")
    print(f"  Total tasks: {dag_summary['total_tasks']}")
    print(f"  Critical path: {dag_summary['critical_path']}")
    print(f"  Bottlenecks: {dag_summary['bottlenecks']}")
    print("\n✅ Job complete!")

    return enriched_tasks

def run_worker():
    print("Worker is listening for jobs...")
    while True:
        _, data = r.brpop("flowstate:jobs")
        job = json.loads(data)
        process_job(job)

if __name__ == "__main__":
    run_worker()