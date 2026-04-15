"""Slack bot package entrypoint."""

from __future__ import annotations

import argparse

import uvicorn


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Flowstate Slack bot webhook service")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8001, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable development reload")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    uvicorn.run("flowstate.slack_app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
