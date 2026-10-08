---
name: codex-memory-helper
description: Install persistent requirement-memory hooks and answer natural-language queries about current requirements and recent changes.
---

# Codex Memory Helper

Use this skill when the user wants to add the requirement-memory system to a new project. It installs project-local hooks and storage; it does not modify application source code.

## Initialization

1. Confirm the target is the intended Git project root. Preserve existing `.codex/hooks.json`, `.codex/memory_config.json`, and hook scripts; do not overwrite them unless the user explicitly requests replacement.
2. Run the bundled installer from this skill directory:

   ```bash
   python3 scripts/install.py --project /absolute/path/to/project
   ```

   Use `--force` only after inspecting conflicts and receiving explicit permission to replace them.

3. Verify that the project contains:

   ```text
   .codex/hooks.json
   .codex/hooks/on_user_prompt.py
   .codex/hooks/on_session_start.py
   .codex/hooks/requirement_extractor.schema.json
   .codex/memory_config.json
   .codex/memory/requirements_report.py
   .agent-memory/requirements.jsonl
   ```

4. Tell the user to run `/hooks` in Codex, review the project-local hook definitions, and trust them. Hook trust is a Codex runtime action and must not be simulated by editing files.
5. Restart or resume the session, then send a harmless test prompt and verify Hook output. Do not add a requirement event for the test unless the user explicitly states a durable requirement.

## Configuration

The template defaults to the `codex` extractor, `gpt-5.6-luna`, and low reasoning effort. To use the direct API extractor, edit `.codex/memory_config.json`, set `extractor.mode` to `api`, and provide credentials through `api_key_file` with a Responses-compatible URL. Never put secrets in the skill or commit them.

`extraction_failure_policy` is `stop` by default: a failed extractor does not continue with stale memory and asks the user to retry. Use `continue` only when fail-open behavior is explicitly desired.

Define the project boundary in `extractor.scope_policy`:

```json
{
  "project_definition": "Only requirements intended to remain valid for this project and its future tasks.",
  "temporary_definition": "Instructions limited to the current task, turn, or experiment.",
  "ambiguous_action": "confirm"
}
```

The Extractor receives this policy on every call. It persists only `PROJECT`
events; `SESSION` and `IGNORE` are discarded. If scope is unclear and the
policy says `confirm`, it stores a single pending candidate and asks the user
to choose `1) 确认保存` or `2) 不确认/取消`. Only the first option persists the
candidate.

The system stores append-only events in `.agent-memory/requirements.jsonl`. Keep this file project-local for this workflow.

The extractor classifies candidate changes by scope: `PROJECT` is persisted,
while temporary `SESSION` instructions and `IGNORE` queries/facts are not
written to the durable requirement log. When the scope is ambiguous, preserve
the existing requirement state rather than promoting a temporary instruction.

## Inspecting memory

After initialization, use the installed report command to view the current effective requirement list and the latest changes:

```bash
python3 .codex/memory/requirements_report.py --project .
```

To show only a recent-change summary:

```bash
python3 .codex/memory/requirements_report.py --summary-only --recent 10
```

The report replays the append-only event log, applies removals and corrections, and never edits memory. Use it when the user asks for the latest requirement list, recent requirement summary, or a memory audit.

## Natural-language queries

Treat questions about requirement memory as read-only queries. Examples include:

- “当前有哪些目标和约束？”
- “最近需求改了什么？”
- “现在还允许修改 Agent 吗？”
- “关于 API 模型的要求是什么？”

For these queries:

1. Run `python3 .codex/memory/requirements_report.py --project .` (use `--summary-only` for a recent-change question).
2. Interpret the resulting requirement list and event summary using the user's natural-language intent.
3. Answer from the report, clearly distinguishing active requirements from historical changes.
4. Do not append the query to `requirements.jsonl`; a question changes memory only when the user also states an explicit requirement or decision.

This is intentionally handled by the current Codex reasoning over a deterministic report, so ordinary queries do not require an additional LLM/API request.

## Boundaries

- This skill installs and verifies the memory integration; it does not infer project requirements.
- Do not trust hooks silently, alter global Codex configuration, or expose API keys.
- If an existing project already has hooks, stop and report the conflict instead of overwriting it.
