from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import json
import time
from typing import Dict, List


@dataclass
class RawEvent:
	source: str
	content: str
	metadata: Dict
	team_id: str
	timestamp: datetime
	external_id: str


class BaseWatcher(ABC):
	def __init__(self, team_id: str, poll_interval: int = 60):
		self.team_id = team_id
		self.poll_interval = poll_interval

	@abstractmethod
	def fetch_new_events(self) -> List[RawEvent]:
		"""Fetch events since last run. Must be idempotent."""

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

		r = get_redis()
		r.rpush(
			"flowstate:raw_events",
			json.dumps(
				{
					"source": event.source,
					"content": event.content,
					"metadata": event.metadata,
					"team_id": event.team_id,
					"timestamp": event.timestamp.isoformat(),
					"external_id": event.external_id,
				}
			),
		)
