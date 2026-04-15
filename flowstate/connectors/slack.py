"""Slack connector — sends notifications to Slack channels."""

import hashlib
import json
import os
import redis
from datetime import datetime
from typing import Any, List, Optional
from flowstate.connectors.base import BaseConnector, ConnectorResult, GraphEvent

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _get_idempotency_key(task_id: str, event_type: str, recipient: str) -> str:
	"""Generate idempotency key to prevent duplicate messages."""
	content = f"slack:{task_id}:{event_type}:{recipient}:{datetime.utcnow().date()}"
	return hashlib.sha256(content.encode()).hexdigest()


def _already_sent(key: str) -> bool:
	"""Check if this message has already been sent."""
	try:
		r = redis.from_url(REDIS_URL)
		return r.sismember("flowstate:slack:sent", key)
	except Exception:
		return False


def _mark_sent(key: str):
	"""Mark this message as sent."""
	try:
		r = redis.from_url(REDIS_URL)
		r.sadd("flowstate:slack:sent", key)
		r.expire(key, 30 * 24 * 60 * 60)  # Keep for 30 days
	except Exception:
		pass


class SlackConnector(BaseConnector):
	"""Sends Slack notifications for task events."""
	
	name = "slack"
	description = "Sends Slack notifications for task_blocked, blocker_resolved, and digest events"

	def __init__(self, team_id: str, credentials: Optional[dict] = None):
		super().__init__(team_id=team_id, credentials=credentials)
		self.webhook_url = credentials.get("webhook_url") if credentials else None
		self.user_id_map = credentials.get("user_id_map", {}) if credentials else {}

	def can_handle(self, event: GraphEvent) -> bool:
		"""Handle task_blocked, blocker_resolved, and digest events."""
		return event.event_type in ("task_blocked", "blocker_resolved", "digest")

	def execute(self, task: Any, event: GraphEvent) -> ConnectorResult:
		"""Send Slack message for the event."""
		if not self.webhook_url:
			return ConnectorResult(
				success=False,
				external_id=None,
				message="Slack webhook URL not configured"
			)

		try:
			message = self._build_message(task, event)
			recipient = self._get_recipient(task, event)
			
			# Idempotency check
			idempotency_key = _get_idempotency_key(task.id, event.event_type, recipient)
			if _already_sent(idempotency_key):
				return ConnectorResult(
					success=True,
					external_id=None,
					message=f"Message already sent to {recipient}"
				)

			# Send via webhook
			import requests
			response = requests.post(
				self.webhook_url,
				json=message,
				headers={"Content-Type": "application/json"},
				timeout=10
			)
			
			if response.status_code == 200:
				_mark_sent(idempotency_key)
				return ConnectorResult(
					success=True,
					external_id=response.text,
					message=f"Sent to {recipient}"
				)
			else:
				return ConnectorResult(
					success=False,
					external_id=None,
					message=f"Slack API error: {response.status_code}"
				)
		except Exception as e:
			return ConnectorResult(
				success=False,
				external_id=None,
				message=str(e)
			)

	def _build_message(self, task: Any, event: GraphEvent) -> dict:
		"""Build Slack message payload."""
		draft_text = event.metadata.get("draft")
		if draft_text:
			return {"text": draft_text}

		if event.event_type == "task_blocked":
			blocker_title = event.metadata.get("blocker_title", "Unknown task")
			blocker_owner = event.metadata.get("blocker_owner", "Unknown")
			return {
				"text": f"🚨 {task.title}",
				"blocks": [
					{
						"type": "section",
						"text": {
							"type": "mrkdwn",
							"text": f"*Task blocked:* {task.title}\n" +
									f"*Blocked by:* {blocker_title} (owner: {blocker_owner})"
						}
					},
					{
						"type": "actions",
						"elements": [
							{
								"type": "button",
								"text": {"type": "plain_text", "text": "View in Flowstate"},
								"url": f"https://flowstate.example.com/tasks/{task.id}"
							}
						]
					}
				]
			}
		
		elif event.event_type == "blocker_resolved":
			was_blocked_by = event.metadata.get("was_blocked_by", "Unknown task")
			return {
				"text": f"✅ Unblocked: {task.title}",
				"blocks": [
					{
						"type": "section",
						"text": {
							"type": "mrkdwn",
							"text": f"✅ *{task.title}* is now unblocked!\n" +
									f"Previously blocked by: {was_blocked_by}"
						}
					},
					{
						"type": "context",
						"elements": [
							{"type": "mrkdwn", "text": f"Owner: {task.owner or 'Unassigned'}"}
						]
					}
				]
			}
		
		elif event.event_type == "digest":
			total_tasks = event.metadata.get("total_tasks", 0)
			critical_count = event.metadata.get("critical_count", 0)
			return {
				"text": "📊 Daily digest",
				"blocks": [
					{
						"type": "section",
						"text": {
							"type": "mrkdwn",
							"text": f"*Daily Digest*\n" +
									f"Total tasks: {total_tasks}\n" +
									f"🔴 Critical: {critical_count}"
						}
					}
				]
			}
		
		return {"text": "Task update"}

	def _get_recipient(self, task: Any, event: GraphEvent) -> str:
		"""Get recipient for the message (user_id or channel)."""
		if event.event_type == "task_blocked":
			return event.metadata.get("blocker_owner", task.owner or "team")
		elif event.event_type == "blocker_resolved":
			return task.owner or "team"
		else:  # digest
			return "#flowstate-digest"
