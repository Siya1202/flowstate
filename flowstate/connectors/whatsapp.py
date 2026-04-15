"""WhatsApp connector — sends nudges via WhatsApp Business API."""

import hashlib
import os
import redis
from typing import Any, Optional
from flowstate.connectors.base import BaseConnector, ConnectorResult, GraphEvent
from datetime import datetime

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _get_idempotency_key(task_id: str, recipient_phone: str) -> str:
	"""Generate idempotency key to prevent duplicate messages."""
	content = f"whatsapp:{task_id}:{recipient_phone}:{datetime.utcnow().date()}"
	return hashlib.sha256(content.encode()).hexdigest()


def _already_sent(key: str) -> bool:
	"""Check if this message has already been sent."""
	try:
		r = redis.from_url(REDIS_URL)
		return r.sismember("flowstate:whatsapp:sent", key)
	except Exception:
		return False


def _mark_sent(key: str):
	"""Mark this message as sent."""
	try:
		r = redis.from_url(REDIS_URL)
		r.sadd("flowstate:whatsapp:sent", key)
		r.expire(key, 30 * 24 * 60 * 60)  # Keep for 30 days
	except Exception:
		pass


class WhatsAppConnector(BaseConnector):
	"""Sends nudge messages via WhatsApp Business API."""
	
	name = "whatsapp"
	description = "Sends nudge messages via WhatsApp Business API"

	def __init__(self, team_id: str, credentials: Optional[dict] = None):
		super().__init__(team_id=team_id, credentials=credentials)
		self.phone_number_id = credentials.get("phone_number_id") if credentials else None
		self.access_token = credentials.get("access_token") if credentials else None
		self.recipient_map = credentials.get("recipient_map", {}) if credentials else {}

	def can_handle(self, event: GraphEvent) -> bool:
		"""Handle nudge events."""
		return event.event_type == "nudge"

	def execute(self, task: Any, event: GraphEvent) -> ConnectorResult:
		"""Send nudge message via WhatsApp."""
		if not self.phone_number_id or not self.access_token:
			return ConnectorResult(
				success=False,
				external_id=None,
				message="WhatsApp credentials not configured"
			)

		recipient_phone = self._get_recipient_phone(task, event)
		if not recipient_phone:
			return ConnectorResult(
				success=False,
				external_id=None,
				message="No recipient phone number found"
			)

		# Idempotency check
		idempotency_key = _get_idempotency_key(task.id, recipient_phone)
		if _already_sent(idempotency_key):
			return ConnectorResult(
				success=True,
				external_id=None,
				message=f"Nudge already sent to {recipient_phone}"
			)

		try:
			message_text = self._build_message_text(task, event)
			
			import requests
			url = f"https://graph.instagram.com/v18.0/{self.phone_number_id}/messages"
			
			payload = {
				"messaging_product": "whatsapp",
				"recipient_type": "individual",
				"to": recipient_phone.lstrip("+"),
				"type": "text",
				"text": {"body": message_text},
			}
			
			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json",
			}
			
			response = requests.post(url, json=payload, headers=headers, timeout=10)
			
			if response.status_code == 200:
				response_data = response.json()
				message_id = response_data.get("messages", [{}])[0].get("id")
				_mark_sent(idempotency_key)
				
				return ConnectorResult(
					success=True,
					external_id=message_id,
					message=f"Nudge sent to {recipient_phone}"
				)
			else:
				return ConnectorResult(
					success=False,
					external_id=None,
					message=f"WhatsApp API error: {response.status_code} - {response.text}"
				)
		except Exception as e:
			return ConnectorResult(
				success=False,
				external_id=None,
				message=str(e)
			)

	def _build_message_text(self, task: Any, event: GraphEvent) -> str:
		"""Build the nudge message text."""
		draft_text = event.metadata.get("draft")
		if draft_text:
			return draft_text

		blocked_by = event.metadata.get("blocked_by", "a task")
		blocker_owner = event.metadata.get("blocker_owner", "someone")
		days_stuck = event.metadata.get("days_stuck", 1)
		
		return (
			f"Hi {task.owner or 'there'}! 👋\n\n"
			f"'{task.title}' is waiting on '{blocked_by}' from {blocker_owner}. "
			f"It's been stuck for {days_stuck} day{'s' if days_stuck != 1 else ''}.\n\n"
			f"Can you help unblock it? Thanks!"
		)

	def _get_recipient_phone(self, task: Any, event: GraphEvent) -> Optional[str]:
		"""Get recipient's phone number."""
		# First, check if there's a mapping for this person
		owner = task.owner or event.metadata.get("recipient")
		if owner and owner in self.recipient_map:
			return self.recipient_map[owner]
		
		# Otherwise, try to get from event metadata
		return event.metadata.get("recipient_phone")
