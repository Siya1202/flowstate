# 🤖 Flowstate — Coding Agent Reference (SKILLS.md)

> **Who this is for:** Any AI coding agent (Claude Code, Cursor, Copilot, or similar) working inside the Flowstate repository.
> **Read this before touching any file.**
> **Last Updated:** June 2026

---

## 🧭 Before You Write a Single Line

Ask yourself three questions:

1. **Which engine owns this?** Every feature belongs to exactly one engine or layer. Find it in the [Module Ownership Map](#module-ownership-map) before creating files.
2. **Does this use an LLM?** If yes — check [Where LLMs Are Allowed](#where-llms-are-allowed). LLMs are permitted in exactly three places.
3. **Does this touch infrastructure?** If yes — check [The Adapter Rule](#the-adapter-rule). The domain must never import from infrastructure.

If you skip these three checks, you will break the architecture.

---

## 🗺️ Module Ownership Map

Every file in this repo has exactly one owner. When adding new code, place it in the correct module. Do not create new top-level modules without an RFC.

```
backend/
├── api/                    → HTTP surface only. No business logic here.
│   └── routes/             → Thin controllers. Call core engines. Return responses.
│
├── core/                   → The intelligence. This is what Flowstate IS.
│   ├── activity/           → Event → structured knowledge (Tasks, Commitments, Entities)
│   ├── graph/              → DAG, traversal, critical path, bottlenecks
│   ├── memory/             → Semantic retrieval, embeddings, provenance, timeline
│   ├── user_model/         → Preferences, tone, working hours, relationship context
│   ├── planning/           → What should happen next? Recommendations, daily plan
│   ├── execution/          → Draft, send, schedule, create — via adapter only
│   └── learning/           → Feedback diffs → model recalibration
│
├── ingestion/              → File upload, object store, Redis queue push
├── preprocessing/          → Multimodal normalisation → Chunk objects
├── extraction/             → LLM schema-enforced extraction from Chunks
├── enrichment/             → Ownership inference, deadline normalisation, deduplication
│
├── agents/                 → Thin orchestration wrappers over core engines
│   ├── orchestrator/       → Coordinates multi-engine flows
│   ├── planner/            → Wraps Planning Engine, exposes agent interface
│   ├── communicator/       → Drafts emails/messages using User Model + Execution Engine
│   └── memory/             → Wraps Memory Engine for agent-style retrieval
│
├── infrastructure/         → Everything that talks to the outside world
│   ├── connectors/         → ConnectorAdapter + OpenClaw client
│   └── workflows/          → WorkflowAdapter + n8n client
│
├── models/
│   ├── domain.py           → Core domain types: Commitment, Event, Entity, Task, Preference
│   └── schemas.py          → Pydantic API request/response schemas
│
├── db/                     → SQLAlchemy session, migrations, query helpers
├── vector_db.py            → ChromaDB client wrapper
└── worker.py               → Redis brpop consumer loop
```

---

## 🏛️ The Dependency Rule

**Dependencies always point inward. This rule is never broken.**

```
External APIs (Gmail, Slack, GitHub)
        ↓
infrastructure/connectors/openclaw/
        ↓
infrastructure/connectors/connector_adapter.py
        ↓
core/execution/engine.py
        ↓
core/planning/engine.py
        ↓
core/graph/  core/memory/  core/user_model/
        ↓
models/domain.py
```

**What this means in practice:**

```python
# ✅ CORRECT — execution engine calls the adapter
# backend/core/execution/engine.py
class ExecutionEngine:
    def __init__(self, connector: ConnectorAdapter):
        self.connector = connector

    def send_email(self, draft: Draft) -> None:
        self.connector.send_email(draft.to, draft.subject, draft.body)

# ❌ WRONG — core imports from infrastructure directly
# backend/core/execution/engine.py
import openclaw  # NEVER DO THIS
from backend.infrastructure.connectors.openclaw.client import OpenClawClient  # NEVER DO THIS
```

**The graph engine must not know Gmail exists. The planning engine must not know n8n exists.**

---

## 🔌 The Adapter Rule

Any call to an external service goes through an adapter. No exceptions.

### ConnectorAdapter

```python
# backend/infrastructure/connectors/connector_adapter.py
# This is the ONLY file that knows OpenClaw exists.

class ConnectorAdapter:
    def get_emails(self, since: datetime) -> list[Event]: ...
    def send_email(self, to: str, subject: str, body: str) -> None: ...
    def search_messages(self, query: str) -> list[Event]: ...
    def list_calendar_events(self, date: date) -> list[Event]: ...
    def create_calendar_event(self, event: CalendarEvent) -> None: ...
    def get_slack_messages(self, channel: str) -> list[Event]: ...
```

If OpenClaw changes its SDK tomorrow, you rewrite `openclaw/client.py` only. Nothing else changes.

### WorkflowAdapter

```python
# backend/infrastructure/workflows/workflow_adapter.py
# This is the ONLY file that knows n8n exists.

class WorkflowAdapter:
    def run(self, workflow_name: str, payload: dict) -> dict: ...
    def schedule(self, workflow_name: str, cron: str) -> None: ...
```

---

## 🤖 Where LLMs Are Allowed

**LLMs are used in exactly three places. Nowhere else.**

| Location | Purpose | Allowed |
|----------|---------|---------|
| `backend/extraction/extractor.py` | Extract Tasks/Commitments from Chunks | ✅ |
| `backend/core/planning/engine.py` | Reason about next actions | ✅ |
| `backend/agents/communicator/agent.py` | Draft emails and messages | ✅ |
| `backend/core/graph/dag.py` | Graph algorithms | ❌ Use NetworkX |
| `backend/core/memory/engine.py` | Retrieval | ❌ Use ChromaDB similarity search |
| `backend/enrichment/duplicates.py` | Duplicate detection | ❌ Use cosine similarity |
| `backend/enrichment/deadlines.py` | Deadline normalisation | ❌ Use deterministic parsing |
| `backend/core/execution/engine.py` | Action execution | ❌ Deterministic only |
| Anywhere else | Anything | ❌ |

**If you find yourself calling Ollama from `graph/dag.py` or `enrichment/ownership.py`, stop. You are in the wrong place.**

### Calling Ollama (the correct pattern)

```python
import httpx
import os

OLLAMA_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
MODEL = "mistral"

async def call_llm(prompt: str, system: str = "") -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
```

Always enforce JSON output with a schema. Never trust free-text LLM output for structured data. See [Schema-Enforced Extraction](#schema-enforced-extraction).

---

## 📦 Domain Types

These are the only canonical domain objects. Do not invent new top-level types without an RFC. All new features are expressed in terms of these objects.

```python
# backend/models/domain.py

@dataclass
class Event:
    id: str
    type: str               # "email_received" | "slack_message" | "calendar_event" | "file_upload"
    source: str             # "gmail" | "slack" | "calendar" | "whatsapp" | "upload"
    content: str
    participants: list[str]
    timestamp: datetime
    raw: dict               # original payload, always preserved

@dataclass
class Task:
    id: str
    description: str
    owner: str | None
    deadline: datetime | None
    confidence: float       # 0.0 – 1.0
    source_ref: str         # "filename:line_number"
    source_snippet: str     # exact original text
    inference_trace: str    # how owner was determined
    commitment_id: str | None
    status: str             # "pending" | "approved" | "rejected" | "completed"

@dataclass
class Commitment:
    id: str
    title: str
    description: str
    owner: str | None
    deadline: datetime | None
    tasks: list[str]        # task IDs
    events: list[str]       # event IDs
    documents: list[str]    # document IDs
    status: str             # "active" | "completed" | "stalled"

@dataclass
class Entity:
    id: str
    type: str               # "person" | "project" | "document" | "organisation"
    name: str
    aliases: list[str]

@dataclass
class Preference:
    user_id: str
    key: str                # e.g. "tone:recruiter" | "priority:weight:deadline"
    value: str
    confidence: float
    evidence: list[str]     # event or task IDs that produced this
    last_updated: datetime
```

**The `Commitment` is the central object.** Tasks, Events, and Documents roll up into Commitments. If you're building something that connects these, you're probably adding to `Commitment`.

---

## 📐 Schema-Enforced Extraction

Every LLM call that produces structured data must use a JSON schema and validate the output. Never parse free-text.

```python
# backend/extraction/extractor.py — reference pattern

TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task":         { "type": "string" },
        "owner":        { "type": ["string", "null"] },
        "deadline":     { "type": ["string", "null"] },
        "dependencies": { "type": "array", "items": { "type": "string" } },
        "confidence":   { "type": "number", "minimum": 0, "maximum": 1 },
        "source_ref":   { "type": "string" },
        "commitment":   { "type": ["string", "null"] }
    },
    "required": ["task", "confidence", "source_ref"]
}

import jsonschema

def extract_and_validate(raw_output: str) -> dict:
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ExtractionError(f"LLM returned non-JSON: {raw_output[:200]}")
    try:
        jsonschema.validate(data, TASK_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ExtractionError(f"Schema violation: {e.message}")
    return data
```

System prompt for extraction must:
1. Specify the exact JSON schema
2. Include at least 4 few-shot examples
3. Instruct the model to return JSON only, no preamble
4. Include an example with `owner: null` (not everyone is named)
5. Include an example with a relative deadline ("by EOD Friday")

---

## 🗄️ Database Conventions

### Tables

| Table | Owns |
|-------|------|
| `users` | User accounts |
| `events` | Normalised Events from all sources |
| `tasks` | Extracted Tasks |
| `commitments` | Commitments (groups of tasks/events) |
| `graph_edges` | Adjacency list (source_id, target_id, relationship_type) |
| `preferences` | User Model preferences |
| `feedback_diffs` | Original vs edited task diffs |
| `confidence_scores` | Per-task confidence audit trail |
| `version_history` | Immutable event log of all changes |

### Naming conventions

- Table names: `snake_case`, plural
- Column names: `snake_case`
- Foreign keys: `{table_singular}_id` (e.g., `task_id`, `commitment_id`)
- Timestamps: always `created_at`, `updated_at` (UTC, timezone-aware)
- Soft deletes: `deleted_at` nullable column, never hard-delete domain objects

### SQLAlchemy session pattern

```python
# backend/db/database.py — use this pattern everywhere

from contextlib import contextmanager
from sqlalchemy.orm import Session

@contextmanager
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Always use `get_db()` as a context manager. Never commit inside a repository function — commit at the service layer.

---

## 🔄 Async Worker Pattern

The worker is a plain Python Redis list consumer. It does not use Celery.

```python
# backend/worker.py — reference pattern

import redis
import json

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
QUEUE = "flowstate:jobs"

def consume():
    while True:
        _, raw = r.brpop(QUEUE)         # blocking pop, right side
        job = json.loads(raw)
        handle_job(job)                 # dispatch by job["type"]
```

**Pushing a job:**

```python
r.lpush("flowstate:jobs", json.dumps({
    "type": "process_upload",
    "file_path": "/storage/objects/abc123.txt",
    "file_type": "txt",
    "team_id": "team_alpha",
    "job_id": "job_789"
}))
```

Supported `job["type"]` values: `process_upload`, `run_enrichment`, `rebuild_graph`, `sync_connector`.

---

## 🧮 Graph Engine Conventions

All graph work goes through NetworkX. No LLMs in the graph engine.

```python
# backend/core/graph/dag.py — conventions

import networkx as nx

# Always use DiGraph (directed), never Graph
G = nx.DiGraph()

# Node attributes required on every node
G.add_node(task_id, **{
    "type": "task",             # "task" | "commitment" | "person" | "document" | "meeting"
    "label": task.description,
    "deadline": task.deadline.isoformat() if task.deadline else None,
    "owner": task.owner,
    "confidence": task.confidence,
    "status": task.status
})

# Edge attributes required on every edge
G.add_edge(a_id, b_id, relationship="depends_on")
# Allowed relationships: depends_on | blocks | belongs_to | created_by | mentions | owned_by

# Cycle detection — run before persisting any new edge
if not nx.is_directed_acyclic_graph(G):
    raise GraphCycleError(f"Adding edge {a_id} → {b_id} creates a cycle")
```

**Persistence:** Edges stored in PostgreSQL `graph_edges` table. Graph reconstructed in memory on demand via `build_dag()`. Do not persist the NetworkX object itself.

---

## 💾 Memory & Embeddings Conventions

```python
# backend/core/memory/engine.py — conventions

from sentence_transformers import SentenceTransformer
import chromadb

MODEL_NAME = "all-MiniLM-L6-v2"   # do not change without benchmarking
COLLECTION = "flowstate_memories"

# Always include metadata with every embedding
collection.add(
    documents=[text],
    embeddings=[embedding.tolist()],
    metadatas=[{
        "entity_id": entity_id,
        "entity_type": entity_type,    # "task" | "event" | "document" | "conversation"
        "source": source,
        "timestamp": timestamp.isoformat(),
        "user_id": user_id
    }],
    ids=[f"{entity_type}:{entity_id}"]
)

# Always filter by user_id on retrieval — never return another user's memories
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=top_k,
    where={"user_id": user_id}
)
```

---

## ✅ Confidence Score Rules

Every extracted value must carry a confidence score. These thresholds are enforced at the governance layer.

| Field | Auto-approve threshold | Review-queue threshold |
|-------|----------------------|----------------------|
| Task extraction | ≥ 0.75 | < 0.75 |
| Owner inference | ≥ 0.70 | < 0.70 |
| Duplicate detection | similarity < 0.85 | similarity ≥ 0.85 |

Do not hardcode these thresholds in module code. Always read from environment:

```python
EXTRACTION_THRESHOLD = float(os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.75"))
OWNERSHIP_THRESHOLD  = float(os.getenv("OWNERSHIP_INFERENCE_THRESHOLD", "0.70"))
DUPLICATE_THRESHOLD  = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85"))
```

---

## 🧪 Testing Requirements

Every new module must have tests before the PR is merged.

### Test locations

```
tests/
├── unit/               → Single function, no I/O, no DB
│   ├── test_dag.py
│   ├── test_normalizer.py
│   └── test_extractor.py
├── integration/        → Multiple modules, real DB (test schema), real Redis
│   ├── test_upload_flow.py
│   └── test_enrichment_pipeline.py
└── fixtures/
    ├── sample_whatsapp.txt
    ├── sample_email.json
    └── sample_screenshot.png
```

### What to test

For every new function:
- Happy path with valid input
- Null/missing optional fields
- Malformed input (especially for extraction — LLMs produce garbage sometimes)
- Confidence score is present and in `[0.0, 1.0]`
- Domain type returned, not raw dict

### Run tests

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v --tb=short
```

### Mocking the connector

```python
# Always mock ConnectorAdapter in tests — never call real external APIs
from unittest.mock import MagicMock

connector = MagicMock(spec=ConnectorAdapter)
connector.get_emails.return_value = [sample_event]
```

---

## 🚫 Things You Must Never Do

These will break the architecture or cause production bugs. Non-negotiable.

| Never | Why |
|-------|-----|
| Import `openclaw` anywhere outside `infrastructure/connectors/openclaw/` | Violates adapter rule |
| Import `n8n` anywhere outside `infrastructure/workflows/n8n/` | Violates adapter rule |
| Call Ollama from `graph/`, `memory/`, `enrichment/`, `execution/` | LLMs only in 3 places |
| Hard-delete any domain object (Task, Commitment, Event, Entity) | Use `deleted_at` soft delete |
| Commit inside a repository function | Commit at service layer only |
| Store embeddings without `user_id` metadata | Privacy/data isolation |
| Add a cycle to the task graph | `detect_cycles()` before every edge insert |
| Return raw LLM text as structured data without schema validation | Extraction will silently corrupt |
| Create a new connector method outside `ConnectorAdapter` | Break the abstraction |
| Create a new top-level module in `backend/` without an RFC | Architecture drift |

---

## 📋 Pre-Commit Checklist

Before opening a PR, verify:

- [ ] New files placed in the correct module (checked against [Module Ownership Map](#module-ownership-map))
- [ ] No imports crossing the dependency boundary (domain → infrastructure)
- [ ] LLM calls only in the three permitted locations
- [ ] All external service calls go through `ConnectorAdapter` or `WorkflowAdapter`
- [ ] New domain types added to `models/domain.py` only
- [ ] Confidence scores present on all extracted values
- [ ] Confidence thresholds read from env, not hardcoded
- [ ] Idempotency check present on every `ExecutionEngine` action
- [ ] Unit tests written for every new function
- [ ] No hard-deletes of domain objects
- [ ] No raw dict returned where a domain type should be returned
- [ ] New DB columns have a migration in `db/migrations/`
- [ ] ChromaDB queries filtered by `user_id`
- [ ] `detect_cycles()` called before any new graph edge is persisted

---

## 🏃 Quick Reference — Running Everything

```bash
# Infrastructure
docker-compose -f docker/docker-compose.yml up -d postgres chromadb redis

# LLM runtime
ollama serve
ollama pull mistral

# DB migrations
alembic upgrade head

# Backend API
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload

# Async worker (NOT celery, plain Python)
python -m backend.worker

# Frontend
cd frontend && npm run dev

# Tests
pytest tests/ -v
```

---

## 🔗 Key Files to Read First

When working on a specific area, read these before writing code:

| Working on | Read first |
|-----------|-----------|
| Extraction / enrichment | `backend/extraction/extractor.py`, `backend/models/domain.py` |
| Graph features | `backend/core/graph/dag.py`, `docs/adr/001-postgres-over-graph-db.md` |
| Memory / embeddings | `backend/core/memory/engine.py`, `backend/vector_db.py` |
| Planning / recommendations | `backend/core/planning/engine.py`, `backend/agents/planner/agent.py` |
| External integrations | `backend/infrastructure/connectors/connector_adapter.py`, `docs/adr/002-openclaw-behind-adapter.md` |
| API routes | `backend/api/main.py`, `backend/api/routes/` |
| Frontend graph view | `frontend/app/graph/`, install note: `npm install cytoscape` |
| New DB table | `backend/db/database.py`, then run `alembic revision --autogenerate` |

---

## 📎 Architecture Decision Records

All major decisions are documented in `docs/adr/`. Read the relevant ADR before changing anything architectural.

| ADR | Decision |
|-----|----------|
| `001` | PostgreSQL + NetworkX over a native graph database |
| `002` | OpenClaw behind ConnectorAdapter |
| `003` | Ollama as primary inference runtime |
| `004` | Commitment as the central domain object |
| `005` | LLMs restricted to Activity Engine, Planning Engine, Communicator Agent |

To propose a new architectural decision: create `docs/adr/NNN-short-title.md` and open a PR for review before implementing.