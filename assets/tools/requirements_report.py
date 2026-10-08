#!/usr/bin/env python3
"""Show current requirement memory and summarize recent requirement events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def project_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise SystemExit("target must be inside a Git project")


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as error:
                raise SystemExit(f"invalid JSON on line {line_number}: {error}") from error
            if not isinstance(event, dict):
                raise SystemExit(f"line {line_number} is not a JSON object")
            events.append(event)
    return events


def active_requirements(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for event in events:
        key = event.get("key")
        operation = str(event.get("operation", "")).upper()
        if not isinstance(key, str) or not key.strip():
            continue
        key = key.strip()
        if operation == "REMOVE":
            active.pop(key, None)
        elif operation in {"CREATE", "UPDATE", "CORRECT"}:
            content = event.get("new_content")
            if isinstance(content, str) and content.strip():
                active[key] = {
                    "key": key,
                    "type": event.get("type", "REQUIREMENT"),
                    "content": content.strip(),
                    "version": event.get("version", 1),
                    "updated_at": event.get("created_at"),
                }
    return active


def print_requirements(active: dict[str, dict[str, Any]]) -> None:
    print("Current active requirements:")
    if not active:
        print("- (none)")
        return
    for key in sorted(active):
        item = active[key]
        print(f"- [{item['type']}] {key} (v{item['version']}): {item['content']}")


def print_summary(events: list[dict[str, Any]], count: int) -> None:
    recent = events[-count:] if count > 0 else []
    print(f"Recent requirement changes (last {len(recent)} events):")
    if not recent:
        print("- (none)")
        return
    for event in recent:
        operation = str(event.get("operation", "UNKNOWN")).upper()
        key = event.get("key", "<unknown>")
        content = event.get("new_content")
        if content is None:
            content = "(removed)"
        print(f"- {operation} {key}: {str(content).strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--recent", type=int, default=5, help="number of recent events")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.recent < 0:
        raise SystemExit("--recent must be non-negative")

    root = project_root(args.project)
    events = read_events(root / ".agent-memory" / "requirements.jsonl")
    if not args.summary_only:
        print_requirements(active_requirements(events))
        print()
    print_summary(events, args.recent)


if __name__ == "__main__":
    main()
