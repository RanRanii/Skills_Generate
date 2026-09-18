# 工作流 08：论文代码仓库发布审查

## 触发条件

用户准备将论文附带代码、配置、结果生成脚本或复现说明公开到 GitHub，或明确要求检查公开发布包时使用。本工作流审查的是目标论文仓库，不是本 Skill 自身。

## 开始前读取

- `references/release-manifest-schema.md`
- `references/audit-output-schema.md`
- `references/reproducibility-rules.md`
- `references/severity-rules.md`

## 审查顺序

1. 确认公开仓库、分支、提交和论文版本，生成发布范围卡。
2. 读取 `release-manifest.json`，检查文档、安装、数据准备、训练、评估、结果生成和默认配置入口。
3. 使用 `scripts/check_release_package.py` 做确定性检查；该脚本不执行目标仓库代码。
4. 扫描仓库中的敏感文件名、本机绝对路径、私有依赖和仓库外符号链接。
5. 核对 checkpoint 是仓库内置还是外部获取，不能同时声明两种方式。
6. 核对数据限制、再分发说明和许可证状态；个人项目可明确使用 `UNLICENSED`，不得虚构 MIT/Apache 授权。
7. 将发布包问题关联到 `RELEASE` 类型 claim 和规范 finding category。
8. 只有在用户授权后，才执行低成本 smoke test 或复现命令；长时训练、下载和 GPU 任务继续遵循成本授权门槛。
9. 生成 Markdown 报告与 `audit-summary.json`，运行结构校验并确认发布决定与 finding 状态一致。

## 结论边界

- 检查器 PASS 只表示清单声明的结构、路径和文件名启发式检查通过。
- PASS 不证明目标仓库已完成完整训练，也不等同于安全扫描或科学结论证明。
- 缺少命令、入口、数据获取说明、checkpoint 说明或可追溯结果时，发布状态应为 `CONDITIONAL`、`BLOCKED` 或 `UNKNOWN`。
