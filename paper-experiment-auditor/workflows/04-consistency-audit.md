# 工作流 04：静态一致性审计

## 目标

在不修改实现的前提下，核验论文实验规格与代码、配置和已有产物是否一致。

## 开始前读取

- `references/evidence-and-verdict-rules.md`
- `references/experiment-checklist.md`
- `references/result-traceability.md`
- `references/severity-rules.md`

## 核验维度

逐项检查：

1. 数据来源、版本、划分、预处理与泄漏风险。
2. 模型结构、公式、张量维度、损失项及权重。
3. 优化器、学习率、scheduler、训练轮数、早停与 checkpoint 选择。
4. 评价指标的公式、输入、方向、类别平均和样本聚合方式。
5. baseline 是否共享公平的数据、预算、调参和评价流程。
6. 消融开关是否真实关闭或替换目标模块。
7. 随机性设置是否覆盖所用框架、数据加载器和多进程路径。
8. 重复次数、均值、标准差、最佳结果选择是否与论文一致。
9. 表格和图是否能追溯到仓库中的结果与生成流程。
10. GitHub 发布包是否包含必要入口、说明、配置和环境信息。

如果论文数值和运行结果已整理为 CSV、TSV 或 JSON 表，可读取 `references/script-usage.md` 并使用 `scripts/compare_result_tables.py`。在查看差异前确定行键、比较列和容差；比较报告只能支持数值一致性结论，不能独立证明实验协议正确。

## 输出规则

- 每条声明必须给出固定状态，不允许仅写“看起来正确”。
- 每个 `MISMATCH`、关键 `UNVERIFIABLE` 或高风险 `AMBIGUOUS` 建立 `FND-###`。
- 问题描述必须包含期望、实际、证据、影响和最小建议。
- 静态证据一致时最高判为 `CONSISTENT`。
- 使用 `templates/claim-code-matrix.md` 和 `templates/audit-report.md`。

## 完成条件

- 所有范围内声明都有状态。
- 报告给出声明覆盖率和各状态数量。
- 阻断 GitHub 发布复现的缺口被单独列出。
- 所有发布建议均能追溯到具体发现。
