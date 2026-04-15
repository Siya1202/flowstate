# Flowstate 🌊

> An always-on workflow orchestrator that watches where work actually happens — Whatsapp, Slack, email, GitHub, docs — extracts tasks and dependencies automatically, builds a live dependency graph, and acts on it without anyone maintaining a project management tool.

Built by **Siya** and **Srishti**.

---

## What this is

Flowstate is not a to-do list. It's not a project tracker. It's the intelligent layer that sits underneath all of that.

Every team has two versions of their work:
- **The official version** — Jira boards, Notion pages, Gantt charts that go stale within 48 hours
- **The real version** — scattered across Slack threads, email chains, Google Docs comments, and someone's memory

Flowstate reads the real version. It builds a dependency graph from it, keeps it alive, and acts on it — nudging blockers, scheduling reminders, drafting messages, routing approvals — automatically.

---

## Quickstart for library users

Install from source (editable):

```bash
python -m pip install -e .
```

Check package and CLI entrypoints:

```bash
flowstate --version
flowstate-agent-loop --help
flowstate-mcp --help
```

Use Flowstate directly in Python:

```python
from flowstate import FlowstateDAG, get_critical_path

dag = FlowstateDAG(team_id="team_alpha")
dag.load_from_db()
critical = get_critical_path(dag)
print(critical)
```

Run the Slack bot webhook service:

```bash
SLACK_SIGNING_SECRET=your-signing-secret \
REDIS_URL=redis://localhost:6379 \
flowstate-slack-bot --host 127.0.0.1 --port 8011
```

Run the MCP server over stdio:

```bash
flowstate-mcp --team-id team_alpha
```

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Queue | Redis + custom worker |
| Vector store | ChromaDB |
| Graph engine | NetworkX |
| LLM | Mistral (local via Ollama) |
| Embeddings | SentenceTransformer |
| Frontend | React + Vite |

---

## Packaging and Release

### Version bump command path

```bash
flowstate-bump-version patch
# or
flowstate-bump-version minor
# or explicit
flowstate-bump-version patch --set-version 0.2.0
```

### Build + metadata validation

```bash
python -m build
python -m twine check dist/*
```

### TestPyPI dry-run upload command

Use an API token generated from TestPyPI account settings.

```bash
python -m twine upload \
    --repository-url https://test.pypi.org/legacy/ \
    --username __token__ \
    --password "$TEST_PYPI_API_TOKEN" \
    --non-interactive \
    --skip-existing \
    dist/*
```

---

## Repo structure

```
flowstate/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── worker.py                # Redis job consumer ✅ working
│   └── slack_bot.py             # Slack webhook receiver ✅ working
├── flowstate/
│   ├── infra/                   # DB/Redis/Chroma clients + SQLAlchemy models ✅ working
│   ├── config.py                # Env-driven config ✅ working
│   ├── watchers/                # Always-on input sources (Layer 1)
│   │   ├── base.py
│   │   ├── file_watcher.py
│   │   ├── email_watcher.py
│   │   ├── registry.py
│   │   └── runner.py
│   ├── extraction/              # LLM-based task extraction
│   │   └── extractor.py         ✅ working
│   ├── preprocessing/
│   │   └── normalizer.py        ✅ working
│   ├── enrichment/              # Ownership, deadlines, dedup ✅ working
│   ├── graph/
│   │   ├── dag.py               ✅ working
│   │   └── intelligence.py      ✅ working
│   ├── governance/
│   │   └── router.py            ✅ working
│   ├── connectors/              # Output actions (Layer 3)
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── google_calendar.py
│   │   ├── slack.py
│   │   ├── webhook.py
│   │   └── whatsapp.py
│   ├── drafting/
│   │   └── generator.py         ✅ working
│   ├── agent/                   # Agent loop + tools ✅ working
│   │   ├── tools.py
│   │   └── loop.py
│   ├── evaluation/              # Scoring + feedback (Layer 6)
│   │   └── scorer.py
│   ├── mcp_server.py            # MCP server entry point ✅ working
│   └── slack_bot.py             # Slack bot runner ✅ working
├── automation/
│   ├── calendar.py              ✅ working — becomes first connector
│   └── trigger.py               ✅ idempotency pattern — reuse everywhere
├── vector_db.py                 ✅ working
├── ml.py                        ✅ working
├── frontend/                    # React + Vite (Layer 7)
├── alembic/                     ✅ migrations in place
├── docker-compose.yml
└── .env.example
```

---

## What's already working — don't rewrite these

| Module | Status | Notes |
|---|---|---|
| `extraction/extractor.py` | ✅ | Mistral task extraction — just extend |
| `flowstate/agent/tools.py` | ✅ | Agent tools for graph, drafting, governance |
| `flowstate/agent/loop.py` | ✅ | Agent loop wired for tool-calling |
| `flowstate/mcp_server.py` | ✅ | MCP server entrypoint available via CLI |
| `backend/slack_bot.py` + `flowstate/slack_bot.py` | ✅ | Slack webhook receiver + package runner |
| `enrichment/` | ✅ | Ownership, deadlines, dedup — solid |
| `graph/dag.py` + `graph/intelligence.py` | ✅ | DAG storage + critical-path and bottleneck helpers |
| `governance/router.py` | ✅ | Approve/review routing |
| `connectors/` (`google_calendar`, `slack`, `webhook`, `whatsapp`) | ✅ | Connector interfaces and implementations in place |
| `automation/calendar.py` | ✅ | Google Calendar — becomes first connector |
| `automation/trigger.py` | ✅ | Idempotency hash — copy this pattern for all connectors |
| `vector_db.py` | ✅ | ChromaDB + similarity search |
| `ml.py` | ✅ | SentenceTransformer embeddings |
| Redis queue + `worker.py` | ✅ | Worker pipeline is running and extensible |
| Alembic + Postgres config | ✅ | Initial migrations exist and are tracked |

---

## Build phases

---

## 🔧 Layer 0 — Foundations
### *Do this first. Everything else depends on it.*

---

### 0.1 — Harden and extend the existing PostgreSQL schema

The SQLAlchemy + Alembic foundation is already in place under `flowstate/infra/` and `alembic/`.
Extend the schema incrementally and keep migrations clean and reproducible.

**Tables to define:**

```python
# flowstate/infra/models.py

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship
import enum, uuid

Base = declarative_base()

class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"

class DependencyType(str, enum.Enum):
    blocks = "blocks"
    informs = "informs"
    requires_approval = "requires_approval"

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    owner = Column(String)
    deadline = Column(DateTime)
    status = Column(Enum(TaskStatus), default=TaskStatus.open)
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    source_ref_id = Column(String, ForeignKey("source_refs.id"))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Dependency(Base):
    __tablename__ = "dependencies"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_task_id = Column(String, ForeignKey("tasks.id"))
    to_task_id = Column(String, ForeignKey("tasks.id"))
    dep_type = Column(Enum(DependencyType), default=DependencyType.blocks)

class Team(Base):
    __tablename__ = "teams"
    id = Column(String, primary_key=True)
    name = Column(String)
    llm_provider = Column(String, default="ollama")
    timezone = Column(String, default="UTC")

class SourceRef(Base):
    __tablename__ = "source_refs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String)       # "slack", "email", "github", etc.
    external_id = Column(String)  # message ID, PR number, etc.
    url = Column(String)
    team_id = Column(String, ForeignKey("teams.id"))

class ConnectorRun(Base):
    __tablename__ = "connector_runs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_name = Column(String)
    task_id = Column(String, ForeignKey("tasks.id"))
    status = Column(String)       # "success", "failed", "skipped"
    ran_at = Column(DateTime)
    result = Column(Text)
```

Alembic workflow:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

### 0.2 — Infra bootstrapping

Business logic should never import a database connection directly. Keep infra behind a clean boundary:

```python
# flowstate/infra/__init__.py

from flowstate.infra.db import get_db_session
from flowstate.infra.redis_client import get_redis
from flowstate.infra.chroma_client import get_chroma

# Usage in any module:
# from flowstate.infra import get_db_session
```

```python
# flowstate/infra/db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flowstate.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### 0.3 — Config + multi-tenancy

```python
# flowstate/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DEFAULT_MODEL: str = "mistral"
    ENCRYPTION_KEY: str  # for connector credentials

    class Config:
        env_file = ".env"

settings = Settings()
```

Every resource — watcher, connector, agent, task — must carry `team_id`. No exceptions. If you're writing a function that touches tasks or connectors and it doesn't accept `team_id`, it's wrong.

---

## 👂 Layer 1 — Watchers
### *The always-on input layer. These run forever.*

---

### Base class

```python
# flowstate/watchers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List
import time

@dataclass
class RawEvent:
    source: str           # "slack", "email", "github", etc.
    content: str          # raw text content
    metadata: dict        # source-specific (channel, sender, PR number, etc.)
    team_id: str
    timestamp: datetime
    external_id: str      # for deduplication

class BaseWatcher(ABC):
    def __init__(self, team_id: str, poll_interval: int = 60):
        self.team_id = team_id
        self.poll_interval = poll_interval

    @abstractmethod
    def fetch_new_events(self) -> List[RawEvent]:
        """Fetch events since last run. Must be idempotent."""
        ...

    def run_forever(self):
        print(f"[{self.__class__.__name__}] Starting for team {self.team_id}")
        while True:
            try:
                events = self.fetch_new_events()
                for event in events:
                    self._push_to_queue(event)
            except Exception as e:
                print(f"[{self.__class__.__name__}] Error: {e}")
            time.sleep(self.poll_interval)

    def _push_to_queue(self, event: RawEvent):
        from flowstate.infra import get_redis
        import json
        r = get_redis()
        r.rpush("flowstate:raw_events", json.dumps({
            "source": event.source,
            "content": event.content,
            "metadata": event.metadata,
            "team_id": event.team_id,
            "timestamp": event.timestamp.isoformat(),
            "external_id": event.external_id,
        }))
```

---

### Watcher → normalizer contract

The existing `preprocessing/normalizer.py` produces `Chunk` objects. Extend it to accept `RawEvent`:

```python
# preprocessing/normalizer.py (extend this)

from flowstate.watchers.base import RawEvent

def normalize_raw_event(event: RawEvent) -> List[Chunk]:
    """Convert any RawEvent into Chunks for the extraction pipeline."""
    return normalize(
        content=event.content,
        source=event.source,
        metadata={**event.metadata, "team_id": event.team_id}
    )
```

This means Slack messages, emails, GitHub comments, and uploaded files all funnel into the exact same extraction pipeline. One pipe. All sources.

---

### Watcher build order

| Priority | Watcher | Source | Method |
|---|---|---|---|
| 1 | `FileWatcher` | Local files / mounted Drive | inotify / polling |
| 2 | `EmailWatcher` | Gmail / Outlook | Gmail API push |
| 3 | `SlackWatcher` | Slack workspace | Slack Events API |
| 4 | `GitHubWatcher` | PRs, issues, comments | GitHub Webhooks |
| 5 | `JiraWatcher` | Issues, status changes | Jira Webhooks |
| 6 | `WhatsAppWatcher` | WhatsApp Business | Webhook |
| 7 | `CalendarWatcher` | Google / Outlook | API polling |
| 8 | `NotionWatcher` | Pages, databases | Notion API polling |

---

## 🔗 Layer 2 — DAG Engine
### *The core product. The graph is everything.*

---

### The problem with the current DAG

`graph/dag.py` is ephemeral — it lives in memory per extraction run. We need it to be **live** and **persisted**.

### Persisting the DAG

```python
# flowstate/graph/dag.py (extend existing)

import networkx as nx
from flowstate.infra import get_db_session
from flowstate.infra.models import Task, Dependency

class FlowstateDAG:
    def __init__(self, team_id: str):
        self.team_id = team_id
        self.G = nx.DiGraph()

    def load_from_db(self):
        """Load the live graph for this workspace from Postgres."""
        with get_db_session() as db:
            tasks = db.query(Task).filter_by(team_id=self.team_id).all()
            deps = db.query(Dependency).join(
                Task, Dependency.from_task_id == Task.id
            ).filter(Task.team_id == self.team_id).all()

        for task in tasks:
            self.G.add_node(task.id, **{
                "title": task.title,
                "owner": task.owner,
                "deadline": task.deadline,
                "status": task.status,
            })
        for dep in deps:
            self.G.add_edge(dep.from_task_id, dep.to_task_id, type=dep.dep_type)

    def merge_new_tasks(self, new_tasks: list, new_deps: list):
        """
        Merge extraction results into the live graph.
        Deduplicates by task title + owner. Never replaces existing nodes.
        """
        # dedup logic here — match by embedding similarity via ChromaDB
        ...

    def save_snapshot(self):
        """Record current graph state as a versioned snapshot with diff."""
        ...
```

---

### Graph intelligence — expose these via API

```python
# flowstate/graph/intelligence.py

def get_critical_path(dag: FlowstateDAG) -> List[str]:
    """Return the longest dependency chain (task IDs in order)."""
    return nx.dag_longest_path(dag.G)

def get_bottlenecks(dag: FlowstateDAG, top_n: int = 5) -> List[dict]:
    """Nodes blocking the most other nodes."""
    centrality = nx.betweenness_centrality(dag.G)
    return sorted([
        {"task_id": k, "score": v}
        for k, v in centrality.items()
    ], key=lambda x: -x["score"])[:top_n]

def get_do_first_tasks(dag: FlowstateDAG, limit: int = 10) -> List[dict]:
    """
    Score = (urgency × impact) / (1 + num_blockers)
    urgency: 1/days_to_deadline
    impact: number of tasks this unblocks
    """
    results = []
    for node_id, data in dag.G.nodes(data=True):
        deadline = data.get("deadline")
        urgency = (1 / max((deadline - datetime.now()).days, 1)) if deadline else 0.1
        impact = len(list(dag.G.successors(node_id)))
        blockers = len([
            n for n in dag.G.predecessors(node_id)
            if dag.G.nodes[n].get("status") != "done"
        ])
        score = (urgency * impact) / (1 + blockers)
        results.append({"task_id": node_id, "score": score, **data})
    return sorted(results, key=lambda x: -x["score"])[:limit]

def get_stale_blockers(dag: FlowstateDAG, stale_days: int = 3) -> List[str]:
    """Tasks untouched for N days that are actively blocking something."""
    stale = []
    for node_id, data in dag.G.nodes(data=True):
        if data.get("status") in ("open", "in_progress"):
            updated = data.get("updated_at")
            if updated and (datetime.now() - updated).days >= stale_days:
                if dag.G.out_degree(node_id) > 0:  # is blocking something
                    stale.append(node_id)
    return stale
```

---

## ⚡ Layer 3 — Connectors
### *How Flowstate acts on the world.*

---

### Base class

```python
# flowstate/connectors/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from flowstate.infra.models import Task

@dataclass
class GraphEvent:
    event_type: str       # "task_blocked", "deadline_approaching", "pr_stale", etc.
    task_id: str
    team_id: str
    metadata: dict

@dataclass
class ConnectorResult:
    success: bool
    external_id: Optional[str]   # created issue ID, message ID, etc.
    message: str

class BaseConnector(ABC):
    name: str
    description: str

    def __init__(self, team_id: str, credentials: dict):
        self.team_id = team_id
        self.credentials = credentials

    @abstractmethod
    def can_handle(self, event: GraphEvent) -> bool: ...

    @abstractmethod
    def execute(self, task: Task, event: GraphEvent) -> ConnectorResult: ...
```

---

### Connector registry

```python
# flowstate/connectors/registry.py

from typing import Dict, List
from flowstate.connectors.base import BaseConnector, GraphEvent
from flowstate.infra.models import Task

_registry: Dict[str, List[BaseConnector]] = {}  # team_id → list of connectors

def register_connector(connector: BaseConnector):
    _registry.setdefault(connector.team_id, []).append(connector)

def get_connectors_for_team(team_id: str) -> List[BaseConnector]:
    return _registry.get(team_id, [])

def dispatch_event(task: Task, event: GraphEvent):
    """Find all connectors that can handle this event and execute them."""
    connectors = get_connectors_for_team(event.team_id)
    for connector in connectors:
        if connector.can_handle(event):
            result = connector.execute(task, event)
            _log_connector_run(connector.name, task.id, result)
```

---

### Example: wrapping the existing calendar connector

```python
# flowstate/connectors/google_calendar.py

from flowstate.connectors.base import BaseConnector, GraphEvent, ConnectorResult
from automation.calendar import schedule_task   # existing module ✅

class GoogleCalendarConnector(BaseConnector):
    name = "google_calendar"
    description = "Schedules tasks as Google Calendar events"

    def can_handle(self, event: GraphEvent) -> bool:
        return event.event_type == "deadline_approaching"

    def execute(self, task, event) -> ConnectorResult:
        try:
            event_id = schedule_task(
                title=task.title,
                deadline=task.deadline,
                credentials=self.credentials
            )
            return ConnectorResult(success=True, external_id=event_id,
                                   message=f"Scheduled: {task.title}")
        except Exception as e:
            return ConnectorResult(success=False, external_id=None, message=str(e))
```

Use `automation/trigger.py`'s idempotency hash pattern for every connector so actions never fire twice.

---

### Connector build order

| Priority | Connector | Trigger event |
|---|---|---|
| 1 | `GoogleCalendarConnector` | `deadline_approaching` — already exists, wrap it |
| 2 | `SlackConnector` | `task_blocked`, `blocker_resolved`, `digest` |
| 3 | `WebhookConnector` | any — generic escape hatch |
| 4 | `EmailConnector` | `nudge`, `deadline_reminder` |
| 5 | `JiraConnector` | `task_created`, `task_updated` |
| 6 | `GitHubConnector` | `pr_stale`, `task_created` |
| 7 | `LinearConnector` | `task_created` |
| 8 | `NotionConnector` | `task_created`, `digest` |
| 9 | `WhatsAppConnector` | `nudge` |

---

## ✍️ Layer 4 — Message Drafting Engine
### *The difference between Flowstate feeling like a robot and a thoughtful teammate.*

---

```python
# flowstate/drafting/generator.py

from flowstate.infra.models import Task
from flowstate.connectors.base import GraphEvent
from dataclasses import dataclass
import ollama

DRAFT_PROMPTS = {
    "nudge": """
You are a professional assistant helping a team stay unblocked.
Task: {title}
Owner: {owner}
Blocked by: {blocked_by}
Blocking: {blocking}
Days stuck: {days_stuck}

Write a short, polite Slack message to {blocked_by_name} asking for an update.
Do not use filler phrases. Be specific. Max 3 sentences.
""",

    "deadline_reminder": """
Task: {title}
Owner: {owner}
Due: {deadline} ({hours_remaining}h remaining)
Current status: {status}

Write a brief reminder to {owner} that this task is due soon.
Mention the deadline. Ask for a status update or flag if help is needed.
""",

    "blocker_resolved": """
Task: {title}
Owner: {owner}
Previously blocked by: {was_blocked_by}

This task just became unblocked. Write a short Slack message to {owner}
letting them know they're clear to proceed.
""",
}

@dataclass
class Draft:
    task_id: str
    draft_type: str
    body: str
    suggested_recipient: str
    suggested_channel: str
    status: str = "draft"   # draft | edited_before_send | sent

def generate_draft(task: Task, event: GraphEvent, draft_type: str) -> Draft:
    prompt_template = DRAFT_PROMPTS.get(draft_type)
    if not prompt_template:
        raise ValueError(f"Unknown draft type: {draft_type}")

    context = _build_context(task, event)
    prompt = prompt_template.format(**context)

    response = ollama.chat(model="mistral", messages=[
        {"role": "user", "content": prompt}
    ])

    return Draft(
        task_id=task.id,
        draft_type=draft_type,
        body=response["message"]["content"].strip(),
        suggested_recipient=context.get("owner", ""),
        suggested_channel=context.get("channel", ""),
    )
```

**Learning from edits:** When a user edits a draft before sending, store the diff and inject it as a few-shot example in future prompts for that workspace. Implement this in `drafting/feedback.py`.

### Draft types

| Type | Trigger |
|---|---|
| `nudge` | Task is blocked waiting on a specific person |
| `deadline_reminder` | Task due in <24h, owner hasn't updated status |
| `blocker_resolved` | A blocking dependency just moved to done |
| `pr_stale` | PR open 5+ days with no reviewer activity |
| `weekly_digest` | DAG state summary, critical path changes, what's at risk |

---

## 🤖 Layer 5 — Agent Interface
### *Chat-triggered commands + MCP server.*

---

### Agent tools

Wrap every core pipeline function as a callable tool:

```python
# flowstate/agent/tools.py

TOOLS = [
    {
        "name": "get_do_first_tasks",
        "description": "Returns the highest-priority tasks ranked by urgency × impact / blockers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "limit": {"type": "integer", "default": 5}
            },
            "required": ["team_id"]
        }
    },
    {
        "name": "get_bottlenecks",
        "description": "Returns tasks blocking the most other tasks in the DAG.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "top_n": {"type": "integer", "default": 5}
            },
            "required": ["team_id"]
        }
    },
    {
        "name": "draft_message",
        "description": "Drafts a message for a specific task and event type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "draft_type": {
                    "type": "string",
                    "enum": ["nudge", "deadline_reminder", "blocker_resolved", "digest"]
                }
            },
            "required": ["task_id", "draft_type"]
        }
    },
    {
        "name": "search_tasks",
        "description": "Semantic search across all tasks for this workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "team_id": {"type": "string"}
            },
            "required": ["query", "team_id"]
        }
    },
    # also: ingest_document, extract_tasks, get_dag_summary, trigger_connector
]
```

---

### AgentLoop

```python
# flowstate/agent/loop.py

class AgentLoop:
    """
    Single entry point for all chat interfaces.
    Slack bot, WhatsApp bot, Telegram bot — all call this.
    """

    def __init__(self, team_id: str):
        self.team_id = team_id

    def run(self, user_message: str, user_id: str) -> str:
        messages = [{"role": "user", "content": user_message}]

        while True:
            response = ollama.chat(
                model="mistral",
                messages=messages,
                tools=TOOLS
            )

            if response.get("tool_calls"):
                for call in response["tool_calls"]:
                    result = self._dispatch_tool(call["name"], call["arguments"])
                    messages.append({"role": "tool", "content": str(result)})
            else:
                return response["message"]["content"]

    def _dispatch_tool(self, tool_name: str, args: dict):
        args["team_id"] = self.team_id  # always scope to workspace
        return TOOL_HANDLERS[tool_name](**args)
```

---

### MCP Server

```python
# flowstate/mcp_server.py
# Run with: python -m flowstate.mcp_server

from mcp.server import MCPServer
from flowstate.agent.tools import TOOLS, TOOL_HANDLERS

server = MCPServer(name="flowstate")

for tool in TOOLS:
    server.register_tool(tool, TOOL_HANDLERS[tool["name"]])

if __name__ == "__main__":
    server.run()
```

Anyone using Claude Desktop, Cursor, or any MCP-compatible client can plug into Flowstate as a native toolset. This is also the `pip install flowstate` SDK path.

---

## 📊 Layer 6 — Evaluation & Feedback Loop
### *We measure everything. Gut feelings are not a feedback loop.*

---

### Extraction scorer

```python
# flowstate/evaluation/scorer.py

from dataclasses import dataclass
from typing import List

@dataclass
class ExtractionResult:
    extracted_tasks: List[str]   # task titles
    ground_truth: List[str]

def score_extraction(result: ExtractionResult) -> dict:
    extracted = set(result.extracted_tasks)
    truth = set(result.ground_truth)

    tp = len(extracted & truth)
    fp = len(extracted - truth)
    fn = len(truth - extracted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
```

### Synthetic data generator

```python
# flowstate/evaluation/synthetic.py

def generate_transcript(num_tasks: int = 5) -> dict:
    """
    Ask Mistral to generate a fake meeting transcript
    with exactly num_tasks embedded action items.
    Returns {"transcript": str, "ground_truth": List[str]}
    """
    prompt = f"""
Generate a realistic team meeting transcript (Slack format, 10-15 messages)
that contains exactly {num_tasks} action items.

After the transcript, output a JSON block:
{{"ground_truth": ["task 1", "task 2", ...]}}

The tasks should be naturally embedded — not labeled explicitly.
"""
    response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
    # parse transcript + ground_truth from response
    ...
```

Run the scorer against synthetic data as a regression test every time the extraction prompt changes.

### Human feedback

The Review Queue (Layer 7) lets users mark extracted tasks as correct, incorrect, or edited. Corrections land in a `task_feedback` table and feed back into prompt tuning.

---

## 🖥️ Layer 7 — Frontend
### *React + Vite. Build in this order.*

---

| Priority | View | Key details |
|---|---|---|
| 1 | **DAG Viewer** | React Flow graph, critical path highlighted, bottlenecks in red, click node → task detail |
| 2 | **Task Board** | Kanban by status, filter by owner / team / deadline |
| 3 | **Review Queue** | Tasks routed for human review — approve / reject / edit before they propagate |
| 4 | **Draft Inbox** | Drafted messages waiting for send approval, edit-before-send diff |
| 5 | **Watcher Status** | Active connectors, last sync time, auth errors |
| 6 | **Workspace Settings** | Connect apps, manage credentials, set staleness thresholds |

Use **React Flow** for the DAG Viewer. It handles large graphs well and supports custom node renderers.

---

## Recommended build order

### Sprint 1 — Solid foundation
- [ ] Postgres schema (Layer 0) — all tables, Alembic migration running cleanly
- [ ] `FileWatcher` + `EmailWatcher` (Layer 1)
- [ ] Connector base class + registry (Layer 3)
- [ ] `SlackConnector` + `WebhookConnector` (Layer 3)

### Sprint 2 — Live graph
- [ ] Persisted DAG in Postgres — merge on extraction, snapshot on diff (Layer 2)
- [ ] Do-first ranking + staleness detection (Layer 2)
- [ ] Draft generator — nudge + deadline reminder types (Layer 4)
- [ ] DAG Viewer with React Flow (Layer 7)

### Sprint 3 — Agent layer
- [ ] Agent tools + `AgentLoop` (Layer 5)
- [ ] Slack bot entry point (Layer 5)
- [ ] MCP server (Layer 5)
- [ ] Python SDK (`pip install flowstate`)

### Sprint 4 — Intelligence & feedback
- [ ] Evaluation scorer + synthetic data generator (Layer 6)
- [ ] Human feedback UI — Review Queue + Task Board (Layer 7)
- [ ] Learning from draft edits (Layer 4)

### Sprint 5 — Scale & full coverage
- [ ] All remaining watchers: GitHub, Jira, WhatsApp, Notion, Calendar (Layer 1)
- [ ] All remaining connectors (Layer 3)
- [ ] Multi-tenant workspace isolation end-to-end (Layer 0)
- [ ] Weekly digest connector (Layer 3)

---

## Local setup

```bash
# Clone
git clone https://github.com/your-org/flowstate
cd flowstate

# Python env
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker-compose up -d   # Postgres, Redis, ChromaDB

# Migrations
alembic upgrade head

# Ollama (local LLM)
ollama pull mistral

# Start API
uvicorn backend.main:app --reload

# Start worker
python -m backend.worker

# Frontend
cd frontend && npm install && npm run dev
```

Copy `.env.example` to `.env` and fill in credentials before starting.

---

## Notes for Siya and Srishti

- **Layer 0 is the blocker for everything.** Don't start Layer 1 or 3 until the Postgres schema is solid and Alembic is running cleanly. Migrations are cheap to write now, painful to retrofit later.

- **The idempotency pattern in `automation/trigger.py` is your friend.** Copy it for every connector and watcher. Double-firing a Slack message or creating a duplicate Jira issue is embarrassing. Hash the inputs, check before acting.

- **Keep business logic portable.** If a module can't be imported without a running database, it's wrong. The MCP server and SDK path depend on clean separation between `flowstate/infra/` and everything else.

- **Draft types first, then connectors.** A connector that sends a poorly worded message is worse than no connector. Get nudge + deadline reminder quality right before wiring up delivery.

- **Measure extraction quality from day one.** Write the scorer before you start tuning prompts. Otherwise you're flying blind. Synthetic data is cheap to generate and catches regressions fast.
