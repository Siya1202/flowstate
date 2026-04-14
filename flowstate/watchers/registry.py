from typing import Any, Callable, Dict, Optional

from flowstate.config import settings
from flowstate.watchers.base import BaseWatcher
from flowstate.watchers.email_watcher import EmailWatcher
from flowstate.watchers.file_watcher import FileWatcher

WatcherBuilder = Callable[[str, Dict[str, Any]], BaseWatcher]


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_file_watcher(team_id: str, runtime_config: Dict[str, Any]) -> BaseWatcher:
    watch_paths = runtime_config.get("file_watch_paths") or _csv_to_list(settings.FILE_WATCH_PATHS)
    extensions = runtime_config.get("file_watch_extensions") or set(_csv_to_list(settings.FILE_WATCH_EXTENSIONS))
    return FileWatcher(
        team_id=team_id,
        watch_paths=watch_paths,
        poll_interval=runtime_config.get("poll_interval", settings.WATCHER_POLL_INTERVAL),
        allowed_extensions=extensions,
    )


def build_email_watcher(team_id: str, runtime_config: Dict[str, Any]) -> BaseWatcher:
    gmail_service = runtime_config.get("gmail_service")
    query = runtime_config.get("email_query", settings.EMAIL_WATCH_QUERY)
    label_ids = runtime_config.get("email_label_ids") or _csv_to_list(settings.EMAIL_WATCH_LABEL_IDS)
    return EmailWatcher(
        team_id=team_id,
        poll_interval=runtime_config.get("poll_interval", settings.WATCHER_POLL_INTERVAL),
        gmail_service=gmail_service,
        query=query,
        label_ids=label_ids if label_ids else None,
    )


REGISTRY: dict[str, WatcherBuilder] = {
    "file": build_file_watcher,
    "email": build_email_watcher,
}


def build_watcher(watcher_type: str, team_id: str, runtime_config: Optional[Dict[str, Any]] = None) -> BaseWatcher:
    runtime_config = runtime_config or {}
    builder = REGISTRY.get(watcher_type)
    if builder is None:
        raise ValueError(f"Unsupported watcher type: {watcher_type}")
    return builder(team_id, runtime_config)
