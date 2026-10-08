# Codex Memory Helper

用于给 Codex 项目安装持久化需求记忆的 Skill。它将用户明确表达、且在当前项目后续任务中持续有效的需求记录为项目本地追加日志，并在会话启动和每次用户提交消息时注入当前有效需求。

## 目标与边界

系统帮助 Codex 在多轮对话中保持项目级需求一致性，减少需求丢失、需求更新不同步和未经授权的语义漂移。

只保存用户明确表达、并应在项目后续任务中持续有效的需求。任务进度、工具结果、代码状态和测试结果属于运行时上下文，不会重复写入需求记忆。

需求事件只保存于项目本地的 `.agent-memory/requirements.jsonl`；不使用外部数据库或向量数据库。

## 项目结构

初始化后，目标项目会拥有以下核心文件；`docs/codex-memory-system.md` 是建议由项目维护的说明文档位置，安装器不会自动创建它：

```text
project/
├── .codex/
│   ├── hooks.json
│   ├── memory_config.json
│   ├── hooks/
│   │   ├── on_user_prompt.py
│   │   ├── on_session_start.py
│   │   └── requirement_extractor.schema.json
│   └── memory/
│       └── requirements_report.py
├── .agent-memory/
│   └── requirements.jsonl
└── docs/
    └── codex-memory-system.md
```

`requirements.jsonl` 是只追加的事件日志。当前有效需求通过按事件顺序重放得到，而不是维护另一张可变的数据库表。

## 安装

将本仓库安装为 Codex Skill 后，在目标 Git 项目中调用：

```text
Use $codex-memory-helper to initialize requirement memory in this project.
```

Skill 会先确认目标是预期的 Git 项目根目录。若 `.codex/hooks.json`、`.codex/memory_config.json` 或 Hook 脚本已存在，安装器默认拒绝覆盖；只有检查冲突并获得明确许可后，才可使用 `--force`。

安装完成后：

1. 在 Codex 中运行 `/hooks`，审核并信任项目本地 Hook。
2. 重启或恢复会话。
3. 发送一条不包含持久需求的测试消息，确认 Hook 输出正常。

Hook 信任是 Codex Runtime 的安全操作，不能通过修改文件自动代替。

## Hook 职责

### `on_session_start.py`

在 `SessionStart` 事件触发时运行，包括启动、恢复、清空和压缩后的会话。它定位项目根目录，读取并重放 `requirements.jsonl`，然后通过 `additionalContext` 注入当前有效需求。

该 Hook 只负责加载：不调用 LLM，也不修改记忆文件。

### `on_user_prompt.py`

在每次 `UserPromptSubmit` 事件触发时运行。它读取用户消息和当前需求，调用 Extractor 判断是否发生项目级需求变化，校验并规范化事件，必要时追加日志，重建快照并注入当前需求。

未发生项目级需求变化时，日志不会追加新事件，但当前有效需求仍会被注入。Hook 通过 `systemMessage` 区分结果：有事件时显示操作和 key；无事件时显示“当前 Prompt 无需更新需求”。Extractor 失败时会显示失败，并按失败策略处理。

## Extractor

Extractor 只将自然语言转换为结构化候选结果，Python Hook 负责确定性地校验和写入文件。

支持三种模式：

| 模式 | 行为 |
| --- | --- |
| `codex` | 调用一次 `codex exec`；模板默认模型为 `gpt-5.6-luna`，推理强度为 `low`。 |
| `api` | 调用一次 Responses-compatible API。 |
| `mock` | 使用配置中的固定事件，不调用 LLM。 |

每条用户消息通常只产生一次 Extractor 调用。普通查询不会额外调用 LLM；需求查询由 Codex 读取报告后直接回答。

Extractor 输出符合 `requirement_extractor.schema.json`，核心结构如下：

```json
{
  "changes_requirement_state": true,
  "scope": "PROJECT",
  "needs_confirmation": false,
  "events": []
}
```

支持的事件操作：

| 操作 | 含义 |
| --- | --- |
| `CREATE` | 新增需求。 |
| `UPDATE` | 更新已有需求。 |
| `CORRECT` | 纠正之前记录。 |
| `REMOVE` | 移除需求。 |

## 需求范围与待确认流程

| 范围 | 含义 | 是否写入日志 |
| --- | --- | --- |
| `PROJECT` | 当前项目及后续任务持续有效。 | 是 |
| `SESSION` | 当前会话、任务或一次性实验有效。 | 否 |
| `IGNORE` | 查询、事实、解释或一次性动作。 | 否 |

例如，“这次先临时使用 SQLite 测一下”属于 `SESSION`，不会持久化；“这个项目以后不能使用外部数据库”属于 `PROJECT`，会产生持久化约束。

项目可通过 `.codex/memory_config.json` 定义范围策略：

```json
{
  "extractor": {
    "scope_policy": {
      "project_definition": "Only requirements explicitly intended to remain valid for this project and its future tasks.",
      "temporary_definition": "Instructions limited to the current task, turn, experiment, or one-off action.",
      "ambiguous_action": "confirm"
    }
  }
}
```

范围不明确时，Extractor 返回 `needs_confirmation: true`，不直接持久化事件。候选会保存到 `.agent-memory/pending_confirmation.json`，当前请求暂停，并提示 `1) 确认保存` 或 `2) 不确认/取消`。确认会写入候选事件，取消会丢弃候选；在待确认期间的其他输入会继续提示先完成选择。

## 事件日志与快照

每个持久化事件都追加到 `.agent-memory/requirements.jsonl`。示例：

```json
{"session_id":"s1","operation":"CREATE","type":"CONSTRAINT","key":"storage_backend","old_content":null,"new_content":"不能使用外部数据库。","version":1,"created_at":"2026-10-09T10:00:00+08:00"}
```

事件重放规则：

- `CREATE`、`UPDATE`、`CORRECT` 写入或替换 key 对应的当前值。
- `REMOVE` 追加移除事件，并从当前有效需求中逻辑移除该 key，不删除历史日志。

因此，需求演化历史可追溯，且能随时重新构建当前快照。

## 上下文注入

Hook 使用 Codex Hook 标准输出返回额外上下文：

```json
{
  "continue": true,
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Persistent requirement memory is authoritative user-provided context..."
  }
}
```

Codex 会将 `additionalContext` 作为额外开发者上下文提供给模型，不修改用户原始消息。相关 Hook 的 `additionalContextLimit` 设为约 2500 token；超出限制时，Codex 会保存完整输出并向模型提供较短预览。

## 失败策略

模板默认配置为：

```json
{
  "extractor": {
    "extraction_failure_policy": "stop"
  }
}
```

在 `stop` 模式下，Extractor 调用失败时不会追加事件，Hook 返回 `continue: false` 并要求用户重新提交。将策略显式改为 `continue` 后，系统采用 fail-open 行为：继续使用已有需求，但不保存本次候选需求。

API 模式需要可访问的 Responses-compatible endpoint 和有效凭证。通过 `api_key_file` 提供密钥，切勿将密钥写入本仓库或提交到版本控制。

## 查看与查询需求

安装器会复制报告脚本。查看当前有效需求和最近变更：

```bash
python3 .codex/memory/requirements_report.py --project .
```

仅查看最近变更：

```bash
python3 .codex/memory/requirements_report.py --summary-only --recent 10
```

也可直接询问 Codex，例如“当前有哪些目标和约束？”、“最近需求改了什么？”或“现在还允许修改 Agent 吗？”。这些查询是只读操作，不会写入 `requirements.jsonl`。

## 兼容性与限制

- 当前仅保存项目级需求，不保存临时 Session 状态。
- `PROJECT` 范围由 `scope_policy` 定义；歧义情况不会自动猜测。
- 待确认流程使用单一 `pending_confirmation.json`，不支持多个并行候选。
- 事件的语义判断依赖 Extractor；Schema、来源文本、版本和写入校验由确定性 Python 代码负责。
- 当前实现以 Python Hook 为主。未来迁移到 Go 时，必须保持 Hook 输入输出协议和文件格式兼容。

## License

在公开发布前添加适合目标分发方式的许可证。
