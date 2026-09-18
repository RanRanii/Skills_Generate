# Claim–Code Matrix

## 状态说明

允许状态：`VERIFIED`、`CONSISTENT`、`MISMATCH`、`UNVERIFIABLE`、`AMBIGUOUS`、`NOT_APPLICABLE`。

## 覆盖概览

| 总声明数 | VERIFIED | CONSISTENT | MISMATCH | UNVERIFIABLE | AMBIGUOUS | NOT_APPLICABLE |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 声明映射

| Claim ID | Claim Type | Criticality | 论文声明 | Source Locator | 预期实现/值 | 代码与配置位置 | 实际生效实现/值 | Evidence IDs | 状态 | Finding IDs |
|---|---|---|---|---|---|---|---|---|---|---|
| CLM-001 | TRAINING | CORE |  | Section 3.1 |  |  |  | EVD-001 | UNVERIFIABLE |  |

## 未映射声明

| Claim ID | 搜索范围 | 缺失证据 | 继续核验所需材料 |
|---|---|---|---|
|  |  |  |  |

## 使用规则

- 一行只表达一个可独立判定的声明。
- `Claim Type` 使用 `DATA`、`METHOD`、`TRAINING`、`METRIC`、`RESULT`、`RELEASE`。
- `Criticality` 使用 `CORE`、`SUPPORTING`、`OPERATIONAL`；CORE 声明参与发布门禁。
- `Source Locator` 必须能回到论文章节、表格、公式或图注。
- Evidence IDs 与 Finding IDs 必须与结构化摘要中的双向引用一致。
- “代码与配置位置”使用仓库相对路径，并尽量补充函数、类或键名。
- 实际值必须考虑配置和命令行覆盖关系。
- 每个 `MISMATCH` 以及重要的 `UNVERIFIABLE`/`AMBIGUOUS` 应关联 `FND-###`；不要用自由文本置信度替代证据强度。
