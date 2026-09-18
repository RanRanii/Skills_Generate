# 工作流 02：论文实验声明提取

## 目标

将稿件中的自然语言、公式、表格和图注转换为可与代码逐项核对的实验规格。

## 开始前读取

- `references/experiment-checklist.md`
- `references/evidence-and-verdict-rules.md`

## 提取范围

优先检查 Methods、Experimental Setup、Implementation Details、Results、Appendix、表格和图注。提取：

- 数据集名称、版本、样本选择、划分与预处理
- 输入输出定义、模型组件、关键公式和损失项
- 优化器、学习率、scheduler、batch size、epoch、早停和 checkpoint 选择
- 随机种子、独立重复次数、结果聚合与不确定性报告
- baseline、对比公平性和消融变量
- 指标定义、实现细节、方向和平均方式
- 表格、图片和主结论对应的数值
- 依赖、硬件或运行环境方面的明确声明

## 规范化规则

1. 每条可验证声明分配唯一编号 `CLM-###`。
2. 一条声明只表达一个可判定事实；复合句拆为多条。
3. 保留原文短句或准确释义，以及章节、页码、表格或图编号。
4. 区分：明确陈述、由公式直接推出、合理推断、未说明。
5. 对模糊表述记录待澄清问题，不自行补全实验参数。
6. 将表格或图中支撑核心结论的数字也视为声明。

## 建议字段

```text
claim_id
claim_type
criticality
statement
source_locator
expected_behavior
expected_value
tolerance_or_equivalence
notes
```

当需要生成 `audit-summary.json` 时，以上字段分别映射到 `claims[].id`、`claim_type`、`criticality`、`statement` 和 `source_locator`。不要再使用未定义的 `category`、`paper_location` 或自由文本 `importance` 替代 V1 字段。

## 输出

- 论文实验规格表
- 待澄清声明列表
- 需要在代码、配置和结果中寻找的证据列表
