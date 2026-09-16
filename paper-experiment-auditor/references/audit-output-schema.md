# 结构化审计输出规范（v0.3）

正式审计、自动评测或下游程序需要机器可读结果时，在 Markdown 报告之外生成 `audit-summary.json`。普通对话式核验不强制生成该文件。

## 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定为 `0.3` |
| `audit_id` | string | 当前审计的稳定标识 |
| `scope` | object | 稿件、仓库与提交标识 |
| `claims` | array | 论文声明及判定 |
| `evidence` | array | 可定位证据 |
| `findings` | array | 问题、歧义或不可核验项 |
| `coverage` | object | 声明数量与证据覆盖 |
| `release_readiness` | string | `READY`、`CONDITIONAL`、`BLOCKED` 或 `UNKNOWN` |

使用 [templates/audit-summary.json](../templates/audit-summary.json) 作为字段示例。

## Claim

```json
{
  "claim_id": "CLM-001",
  "statement": "论文中的可验证声明",
  "status": "MISMATCH",
  "evidence_ids": ["EVD-001"],
  "finding_ids": ["FND-001"]
}
```

状态只能使用 Skill 定义的六种判定。`VERIFIED` 必须链接至少一项 `RUNTIME` 证据；`MISMATCH` 必须链接 finding。

## Evidence

```json
{
  "evidence_id": "EVD-001",
  "type": "CONFIG",
  "path": "configs/train.json",
  "locator": "training.lr",
  "observation": "配置值为 0.01"
}
```

证据类型限定为 `PAPER`、`CODE`、`CONFIG`、`ARTIFACT`、`RUNTIME` 或 `DOC`。`path` 必须是安全的相对路径，不得包含本机绝对路径或 `..`。

## Finding

```json
{
  "finding_id": "FND-001",
  "category": "CONFIG_OVERRIDE",
  "severity": "MAJOR",
  "claim_ids": ["CLM-001"],
  "evidence_ids": ["EVD-001", "EVD-002"],
  "expected": "学习率为 0.001",
  "actual": "启动脚本覆盖为 0.01",
  "impact": "公开代码执行的训练协议与论文不一致"
}
```

`category` 使用稳定的 `UPPER_SNAKE_CASE` 语义类别。发现符合下列核心类别时必须使用对应规范名称，不要添加 `_MISMATCH`、`_ERROR` 等近义后缀：

| 规范类别 | 使用条件 |
|---|---|
| `CONFIG_OVERRIDE` | 默认配置被入口、CLI 或代码覆盖，导致实际值与论文不同 |
| `DATA_LEAKAGE` | 训练阶段使用测试信息或以其他方式污染评估 |
| `METRIC_MISMATCH` | 指标公式、输入、方向、平均方式或聚合与论文不同 |
| `CHECKPOINT_SELECTION` | checkpoint 的保存、选择或报告规则与论文不同 |
| `INEFFECTIVE_ABLATION` | 消融开关未真实改变目标模块或执行路径 |
| `INCOMPLETE_SEEDING` | 随机种子设置时机或覆盖范围不足 |
| `RESULT_PROVENANCE_BREAK` | 报告值无法追溯到运行记录、原始结果或生成链路 |
| `MANUSCRIPT_AMBIGUITY` | 稿件本身存在多个合理解释，无法确定唯一核验目标 |

只有找不到适用的核心类别时才创建新的精确类别，并在 Markdown 报告中解释其边界。严重性沿用 `BLOCKER`、`MAJOR`、`MODERATE`、`MINOR`、`INFO`。

## 一致性要求

- 所有 ID 唯一，所有引用必须存在。
- `coverage.total_claims` 等于 claims 数量。
- `coverage.mapped_claims` 等于至少链接一项证据的 claim 数量。
- Markdown 报告与 JSON 中的状态、严重性、数量和 ID 必须一致。
- 不得写入凭据、个人数据、本机绝对路径或无法验证的运行事实。

## 校验

```powershell
python scripts/validate_audit_output.py audit-summary.json --format markdown
```

退出码：`0` 表示有效且无警告；`1` 表示结构有效但有审计警告；`2` 表示输入或结构无效。
