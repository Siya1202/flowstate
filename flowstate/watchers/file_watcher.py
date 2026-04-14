from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Iterable, List, Optional

from flowstate.watchers.base import BaseWatcher, RawEvent


class FileWatcher(BaseWatcher):
	"""Watcher for local files or mounted drives using polling."""

	def __init__(
		self,
		team_id: str,
		watch_paths: Iterable[str],
		poll_interval: int = 60,
		allowed_extensions: Optional[set[str]] = None,
	):
		super().__init__(team_id=team_id, poll_interval=poll_interval)
		self.watch_paths = [Path(p).expanduser().resolve() for p in watch_paths]
		self.allowed_extensions = allowed_extensions or {".txt", ".md", ".json", ".csv", ".log"}

	def fetch_new_events(self) -> List[RawEvent]:
		from flowstate.infra import get_redis

		r = get_redis()
		events: List[RawEvent] = []

		for base in self.watch_paths:
			if not base.exists() or not base.is_dir():
				continue

			for path in base.rglob("*"):
				if not path.is_file() or path.suffix.lower() not in self.allowed_extensions:
					continue

				stat = path.stat()
				fingerprint = f"{path}:{int(stat.st_mtime)}:{stat.st_size}"
				external_id = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
				dedupe_key = f"flowstate:file_watcher:seen:{self.team_id}:{external_id}"

				# SETNX ensures idempotency across restarts and concurrent workers.
				if not r.setnx(dedupe_key, "1"):
					continue

				r.expire(dedupe_key, 60 * 60 * 24 * 30)

				with path.open("r", encoding="utf-8", errors="replace") as f:
					content = f.read()

				events.append(
					RawEvent(
						source="file",
						content=content,
						metadata={
							"path": str(path),
							"filename": path.name,
							"extension": path.suffix.lower(),
							"size": stat.st_size,
						},
						team_id=self.team_id,
						timestamp=datetime.now(timezone.utc),
						external_id=external_id,
					)
				)

		return events
