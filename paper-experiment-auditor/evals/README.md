# Behavioral evaluation fixtures

这些案例用于测试 `paper-experiment-auditor` 的行为边界。全部论文片段、代码和结果均为合成材料，不代表真实研究结论。

运行 fixture 校验：

```powershell
python scripts/validate_eval_fixtures.py evals/cases
```

评测时只向被评测实例提供 Skill、案例中的 `request.md`、`manuscript.md` 和 `repository/`。不要提供 `oracle.json`，也不要让案例读取彼此输出。把生成的 `<case-id>.json` 放到 Skill 目录之外的隔离临时目录，评分后清理，不提交到仓库。得到输出后运行：

```powershell
python scripts/validate_audit_output.py <audit-summary.json>
python scripts/grade_audit_case.py <case-directory> <audit-summary.json>
```

案例格式与发布门禁见 [`../references/behavioral-evaluation.md`](../references/behavioral-evaluation.md)。
