"""
connector_adapter.py
Abstract base class for all Flowstate connector adapters.

Every connector (OpenClaw, direct Gmail, Slack, etc.) must implement this
interface so the rest of the system can treat them polymorphically.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from backend.models import Event


class ConnectorAdapter(ABC):
    """
    Abstract connector interface.

    Concrete implementations wrap third-party APIs (OpenClaw, Google APIs, etc.)
    and translate their responses into the canonical Event model.
    """

    # ------------------------------------------------------------------ #
    # Read operations                                                       #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_emails(self, since: datetime) -> List[Event]:
        """
        Fetch emails received after *since*.

        Args:
            since: Fetch only emails newer than this UTC datetime.

        Returns:
            A list of Event objects with type="email_received".
        """
        ...

    @abstractmethod
    def get_slack_messages(self, channel: str, since: datetime) -> List[Event]:
        """
        Fetch Slack messages from *channel* posted after *since*.

        Args:
            channel: Slack channel ID or name.
            since:   Fetch only messages newer than this UTC datetime.

        Returns:
            A list of Event objects with type="slack_message".
        """
        ...

    # ------------------------------------------------------------------ #
    # Write / action operations                                             #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> None:
        """
        Send an email via the underlying connector.

        Args:
            to:      Recipient email address.
            subject: Email subject line.
            body:    Plain-text or HTML body.
        """
        ...

    @abstractmethod
    def create_calendar_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
    ) -> None:
        """
        Create a calendar event.

        Args:
            title: Human-readable event title.
            start: Event start in UTC.
            end:   Event end in UTC.
        """
        ...
