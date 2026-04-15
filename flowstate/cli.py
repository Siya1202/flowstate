"""CLI entry point for the Flowstate Python package."""

from __future__ import annotations

import argparse

from flowstate import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flowstate",
        description="Flowstate command line interface",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print installed Flowstate version and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
