---
name: paper-experiment-auditor
description: 以作者提供的论文稿件为规范来源，对准备随论文公开到 GitHub 的实验代码、配置、数据流程、评价指标和结果产物进行证据驱动的一致性与可复现性核验。适用于论文代码发布前审计、论文声明与实现映射、结果溯源和复现准备；不用于普通代码风格审查，也不在审计阶段自动修改稿件、代码或结果。
metadata:
  short-description: "核验论文实验声明与公开代码是否一致"
---

# 论文实验代码一致性核验

把论文稿件视为规范性输入，把准备公开的代码仓库视为待核验实现。目标是形成可追溯的“论文声明—代码—配置—运行产物—判定”证据链，帮助作者在上传 GitHub 前发现实现缺失、配置冲突、结果不可追溯和复现障碍。

## 核心约束

- 默认执行只读审计。除非用户明确要求修复，否则不得修改论文、源码、配置、实验日志或结果文件。
- 不把“未发现问题”表述为“已证明正确”。静态阅读只能产生 `CONSISTENT`，实际执行证据满足要求后才能使用 `VERIFIED`。
- 每项结论必须指向具体证据；缺少证据时使用 `UNVERIFIABLE` 或 `AMBIGUOUS`，不得补写事实。
- 区分论文计划、代码默认值、命令行覆盖、实际运行配置和最终报告值。优先判断实际生效值。
- 审计发布完整性时应检查 GitHub 用户将获得什么，而不是依赖作者本机未纳入仓库的隐含状态。
- 长时训练、大规模下载、GPU 运行、外部服务调用或其他显著成本操作，必须先完成静态预检并取得用户明确授权。

## 输入与工作模式

先根据现有材料选择最小充分工作流：

- 只有稿件或稿件描述：读取 [workflows/01-intake-and-scope.md](workflows/01-intake-and-scope.md) 与 [workflows/02-manuscript-extraction.md](workflows/02-manuscript-extraction.md)，产出实验规格和缺失材料清单。
- 稿件与代码仓库齐全：完成稿件提取后，读取 [workflows/03-code-config-mapping.md](workflows/03-code-config-mapping.md) 和 [workflows/04-consistency-audit.md](workflows/04-consistency-audit.md)。
- 用户要求运行、复现或验证结果：完成静态审计后，再读取 [workflows/05-reproduction-validation.md](workflows/05-reproduction-validation.md)。
- 用户明确要求依据报告修复：读取 [workflows/06-remediation.md](workflows/06-remediation.md)，修复后重新核验受影响声明。
- 用户要求评估或发布本 Skill 新版本：读取 [workflows/07-evaluation-and-release-gate.md](workflows/07-evaluation-and-release-gate.md)。评测 oracle 只能在核验输出完成后用于评分。

不要默认读取所有参考文件。工作流会说明当前阶段需要读取哪些规则。

## 基本流程

1. 明确论文、代码、配置、数据、结果和公开范围，生成审计范围卡。
2. 从正文、方法、实验、附录、表格和图注提取可验证声明，编号为 `CLM-###`。
3. 将每条声明映射到源码、配置、脚本、环境文件和产物；保留文件路径、符号名、行号或键路径。
4. 核验数据、模型、训练、指标、基线、消融、随机性、结果汇总和发布完整性。
5. 将每项判定写入 Claim–Code Matrix，发现编号为 `FND-###`。
6. 如获授权，执行最小成本的动态验证，并记录命令、环境、输入、输出和退出状态。
7. 使用固定模板生成报告，区分事实、推断、限制和建议；需要自动评测或下游处理时，同时生成结构化摘要。

## 确定性工具

当任务需要稳定、重复的机械归集或比较时，读取 [references/script-usage.md](references/script-usage.md)，并优先复用：

- `scripts/collect_repo_structure.py`：生成仓库清单、类型统计和敏感文件名提醒。
- `scripts/collect_config_values.py`：展开 JSON、TOML、INI/CFG 配置；安装 PyYAML 时也支持 YAML。
- `scripts/compare_result_tables.py`：按行键和预先声明的数值容差比较 CSV、TSV 或 JSON 结果表。
- `scripts/validate_audit_output.py`：校验结构化审计摘要的 ID、引用、证据门槛与覆盖率。
- `scripts/validate_eval_fixtures.py`：校验行为评测案例及 oracle 的完整性和安全边界。
- `scripts/grade_audit_case.py`：在隔离评测完成后按行为不变量评分，不比较固定措辞。

脚本输出属于辅助证据。仓库清单不替代代码调用链分析；配置归集不证明某个值实际生效；表格相等不证明训练过程与论文一致。

## 判定词表

- `VERIFIED`：有足够的实际执行或可重复产物证据，且与论文声明一致。
- `CONSISTENT`：静态证据一致，但未完成足以支持 `VERIFIED` 的动态验证。
- `MISMATCH`：论文声明与实际实现或结果存在明确冲突。
- `UNVERIFIABLE`：缺少代码、配置、数据、日志、产物或环境，当前无法核验。
- `AMBIGUOUS`：稿件或实现存在多种合理解释，无法唯一判断。
- `NOT_APPLICABLE`：该检查项不适用于当前研究。

判定、证据门槛和冲突优先级见 [references/evidence-and-verdict-rules.md](references/evidence-and-verdict-rules.md)。

## 交付物

根据任务范围生成以下一个或多个文件：

- 审计范围卡：采用 [templates/audit-intake.md](templates/audit-intake.md)。
- Claim–Code Matrix：采用 [templates/claim-code-matrix.md](templates/claim-code-matrix.md)。
- 复现记录：采用 [templates/reproduction-log.md](templates/reproduction-log.md)。
- 总体审计报告：采用 [templates/audit-report.md](templates/audit-report.md)。
- 机器可读摘要：需要评测、自动化或下游消费时，读取 [references/audit-output-schema.md](references/audit-output-schema.md)，并采用 [templates/audit-summary.json](templates/audit-summary.json)。

报告必须说明核验覆盖率、阻断性缺口和“可以随论文公开”结论的适用边界。Markdown 与 JSON 中的 ID、状态、严重性和数量必须一致。若没有足够证据，不得给出无条件发布通过结论。
