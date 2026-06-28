# 🚀 Flowstate — Engineering Build Log

> **Status:** 🔨 Active Development
> **Builders:** Srishti & Siya
> **Project:** AI-Powered Workflow Orchestration System — Full Production Architecture
> **Last Updated:** June 2026
> **Version:** 2.0 — Full Production System

---

## 📌 What We're Building

Flowstate is an AI-powered workflow orchestration system that converts unstructured communication (WhatsApp exports, emails, meeting transcripts, screenshots) into structured, actionable task workflows — surfaced through a live intelligence layer that learns how you work.

This document is the **authoritative build log** for the full production system: infrastructure, core engines, agent layer, API, and frontend.

> **Inference Strategy:** Ollama as the primary runtime (Phases 0–12). Lemonade integration explored post-stabilisation as a performance layer.

---

## 👩‍💻 Team

| Name | Role |
|------|------|
| Srishti | Co-builder |
| Siya | Co-builder |

---

## 🗂️ Table of Contents

1. [System Architecture](#system-architecture)
2. [Repository Structure](#repository-structure)
3. [Prerequisites](#prerequisites)
4. [Environment Setup](#environment-setup)
5. [Architecture Decision Records](#architecture-decision-records)
6. [Build Process — Phase by Phase](#build-process)
7. [Running the System](#running-the-system)
8. [Testing & Evaluation](#testing--evaluation)
9. [Deployment](#deployment)
10. [Current Progress](#current-progress)
11. [Engineering Principles](#engineering-principles)
12. [Known Issues](#known-issues)
13. [Roadmap — Post MVP](#roadmap)

---

## 🏛️ System Architecture

The full production system is layered into four tiers. Dependencies always point inward — the domain never knows that infrastructure exists.

```
                        Flowstate
═══════════════════════════════════════════════════

                  Frontend (Next.js)
                         │
                  Flowstate API (FastAPI)
                         │

═══════════════════════════════════════════════════
                   FLOWSTATE CORE
═══════════════════════════════════════════════════

    Activity Engine      │    Graph Engine
    Memory Engine        │    User Model Engine
    Planning Engine      │    Execution Engine
    Learning Engine      │

═══════════════════════════════════════════════════
              AGENT LAYER
═══════════════════════════════════════════════════

    Orchestrator Agent   │    Planner Agent
    Communicator Agent   │    Memory Agent

═══════════════════════════════════════════════════
              INFRASTRUCTURE LAYER
═══════════════════════════════════════════════════

    Connector Adapter    │    Workflow Adapter
    (OpenClaw)           │    (n8n)

═══════════════════════════════════════════════════
              EXTERNAL SYSTEMS
═══════════════════════════════════════════════════

    Gmail  │  Slack  │  GitHub  │  Calendar
    WhatsApp │ Drive │ Notion   │  Discord
```

### The Dependency Rule

```
Gmail / Slack / External
        ↓
   Infrastructure Adapters
        ↓
   Execution Engine
        ↓
   Planning Engine
        ↓
   Graph / Memory / User Model
        ↓
   Domain (Commitments, Events, Entities)
```

**The domain never imports from infrastructure. Infrastructure never imports from the domain.**

### Core Domain Object

Everything in Flowstate rolls up into a **Commitment** — not a Task, not an Email, not a Meeting.

```
Commitment: Apply to Databricks

├── Email from recruiter        (Event)
├── Resume document             (Document)
├── Calendar reminder           (Event)
├── Interview prep tasks        (Tasks)
├── GitHub portfolio            (Entity)
└── Follow-up email             (Task)
```

The graph doesn't just connect tasks — it connects **intent**.

---

## 📁 Repository Structure

```
flowstate/

├── frontend/
│   ├── app/
│   │   ├── dashboard/
│   │   ├── graph/
│   │   ├── inbox/
│   │   └── memory/
│   ├── components/
│   └── package.json

├── backend/

│   ├── api/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── routes/
│   │   │   ├── upload.py
│   │   │   ├── tasks.py
│   │   │   ├── graph.py
│   │   │   ├── review.py
│   │   │   ├── planning.py
│   │   │   └── execution.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       └── logging.py

│   ├── core/
│   │   ├── activity/
│   │   │   └── engine.py            # Event → structured knowledge
│   │   ├── graph/
│   │   │   └── dag.py               # DAG, critical path, bottlenecks
│   │   ├── memory/
│   │   │   └── engine.py            # Semantic retrieval, embeddings
│   │   ├── user_model/
│   │   │   └── engine.py            # Preferences, tone, schedule
│   │   ├── planning/
│   │   │   └── engine.py            # Next-action recommendations
│   │   ├── execution/
│   │   │   └── engine.py            # Draft, send, schedule, create
│   │   └── learning/
│   │       └── engine.py            # Feedback → refinement loop

│   ├── ingestion/
│   │   └── upload.py                # File upload, async queue
│   ├── preprocessing/
│   │   └── normalizer.py            # Multimodal → clean chunks
│   ├── extraction/
│   │   └── extractor.py             # LLM schema-enforced extraction
│   ├── enrichment/
│   │   ├── pipeline.py
│   │   ├── ownership.py
│   │   ├── deadlines.py
│   │   └── duplicates.py

│   ├── agents/
│   │   ├── orchestrator/
│   │   │   └── agent.py
│   │   ├── planner/
│   │   │   └── agent.py
│   │   ├── communicator/
│   │   │   └── agent.py
│   │   └── memory/
│   │       └── agent.py

│   ├── infrastructure/
│   │   ├── connectors/
│   │   │   ├── connector_adapter.py # Abstraction over OpenClaw
│   │   │   └── openclaw/
│   │   │       └── client.py
│   │   └── workflows/
│   │       ├── workflow_adapter.py  # Abstraction over n8n
│   │       └── n8n/
│   │           └── client.py

│   ├── models/
│   │   ├── domain.py                # Commitment, Event, Entity, Task
│   │   └── schemas.py               # Pydantic API schemas
│   ├── db/
│   │   ├── database.py
│   │   └── migrations/
│   ├── vector_db.py
│   └── worker.py                    # Redis async job consumer

├── inference/
│   └── ollama/
│       └── pull_model.sh

├── scripts/
│   ├── synthetic_gen.py
│   ├── eval.py
│   └── auth_calendar.py

├── docker/
│   └── docker-compose.yml

├── docs/
│   └── adr/                         # Architecture Decision Records
│       ├── 001-postgres-over-graph-db.md
│       ├── 002-openclaw-behind-adapter.md
│       └── 003-ollama-primary-runtime.md

├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/

├── data/
│   └── synthetic_hackathon.json

├── .env.example
├── requirements.txt
├── testing.md
└── BUILD_LOG.md                     # ← You are here
```

---

## ✅ Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| OS | Ubuntu 22.04 / macOS 13 / Windows 11 WSL2 | Ubuntu 22.04 LTS |
| RAM | 16 GB | 32 GB |
| CPU | Modern multi-core | Any |
| GPU | Optional (CUDA / Metal) | Optional |
| Disk | 30 GB free | 50 GB free |

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend |
| Docker + Docker Compose | Latest | Containerised services |
| Git | Any | Version control |
| Ollama | Latest | LLM inference runtime |
| Tesseract OCR | Latest | Image OCR binary |

### Installing Tesseract OCR

```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download: https://github.com/UB-Mannheim/tesseract/wiki
```

---

## 🛠️ Environment Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/your-org/flowstate.git
cd flowstate
```

### Step 2 — Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### Step 3 — Copy Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Inference
INFERENCE_RUNTIME=ollama
OLLAMA_API_BASE=http://localhost:11434

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=flowstate
POSTGRES_USER=flowstate_user
POSTGRES_PASSWORD=flowstate123

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Redis
REDIS_URL=redis://localhost:6379

# Object Store
OBJECT_STORE_PATH=./storage/objects

# Confidence Thresholds
EXTRACTION_CONFIDENCE_THRESHOLD=0.75
OWNERSHIP_INFERENCE_THRESHOLD=0.70
DUPLICATE_SIMILARITY_THRESHOLD=0.85

# Optional: Calendar Integration
GOOGLE_CALENDAR_CREDENTIALS_PATH=./credentials/google_calendar.json

# Optional: OpenClaw
OPENCLAW_API_KEY=your_key_here
OPENCLAW_API_BASE=https://api.openclaw.io/v1

# Optional: n8n
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_n8n_key
```

> **Important:** `POSTGRES_PASSWORD` must match `docker/docker-compose.yml`. Default is `flowstate123`. Change both together.

---

## 📐 Architecture Decision Records

Every major decision lives in `docs/adr/`. Key decisions:

| ADR | Decision | Reason |
|-----|----------|--------|
| 001 | PostgreSQL + pgvector over a graph DB | Simpler ops, SQL for structured queries, pgvector for embeddings. Graph algorithms via NetworkX in Python. |
| 002 | OpenClaw behind ConnectorAdapter | Swap the connector provider in one folder without touching the core. |
| 003 | Ollama as primary runtime | Local, no API cost, CPU-compatible. Lemonade explored post-stabilisation. |
| 004 | Commitment as the core domain object | Tasks are ephemeral. Commitments are what users actually track across time. |
| 005 | LLMs only in 3 places | Activity Engine, Planning Engine, Communicator Agent. Everything else is deterministic. |

---

## 🏗️ Build Process

The build is organised around **capabilities the product gains**, not technologies implemented.

---

### Phase 0 — Architecture & Specification ⬜ Not Started

**Goal:** Freeze the full architecture before a single line of implementation code is written.

**Deliverables:**

- Product Requirements Document (PRD)
- Engineering Design Document (EDD)
- Domain Model with all entities and relationships
- API contracts between every engine
- Database schema (PostgreSQL tables + pgvector columns)
- Sequence diagrams for key flows
- Deployment architecture

**Domain Objects:**

```text
User
Event
Entity
Commitment
Task
Project
Document
Conversation
Relationship
Preference
```

**Relationship Types:**

```text
created_by    depends_on    blocks
belongs_to    owned_by      mentions
related_to    inferred_from
```

**Key Sequence Diagrams to Define:**

1. `email_arrives → event → graph_update → recommendation`
2. `file_upload → normalise → extract → enrich → DAG`
3. `user_edits_task → diff_stored → user_model_updated`
4. `planner_query → graph + memory + user_model → plan`

**Exit criteria:** No architecture changes without a written RFC. ADR folder populated.

---

### Phase 1 — Project Foundation ⬜ Not Started

**Goal:** Deploy an empty application skeleton end-to-end.

**Backend skeleton:**

```bash
backend/
  api/main.py          → returns {"status": "ok"}
  core/                → empty __init__.py in each module
  infrastructure/      → empty adapters
  models/domain.py     → Commitment, Event, Entity, Task dataclasses
  db/database.py       → SQLAlchemy session factory
```

**Infrastructure:**

```bash
# Docker Compose with:
# postgres, chromadb, redis, ollama

docker-compose -f docker/docker-compose.yml up -d
```

**CI/CD:**

- Linting: `ruff`
- Formatting: `black`
- Unit tests: `pytest`
- Auto-deploy on push to `main`

**Authentication:**

```python
# JWT-based auth
# POST /auth/login → token
# All /api/* routes require Bearer token
```

**Exit criteria:** Empty FastAPI app deploys. Docker services start. CI passes.

---

### Phase 2 — Connector Layer ⬜ Not Started

**Goal:** Connect Flowstate to external systems through a stable abstraction.

**ConnectorAdapter interface:**

```python
# backend/infrastructure/connectors/connector_adapter.py

class ConnectorAdapter:
    def get_emails(self, since: datetime) -> list[Event]: ...
    def send_email(self, to: str, subject: str, body: str) -> None: ...
    def search_messages(self, query: str) -> list[Event]: ...
    def list_events(self, date: date) -> list[Event]: ...
    def create_calendar_event(self, event: CalendarEvent) -> None: ...
    def get_slack_messages(self, channel: str) -> list[Event]: ...
```

Under the hood:

```python
# backend/infrastructure/connectors/openclaw/client.py
# Wraps OpenClaw SDK calls → returns normalised Event objects
```

**Event Normalisation:**

Every source produces identical `Event` objects:

```python
@dataclass
class Event:
    id: str
    type: str               # "email_received", "slack_message", "calendar_event"
    source: str             # "gmail", "slack", "calendar"
    content: str
    participants: list[str]
    timestamp: datetime
    raw: dict               # original payload preserved
```

**Connectors to implement (in order):**

1. Gmail (email received, email sent)
2. Google Calendar (event created, event upcoming)
3. Slack (message received)
4. WhatsApp (exported chat upload)
5. GitHub (PR opened, review requested)

**WorkflowAdapter interface:**

```python
# backend/infrastructure/workflows/workflow_adapter.py

class WorkflowAdapter:
    def run(self, workflow_name: str, payload: dict) -> dict: ...
    def schedule(self, workflow_name: str, cron: str) -> None: ...
```

**Exit criteria:** Events stream from Gmail and Calendar into the database. `ConnectorAdapter` tested with mock. Core never imports `openclaw` directly.

---

### Phase 3 — Ingestion & Preprocessing 🔨 In Progress / Testing

**Goal:** Accept any file format, normalise to clean text chunks with speaker metadata.

**Upload endpoint:**

```python
# backend/ingestion/upload.py

@router.post("/upload")
async def upload_file(file: UploadFile, team_id: str):
    # Save raw file to object store
    # Push job metadata to Redis list
    # Return job_id
```

Supported formats: `.txt` (WhatsApp export), `.pdf`, `.docx`, `.png`/`.jpg`, `.json` (Discord).

**Start the async worker:**

```bash
python -m backend.worker
# Plain Python Redis consumer (brpop on flowstate:jobs)
# Does NOT use Celery
```

**Normaliser:**

```python
# backend/preprocessing/normalizer.py

def normalize(file_path: str, file_type: str) -> list[Chunk]:
    if file_type == "txt":
        return chunk_by_speaker(file_path)
    elif file_type == "pdf":
        return extract_pdf_text(file_path)
    elif file_type in ["png", "jpg"]:
        return extract_image_text(file_path)   # pytesseract
    elif file_type == "docx":
        return extract_docx_text(file_path)
```

**Test preprocessing:**

```bash
python -m backend.preprocessing.normalizer --file tests/fixtures/sample_whatsapp.txt
python -m backend.preprocessing.normalizer --file tests/fixtures/sample_screenshot.png
```

**Exit criteria:** All five input formats produce valid `Chunk` objects. Worker consumes from Redis correctly.

---

### Phase 4 — Activity Engine 🔨 In Progress / Testing

**Goal:** Convert normalised events into structured domain objects (Tasks, Commitments, Entities).

**Extraction schema (strict JSON enforcement):**

```python
TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task":         { "type": "string" },
        "owner":        { "type": ["string", "null"] },
        "deadline":     { "type": ["string", "null"] },
        "dependencies": { "type": "array", "items": { "type": "string" } },
        "confidence":   { "type": "number" },
        "source_ref":   { "type": "string" },
        "commitment":   { "type": ["string", "null"] }
    },
    "required": ["task", "confidence", "source_ref"]
}
```

Few-shot prompt covers:
- Clean task with explicit owner
- Implicit deadline ("by end of day Friday")
- Task with dependency chain
- Task assigned to no one

**Test extraction:**

```bash
python -m backend.extraction.extractor \
  --chunk "Rahul can you finish the pitch deck by Thursday evening?"
# Expected: {task: "Complete pitch deck", owner: "Rahul", deadline: "Thursday evening", confidence: 0.94}
```

**Enrichment pipeline:**

```python
# backend/enrichment/pipeline.py
# ownership.py  → infer missing owners from history + speaker frequency
# deadlines.py  → "Next Friday" → "2026-06-30T23:59:00+05:30"
# duplicates.py → cosine similarity check against ChromaDB
```

**Exit criteria:** Incoming events automatically create `Task` and `Commitment` records. Enrichment covers ownership inference, deadline normalisation, and deduplication.

---

### Phase 5 — Graph Engine 🔨 In Progress / Testing

**Goal:** Model all entities and commitments as a directed acyclic graph. Surface dependencies, bottlenecks, critical path.

```python
# backend/core/graph/dag.py
import networkx as nx

G = nx.DiGraph()
G.add_node("task_001", label="Design wireframes", deadline="2026-07-01")
G.add_node("task_002", label="Build frontend", deadline="2026-07-05")
G.add_edge("task_001", "task_002")  # frontend depends on wireframes

critical_path = nx.dag_longest_path(G)
bottlenecks   = [n for n in G.nodes if G.in_degree(n) > 2]
```

**Graph node types:**

| Node Type | Example |
|-----------|---------|
| Task | "Complete pitch deck" |
| Commitment | "Databricks application" |
| Project | "Q3 hiring" |
| Document | "Resume v3.pdf" |
| Meeting | "Interview — Monday 10am" |
| Person | "Rahul", "Siya" |

**Edge types:**

| Edge | Meaning |
|------|---------|
| `depends_on` | B cannot start until A is done |
| `blocks` | A is blocking B |
| `belongs_to` | Task belongs to Commitment |
| `created_by` | Entity created by Person |
| `mentions` | Event mentions Entity |
| `owned_by` | Task owned by Person |

**Available functions in `backend/core/graph/dag.py`:**

- `build_dag(transcript_id)` — construct from stored task/edge data
- `get_critical_path()` — longest dependency chain
- `get_bottlenecks()` — high-in-degree nodes
- `get_dag_summary()` — summary dict for API
- `detect_cycles()` — validation before persistence
- `impact_analysis(task_id)` — what breaks if this task is late

**Storage:** Edges in PostgreSQL (adjacency list). Traversal in memory via NetworkX.

**Test:**

```bash
python -m backend.core.graph.dag --transcript-id <id>
```

**Exit criteria:** Graph updates automatically on new task creation. Critical path and bottleneck APIs respond correctly.

---

### Phase 6 — Memory Engine ⬜ Not Started

**Goal:** Give Flowstate persistent context — every entity has provenance.

**What Memory Engine stores:**

```text
Task / Commitment embeddings
Conversation history
Meeting summaries
Document content embeddings
Person → context associations
```

**Retrieval modes:**

```python
# backend/core/memory/engine.py

class MemoryEngine:
    def search(self, query: str, top_k: int = 5) -> list[MemoryResult]: ...
    def get_context_for_task(self, task_id: str) -> Context: ...
    def get_timeline(self, entity_id: str) -> list[Event]: ...
    def remember(self, event: Event) -> None: ...
```

**Timeline:**

When a user clicks any task, Flowstate explains:
- Where it originated (source event + line reference)
- Related conversations
- Related documents
- Related meetings

**Vector store:** ChromaDB at `http://localhost:8000`
**Embeddings:** `all-MiniLM-L6-v2` (sentence-transformers, ~80MB)

```bash
# Preload model
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

**Exit criteria:** Every entity has provenance. Memory search returns relevant context in <500ms.

---

### Phase 7 — User Model Engine ⬜ Not Started

**Goal:** Build the system's moat — learn exactly how each user works, communicates, and prioritises.

**What is learned:**

```text
Writing style per relationship type
Priority corrections
Communication preferences (formal / informal / short)
Working hours and timezone
Relationship-specific tone overrides
```

**Example model in action:**

```text
Recipient: Professor Nair   → Formal, complete sentences
Recipient: Siya (co-founder) → Short, direct, no sign-off
Recipient: Recruiter         → Friendly, enthusiastic
```

**Schema:**

```python
@dataclass
class Preference:
    user_id: str
    key: str                   # e.g. "tone:recruiter"
    value: str                 # e.g. "friendly"
    confidence: float
    evidence: list[str]        # task IDs or event IDs that produced this
    last_updated: datetime
```

**Update triggers:**

1. User edits a draft email → tone preference updated
2. User reassigns a task owner → ownership model updated
3. User corrects a deadline → deadline inference model updated

**Exit criteria:** User corrections change future AI outputs. Preferences are queryable by the Planning Engine.

---

### Phase 8 — Planning Engine ⬜ Not Started

**Goal:** Answer "What should I do next?" using graph + memory + user model.

**Inputs:**

```text
Graph (dependencies, critical path, blocked work)
Memory (past context, related events)
User Model (priorities, working hours, preferences)
Calendar (free slots, upcoming deadlines)
```

**Outputs:**

```text
Recommended task list (ordered)
Critical path summary
Blocked work (and what's blocking it)
Upcoming commitment deadlines
Suggested schedule for today
```

**Planning Agent:**

```python
# backend/agents/planner/agent.py

class PlannerAgent:
    def __init__(self, graph: GraphEngine, memory: MemoryEngine, user_model: UserModelEngine):
        ...

    def get_daily_plan(self, user_id: str, date: date) -> Plan: ...
    def get_recommendations(self, user_id: str) -> list[Recommendation]: ...
```

Agents **never** call OpenClaw directly. Flow:

```
Planner Agent
     ↓
Planning Engine
     ↓
Execution Engine
     ↓
Connector Adapter
     ↓
OpenClaw
```

**LLM use:** Reasoning only. No LLM for graph traversal, scheduling arithmetic, or data retrieval.

**Exit criteria:** System produces a ranked daily recommendation list. Recommendations are traceable back to graph + memory inputs.

---

### Phase 9 — Execution Engine ⬜ Not Started

**Goal:** Act on behalf of the user, idempotently.

**Capabilities:**

```python
# backend/core/execution/engine.py

class ExecutionEngine:
    def draft_email(self, context: Context) -> Draft: ...
    def send_email(self, draft: Draft) -> None: ...
    def create_task(self, task: Task) -> str: ...
    def create_calendar_event(self, event: CalendarEvent) -> None: ...
    def schedule_meeting(self, participants: list[str], slot: datetime) -> None: ...
    def generate_summary(self, events: list[Event]) -> str: ...
```

**Idempotency check (required before every action):**

```python
task_hash = sha256(f"{task_id}:{owner}:{deadline}".encode()).hexdigest()
if already_processed(task_hash):
    return  # Skip — already triggered
```

**Execution never imports directly from connectors:**

```python
# ✅ Correct
self.connector.send_email(to, subject, body)

# ❌ Wrong
import openclaw; openclaw.gmail.send(...)
```

**Exit criteria:** All action types execute successfully. Duplicate actions are suppressed by idempotency check. Execution tested against mock connector.

---

### Phase 10 — AI Governance & Review Queue ⬜ Not Started

**Goal:** Route low-confidence extractions to human review. Build trust into every task.

**Routing logic:**

```python
def route_task(task: ExtractedTask):
    if (task.confidence < 0.75
        or task.inference_confidence < 0.70
        or task.is_duplicate_candidate):
        send_to_review_queue(task)
    else:
        auto_approve(task)
```

**Every task carries:**

```text
confidence_score        (0.0 – 1.0)
source_snippet          (exact chat line / email paragraph)
source_ref              (file name + line number)
inference_trace         (how the owner was determined)
```

**Review Queue API:**

```bash
GET  /api/review-queue
POST /api/review-queue/:id/approve
POST /api/review-queue/:id/edit
POST /api/review-queue/:id/reject
```

**Exit criteria:** Tasks below threshold reach the review queue. Approved tasks flow into the graph. Rejected tasks are discarded with reason stored.

---

### Phase 11 — Frontend & Visualisation ⬜ Not Started

**Goal:** Build the intelligence surface — dashboard, graph, memory timeline, inbox.

```bash
cd frontend
npm run dev
# http://localhost:3000
```

**Views to build:**

**Dashboard**
- Today's priorities (AI-ranked)
- Critical path summary
- Upcoming deadlines
- Blocked work

**Task Graph**
- Cytoscape.js interactive DAG
- Critical path highlighted in red
- Bottleneck nodes flagged with indicator
- Click any node → Trust Popover

**Trust Popover (click any task):**

```text
Task: "Complete pitch deck"
Owner: Rahul (inferred, 87% confidence)
Deadline: Thursday 6pm (relative → absolute)
Source: whatsapp_2026-06-15.txt, line 47
Context: "Rahul can you finish the pitch deck by Thursday evening?"
```

**Memory Timeline**
- Past events related to the selected entity
- Linked conversations, documents, meetings

**Inbox**
- Suggested actions
- AI-generated draft emails (editable)
- Human review queue items

**Install graph library:**

```bash
npm install cytoscape
npm install react-flow-renderer   # alternative for simpler DAG views
```

**Exit criteria:** All four views render with live data. Trust Popover is accessible from every task. Graph updates in near-real-time.

---

### Phase 12 — Feedback Loop & Continuous Learning ⬜ Not Started

**Goal:** Measure extraction quality and improve the system from every correction.

**Human Feedback Storage:**

Every user edit stores a diff:

```python
{
    "original": { "owner": null, "deadline": "Friday" },
    "edited":   { "owner": "Siya", "deadline": "2026-07-04T17:00:00+05:30" },
    "task_id": "task_042",
    "edited_at": "2026-06-28T11:30:00Z"
}
```

**Feedback triggers model updates:**

```text
Owner correction   → ownership inference model recalibrated
Deadline edit      → deadline normalisation thresholds adjusted
Tone edit          → user model preference updated
Priority change    → planning engine weights adjusted
```

**Synthetic Dataset Generator:**

```bash
python scripts/synthetic_gen.py --count 200 --output data/synthetic_hackathon.json
```

**Evaluation:**

```bash
python scripts/eval.py --dataset data/synthetic_hackathon.json
```

Expected output:

```
Precision: 0.941
Recall:    0.928
F1 Score:  0.934
```

Target: **F1 ≥ 0.90** before release.

**Exit criteria:** Every recommendation type has a feedback mechanism. User corrections demonstrably change future outputs. Eval script runs cleanly in CI.

---

### Phase 13 — Hybrid Memory Architecture ⬜ Not Started

**Goal:** Ensure all three data stores are live, queryable, and consistent.

| Store | Technology | What It Stores |
|-------|-----------|----------------|
| Structured | PostgreSQL | Tasks, owners, deadlines, graph edges, version history, preferences |
| Vector | ChromaDB | Task embeddings, conversation embeddings, document embeddings |
| Object | Local FS / S3-compatible | Raw transcripts, uploaded files, OCR outputs |

**Verify all stores operational:**

```bash
# PostgreSQL
psql -h localhost -U flowstate_user -d flowstate -c "\dt"

# ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Object store
ls ./storage/objects/
```

**Migrations:**

```bash
alembic upgrade head
```

Tables: `users`, `events`, `tasks`, `commitments`, `owners`, `deadlines`, `graph_edges`, `confidence_scores`, `preferences`, `feedback_diffs`, `version_history`

**Exit criteria:** All three stores persist across restarts. No data loss on service restart.

---

### Phase 14 — Integration Testing ⬜ Not Started

**Goal:** Test complete flows end-to-end with automated assertions.

**Key flows to test:**

```text
Flow 1: File upload → normalise → extract → enrich → graph update → dashboard visible
Flow 2: Email arrives → connector → activity engine → recommendation → user action
Flow 3: User edits task → diff stored → user model updated → next draft improved
Flow 4: Planning query → graph + memory + user model → ranked plan returned
Flow 5: Low-confidence task → review queue → human approves → enters graph
```

**Run integration tests:**

```bash
pytest tests/integration/ -v
```

**Exit criteria:** All five flows have passing automated tests. No manual click-testing required for regression.

---

### Phase 15 — Containerised Deployment ⬜ Not Started

**Goal:** One-command deploy of the entire production stack.

**Build all images:**

```bash
docker-compose -f docker/docker-compose.yml build
```

**Start everything:**

```bash
docker-compose -f docker/docker-compose.yml up
```

**Services:**

| Service | Port | Description |
|---------|------|-------------|
| Backend API | 8001 | FastAPI app |
| Frontend | 3000 | Next.js dashboard |
| PostgreSQL | 5432 | Structured DB |
| ChromaDB | 8000 | Vector store |
| Redis | 6379 | Async queue |
| Ollama | 11434 | LLM inference |
| n8n | 5678 | Workflow engine |

**Teardown:**

```bash
docker-compose -f docker/docker-compose.yml down -v
```

**Exit criteria:** `docker-compose up` starts all services cleanly. Application is usable within 60 seconds of command.

---

### Phase 16 — Closed Beta ⬜ Not Started

**Goal:** Deploy to 10–20 users. Measure real-world accuracy and retention.

**Metrics to track:**

```text
Extraction accuracy (precision / recall / F1)
Time saved per user per week (self-reported)
Correction rate (how often users edit AI output)
Feature usage (which engines are used most)
Retention at 7 days, 14 days, 30 days
```

**Feedback collection:**

Every recommendation gets explicit feedback:

```text
Priority suggestion   → ✓ Correct  /  ✗ Wrong
Email draft           → ✓ Send as-is  /  ✗ Rewrite
Task owner            → ✓ Correct  /  ✗ Wrong owner
```

The goal is not "zero bugs." The goal is learning which capabilities users rely on and which assumptions need refinement.

---

## ▶️ Running the Full System

```bash
# 1. Start infrastructure
docker-compose -f docker/docker-compose.yml up -d postgres chromadb redis

# 2. Start inference runtime
ollama serve

# 3. Run database migrations
alembic upgrade head

# 4. Start backend API
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload

# 5. Start async job worker (plain Python Redis consumer, not Celery)
python -m backend.worker

# 6. Start frontend
cd frontend && npm run dev
```

Visit `http://localhost:3000`.

---

## 🧪 Testing & Evaluation

See [`testing.md`](./testing.md) for the full testing guide.

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Extraction accuracy eval
python scripts/eval.py --dataset data/synthetic_hackathon.json

# Single file end-to-end test
curl -X POST http://localhost:8001/upload \
  -F "file=@tests/fixtures/sample_whatsapp.txt" \
  -F "team_id=test_team"
```

---

## 🐳 Deployment

```bash
# One-command deploy
docker-compose -f docker/docker-compose.yml up --build

# Tail backend logs
docker-compose -f docker/docker-compose.yml logs -f backend

# Full teardown
docker-compose -f docker/docker-compose.yml down -v
```

No cloud dependency required — runs entirely locally.

---

## 📊 Current Progress

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 — Architecture Spec | ⬜ Not Started | PRD, EDD, domain model, sequence diagrams |
| Phase 1 — Foundation | ⬜ Not Started | Skeleton, CI/CD, auth, migrations |
| Phase 2 — Connector Layer | ⬜ Not Started | OpenClaw adapter, event normalisation |
| Phase 3 — Ingestion & Preprocessing | 🔨 In Progress | Upload API, Redis worker, multimodal normaliser |
| Phase 4 — Activity Engine | 🔨 In Progress | Extraction, enrichment, deduplication |
| Phase 5 — Graph Engine | 🔨 In Progress | DAG, critical path, bottlenecks |
| Phase 6 — Memory Engine | ⬜ Not Started | ChromaDB, semantic retrieval, provenance |
| Phase 7 — User Model Engine | ⬜ Not Started | Preferences, tone, learning |
| Phase 8 — Planning Engine | ⬜ Not Started | Recommendations, daily plan |
| Phase 9 — Execution Engine | ⬜ Not Started | Draft, send, schedule, create |
| Phase 10 — Governance & Review | ⬜ Not Started | Confidence routing, review queue |
| Phase 11 — Frontend | ⬜ Not Started | Dashboard, graph, memory timeline, inbox |
| Phase 12 — Feedback Loop | ⬜ Not Started | Diff storage, model recalibration, eval |
| Phase 13 — Hybrid Memory | ⬜ Not Started | PostgreSQL + ChromaDB + object store verified |
| Phase 14 — Integration Testing | ⬜ Not Started | End-to-end flow tests |
| Phase 15 — Containerised Deploy | ⬜ Not Started | One-command docker-compose |
| Phase 16 — Closed Beta | ⬜ Not Started | 10–20 users, metrics, feedback |

---

## 🧭 Engineering Principles

These are pinned. They do not change without an RFC.

1. **Domain-first.** Business concepts (events, commitments, relationships) drive the architecture — not frameworks or infrastructure.

2. **Infrastructure is replaceable.** OpenClaw, n8n, databases, queues, and LLM providers sit behind adapters. Swap any of them by rewriting one folder.

3. **Deterministic where possible.** Graph algorithms, dependency resolution, scheduling, and state transitions do not depend on LLMs. Only three things use LLMs: Activity Engine (extraction), Planning Engine (reasoning), Communicator Agent (drafting).

4. **Commitments, not tasks.** Tasks are ephemeral. The core object is a Commitment — persistent intent that aggregates events, documents, meetings, and tasks into a single trackable unit.

5. **Everything is observable.** Every recommendation is traceable back to the events, graph relationships, and user preferences that produced it. The Trust Popover is not optional.

6. **ADRs are mandatory.** Every major technical decision gets written down in `docs/adr/` before implementation begins.

---

## 🗺️ Roadmap — Post MVP

Once all 16 phases are stable on Ollama:

- **Lemonade integration** — AMD's hybrid NPU/iGPU/CPU inference runtime as a drop-in performance layer
- **Model benchmarking** — Latency and throughput comparison between Ollama and Lemonade on equivalent hardware
- **Selective offloading** — High-frequency extraction tasks routed to Lemonade; Ollama as fallback
- **Multi-user workspaces** — Shared commitment graph across a team
- **Public API** — Allow third-party Flowstate integrations

---

## 🐛 Known Issues

- Image OCR (Phase 3) via `pytesseract` is slow on CPU without GPU acceleration. Large screenshots may take 3–8 seconds.
- The `/enrich` API endpoint is defined in `backend/api/enrichment.py` but is not yet mounted in `backend/api/main.py`. It will not respond until the router is registered.
- Google Calendar integration requires manual OAuth setup on first run.
- Redis backpressure not yet handled for large batch uploads.
- `ConnectorAdapter` is a stub until OpenClaw credentials are configured.
- n8n `WorkflowAdapter` is a stub — `N8N_BASE_URL` and `N8N_API_KEY` must be set before workflows run.

---

## 📎 References

- [Ollama](https://ollama.ai)
- [ChromaDB](https://docs.trychroma.com)
- [Sentence Transformers](https://www.sbert.net)
- [Cytoscape.js](https://js.cytoscape.org)
- [FastAPI](https://fastapi.tiangolo.com)
- [NetworkX DAG Docs](https://networkx.org/documentation/stable/reference/algorithms/dag.html)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [pytesseract](https://github.com/madmaze/pytesseract)
- [n8n](https://docs.n8n.io)
- [Clean Architecture — Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
