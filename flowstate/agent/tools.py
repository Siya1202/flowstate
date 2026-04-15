from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from flowstate.connectors.base import GraphEvent
from flowstate.drafting.generator import generate_draft
from flowstate.governance.router import Task as GovernanceTask
from flowstate.governance.router import route_tasks
from flowstate.graph.dag import FlowstateDAG
from flowstate.graph.intelligence import (
	get_bottlenecks,
	get_critical_path,
	get_do_first_tasks,
	get_stale_blockers,
)
from flowstate.infra import get_db_session
from flowstate.infra.models import Task as DBTask


def _json_safe(value: Any) -> Any:
	if isinstance(value, datetime):
		return value.isoformat()
	if isinstance(value, dict):
		return {k: _json_safe(v) for k, v in value.items()}
	if isinstance(value, list):
		return [_json_safe(item) for item in value]
	if hasattr(value, "value"):
		return value.value
	return value


def _resolve_draft_type(event_type: str, draft_type: str | None) -> str:
	if draft_type:
		return draft_type

	mapping = {
		"nudge": "nudge",
		"deadline_approaching": "deadline_reminder",
		"deadline_reminder": "deadline_reminder",
	}
	return mapping.get(event_type, "nudge")


class AgentTools:
	"""Reusable team-scoped tools used by MCP, CLI, and the agent loop."""

	def __init__(self, team_id: str):
		self.team_id = team_id

	def list_tools(self) -> list[dict[str, Any]]:
		return [
			{
				"name": "graph_summary",
				"description": "Return graph size and top intelligence signals for a team.",
				"inputSchema": {"type": "object", "properties": {}},
			},
			{
				"name": "get_critical_path",
				"description": "Return the longest dependency chain as task IDs.",
				"inputSchema": {"type": "object", "properties": {}},
			},
			{
				"name": "analyze_bottlenecks",
				"description": "Find tasks with the highest graph centrality.",
				"inputSchema": {
					"type": "object",
					"properties": {
						"top_n": {"type": "integer", "default": 5, "minimum": 1, "maximum": 100}
					},
				},
			},
			{
				"name": "get_do_first_tasks",
				"description": "Prioritize tasks by urgency, impact, and blockers.",
				"inputSchema": {
					"type": "object",
					"properties": {
						"limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}
					},
				},
			},
			{
				"name": "get_stale_blockers",
				"description": "Return blocking tasks untouched for N days.",
				"inputSchema": {
					"type": "object",
					"properties": {
						"stale_days": {"type": "integer", "default": 3, "minimum": 1, "maximum": 365}
					},
				},
			},
			{
				"name": "draft_message",
				"description": "Generate a connector-ready draft for a task event.",
				"inputSchema": {
					"type": "object",
					"required": ["task_id", "event_type"],
					"properties": {
						"task_id": {"type": "string"},
						"event_type": {"type": "string"},
						"draft_type": {"type": "string"},
						"metadata": {"type": "object", "default": {}},
						"model": {"type": "string"},
					},
				},
			},
			{
				"name": "route_tasks",
				"description": "Run governance routing for candidate tasks.",
				"inputSchema": {
					"type": "object",
					"required": ["tasks"],
					"properties": {
						"tasks": {
							"type": "array",
							"items": {
								"type": "object",
								"required": ["task", "confidence"],
								"properties": {
									"task": {"type": "string"},
									"confidence": {"type": "number"},
									"owner": {"type": "string"},
									"inference_confidence": {"type": "number"},
									"inferred_owner": {"type": "string"},
									"duplicate_candidates": {
										"type": "array",
										"items": {"type": "string"},
									},
								},
							},
						}
					},
				},
			},
		]

	def invoke(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
		arguments = arguments or {}
		dispatch: dict[str, Callable[..., dict[str, Any]]] = {
			"graph_summary": lambda: self.graph_summary(),
			"get_critical_path": lambda: self.critical_path(),
			"analyze_bottlenecks": lambda: self.bottlenecks(top_n=int(arguments.get("top_n", 5))),
			"get_do_first_tasks": lambda: self.do_first(limit=int(arguments.get("limit", 10))),
			"get_stale_blockers": lambda: self.stale_blockers(stale_days=int(arguments.get("stale_days", 3))),
			"draft_message": lambda: self.draft_message(
				task_id=str(arguments["task_id"]),
				event_type=str(arguments["event_type"]),
				draft_type=arguments.get("draft_type"),
				metadata=arguments.get("metadata") or {},
				model=arguments.get("model"),
			),
			"route_tasks": lambda: self.route_candidate_tasks(arguments.get("tasks") or []),
		}

		handler = dispatch.get(name)
		if handler is None:
			available = ", ".join(sorted(dispatch))
			raise ValueError(f"Unknown tool '{name}'. Available tools: {available}")

		return _json_safe(handler())

	def graph_summary(self) -> dict[str, Any]:
		dag = self._load_dag()
		return {
			"team_id": self.team_id,
			"total_tasks": dag.G.number_of_nodes(),
			"total_dependencies": dag.G.number_of_edges(),
			"critical_path": get_critical_path(dag),
			"bottlenecks": get_bottlenecks(dag, top_n=5),
			"stale_blockers": get_stale_blockers(dag, stale_days=3),
		}

	def critical_path(self) -> dict[str, Any]:
		dag = self._load_dag()
		return {"team_id": self.team_id, "critical_path": get_critical_path(dag)}

	def bottlenecks(self, top_n: int = 5) -> dict[str, Any]:
		dag = self._load_dag()
		return {"team_id": self.team_id, "bottlenecks": get_bottlenecks(dag, top_n=top_n)}

	def do_first(self, limit: int = 10) -> dict[str, Any]:
		dag = self._load_dag()
		return {"team_id": self.team_id, "tasks": get_do_first_tasks(dag, limit=limit)}

	def stale_blockers(self, stale_days: int = 3) -> dict[str, Any]:
		dag = self._load_dag()
		return {"team_id": self.team_id, "stale_blockers": get_stale_blockers(dag, stale_days=stale_days)}

	def draft_message(
		self,
		task_id: str,
		event_type: str,
		draft_type: str | None = None,
		metadata: dict[str, Any] | None = None,
		model: str | None = None,
	) -> dict[str, Any]:
		with get_db_session() as db:
			task = db.query(DBTask).filter(DBTask.id == task_id, DBTask.team_id == self.team_id).first()

		if task is None:
			raise ValueError(f"Task not found for team_id={self.team_id}, task_id={task_id}")

		event = GraphEvent(
			event_type=event_type,
			task_id=task_id,
			team_id=self.team_id,
			metadata=metadata or {},
		)

		resolved_type = _resolve_draft_type(event_type=event_type, draft_type=draft_type)
		draft = generate_draft(task, event, draft_type=resolved_type, model=model)

		return {
			"task_id": task_id,
			"team_id": self.team_id,
			"event_type": event_type,
			"draft_type": resolved_type,
			"body": draft.body,
			"suggested_recipient": draft.suggested_recipient,
			"suggested_channel": draft.suggested_channel,
		}

	def route_candidate_tasks(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
		payload: list[GovernanceTask] = []
		for item in tasks:
			payload.append(
				GovernanceTask(
					task=str(item.get("task", "")),
					confidence=float(item.get("confidence", 0.0)),
					inference_confidence=(
						float(item["inference_confidence"])
						if item.get("inference_confidence") is not None
						else None
					),
					owner=item.get("owner"),
					inferred_owner=item.get("inferred_owner"),
					duplicate_candidates=list(item.get("duplicate_candidates") or []),
				)
			)

		routed = route_tasks(payload)
		return {
			"team_id": self.team_id,
			"approved": routed.get("approved", []),
			"review": routed.get("review", []),
		}

	def _load_dag(self) -> FlowstateDAG:
		dag = FlowstateDAG(team_id=self.team_id)
		dag.load_from_db()
		return dag
