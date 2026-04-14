from fastapi import FastAPI
from pydantic import BaseModel, Field
from flowstate.graph.dag import FlowstateDAG
from flowstate.graph.intelligence import (
    get_bottlenecks,
    get_critical_path,
    get_do_first_tasks,
    get_stale_blockers,
)

try:
    from backend.ingestion.upload import router as upload_router
except ModuleNotFoundError:
    upload_router = None

app = FastAPI(title="Flowstate API")

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