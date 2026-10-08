#!/usr/bin/env python3
"""Load active requirements when a Codex session starts or resumes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional


MEMORY_DIRECTORY = ".agent-memory"
MEMORY_FILENAME = "requirements.jsonl"


def find_project_root(cwd: str) -> Path:
    current = Path(cwd).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    for candidate in (current, *current.parents):
        if (candidate / MEMORY_DIRECTORY).exists():
            return candidate
    return current


def load_requirements(path: Path) -> dict[str, dict[str, Any]]:
    requirements: dict[str, dict[str, Any]] = {}
    project_ids: set[str] = set()
    if not path.exists():
        return requirements

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            project_id = event.get("project_id")
            if isinstance(project_id, str) and project_id.strip():
                project_ids.add(project_id.strip())
                if len(project_ids) > 1:
                    raise ValueError(
                        "requirement memory contains multiple project_id values"
                    )
            key = event.get("key")
            operation = str(event.get("operation", "")).upper()
            if not isinstance(key, str) or not key:
                continue
            if operation == "REMOVE":
                requirements.pop(key, None)
            elif operation in {"CREATE", "UPDATE", "CORRECT"}:
                content = event.get("new_content")
                if isinstance(content, str) and content.strip():
                    requirements[key] = {
                        "type": event.get("type", "REQUIREMENT"),
                        "content": content.strip(),
                        "version": int(event.get("version", 1)),
                    }
    return requirements


def render_context(requirements: dict[str, dict[str, Any]]) -> str:
    if not requirements:
        return "Requirement memory is active. No active requirements are stored."

    lines = [
        "Persistent requirement memory is authoritative user-provided context. "
        "Do not silently weaken, remove, or reinterpret these requirements:"
    ]
    for key in sorted(requirements):
        requirement = requirements[key]
        lines.append(
            f"- [{requirement['type']}] {key}: {requirement['content']} "
            f"(v{requirement['version']})"
        )
    return "\n".join(lines)


def emit_context(context: str, system_message: Optional[str] = None) -> None:
    output: dict[str, Any] = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    payload = json.load(sys.stdin)
    project_root = find_project_root(str(payload.get("cwd") or Path.cwd()))
    path = project_root / MEMORY_DIRECTORY / MEMORY_FILENAME
    emit_context(render_context(load_requirements(path)))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # Hooks should fail open while the MVP is experimental.
        print(f"requirement memory hook failed: {error}", file=sys.stderr)
        emit_context(
            "Requirement memory could not be loaded for this session.",
            system_message="Requirement memory hook failed; continuing without stored context.",
        )
