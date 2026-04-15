from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any


class FlowstateMCPServer:
	"""Lightweight stdio MCP-style server exposing Flowstate AgentTools."""

	def __init__(self, team_id: str = "team_alpha"):
		self.team_id = team_id
		from flowstate.agent.tools import AgentTools

		self.tools = AgentTools(team_id=team_id)

	def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
		req_id = request.get("id")
		method = request.get("method")
		params = request.get("params") or {}

		try:
			if method == "initialize":
				return self._ok(
					req_id,
					{
						"serverInfo": {
							"name": "flowstate-mcp",
							"version": "0.1.0",
						},
						"capabilities": {
							"tools": {},
						},
					},
				)

			if method == "tools/list":
				return self._ok(req_id, {"tools": self.tools.list_tools()})

			if method == "tools/call":
				tool_name = params.get("name")
				if not tool_name:
					return self._err(req_id, code=-32602, message="Missing tool name")

				arguments = params.get("arguments") or {}
				result = self.tools.invoke(name=tool_name, arguments=arguments)
				return self._ok(req_id, {"result": result})

			if method == "ping":
				return self._ok(req_id, {"ok": True})

			# For unknown notifications without id, ignore silently.
			if req_id is None:
				return None

			return self._err(req_id, code=-32601, message=f"Unknown method: {method}")
		except Exception as exc:
			if req_id is None:
				return None
			return self._err(req_id, code=-32000, message=str(exc), data=traceback.format_exc())

	def run_stdio(self):
		for line in sys.stdin:
			raw = line.strip()
			if not raw:
				continue

			try:
				request = json.loads(raw)
			except json.JSONDecodeError as exc:
				response = self._err(None, code=-32700, message=f"Invalid JSON payload: {exc}")
			else:
				response = self.handle_request(request)

			if response is None:
				continue

			sys.stdout.write(json.dumps(response) + "\n")
			sys.stdout.flush()

	@staticmethod
	def _ok(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
		return {"jsonrpc": "2.0", "id": req_id, "result": result}

	@staticmethod
	def _err(req_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
		payload: dict[str, Any] = {"code": code, "message": message}
		if data is not None:
			payload["data"] = data
		return {"jsonrpc": "2.0", "id": req_id, "error": payload}


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Run Flowstate MCP server over stdio.")
	parser.add_argument("--team-id", default="team_alpha", help="Team context for tool execution.")
	return parser


def main() -> int:
	args = _build_parser().parse_args()
	server = FlowstateMCPServer(team_id=args.team_id)
	server.run_stdio()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
