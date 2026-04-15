"""Release helpers for local version bumping."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT / "pyproject.toml"
INIT_PATH = ROOT / "flowstate" / "__init__.py"

VERSION_PATTERN = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')


def _read_current_version() -> str:
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find project version in pyproject.toml")
    return match.group(1)


def _bump_version(version: str, part: str) -> str:
    match = VERSION_PATTERN.match(version)
    if not match:
        raise ValueError(f"Version '{version}' is not semver-like (X.Y.Z)")

    major, minor, patch = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Unsupported bump part: {part}")

    return f"{major}.{minor}.{patch}"


def _set_version_in_file(path: Path, pattern: str, new_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, rf'\g<1>{new_version}\g<2>', text, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Expected one version match in {path}, found {count}")
    path.write_text(updated, encoding="utf-8")


def update_versions(new_version: str) -> None:
    _set_version_in_file(
        PYPROJECT_PATH,
        r'^(version\s*=\s*")([^"]+)(")',
        new_version,
    )
    _set_version_in_file(
        INIT_PATH,
        r'^(\s*__version__\s*=\s*")([^"]+)(")',
        new_version,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bump Flowstate package version")
    parser.add_argument(
        "part",
        choices=["major", "minor", "patch"],
        help="Which semantic version segment to bump.",
    )
    parser.add_argument(
        "--set-version",
        dest="set_version",
        default=None,
        help="Set an explicit version instead of bumping.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    current = _read_current_version()
    if args.set_version:
        if not VERSION_PATTERN.match(args.set_version):
            raise SystemExit("--set-version must be in X.Y.Z format")
        target = args.set_version
    else:
        target = _bump_version(current, args.part)

    update_versions(target)
    print(f"Updated version: {current} -> {target}")
    print("Next steps:")
    print("  1. python -m build")
    print("  2. python -m twine check dist/*")
    print("  3. git add pyproject.toml flowstate/__init__.py && git commit -m 'chore: bump version'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
