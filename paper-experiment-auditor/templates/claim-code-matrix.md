# Claim–Code Matrix

## 状态说明

允许状态：`VERIFIED`、`CONSISTENT`、`MISMATCH`、`UNVERIFIABLE`、`AMBIGUOUS`、`NOT_APPLICABLE`。

## 覆盖概览

| 总声明数 | VERIFIED | CONSISTENT | MISMATCH | UNVERIFIABLE | AMBIGUOUS | NOT_APPLICABLE |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 声明映射

| Claim ID | 类别 | 论文声明 | 论文位置 | 预期实现/值 | 代码与配置位置 | 实际生效实现/值 | 运行/产物证据 | 状态 | 置信度 | Finding ID |
|---|---|---|---|---|---|---|---|---|---|---|
| CLM-001 | 示例：训练配置 |  |  |  |  |  |  | UNVERIFIABLE | 低 |  |

## 未映射声明

| Claim ID | 搜索范围 | 缺失证据 | 继续核验所需材料 |
|---|---|---|---|
|  |  |  |  |

## 使用规则

- 一行只表达一个可独立判定的声明。
- “代码与配置位置”使用仓库相对路径，并尽量补充函数、类或键名。
- 实际值必须考虑配置和命令行覆盖关系。
- 每个 `MISMATCH` 以及重要的 `UNVERIFIABLE`/`AMBIGUOUS` 应关联 `FND-###`。

