import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import redis
from redis import exceptions as redis_exceptions

from flowstate.connectors import (
    GoogleCalendarConnector,
    GraphEvent,
    SlackConnector,
    WebhookConnector,
    WhatsAppConnector,
    dispatch_event,
    get_connectors_for_team,
    register_connector,
)
from flowstate.drafting import generate_draft
from flowstate.enrichment.pipeline import enrich_task
from flowstate.extraction.extractor import extract_tasks
from flowstate.graph.dag import FlowstateDAG
from flowstate.graph.intelligence import get_bottlenecks, get_critical_path, get_stale_blockers
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


@dataclass
class ConnectorTaskView:
    id: str
    title: str
    owner: Optional[str] = None
    deadline: Optional[Any] = None
    status: str = "open"


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


def _parse_deadline(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def _ensure_connectors_registered(team_id: str):
    if get_connectors_for_team(team_id):
        return

    # Register only configured connectors to avoid noisy auth/runtime failures.
    if os.getenv("ENABLE_GOOGLE_CALENDAR_CONNECTOR", "true").lower() == "true":
        register_connector(GoogleCalendarConnector(team_id=team_id, credentials={}))

    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    if slack_webhook:
        register_connector(
            SlackConnector(
                team_id=team_id,
                credentials={"webhook_url": slack_webhook},
            )
        )

    webhook_urls = [url.strip() for url in os.getenv("FLOWSTATE_WEBHOOK_URLS", "").split(",") if url.strip()]
    if webhook_urls:
        register_connector(
            WebhookConnector(
                team_id=team_id,
                credentials={"webhook_urls": webhook_urls},
            )
        )

    whatsapp_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if whatsapp_phone_id and whatsapp_access_token:
        register_connector(
            WhatsAppConnector(
                team_id=team_id,
                credentials={
                    "phone_number_id": whatsapp_phone_id,
                    "access_token": whatsapp_access_token,
                },
            )
        )


def _emit_connector_events(team_id: str, dag: FlowstateDAG):
    _ensure_connectors_registered(team_id)
    connector_count = len(get_connectors_for_team(team_id))
    if connector_count == 0:
        print("[worker] No connectors configured; skipping connector dispatch")
        return

    now = datetime.now(timezone.utc)
    dispatched = 0

    for node_id, data in dag.G.nodes(data=True):
        task_view = ConnectorTaskView(
            id=str(node_id),
            title=data.get("title") or str(node_id),
            owner=data.get("owner"),
            deadline=data.get("deadline"),
            status=data.get("status") or "open",
        )

        deadline_dt = _parse_deadline(task_view.deadline)
        if deadline_dt and task_view.status != "done":
            hours_remaining = int((deadline_dt - now).total_seconds() // 3600)
            if 0 <= hours_remaining <= 24:
                event = GraphEvent(
                    event_type="deadline_approaching",
                    task_id=task_view.id,
                    team_id=team_id,
                    metadata={
                        "hours_remaining": hours_remaining,
                        "status": task_view.status,
                    },
                )
                draft = generate_draft(task_view, event, "deadline_reminder")
                event.metadata["draft"] = draft.body
                dispatch_event(task_view, event)
                dispatched += 1

        for blocker_id in dag.G.predecessors(node_id):
            blocker_data = dag.G.nodes[blocker_id]
            blocker_status = blocker_data.get("status") or "open"
            if blocker_status == "done":
                continue

            blocked_event = GraphEvent(
                event_type="task_blocked",
                task_id=task_view.id,
                team_id=team_id,
                metadata={
                    "blocker_id": str(blocker_id),
                    "blocker_title": blocker_data.get("title") or str(blocker_id),
                    "blocker_owner": blocker_data.get("owner") or "unknown",
                    "status": task_view.status,
                },
            )
            dispatch_event(task_view, blocked_event)
            dispatched += 1

    stale_ids = set(get_stale_blockers(dag, stale_days=3))
    for stale_id in stale_ids:
        stale_data = dag.G.nodes[stale_id]
        stale_task = ConnectorTaskView(
            id=str(stale_id),
            title=stale_data.get("title") or str(stale_id),
            owner=stale_data.get("owner"),
            deadline=stale_data.get("deadline"),
            status=stale_data.get("status") or "open",
        )
        nudge_event = GraphEvent(
            event_type="nudge",
            task_id=stale_task.id,
            team_id=team_id,
            metadata={
                "blocked_by": stale_task.title,
                "blocked_by_name": stale_task.owner or "owner",
                "days_stuck": 3,
                "status": stale_task.status,
            },
        )
        draft = generate_draft(stale_task, nudge_event, "nudge")
        nudge_event.metadata["draft"] = draft.body
        dispatch_event(stale_task, nudge_event)
        dispatched += 1

    print(f"[worker] Connector dispatch complete. Connectors={connector_count}, events={dispatched}")


def _normalize_job_payload(job: dict) -> tuple[list[Any], str]:
    source = "file_job"
    if "content" in job:
        chunks = normalize(
            content=job.get("content", ""),
            source=job.get("source"),
            metadata=job.get("metadata") or {},
        )
        source = str(job.get("source") or "raw_event")
        return chunks, source

    file_path = job.get("file_path")
    file_type = job.get("file_type")
    if not file_type and file_path:
        file_type = Path(file_path).suffix.lower()

    chunks = normalize(file_path, file_type)
    return chunks, source

def process_job(job: dict):
    print(f"\nProcessing job: {job.get('job_id', job.get('external_id', 'raw_event'))}")

    if not ensure_model_warm():
        print("[worker] Skipping job because model service is unavailable.")
        return []

    # Phase 2 — Normalize
    print("Phase 2: Normalizing...")
    _t0 = time.perf_counter()
    try:
        chunks, source_name = _normalize_job_payload(job)
    except Exception as exc:
        print(f"[worker] Normalization failed: {exc}")
        return []
    print(f"Phase 2 done in {time.perf_counter() - _t0:.2f}s — got {len(chunks)} chunks from {source_name}")

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
            source_ref=job.get("filename") or job.get("external_id") or source_name,
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

    # Phase 8 — Connector dispatch
    print("Phase 8: Dispatching graph events to connectors...")
    _emit_connector_events(job["team_id"], dag)

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

            item = r.brpop(["flowstate:jobs", "flowstate:raw_events"], timeout=15)
            if not item:
                continue

            queue_name_raw, data = item
            queue_name = queue_name_raw.decode() if isinstance(queue_name_raw, bytes) else str(queue_name_raw)
            job = json.loads(data)

            if queue_name.endswith("raw_events"):
                # Convert watcher raw events into the existing worker payload contract.
                job = {
                    "job_id": job.get("external_id") or str(uuid.uuid4()),
                    "team_id": job.get("team_id", "team_alpha"),
                    "source": job.get("source", "watcher"),
                    "content": job.get("content", ""),
                    "metadata": job.get("metadata") or {},
                    "external_id": job.get("external_id"),
                }

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