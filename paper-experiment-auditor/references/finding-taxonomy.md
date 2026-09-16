# Finding 分类规范

本文件是 finding `category` 的单一来源。找不到适用的规范类别时才创建新的精确类别，并在 Markdown 报告中解释其边界。不要为同一问题堆叠 `_MISMATCH`、`_ERROR` 等近义后缀。

## 规范类别

| 类别 | 适用边界 | 近义名称（应归并） | 推荐严重性 | 可阻断发布 |
|---|---|---|---|---|
| `CONFIG_OVERRIDE` | 默认配置被入口、CLI 或代码覆盖，导致实际值与论文不同 | config discrepancy, effective config mismatch | MAJOR–MODERATE | 是（影响 CORE 时） |
| `DATA_LEAKAGE` | 训练阶段使用测试信息或以其他方式污染评估 | test contamination, train-test leak | BLOCKER–MAJOR | 是 |
| `SPLIT_MISMATCH` | 训练/验证/测试划分方式、比例或文件与论文不同 | split inconsistency, data split error | MAJOR | 是 |
| `PREPROCESSING_MISMATCH` | 归一化、清洗、增强或特征处理与论文不同 | data processing mismatch, normalization mismatch | MAJOR–MODERATE | 是（影响 CORE 时） |
| `METHOD_MISMATCH` | 模型结构、损失、优化或算法实现与论文不同 | implementation mismatch, algorithm mismatch | MAJOR | 是（影响 CORE 时） |
| `METRIC_MISMATCH` | 指标公式、输入、方向、平均方式或聚合与论文不同 | evaluation metric error | MAJOR | 是 |
| `CHECKPOINT_SELECTION` | checkpoint 的保存、选择或报告规则与论文不同 | model selection mismatch, best checkpoint error | MAJOR–MODERATE | 是（影响 CORE 时） |
| `INEFFECTIVE_ABLATION` | 消融开关未真实改变目标模块或执行路径 | ablation no-op, ablation not wired | MAJOR–MODERATE | 是（影响 CORE 时） |
| `INCOMPLETE_SEEDING` | 随机种子设置时机或覆盖范围不足 | seeding gap, nondeterminism | MODERATE–MINOR | 否 |
| `RESULT_MISMATCH` | 报告数值与代码输出或产物冲突 | result discrepancy, table mismatch | BLOCKER–MAJOR | 是 |
| `RESULT_PROVENANCE_BREAK` | 报告值无法追溯到运行记录、原始结果或生成链路 | missing provenance, untraceable result | BLOCKER–MAJOR | 是 |
| `MISSING_RELEASE_ASSET` | 公开仓库缺少安装、依赖、入口或必要说明文件 | missing README, missing entry point | BLOCKER–MAJOR | 是 |
| `PRIVATE_DEPENDENCY` | 依赖未公开的私有代码、数据或包，公开后无法运行 | internal dependency, closed dependency | BLOCKER | 是 |
| `SENSITIVE_CONTENT_RISK` | 仓库可能包含凭据、个人数据或受限材料 | credential leak, secret exposure | BLOCKER | 是 |
| `MANUSCRIPT_AMBIGUITY` | 稿件本身存在多个合理解释，无法确定唯一核验目标 | paper ambiguity, underspecified claim | MODERATE–MINOR | 否 |

## 归并示例

- 模板旧示例 `IMPLEMENTATION_MISMATCH` → 归并为 `METHOD_MISMATCH` 或 `RESULT_MISMATCH`，按冲突对象选择：实现与论文算法不同用 `METHOD_MISMATCH`，报告数值与产物冲突用 `RESULT_MISMATCH`。

## 何时判 `UNVERIFIABLE` 而不是 `MISMATCH`

`MISMATCH` 要求存在可定位的正向冲突（论文说 X，代码/产物说 Y）。缺少材料导致无法判断时应判 `UNVERIFIABLE`：

- 找不到任何 checkpoint 选择代码 → `CHECKPOINT_SELECTION` 配 `UNVERIFIABLE`；找到选择逻辑但与论文规则相反 → `MISMATCH`。
- 结果无法追溯到任何运行记录 → `RESULT_PROVENANCE_BREAK` 配 `UNVERIFIABLE`；结果追溯到与论文不同的运行/配置 → `MISMATCH`。
- 划分方式在代码中完全缺失 → `SPLIT_MISMATCH` 配 `UNVERIFIABLE`；划分比例与论文不同 → `MISMATCH`。

`MANUSCRIPT_AMBIGUITY` 本身应配合 claim 状态 `AMBIGUOUS`，一般不判 `MISMATCH`。

## 严重性理由

严重性衡量问题对论文结论、实验公平性、公开复现和读者信任的影响，不等同于修复工作量。每项 finding 必须说明严重性理由，不要机械按关键词分级。
