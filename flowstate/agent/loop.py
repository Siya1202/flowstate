from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import redis
from redis import exceptions as redis_exceptions


@dataclass
class AgentLoopStats:
	processed_jobs: int = 0
	failed_jobs: int = 0
	last_success_at: float | None = None
	last_error: str | None = None


class AgentLoop:
	"""Redis-backed async loop that executes the Flowstate worker pipeline."""

	def __init__(
		self,
		team_id: str | None = None,
		queue_names: tuple[str, ...] = ("flowstate:jobs", "flowstate:raw_events"),
		poll_timeout_seconds: int = 15,
		redis_retry_seconds: int = 5,
	):
		self.team_id = team_id or os.getenv("FLOWSTATE_AGENT_TEAM_ID", "team_alpha")
		self.queue_names = queue_names
		self.poll_timeout_seconds = poll_timeout_seconds
		self.redis_retry_seconds = redis_retry_seconds
		self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
		self._redis: redis.Redis | None = None
		self._running = False
		self.stats = AgentLoopStats()

	async def run_forever(self):
		self._running = True
		print(
			f"[agent-loop] Starting for team_id={self.team_id} "
			f"queues={','.join(self.queue_names)}"
		)

		while self._running:
			try:
				await self.process_once()
			except (redis_exceptions.ConnectionError, redis_exceptions.TimeoutError) as exc:
				print(f"[agent-loop] Redis unavailable: {exc}. Retrying in {self.redis_retry_seconds}s...")
				self._redis = None
				await asyncio.sleep(self.redis_retry_seconds)
			except Exception as exc:  # pragma: no cover - safety net for long-running service
				self.stats.failed_jobs += 1
				self.stats.last_error = str(exc)
				print(f"[agent-loop] Unexpected error: {exc}")
				await asyncio.sleep(1)

	async def process_once(self) -> bool:
		client = await self._redis_client()
		item = await asyncio.to_thread(client.brpop, list(self.queue_names), self.poll_timeout_seconds)
		if not item:
			return False

		queue_name_raw, payload_raw = item
		queue_name = queue_name_raw.decode() if isinstance(queue_name_raw, bytes) else str(queue_name_raw)
		payload = payload_raw.decode() if isinstance(payload_raw, bytes) else str(payload_raw)

		try:
			job = json.loads(payload)
		except json.JSONDecodeError as exc:
			self.stats.failed_jobs += 1
			self.stats.last_error = f"Invalid JSON payload from {queue_name}: {exc}"
			print(f"[agent-loop] {self.stats.last_error}")
			return False

		normalized = self._normalize_job(queue_name, job)
		await asyncio.to_thread(self._process_job, normalized)
		self.stats.processed_jobs += 1
		self.stats.last_success_at = time.time()
		return True

	def stop(self):
		self._running = False

	async def _redis_client(self) -> redis.Redis:
		if self._redis is not None:
			return self._redis

		client = redis.from_url(self.redis_url)
		await asyncio.to_thread(client.ping)
		self._redis = client
		return client

	def _normalize_job(self, queue_name: str, payload: dict[str, Any]) -> dict[str, Any]:
		if queue_name.endswith("raw_events"):
			return {
				"job_id": payload.get("external_id") or str(uuid.uuid4()),
				"team_id": payload.get("team_id", self.team_id),
				"source": payload.get("source", "watcher"),
				"content": payload.get("content", ""),
				"metadata": payload.get("metadata") or {},
				"external_id": payload.get("external_id"),
			}

		normalized = dict(payload)
		normalized.setdefault("team_id", self.team_id)
		normalized.setdefault("job_id", str(uuid.uuid4()))
		return normalized

	@staticmethod
	def _process_job(job: dict[str, Any]):
		# Imported lazily so CLI --help works even when non-package modules are absent.
		from backend.worker import process_job

		return process_job(job)


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Run Flowstate agent loop")
	parser.add_argument("--team-id", default=None, help="Team ID used when queue payloads omit team_id.")
	parser.add_argument(
		"--queues",
		default="flowstate:jobs,flowstate:raw_events",
		help="Comma-separated Redis queue names to consume (highest priority first).",
	)
	parser.add_argument(
		"--poll-timeout",
		type=int,
		default=15,
		help="BRPOP timeout in seconds before polling again.",
	)
	return parser


def main() -> int:
	args = _build_parser().parse_args()
	queue_names = tuple(name.strip() for name in args.queues.split(",") if name.strip())
	if not queue_names:
		raise SystemExit("At least one queue name is required.")

	loop = AgentLoop(
		team_id=args.team_id,
		queue_names=queue_names,
		poll_timeout_seconds=args.poll_timeout,
	)
	try:
		asyncio.run(loop.run_forever())
	except KeyboardInterrupt:
		loop.stop()
		print("[agent-loop] Stopped")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
