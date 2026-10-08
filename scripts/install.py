#!/usr/bin/env python3
"""Install the requirement-memory hooks into a target project."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def find_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise SystemExit("target must be inside a Git project")


def copy_new(source: Path, target: Path, force: bool) -> None:
    if target.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    project_root = find_root(args.project)
    hooks_source = skill_root / "assets" / "hooks"
    config_source = skill_root / "assets" / "config"

    for name in (
        "on_user_prompt.py",
        "on_session_start.py",
        "requirement_extractor.schema.json",
    ):
        copy_new(hooks_source / name, project_root / ".codex" / "hooks" / name, args.force)
    copy_new(config_source / "hooks.json", project_root / ".codex" / "hooks.json", args.force)
    copy_new(
        config_source / "memory_config.json",
        project_root / ".codex" / "memory_config.json",
        args.force,
    )
    copy_new(
        skill_root / "assets" / "tools" / "requirements_report.py",
        project_root / ".codex" / "memory" / "requirements_report.py",
        args.force,
    )

    memory_file = project_root / ".agent-memory" / "requirements.jsonl"
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    if not memory_file.exists():
        memory_file.write_text("", encoding="utf-8")

    json.loads((project_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    json.loads((project_root / ".codex" / "memory_config.json").read_text(encoding="utf-8"))
    print(f"Installed Codex requirement memory in {project_root}")
    print("Next: review/trust the hooks with /hooks, then restart or resume Codex.")


if __name__ == "__main__":
    main()
