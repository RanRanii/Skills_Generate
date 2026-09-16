# 结构化审计输出规范（v1.0）

正式审计、自动评测或下游程序需要机器可读结果时，在 Markdown 报告之外生成 `audit-summary.json`。普通对话式核验不强制生成该文件。

本文件定义稳定契约 `1.0`。旧版 `0.3` 保留一个版本周期的向后兼容：校验器仍接受 `0.3` 输出，但返回兼容性警告。

使用 [templates/audit-summary.json](../templates/audit-summary.json) 作为 `1.0` 字段示例。

## 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定为 `1.0` |
| `audit_id` | string | 当前审计的稳定标识 |
| `audit_profile` | string | 审计模式，见下方枚举 |
| `subject` | object | 稿件、仓库与提交标识 |
| `claims` | array | 论文声明及判定 |
| `evidence` | array | 可定位证据 |
| `findings` | array | 问题、歧义或不可核验项 |
| `coverage` | object | 声明数量与证据覆盖 |
| `release_decision` | object | 结构化发布决定 |
| `limitations` | array | 本次审计的适用边界与限制（字符串数组） |

`audit_profile` 取值：`TRIAGE`、`STATIC_AUDIT`、`REPRODUCTION`、`REMEDIATION`、`RELEASE_REVIEW`。

## Claim

```json
{
  "claim_id": "CLM-001",
  "claim_type": "METRIC",
  "criticality": "CORE",
  "source_locator": "Table 2, row 1",
  "statement": "论文中的可验证声明",
  "status": "MISMATCH",
  "evidence_ids": ["EVD-001"],
  "finding_ids": ["FND-001"]
}
```

- `claim_type`：`DATA`、`METHOD`、`TRAINING`、`METRIC`、`RESULT`、`RELEASE`。
- `criticality`：`CORE`、`SUPPORTING`、`OPERATIONAL`。`CORE` 直接影响论文核心结论。
- `source_locator`：论文章节、表格、公式或图注，用于回源定位。

`status` 只能使用六种判定：`VERIFIED`、`CONSISTENT`、`MISMATCH`、`UNVERIFIABLE`、`AMBIGUOUS`、`NOT_APPLICABLE`。

`VERIFIED` 必须链接至少一项 `RUNTIME` 证据；`MISMATCH` 必须链接 finding；`CONSISTENT`/`VERIFIED`/`MISMATCH` 必须链接至少一项证据。

## Evidence

```json
{
  "evidence_id": "EVD-001",
  "type": "CONFIG",
  "strength": "DIRECT",
  "generated_by": "HUMAN",
  "path": "configs/train.json",
  "locator": "training.lr",
  "observation": "配置值为 0.01",
  "digest": "sha256:..."
}
```

- `type`：`PAPER`、`CODE`、`CONFIG`、`ARTIFACT`、`RUNTIME`、`DOC`。
- `strength`：`DIRECT`、`INDIRECT`、`SUPPORTING`。
- `generated_by`：`HUMAN`（人工检查）、`SCRIPT`（确定性脚本）、`COMMAND`（运行命令）。
- `digest`：可选，关键产物的 SHA-256，格式为 `sha256:<64 位十六进制>`。
- `path`：非 `RUNTIME` 证据必填；必须是安全的相对路径，不得包含本机绝对路径或 `..`。

`RUNTIME` 证据必须额外包含：

```json
{
  "type": "RUNTIME",
  "command": "python src/train.py --config configs/train.json",
  "commit": "abc1234",
  "exit_status": 0,
  "artifact": "results/summary.csv"
}
```

`command`、`commit`、`exit_status`、`artifact` 均为必填，`artifact` 必须是安全的相对路径。

## Finding

```json
{
  "finding_id": "FND-001",
  "category": "CONFIG_OVERRIDE",
  "severity": "MAJOR",
  "disposition": "OPEN",
  "claim_ids": ["CLM-001"],
  "evidence_ids": ["EVD-001", "EVD-002"],
  "expected": "学习率为 0.001",
  "actual": "启动脚本覆盖为 0.01",
  "impact": "公开代码执行的训练协议与论文不一致",
  "recommendation": "统一默认配置与启动脚本，或修正论文描述",
  "resolution_evidence_ids": []
}
```

- `category`：使用 [finding-taxonomy.md](finding-taxonomy.md) 中的规范类别，`UPPER_SNAKE_CASE`。
- `severity`：`BLOCKER`、`MAJOR`、`MODERATE`、`MINOR`、`INFO`。
- `disposition`：`OPEN`、`FIXED`、`ACCEPTED_RISK`、`WAIVED`。默认 `OPEN`。
- `resolution_evidence_ids`：可选，`FIXED` 时引用证明已修复的证据。

## Coverage

```json
{
  "total_claims": 1,
  "mapped_claims": 1
}
```

`total_claims` 等于 claims 数量；`mapped_claims` 等于至少链接一项证据的 claim 数量。

## Release decision

```json
{
  "status": "READY",
  "blocking_finding_ids": [],
  "conditional_finding_ids": [],
  "rationale": "所有核心声明已映射，无未解决阻断项"
}
```

`status`：`READY`、`CONDITIONAL`、`BLOCKED`、`UNKNOWN`。

`READY` 必须同时满足：

- 没有未解决（`disposition` 为 `OPEN`）的 `BLOCKER` 或 `MAJOR` finding。
- 所有 `CORE` claim 均已映射到至少一项证据。
- 不存在 `CORE` 且 `status` 为 `MISMATCH` 或 `UNVERIFIABLE` 的 claim。
- 没有虚构证据路径（由 `--repo-root` 校验）。
- `VERIFIED` 声明具有合格的运行证据。

## 一致性要求

- 所有 ID 唯一，所有引用必须存在且双向成立（每个 finding 至少被一个 claim 引用）。
- Markdown 报告与 JSON 中的状态、严重性、数量和 ID 必须一致。
- 不得写入凭据、个人数据、本机绝对路径或无法验证的运行事实。

## 校验

```powershell
python scripts/validate_audit_output.py audit-summary.json --format markdown
python scripts/validate_audit_output.py audit-summary.json --repo-root <repo-root>
```

退出码：`0` 表示有效且无警告；`1` 表示结构有效但有审计警告（含 `0.3` 兼容性警告）；`2` 表示输入或结构无效。
