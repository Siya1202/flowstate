# 🚀 Flowstate — Build Log

> **Status:** 🔨 Active Development
> **Builders:** Siya & Srishti
> **Project:** AI-Powered Workflow Orchestration System
> **Last Updated:** March 2026

---

## 📌 What We're Building

Flowstate is an AI-powered workflow orchestration system that converts unstructured communication (WhatsApp exports, emails, meeting transcripts, screenshots) into structured, actionable task workflows — running locally via Ollama.

We're currently in the **build phase**, implementing the full 11-phase architecture described in the system design. This README tracks our progress, setup steps, and build process end-to-end.

> **Inference Strategy:** We're using **Ollama as the primary runtime** throughout phases 0–11. Lemonade integration will be explored as a performance optimization layer after all phases are complete and stable.

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

<!-- FIX #1: Rewritten to match the actual repository layout -->

```
flowstate/
├── backend/
│   ├── ingestion/          # Phase 1: File upload & async queue
│   │   └── upload.py
│   ├── preprocessing/      # Phase 2: Multimodal normalization
│   │   └── normalizer.py
│   ├── extraction/         # Phase 3: LLM task extraction
│   │   └── extractor.py
│   ├── enrichment/         # Phase 4: Ownership inference, deduplication
│   │   ├── pipeline.py
│   │   ├── ownership.py
│   │   ├── deadlines.py
│   │   └── duplicates.py
│   ├── graph/              # Phase 5: DAG task graph engine
│   │   └── dag.py
│   ├── api/                # FastAPI entrypoint
│   │   ├── main.py
│   │   └── enrichment.py
│   ├── worker.py           # Async Redis job consumer
│   ├── ml.py
│   ├── models.py
│   ├── db.py
│   └── vector_db.py
├── inference/
│   └── ollama/             # Primary runtime config
│       └── pull_model.sh
├── docker/
│   └── docker-compose.yml
├── .env.example
├── testing.md              # Full testing guide
└── README.md               # ← You are here
```

---

## ✅ Prerequisites

Make sure the following are installed and configured before proceeding.

### System Requirements

- OS: Ubuntu 22.04+ / Windows 11 with WSL2 / macOS 13+
- RAM: 16 GB minimum (32 GB recommended for local LLM)
- CPU: Any modern multi-core processor
- GPU (optional): Any CUDA or Metal-compatible GPU
- Disk: 30 GB free space (for models + data)

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend |
| Docker + Docker Compose | Latest | Containerised services |
| Git | Any | Version control |
| Ollama | Latest | LLM inference runtime |
| Tesseract OCR | Latest | System-level OCR binary (required for image preprocessing) |

<!-- FIX #8: Added OS-level Tesseract install instructions -->

### Installing Tesseract OCR

The Python package `pytesseract` is a wrapper around the Tesseract binary, which must be installed at the OS level separately:

```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download the installer from:
# https://github.com/UB-Mannheim/tesseract/wiki
```

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

<!-- FIX #6: Clarified that the password must match the docker-compose.yml hardcoded value -->

Open `.env` and fill in the required fields:

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

> **Important:** The `POSTGRES_PASSWORD` value must match the password hardcoded in `docker/docker-compose.yml`. The default in both files is `flowstate123`. If you change it here, update `docker/docker-compose.yml` to match before starting services.

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
pytesseract                   # Image OCR (requires system-level Tesseract — see Prerequisites)
networkx                      # DAG graph engine
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

### Step 6 — Install and Configure Ollama (Primary Inference Runtime)

Ollama is our primary inference runtime throughout all build phases.

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the primary text model
# FIX #7: Using "mistral" consistently — this is the tag used in backend/extraction/extractor.py
ollama pull mistral

# Start the Ollama server
ollama serve
```

Ollama exposes an OpenAI-compatible API at `http://localhost:11434` — no code changes needed.

Verify it's running:

```bash
curl http://localhost:11434/api/tags
```

> **Note on Lemonade:** AMD's Lemonade runtime will be evaluated as a future optimization layer once all 11 phases are fully built and stable on Ollama. No Lemonade setup is required at this stage.

### Step 7 — Install Sentence Transformers (Embeddings)

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

This will download the MiniLM model (~80 MB) on first run.

### Step 8 — Start Infrastructure Services via Docker

<!-- FIX #3: Added the correct -f flag with path to docker/docker-compose.yml -->

```bash
docker-compose -f docker/docker-compose.yml up -d postgres chromadb redis
```

This starts:
- **PostgreSQL** on port `5432` — structured task/graph storage
- **ChromaDB** on port `8000` — vector store for embeddings
- **Redis** on port `6379` — async message queue

Verify they're running:

```bash
docker-compose -f docker/docker-compose.yml ps
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

### Phase 0 — Inference Runtime Layer 🔨 In Progress / Testing

**Goal:** Set up the Ollama inference layer that powers all extraction.

```bash
# Start Ollama server
ollama serve

# Pull the Mistral model
# FIX #7: Using "mistral" consistently throughout
ollama pull mistral

# Test the endpoint
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral", "messages": [{"role": "user", "content": "Hello"}]}'
```

Validate the response includes the model's reply to your prompt:

```json
{
  "model": "mistral",
  "message": {
    "role": "assistant",
    "content": "Hi! How can I help?"
  }
}
```

**Notes:**
- Ollama runs on `http://localhost:11434` by default.
- No GPU required — CPU inference works out of the box.
- Logs are printed to the terminal. Redirect to `logs/ollama.log` if needed:
  ```bash
  ollama serve >> logs/ollama.log 2>&1
  ```

---

### Phase 1 — Ingestion Layer 🔨 In Progress / Testing

**Goal:** Accept file uploads and push them into an async processing queue.

Build the upload API endpoint:

```python
# backend/ingestion/upload.py
@router.post("/upload")
async def upload_file(file: UploadFile, team_id: str):
    # Save raw file to object store
    # Push job metadata to Redis list
    # Return job_id
```

Supported input formats: `.txt` (WhatsApp), `.pdf`, `.docx`, `.png`/`.jpg` (screenshots), `.json` (Discord).

Test ingestion:

```bash
curl -X POST http://localhost:8001/upload \
  -F "file=@sample_chat.txt" \
  -F "team_id=team_alpha"
```

<!-- FIX #2: Replaced Celery command with the correct plain Python worker command -->

Start the async job worker:

```bash
python -m backend.worker
```

The worker is a plain Python Redis list consumer (`brpop` on `flowstate:jobs`). It does not use Celery.

---

### Phase 2 — Multimodal Preprocessing Layer 🔨 In Progress / Testing

**Goal:** Normalize all input types into clean, chunked text with speaker metadata.

Build the content normalizer:

<!-- FIX #5: Updated to reflect actual pytesseract implementation, not LLaVA -->

```python
# backend/preprocessing/normalizer.py

def normalize(file_path: str, file_type: str) -> list[Chunk]:
    if file_type == "txt":
        return chunk_by_speaker(file_path)
    elif file_type == "pdf":
        return extract_pdf_text(file_path)
    elif file_type in ["png", "jpg"]:
        return extract_image_text(file_path)   # uses pytesseract (Tesseract OCR)
    elif file_type == "docx":
        return extract_docx_text(file_path)
```

For image and screenshot inputs, **Tesseract OCR** (via the `pytesseract` Python wrapper) extracts text from the image. Ensure the system-level Tesseract binary is installed — see [Prerequisites](#prerequisites).

Test preprocessing:

```bash
python -m backend.preprocessing.normalizer --file sample_screenshot.png
```

---

### Phase 3 — Structured Extraction Engine 🔨 In Progress / Testing

**Goal:** Extract tasks, owners, deadlines, and dependencies from normalised chunks using schema-enforced LLM output.

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

### Phase 4 — Intelligence Enrichment 🔨 In Progress / Testing

<!-- FIX #4: Updated from "Not Started" to "In Progress / Testing" -->

**Goal:** Fill gaps in extracted data — infer missing owners, normalise deadline formats, detect duplicates.

**Ownership Inference:**
When `owner == null`, use historical ownership mapping and speaker activity frequency to assign `inferred_owner` with `inference_confidence`.

**Deadline Normalisation:**
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

Implemented in:
- `backend/enrichment/pipeline.py` — end-to-end orchestration
- `backend/enrichment/ownership.py` — owner inference
- `backend/enrichment/deadlines.py` — deadline normalisation
- `backend/enrichment/duplicates.py` — duplicate detection

---

### Phase 5 — Task Graph Intelligence (DAG Engine) 🔨 In Progress / Testing

<!-- FIX #4: Updated from "Not Started" to "In Progress / Testing" -->

**Goal:** Model tasks as a directed acyclic graph to surface dependencies, bottlenecks, and critical path.

```python
# backend/graph/dag.py
import networkx as nx

G = nx.DiGraph()
G.add_node("task_001", label="Design wireframes", deadline="2026-03-25")
G.add_node("task_002", label="Build frontend", deadline="2026-03-28")
G.add_edge("task_001", "task_002")  # frontend depends on wireframes

critical_path = nx.dag_longest_path(G)
bottlenecks   = [n for n in G.nodes if G.in_degree(n) > 2]
```

Available functions in `backend/graph/dag.py`:
- `build_dag()` — construct the graph from stored task/edge data
- `get_critical_path()` — return the longest dependency chain
- `get_bottlenecks()` — identify high-in-degree nodes
- `get_dag_summary()` — return a summary dict for the API

Store graph edges in PostgreSQL (adjacency list) and cache in memory for fast traversal.

Test graph builder:

```bash
python -m backend.graph.dag --transcript-id <id>
```

---

### Phase 6 — AI Governance Layer ⬜ Not Started

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
GET  /api/review-queue            # List tasks needing human review
POST /api/review-queue/:id/approve
POST /api/review-queue/:id/edit
```

---

### Phase 7 — Hybrid Memory Architecture ⬜ Not Started

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

### Phase 8 — Automation Layer ⬜ Not Started

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

### Phase 9 — Dashboard & Visualisation Layer ⬜ Not Started

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
// DAG view component
import cytoscape from 'cytoscape';
// Render nodes (tasks) and edges (dependencies)
// Color critical path red
// Flag high-in-degree nodes as bottlenecks
```

---

### Phase 10 — Continuous Learning & Evaluation ⬜ Not Started

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

### Phase 11 — Containerised Deployment ⬜ Not Started

**Goal:** Package the entire system into a one-command deployable stack.

Build all Docker images:

```bash
docker-compose -f docker/docker-compose.yml build
```

Start everything:

```bash
docker-compose -f docker/docker-compose.yml up
```

Services started:

| Service | Port | Description |
|---------|------|-------------|
| Backend API | 8001 | FastAPI app |
| Frontend | 3000 | React dashboard |
| PostgreSQL | 5432 | Structured DB |
| ChromaDB | 8000 | Vector store |
| Redis | 6379 | Queue |
| Ollama | 11434 | LLM inference |

Full teardown:

```bash
docker-compose -f docker/docker-compose.yml down -v
```

---

## ▶️ Running the System

Once all phases are built:

```bash
# 1. Start infrastructure
docker-compose -f docker/docker-compose.yml up -d postgres chromadb redis

# 2. Start inference runtime
ollama serve

# 3. Start backend
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload

# 4. Start async job worker
# FIX #2: Correct command — worker.py uses plain Python Redis (brpop), not Celery
python -m backend.worker

# 5. Start frontend
cd frontend && npm run dev
```

Visit `http://localhost:3000` to use the dashboard.

---

## 🧪 Testing & Evaluation

<!-- FIX #10: Added reference to testing.md -->

See [testing.md](./testing.md) for the full testing guide.

```bash
# Run extraction accuracy eval
python scripts/eval.py --dataset data/synthetic_hackathon.json

# Test a single file end-to-end
curl -X POST http://localhost:8001/upload \
  -F "file=@tests/fixtures/sample_whatsapp.txt" \
  -F "team_id=test_team"
```

---

## 🐳 Deployment

For demo deployment:

```bash
# One-command deploy
docker-compose -f docker/docker-compose.yml up --build

# Check logs
docker-compose -f docker/docker-compose.yml logs -f backend
```

No cloud dependency required — runs entirely locally.

---

## 📊 Current Progress

<!-- FIX #4: Updated Phase 4 and Phase 5 to reflect actual implementation status -->

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 — Inference Runtime | 🔨 In Progress / Testing | Ollama running, model validation underway |
| Phase 1 — Ingestion Layer | 🔨 In Progress / Testing | Upload API live, Redis queue being tested |
| Phase 2 — Preprocessing | 🔨 In Progress / Testing | Text + PDF working, image OCR via pytesseract in testing |
| Phase 3 — Extraction Engine | 🔨 In Progress / Testing | Schema enforcement + few-shot prompts in testing |
| Phase 4 — Enrichment | 🔨 In Progress / Testing | pipeline.py, ownership.py, deadlines.py, duplicates.py implemented |
| Phase 5 — DAG Engine | 🔨 In Progress / Testing | dag.py implemented with build, critical path, bottleneck, summary functions |
| Phase 6 — Governance | ⬜ Not Started | |
| Phase 7 — Memory Architecture | ⬜ Not Started | |
| Phase 8 — Automation | ⬜ Not Started | |
| Phase 9 — Dashboard | ⬜ Not Started | |
| Phase 10 — Evaluation | ⬜ Not Started | |
| Phase 11 — Deployment | ⬜ Not Started | |

---

## 🗺️ Roadmap — Post Phase 11

Once all phases are complete and stable on Ollama, we plan to explore:

- **Lemonade integration** — AMD's hybrid NPU/iGPU/CPU inference runtime as a drop-in performance layer over the existing Ollama-compatible API
- **Model benchmarking** — Compare latency and throughput between Ollama and Lemonade on equivalent hardware
- **Selective offloading** — Route high-frequency extraction tasks to Lemonade while keeping Ollama as fallback

---

## 🐛 Known Issues

- Image OCR (Phase 2) uses Tesseract via `pytesseract`. On CPU without GPU acceleration, processing large screenshots may be slow.
- The `/enrich` API endpoint is defined in `backend/api/enrichment.py` but is not yet mounted in `backend/api/main.py`. It will not respond until the router is registered.
- Google Calendar integration requires manual OAuth setup (one-time).
- Redis backpressure not yet handled for large batch uploads.

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