# Paper Experiment Auditor

一个面向 Codex 的中文 Skill，用于在论文代码上传 GitHub 前，核验论文实验声明与代码、配置、运行产物和结果之间的一致性与可复现性。

## 设计目标

本 Skill 解决的问题不是“代码写得是否漂亮”，而是：

> 论文声称完成了某项实验，准备公开的仓库是否真实、完整、可追溯地实现了它？

核心证据链为：

```text
论文稿件 → 实验规格 → 代码与配置 → 运行产物 → 证据 → 判定
```

## 当前版本

`v0.3` 提供：

- 论文实验声明提取流程
- 声明与代码、配置映射流程
- 静态一致性审计与 GitHub 发布完整性检查
- 受控复现流程
- 修复与复核流程
- Claim–Code Matrix、复现记录和审计报告模板
- 统一证据状态与问题严重性规则
- 仓库结构、文件类型与发布风险文件名的确定性归集
- JSON、TOML、INI/CFG 及可选 YAML 配置值展开与敏感字段遮盖
- CSV、TSV、JSON 结果表的键控比较、绝对/相对容差和机器可读报告
- JSON 结构化审计摘要、证据 ID 与跨引用校验
- 9 个合成行为评测案例，覆盖 clean control、配置覆盖、数据泄漏、指标不一致、checkpoint 选择、无效消融、随机种子、结果溯源和稿件歧义
- fixture 校验器、行为评分器与版本发布门禁
- 面向六个工具的 19 项标准库单元测试

本版本继续以 Markdown 工作流承载学术判断，仅把稳定、重复的机械操作放入 `scripts/`。脚本输出属于辅助证据，不能替代论文解释、代码调用链分析或完整复现。

## 使用方式

将整个 `paper-experiment-auditor` 目录放入 Codex 可发现的 skills 目录，然后显式调用：

```text
使用 $paper-experiment-auditor 核验我的论文与准备公开的实验代码。
```

建议同时提供论文稿件、待发布仓库、实际实验配置、结果目录和必要的数据说明。材料不足不会阻止静态审计，但相关项目会被标记为 `UNVERIFIABLE` 或 `AMBIGUOUS`。

## v0.3 工具

在 Skill 根目录运行：

```powershell
python scripts/collect_repo_structure.py <repo-root> --format markdown
python scripts/collect_config_values.py <config-files...> --format csv
python scripts/compare_result_tables.py <expected.csv> <actual.csv> --keys model,dataset --metrics accuracy --abs-tol 0.001
python scripts/validate_audit_output.py <audit-summary.json> --format markdown
python scripts/validate_eval_fixtures.py evals/cases
python scripts/grade_audit_case.py <case-directory> <audit-summary.json>
```

完整参数、输出格式和退出码见 `references/script-usage.md`。六个工具默认不需要第三方依赖；读取 YAML 时需要 PyYAML。推荐使用 Python 3.11 或更高版本，以原生支持 TOML。

运行测试：

```powershell
python -m unittest discover -s tests -v
```

Skill 版本发布前还应按 `workflows/07-evaluation-and-release-gate.md` 隔离运行行为案例；被评测实例不能读取 `oracle.json`。

## 默认边界

- 默认只读审计。
- 不自动修改论文、代码、配置或实验结果。
- 不在未获授权时执行长时训练、大型下载或高成本计算。
- `CONSISTENT` 表示静态一致；只有充分的运行证据才能标记为 `VERIFIED`。
