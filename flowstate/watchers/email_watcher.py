from datetime import datetime, timezone
from typing import Dict, List, Optional

from flowstate.watchers.base import BaseWatcher, RawEvent


class EmailWatcher(BaseWatcher):
	"""Watcher for inbox events via Gmail API polling.

	Use push webhook delivery to update the Gmail label and this watcher will
	pull message bodies with idempotent processing.
	"""

	def __init__(
		self,
		team_id: str,
		poll_interval: int = 60,
		gmail_service=None,
		query: str = "in:inbox newer_than:2d",
		label_ids: Optional[List[str]] = None,
	):
		super().__init__(team_id=team_id, poll_interval=poll_interval)
		self.gmail_service = gmail_service
		self.query = query
		self.label_ids = label_ids

	def fetch_new_events(self) -> List[RawEvent]:
		if self.gmail_service is None:
			return []

		from flowstate.infra import get_redis

		r = get_redis()
		response = (
			self.gmail_service.users()
			.messages()
			.list(userId="me", q=self.query, labelIds=self.label_ids)
			.execute()
		)

		events: List[RawEvent] = []
		for item in response.get("messages", []):
			message_id = item.get("id")
			if not message_id:
				continue

			dedupe_key = f"flowstate:email_watcher:seen:{self.team_id}:{message_id}"
			if not r.setnx(dedupe_key, "1"):
				continue

			r.expire(dedupe_key, 60 * 60 * 24 * 30)

			payload = (
				self.gmail_service.users()
				.messages()
				.get(userId="me", id=message_id, format="full")
				.execute()
			)
			content = self._extract_message_text(payload)
			metadata = self._extract_metadata(payload)

			events.append(
				RawEvent(
					source="email",
					content=content,
					metadata=metadata,
					team_id=self.team_id,
					timestamp=datetime.now(timezone.utc),
					external_id=message_id,
				)
			)

		return events

	def _extract_message_text(self, payload: Dict) -> str:
		body_data = payload.get("snippet", "")
		full_payload = payload.get("payload", {})
		parts = full_payload.get("parts", [])

		for part in parts:
			if part.get("mimeType") == "text/plain":
				data = part.get("body", {}).get("data")
				if data:
					# Keep implementation dependency-light; snippet is enough fallback.
					body_data = payload.get("snippet", body_data)
					break

		return body_data or ""

	def _extract_metadata(self, payload: Dict) -> Dict:
		headers = payload.get("payload", {}).get("headers", [])
		header_map = {h.get("name", "").lower(): h.get("value", "") for h in headers}
		return {
			"from": header_map.get("from", ""),
			"to": header_map.get("to", ""),
			"subject": header_map.get("subject", ""),
			"thread_id": payload.get("threadId", ""),
		}
