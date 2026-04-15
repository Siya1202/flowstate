import os
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from flowstate.connectors.base import GraphEvent
from flowstate.drafting import generate_draft
from flowstate.graph.dag import FlowstateDAG
from flowstate.graph.intelligence import (
    get_bottlenecks,
    get_critical_path,
    get_do_first_tasks,
    get_stale_blockers,
)
from flowstate.infra import get_db_session
from flowstate.infra.models import Task as DBTask

try:
    from backend.ingestion.upload import router as upload_router
except ModuleNotFoundError:
    upload_router = None

app = FastAPI(title="Flowstate API")

cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if upload_router is not None:
    app.include_router(upload_router)

@app.get("/")
def root():
    return {"status": "Flowstate is running"}


def _load_live_dag(team_id: str) -> FlowstateDAG:
    dag = FlowstateDAG(team_id=team_id)
    dag.load_from_db()
    return dag


class GraphTaskIn(BaseModel):
    id: str | None = None
    title: str | None = None
    task: str | None = None
    owner: str | list[str] | None = None
    deadline: str | None = None


class GraphDependencyIn(BaseModel):
    from_task_id: str | None = None
    to_task_id: str | None = None
    dep_type: str = "blocks"

    # Aliases accepted from extraction output or prior pipelines.
    from_ref: str | None = Field(default=None, alias="from")
    to_ref: str | None = Field(default=None, alias="to")
    source: str | None = None
    target: str | None = None


class GraphMergeRequest(BaseModel):
    new_tasks: list[GraphTaskIn] = Field(default_factory=list)
    new_deps: list[GraphDependencyIn] = Field(default_factory=list)
    save_snapshot: bool = True


class DraftTaskIn(BaseModel):
    id: str | None = None
    title: str | None = None
    owner: str | None = None
    deadline: str | None = None
    status: str = "open"


class DraftPreviewRequest(BaseModel):
    task_id: str | None = None
    event_type: str
    draft_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    task: DraftTaskIn | None = None
    model: str | None = None


def _resolve_draft_type(event_type: str, explicit_draft_type: str | None) -> str:
    if explicit_draft_type:
        return explicit_draft_type

    event_to_draft = {
        "nudge": "nudge",
        "deadline_approaching": "deadline_reminder",
        "deadline_reminder": "deadline_reminder",
    }
    inferred = event_to_draft.get(event_type)
    if not inferred:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to infer draft_type from event_type. Provide draft_type explicitly. "
                "Supported inferred event types: nudge, deadline_approaching, deadline_reminder."
            ),
        )
    return inferred


def _load_task_for_preview(team_id: str, payload: DraftPreviewRequest) -> SimpleNamespace:
    if payload.task is not None:
        task = payload.task
        return SimpleNamespace(
            id=task.id or payload.task_id or "preview-task",
            title=task.title or "Untitled task",
            owner=task.owner,
            deadline=task.deadline,
            status=task.status,
        )

    if not payload.task_id:
        raise HTTPException(status_code=400, detail="Provide either task_id or task payload for draft preview.")

    with get_db_session() as db:
        db_task = (
            db.query(DBTask)
            .filter(DBTask.id == payload.task_id, DBTask.team_id == team_id)
            .first()
        )

    if db_task is None:
        raise HTTPException(status_code=404, detail=f"Task not found for team_id={team_id}, task_id={payload.task_id}")

    return SimpleNamespace(
        id=db_task.id,
        title=db_task.title,
        owner=db_task.owner,
        deadline=db_task.deadline,
        status=db_task.status.value if hasattr(db_task.status, "value") else str(db_task.status),
    )


@app.get("/graph/{team_id}/critical-path")
def api_get_critical_path(team_id: str):
    dag = _load_live_dag(team_id)
    return {"team_id": team_id, "critical_path": get_critical_path(dag)}


@app.get("/graph/{team_id}/bottlenecks")
def api_get_bottlenecks(team_id: str, top_n: int = 5):
    dag = _load_live_dag(team_id)
    return {"team_id": team_id, "bottlenecks": get_bottlenecks(dag, top_n=top_n)}


@app.get("/graph/{team_id}/do-first")
def api_get_do_first_tasks(team_id: str, limit: int = 10):
    dag = _load_live_dag(team_id)
    return {"team_id": team_id, "tasks": get_do_first_tasks(dag, limit=limit)}


@app.get("/graph/{team_id}/stale-blockers")
def api_get_stale_blockers(team_id: str, stale_days: int = 3):
    dag = _load_live_dag(team_id)
    return {"team_id": team_id, "stale_blockers": get_stale_blockers(dag, stale_days=stale_days)}


@app.get("/graph/{team_id}/viewer")
def api_get_graph_viewer_payload(team_id: str, stale_days: int = 3):
    dag = _load_live_dag(team_id)
    stale = set(get_stale_blockers(dag, stale_days=stale_days))
    critical_path_ordered = get_critical_path(dag)
    critical_path = set(critical_path_ordered)

    nodes = []
    for node_id, data in dag.G.nodes(data=True):
        nodes.append(
            {
                "id": str(node_id),
                "label": data.get("title") or str(node_id),
                "owner": data.get("owner"),
                "deadline": data.get("deadline").isoformat() if hasattr(data.get("deadline"), "isoformat") else data.get("deadline"),
                "status": data.get("status") or "open",
                "is_critical": str(node_id) in critical_path,
                "is_stale_blocker": str(node_id) in stale,
                "out_degree": dag.G.out_degree(node_id),
                "in_degree": dag.G.in_degree(node_id),
            }
        )

    edges = []
    for source, target, edge_data in dag.G.edges(data=True):
        edges.append(
            {
                "id": f"{source}->{target}",
                "source": str(source),
                "target": str(target),
                "type": edge_data.get("type", "blocks"),
                "is_critical": str(source) in critical_path and str(target) in critical_path,
            }
        )

    return {
        "team_id": team_id,
        "summary": {
            "total_tasks": dag.G.number_of_nodes(),
            "total_dependencies": dag.G.number_of_edges(),
            "critical_path": critical_path_ordered,
            "bottlenecks": get_bottlenecks(dag),
            "stale_blockers": list(stale),
        },
        "nodes": nodes,
        "edges": edges,
    }


@app.post("/graph/{team_id}/snapshot")
def api_save_graph_snapshot(team_id: str):
    dag = _load_live_dag(team_id)
    snapshot_id = dag.save_snapshot()
    return {"team_id": team_id, "snapshot_id": snapshot_id}


@app.post("/graph/{team_id}/merge")
def api_merge_graph(team_id: str, payload: GraphMergeRequest):
    dag = _load_live_dag(team_id)
    result = dag.merge_new_tasks(
        new_tasks=[item.model_dump(by_alias=True) for item in payload.new_tasks],
        new_deps=[item.model_dump(by_alias=True) for item in payload.new_deps],
    )

    snapshot_id = dag.save_snapshot() if payload.save_snapshot else None
    return {
        "team_id": team_id,
        "created_task_ids": result.created_task_ids,
        "deduped_task_ids": result.deduped_task_ids,
        "created_dependency_ids": result.created_dependency_ids,
        "created_tasks": len(result.created_task_ids),
        "deduped_tasks": len(result.deduped_task_ids),
        "created_dependencies": len(result.created_dependency_ids),
        "snapshot_id": snapshot_id,
    }


@app.post("/drafts/{team_id}/preview")
def api_preview_draft(team_id: str, payload: DraftPreviewRequest):
    task = _load_task_for_preview(team_id, payload)
    draft_type = _resolve_draft_type(payload.event_type, payload.draft_type)
    event = GraphEvent(
        event_type=payload.event_type,
        task_id=task.id,
        team_id=team_id,
        metadata=payload.metadata,
    )

    try:
        draft = generate_draft(task, event, draft_type=draft_type, model=payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "team_id": team_id,
        "task_id": draft.task_id,
        "event_type": payload.event_type,
        "draft_type": draft_type,
        "draft": {
            "body": draft.body,
            "suggested_recipient": draft.suggested_recipient,
            "suggested_channel": draft.suggested_channel,
            "status": draft.status,
        },
        "task": {
            "id": task.id,
            "title": task.title,
            "owner": task.owner,
            "deadline": task.deadline.isoformat() if hasattr(task.deadline, "isoformat") else task.deadline,
            "status": task.status,
        },
        "metadata": payload.metadata,
    }