# 🚀 Flowstate — AMD Slingshot Build Log

> **Status:** 🔨 Active Development  
> **Builders:** Siya & Srishti
> **Project:** AI-Powered Workflow Orchestration System  
> **Last Updated:** March 2026

---

## 📌 What We're Building

Flowstate is an AI-powered workflow orchestration system that converts unstructured communication (WhatsApp exports, emails, meeting transcripts, screenshots) into structured, actionable task workflows — running locally on AMD-optimized hardware.

We're currently in the **build phase**, implementing the full 11-phase architecture described in the system design. This README tracks our progress, setup steps, and build process end-to-end.

---

## 👩‍💻 Team

| Name | Role |
|------|------|
| Siya | Co-builder |
| Srishti | Co-builder |


---

## 🗂️ Table of Contents

1. [Project Structure](#project-structure)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Installation](#installation)
5. [Build Process — Phase by Phase](#build-process)
6. [Running the System](#running-the-system)
7. [Testing & Evaluation](#testing--evaluation)
8. [Deployment](#deployment)
9. [Current Progress](#current-progress)
10. [Known Issues](#known-issues)

---

## 📁 Project Structure

```
flowstate/
├── backend/
│   ├── ingestion/          # Phase 1: File upload & async queue
│   ├── preprocessing/      # Phase 2: Multimodal normalization
│   ├── extraction/         # Phase 3: LLM task extraction
│   ├── enrichment/         # Phase 4: Ownership inference, deduplication
│   ├── graph/              # Phase 5: DAG task graph engine
│   ├── governance/         # Phase 6: Confidence routing & review
│   ├── memory/             # Phase 7: Hybrid memory (PostgreSQL + ChromaDB)
│   ├── automation/         # Phase 8: Calendar, Kanban, reminders
│   ├── evaluation/         # Phase 10: Synthetic data & F1 scoring
│   └── api/                # FastAPI entrypoint
├── frontend/
│   ├── dashboard/          # Phase 9: Task board UI
│   ├── graph-view/         # DAG visualization (Cytoscape.js)
│   └── trust-popover/      # Source snippet viewer
├── inference/
│   ├── lemonade/           # Primary AMD runtime config
│   └── ollama/             # Fallback runtime
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile.*
├── scripts/
│   ├── synthetic_gen.py    # Synthetic dataset generator
│   └── eval.py             # Precision/Recall/F1 evaluator
├── tests/
├── .env.example
└── README.md               # ← You are here
```

---

## ✅ Prerequisites

Make sure the following are installed and configured before proceeding:

### System Requirements
- OS: Ubuntu 22.04+ / Windows 11 with WSL2 / macOS 13+
- RAM: 16 GB minimum (32 GB recommended for local LLM)
- CPU: AMD Ryzen AI 300 / 8040 series (or any modern multi-core)
- GPU (optional): AMD Radeon with ROCm support
- Disk: 30 GB free space (for models + data)

### Required Tools
| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend |
| Docker + Docker Compose | Latest | Containerized services |
| Git | Any | Version control |
| AMD ROCm (optional) | 6.x | GPU acceleration |

---

## 🛠️ Environment Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/your-org/flowstate.git
cd flowstate
```

### Step 2 — Create and Activate Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# or
venv\Scripts\activate           # Windows
```

### Step 3 — Copy Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required fields:

```env
# Inference
INFERENCE_RUNTIME=lemonade       # or 'ollama' for fallback
LEMONADE_API_BASE=http://localhost:8080/v1
OLLAMA_API_BASE=http://localhost:11434

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=flowstate
POSTGRES_USER=flowstate_user
POSTGRES_PASSWORD=your_secure_password

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Redis (for async queue)
REDIS_URL=redis://localhost:6379

# Object Store
OBJECT_STORE_PATH=./storage/objects

# Confidence thresholds
EXTRACTION_CONFIDENCE_THRESHOLD=0.75
OWNERSHIP_INFERENCE_THRESHOLD=0.70
DUPLICATE_SIMILARITY_THRESHOLD=0.85

# Optional: Calendar integration
GOOGLE_CALENDAR_CREDENTIALS_PATH=./credentials/google_calendar.json
```

---

## 📦 Installation

### Step 4 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

Key packages being installed:
```
fastapi uvicorn
sqlalchemy alembic psycopg2-binary
chromadb
redis
sentence-transformers
pypdf2 python-docx pillow
celery
networkx                  # DAG graph engine
httpx
pydantic
python-multipart
```

### Step 5 — Install Node.js Dependencies (Frontend)

```bash
cd frontend
npm install
cd ..
```

### Step 6 — Install and Configure the Inference Runtime

#### Option A — Lemonade (Primary, AMD-Optimized)

Lemonade is AMD's official 2026 inference runtime with hybrid offload across NPU, iGPU, and CPU.

```bash
# Install Lemonade (AMD official installer)
pip install lemonade-sdk

# Verify installation
lemonade --version

# Pull and serve a model (e.g., Mistral 7B)
lemonade serve mistral-7b-instruct --port 8080
```

Lemonade exposes an OpenAI-compatible API at `http://localhost:8080/v1` — no code changes needed.

#### Option B — Ollama (Fallback)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull mistral
ollama pull llava          # Vision model for screenshot parsing

# Start Ollama server
ollama serve
```

Set `INFERENCE_RUNTIME=ollama` in `.env` if using this path.

### Step 7 — Install Sentence Transformers (Embeddings)

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

This will download the MiniLM model (~80 MB) on first run.

### Step 8 — Start Infrastructure Services via Docker

```bash
docker-compose up -d postgres chromadb redis
```

This starts:
- **PostgreSQL** on port `5432` — structured task/graph storage
- **ChromaDB** on port `8000` — vector store for embeddings
- **Redis** on port `6379` — async message queue

Verify they're running:
```bash
docker-compose ps
```

### Step 9 — Run Database Migrations

```bash
alembic upgrade head
```

This sets up all tables: `tasks`, `owners`, `deadlines`, `graph_edges`, `confidence_scores`, `version_history`.

---

## 🏗️ Build Process

Here's the full step-by-step build sequence we're following, phase by phase.

---

### Phase 0 — Inference Runtime Layer

**Goal:** Set up the LLM inference layer that powers all extraction.

```bash
# Start Lemonade
lemonade serve mistral-7b-instruct --port 8080 --device hybrid

# Test the endpoint
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral-7b-instruct", "messages": [{"role": "user", "content": "Hello"}]}'
```

Validate the hybrid offload is active (NPU → iGPU → CPU fallback chain). Check `lemonade logs` to confirm device allocation.

---

### Phase 1 — Ingestion Layer

**Goal:** Accept file uploads and push them into an async processing queue.

Build the upload API endpoint:

```python
# backend/ingestion/upload.py
@router.post("/upload")
async def upload_file(file: UploadFile, team_id: str):
    # Save raw file to object store
    # Push metadata to Redis stream
    # Return job_id
```

Supported input formats: `.txt` (WhatsApp), `.pdf`, `.docx`, `.png`/`.jpg` (screenshots), `.json` (Discord).

Test ingestion:
```bash
curl -X POST http://localhost:8001/upload \
  -F "file=@sample_chat.txt" \
  -F "team_id=team_alpha"
```

Set up Redis Stream consumer:
```bash
# Start the worker
celery -A backend.worker worker --loglevel=info
```

---

### Phase 2 — Multimodal Preprocessing Layer

**Goal:** Normalize all input types into clean, chunked text with speaker metadata.

Build the content normalizer:

```python
# backend/preprocessing/normalizer.py

def normalize(file_path: str, file_type: str) -> list[Chunk]:
    if file_type == "txt":
        return chunk_by_speaker(file_path)
    elif file_type == "pdf":
        return extract_pdf_text(file_path)
    elif file_type in ["png", "jpg"]:
        return extract_image_text_via_vision(file_path)  # calls vision LLM
    elif file_type == "docx":
        return extract_docx_text(file_path)
```

For image/screenshot inputs, the vision model (LLaVA via Lemonade) extracts text, tables, and UI labels using OCR + layout-aware parsing.

Test preprocessing:
```bash
python -m backend.preprocessing.normalizer --file sample_screenshot.png
```

---

### Phase 3 — Structured Extraction Engine

**Goal:** Extract tasks, owners, deadlines, and dependencies from normalized chunks using schema-enforced LLM output.

This is the **core intelligence layer**. We're using strict JSON schema enforcement so the LLM never returns malformed output:

```python
TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task":         { "type": "string" },
        "owner":        { "type": ["string", "null"] },
        "deadline":     { "type": ["string", "null"] },
        "dependencies": { "type": "array", "items": { "type": "string" } },
        "confidence":   { "type": "number" },
        "source_ref":   { "type": "string" }
    },
    "required": ["task", "confidence", "source_ref"]
}
```

The system prompt includes few-shot examples covering:
- Clean task with explicit owner
- Implicit deadline ("by end of day Friday")
- Task with dependency chain
- Task with no owner identified

Test extraction:
```bash
python -m backend.extraction.extractor --chunk "Rahul can you finish the pitch deck by Thursday evening?"
# Expected: {task: "Complete pitch deck", owner: "Rahul", deadline: "Thursday evening", confidence: 0.94}
```

---

### Phase 4 — Intelligence Enrichment

**Goal:** Fill gaps in extracted data — infer missing owners, normalize deadline formats, detect duplicates.

**Ownership Inference:**
When `owner == null`, use historical ownership mapping and speaker activity frequency to assign `inferred_owner` with `inference_confidence`.

**Deadline Normalization:**
Convert relative times to absolute ISO timestamps:
```python
"Next Friday" → "2026-03-27T23:59:00+05:30"
"EOD"         → "2026-03-24T18:00:00+05:30"
```

**Duplicate Detection:**
Before inserting a new task, compare its embedding against all existing task embeddings in ChromaDB. If cosine similarity exceeds the threshold AND owner/deadline overlap — flag as duplicate candidate.

```bash
# Test enrichment pipeline end-to-end
python -m backend.enrichment.pipeline --task-id <task_id>
```

---

### Phase 5 — Task Graph Intelligence (DAG Engine)

**Goal:** Model tasks as a directed acyclic graph to surface dependencies, bottlenecks, and critical path.

```python
import networkx as nx

G = nx.DiGraph()
G.add_node("task_001", label="Design wireframes", deadline="2026-03-25")
G.add_node("task_002", label="Build frontend", deadline="2026-03-28")
G.add_edge("task_001", "task_002")  # frontend depends on wireframes

critical_path = nx.dag_longest_path(G)
bottlenecks   = [n for n in G.nodes if G.in_degree(n) > 2]
```

Store graph edges in PostgreSQL (adjacency list) and cache in memory for fast traversal.

Test graph builder:
```bash
python -m backend.graph.builder --transcript-id <id>
```

---

### Phase 6 — AI Governance Layer

**Goal:** Route low-confidence extractions to a human review queue. Build trust into every task.

```python
def route_task(task: ExtractedTask):
    if task.confidence < 0.75 or task.inference_confidence < 0.70 or task.is_duplicate_candidate:
        send_to_review_queue(task)
    else:
        auto_approve(task)
```

Every task carries:
- Confidence score (0–1)
- Source snippet reference (exact chat line)
- Inference trace (how the owner was determined)

Build the review queue API:
```bash
GET  /api/review-queue          # List tasks needing human review
POST /api/review-queue/:id/approve
POST /api/review-queue/:id/edit
```

---

### Phase 7 — Hybrid Memory Architecture

**Goal:** Persist all data across three complementary stores.

| Store | Technology | What It Stores |
|-------|-----------|----------------|
| Structured | PostgreSQL | Tasks, owners, deadlines, graph edges, version history |
| Vector | ChromaDB | Task embeddings, conversation embeddings, document embeddings |
| Object | Local FS / S3-compatible | Raw transcripts, uploaded files, OCR outputs |

Verify all three are operational:
```bash
# PostgreSQL
psql -h localhost -U flowstate_user -d flowstate -c "\dt"

# ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Object store
ls ./storage/objects/
```

---

### Phase 8 — Automation Layer

**Goal:** Trigger real-world actions idempotently when tasks are approved.

For each approved task with a deadline:
1. Add event to Google Calendar
2. Create card on Kanban board
3. Send reminder notification to owner
4. Emit event on internal event bus

Idempotency check before every action:
```python
task_hash = sha256(f"{task_id}:{owner}:{deadline}".encode()).hexdigest()
if already_processed(task_hash):
    return  # Skip — already triggered
```

Test automation:
```bash
python -m backend.automation.trigger --task-id <id>
```

Set up Google Calendar credentials:
```bash
# Place OAuth credentials at:
./credentials/google_calendar.json

# Run auth flow (first time only)
python scripts/auth_calendar.py
```

---

### Phase 9 — Dashboard & Visualization Layer

**Goal:** Build the frontend task board with DAG view and source trust popovers.

```bash
cd frontend
npm run dev
# Opens at http://localhost:3000
```

Frontend components to build:
- **Task Board** — AI-generated tasks, editable fields, confidence badge
- **Dependency Graph** — Cytoscape.js DAG with critical path in red, bottlenecks flagged
- **Trust Popover** — Click any task → shows extracted source chat snippet + line reference + confidence score

Build the graph view:
```bash
npm install cytoscape
```

```javascript
// frontend/graph-view/DagView.jsx
import cytoscape from 'cytoscape';
// Render nodes (tasks) and edges (dependencies)
// Color critical path red
// Flag high-in-degree nodes as bottlenecks
```

---

### Phase 10 — Continuous Learning & Evaluation

**Goal:** Measure extraction quality and improve the system over time.

**Human Feedback Loop:**
When a user edits an AI-generated task (owner, deadline, wording), store the diff:
```python
{
    "original": { "owner": null, "deadline": "Friday" },
    "edited":   { "owner": "Siya", "deadline": "2026-03-27T17:00:00" },
    "task_id": "task_042"
}
```

Use diffs to refine system prompts and recalibrate confidence thresholds.

**Synthetic Dataset Generator:**
```bash
python scripts/synthetic_gen.py --count 200 --output data/synthetic_hackathon.json
```

Generates simulated chat transcripts with known ground-truth tasks.

**Evaluation:**
```bash
python scripts/eval.py --dataset data/synthetic_hackathon.json
```

Outputs:
```
Precision: 0.941
Recall:    0.928
F1 Score:  0.934
```

Target: **F1 ≥ 0.90** before final submission.

---

### Phase 11 — Containerized Deployment

**Goal:** Package the entire system into a one-command deployable stack.

Build all Docker images:
```bash
docker-compose build
```

Start everything:
```bash
docker-compose up
```

Services started:
| Service | Port | Description |
|---------|------|-------------|
| Backend API | 8001 | FastAPI app |
| Frontend | 3000 | React dashboard |
| PostgreSQL | 5432 | Structured DB |
| ChromaDB | 8000 | Vector store |
| Redis | 6379 | Queue |
| Lemonade | 8080 | LLM inference |

Full teardown:
```bash
docker-compose down -v
```

---

## ▶️ Running the System

Once all phases are built:

```bash
# 1. Start infrastructure
docker-compose up -d postgres chromadb redis

# 2. Start inference runtime
lemonade serve mistral-7b-instruct --port 8080 --device hybrid

# 3. Start backend
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload

# 4. Start Celery worker (async jobs)
celery -A backend.worker worker --loglevel=info

# 5. Start frontend
cd frontend && npm run dev
```

Visit `http://localhost:3000` to use the dashboard.

---

## 🧪 Testing & Evaluation

```bash
# Run all unit tests
pytest tests/ -v

# Run extraction accuracy eval
python scripts/eval.py --dataset data/synthetic_hackathon.json

# Test a single file end-to-end
curl -X POST http://localhost:8001/upload \
  -F "file=@tests/fixtures/sample_whatsapp.txt" \
  -F "team_id=test_team"
```

---

## 🐳 Deployment

For campus/hackathon demo deployment:

```bash
# One-command deploy
docker-compose -f docker/docker-compose.yml up --build

# Check logs
docker-compose logs -f backend
```

Optimized for AMD Ryzen AI laptops. No cloud dependency required.

---

## 📊 Current Progress

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 — Inference Runtime | 🔨 In Progress | Setting up Lemonade |
| Phase 1 — Ingestion Layer | 🔨 In Progress | Upload API drafted |
| Phase 2 — Preprocessing | ⬜ Not Started | |
| Phase 3 — Extraction Engine | ⬜ Not Started | |
| Phase 4 — Enrichment | ⬜ Not Started | |
| Phase 5 — DAG Engine | ⬜ Not Started | |
| Phase 6 — Governance | ⬜ Not Started | |
| Phase 7 — Memory Architecture | ⬜ Not Started | |
| Phase 8 — Automation | ⬜ Not Started | |
| Phase 9 — Dashboard | ⬜ Not Started | |
| Phase 10 — Evaluation | ⬜ Not Started | |
| Phase 11 — Deployment | ⬜ Not Started | |

---

## 🐛 Known Issues

- Lemonade NPU offload requires Ryzen AI 300 series — falls back to CPU on other hardware
- Vision extraction (Phase 2) slow without GPU; use Ollama + LLaVA as fallback
- Google Calendar integration requires manual OAuth setup (one-time)

---

## 📎 References

- [AMD Lemonade Runtime Docs](https://lemonade.amd.com/docs)
- [Ollama](https://ollama.ai)
- [ChromaDB](https://docs.trychroma.com)
- [Sentence Transformers](https://www.sbert.net)
- [Cytoscape.js](https://js.cytoscape.org)
- [FastAPI](https://fastapi.tiangolo.com)
- [NetworkX DAG Docs](https://networkx.org/documentation/stable/reference/algorithms/dag.html)