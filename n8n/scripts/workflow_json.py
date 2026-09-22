#!/usr/bin/env python3
"""Normalize n8n workflow exports for version control."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

KEEP_FIELDS = (
    "id",
    "name",
    "active",
    "nodes",
    "connections",
    "settings",
    "pinData",
    "versionId",
    "tags",
)

# Ignore metadata-only drift (versionId, tags, pinData).
SUBSTANTIVE_FIELDS = ("name", "active", "nodes", "connections", "settings")


def pick_fields(workflow: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: workflow[key] for key in fields if key in workflow}


def normalize(workflow: dict[str, Any]) -> dict[str, Any]:
    return pick_fields(workflow, KEEP_FIELDS)


def substantive(workflow: dict[str, Any]) -> dict[str, Any]:
    return pick_fields(workflow, SUBSTANTIVE_FIELDS)


def load_export_payload(payload: str | bytes) -> dict[str, Any]:
    data = json.loads(payload)
    if isinstance(data, list):
        if not data:
            raise ValueError("export returned an empty list")
        return data[0]
    if isinstance(data, dict):
        return data
    raise ValueError(f"unexpected export type: {type(data).__name__}")


def diff_fields(repo: dict[str, Any], live: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for key in SUBSTANTIVE_FIELDS:
        if repo.get(key) != live.get(key):
            changed.append(key)
    return changed


def write_workflow(path: Path, workflow: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(normalize(workflow), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write_cmd = sub.add_parser("write", help="Normalize exported workflow JSON and write to a file")
    write_cmd.add_argument("path", type=Path)

    check_cmd = sub.add_parser("check", help="Compare substantive fields between file and export")
    check_cmd.add_argument("path", type=Path)

    args = parser.parse_args()
    exported = load_export_payload(sys.stdin.read())

    if args.command == "write":
        write_workflow(args.path, exported)
        return 0

    repo = json.loads(args.path.read_text(encoding="utf-8"))
    changed = diff_fields(substantive(repo), substantive(exported))
    if not changed:
        return 0

    print(f"{args.path.name}: out of sync ({', '.join(changed)})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
