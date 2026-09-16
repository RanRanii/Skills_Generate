# v0.3 确定性工具使用说明

六个工具均使用 Python 3，默认将 UTF-8 JSON 写到标准输出。只有需要保存审计附件时才使用 `--output`。脚本提供机械证据，不代替学术判断；输出必须与论文声明和调用路径结合后才能形成判定。

## 仓库结构归集

```powershell
python scripts/collect_repo_structure.py <repo-root> --format markdown --output audit/repository-inventory.md
```

用途：生成不读取文件内容的仓库文件清单、类型统计和敏感文件名提醒。默认排除 `.git`、虚拟环境、缓存、构建目录和 `node_modules`。可重复使用 `--exclude` 增加 glob 排除项。

注意：敏感文件提醒仅根据文件名匹配，不能替代密钥扫描或人工检查。

## 配置值归集

```powershell
python scripts/collect_config_values.py configs/train.json configs/model.toml --format csv --output audit/config-values.csv
```

用途：展开 JSON、TOML、INI/CFG 配置为稳定的键路径，便于与论文参数逐项对比。YAML 需要环境已安装 PyYAML；如果没有，应使用项目原有解析器确认实际生效配置，或将配置导出为 JSON/TOML。

脚本自动遮盖名称类似 password、secret、API key、access key、private key 和 token 的字段。不要把遮盖后的值当成配置缺失。

## 结果表对比

```powershell
python scripts/compare_result_tables.py paper-values.csv reproduced-values.csv `
  --keys model,dataset `
  --metrics accuracy,f1 `
  --abs-tol 0.001 `
  --rel-tol 0.0001 `
  --format markdown `
  --output audit/result-comparison.md
```

支持 CSV、TSV 和“对象数组”形式的 JSON。`--keys` 指定行身份字段，`--metrics` 指定比较列；省略 `--metrics` 时比较 expected 表中的全部非键列，actual 表缺少其中任何列都会作为输入错误报告。容差必须在查看比较结果前确定。

## 退出码

| 脚本 | 0 | 1 | 2 |
|---|---|---|---|
| `collect_repo_structure.py` | 成功 | 未使用 | 输入或执行错误 |
| `collect_config_values.py` | 成功 | 未使用 | 输入、格式或执行错误 |
| `compare_result_tables.py` | 表格匹配 | 存在差异 | 输入、格式或执行错误 |
| `validate_audit_output.py` | 有效且无警告 | 有效但有警告 | 输入或结构无效 |
| `validate_eval_fixtures.py` | 全部案例有效 | 未使用 | 案例或输入无效 |
| `grade_audit_case.py` | 评分通过 | 评分失败 | 输入或结构无效 |

结果对比返回 1 表示成功完成比较并发现差异，不应误报为脚本崩溃。

## 审计摘要校验

```powershell
python scripts/validate_audit_output.py audit-summary.json --format markdown
```

校验 schema 版本、ID 唯一性、跨引用、相对证据路径、`VERIFIED` 的运行证据门槛、覆盖率和发布准备度警告。字段定义见 `references/audit-output-schema.md`。

## 行为评测工具

```powershell
python scripts/validate_eval_fixtures.py evals/cases
python scripts/grade_audit_case.py evals/cases/02-config-override audit-summary.json --format markdown
```

先校验 fixture，再在被评测实例看不到 `oracle.json` 的条件下生成摘要，最后评分。案例结构、评分维度和门禁规则见 `references/behavioral-evaluation.md`。

## 校验工具

```powershell
python -m unittest discover -s tests -v
```

在 Skill 根目录运行。测试覆盖仓库归集、配置展开、结果比较、结构化输出约束、9 个 fixture 以及评分器的通过和阻断路径。
