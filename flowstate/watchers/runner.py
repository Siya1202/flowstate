from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import multiprocessing as mp
import os
import signal
import time
from typing import Dict, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from flowstate.config import settings
from flowstate.infra import get_redis
from flowstate.watchers.registry import build_watcher


@dataclass(frozen=True)
class WatcherSpec:
    watcher_type: str
    team_id: str


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _should_enable_watcher(watcher_type: str) -> bool:
    if watcher_type == "file":
        return settings.ENABLE_FILE_WATCHER
    if watcher_type == "email":
        return settings.ENABLE_EMAIL_WATCHER
    return True


def _build_gmail_service():
    if not settings.GMAIL_TOKEN_FILE:
        return None

    creds = Credentials.from_authorized_user_file(
        settings.GMAIL_TOKEN_FILE,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    return build("gmail", "v1", credentials=creds)


def _build_runtime_config() -> Dict:
    config: Dict = {
        "poll_interval": settings.WATCHER_POLL_INTERVAL,
        "file_watch_paths": _csv_to_list(settings.FILE_WATCH_PATHS),
        "file_watch_extensions": set(_csv_to_list(settings.FILE_WATCH_EXTENSIONS)),
        "email_query": settings.EMAIL_WATCH_QUERY,
        "email_label_ids": _csv_to_list(settings.EMAIL_WATCH_LABEL_IDS),
    }

    if settings.ENABLE_EMAIL_WATCHER:
        config["gmail_service"] = _build_gmail_service()

    return config


def _watcher_process_main(watcher_type: str, team_id: str, runtime_config: Dict):
    watcher = build_watcher(watcher_type=watcher_type, team_id=team_id, runtime_config=runtime_config)
    watcher.run_forever()


def _heartbeat_key(spec: WatcherSpec) -> str:
    return f"flowstate:watchers:heartbeat:{spec.team_id}:{spec.watcher_type}"


def _write_heartbeat(spec: WatcherSpec, process: mp.Process):
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "watcher_type": spec.watcher_type,
        "team_id": spec.team_id,
        "pid": process.pid,
        "alive": process.is_alive(),
        "updated_at": now,
    }
    r = get_redis()
    r.set(_heartbeat_key(spec), json.dumps(payload), ex=settings.WATCHER_HEARTBEAT_TTL_SECONDS)


def _load_specs() -> list[WatcherSpec]:
    teams = _csv_to_list(settings.WATCHER_TEAM_IDS)
    watcher_types = _csv_to_list(settings.WATCHER_TYPES)

    specs: list[WatcherSpec] = []
    for team_id in teams:
        for watcher_type in watcher_types:
            if _should_enable_watcher(watcher_type):
                specs.append(WatcherSpec(watcher_type=watcher_type, team_id=team_id))
    return specs


def run_watchers_supervisor():
    specs = _load_specs()
    if not specs:
        print("[watcher-runner] No watchers configured. Exiting.")
        return

    runtime_config = _build_runtime_config()
    procs: Dict[WatcherSpec, mp.Process] = {}
    shutdown = False

    def _request_shutdown(_signum, _frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    for spec in specs:
        proc = mp.Process(
            target=_watcher_process_main,
            args=(spec.watcher_type, spec.team_id, runtime_config),
            daemon=False,
            name=f"watcher-{spec.watcher_type}-{spec.team_id}",
        )
        proc.start()
        procs[spec] = proc
        _write_heartbeat(spec, proc)
        print(f"[watcher-runner] Started {spec.watcher_type} for team={spec.team_id} pid={proc.pid}")

    try:
        while not shutdown:
            time.sleep(settings.WATCHER_MONITOR_INTERVAL_SECONDS)
            for spec, proc in list(procs.items()):
                if not proc.is_alive():
                    exit_code = proc.exitcode
                    print(
                        f"[watcher-runner] {spec.watcher_type} team={spec.team_id} exited code={exit_code}; restarting"
                    )
                    restarted = mp.Process(
                        target=_watcher_process_main,
                        args=(spec.watcher_type, spec.team_id, runtime_config),
                        daemon=False,
                        name=f"watcher-{spec.watcher_type}-{spec.team_id}",
                    )
                    restarted.start()
                    procs[spec] = restarted
                    proc.join(timeout=1)
                    proc.close()
                    proc = restarted

                _write_heartbeat(spec, proc)
    finally:
        for spec, proc in procs.items():
            if proc.is_alive():
                print(f"[watcher-runner] Stopping {spec.watcher_type} for team={spec.team_id}")
                os.kill(proc.pid, signal.SIGTERM)
                proc.join(timeout=10)
                if proc.is_alive():
                    os.kill(proc.pid, signal.SIGKILL)
                    proc.join(timeout=2)
            proc.close()


if __name__ == "__main__":
    run_watchers_supervisor()
