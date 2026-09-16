# 行为评测与版本门禁

## 目的

行为评测用于检查 Skill 能否在小型论文—代码案例中发现预设问题、引用真实证据并控制误报。它不证明 Skill 能覆盖所有科研领域，也不替代真实项目审计。

## 案例结构

每个 `evals/cases/<case-id>/` 包含：

- `case.json`：案例身份、类别与简介。
- `request.md`：提供给被评测 Codex 的用户请求。
- `manuscript.md`：合成论文片段。
- `repository/`：合成的待审计代码仓库。
- `oracle.json`：作者侧预期，只用于评分，不应提前提供给被评测实例。

被评测实例只接收 Skill、`request.md`、`manuscript.md` 和 `repository/`。输出保存到 Skill 目录之外的隔离临时目录，命名为 `<case-id>.json`，然后再使用 oracle 评分；不要把运行产物提交到仓库。

## 评分不变量

- 检出 oracle 要求的 finding category。
- Claim 状态属于允许集合。
- Finding 严重性属于允许集合。
- Evidence 类型和路径覆盖 oracle 要求。
- Evidence 指向 fixture 中真实存在的文件。
- 不产生被禁止类别或高严重性误报。
- 不在缺少运行证据时使用 `VERIFIED`。
- 发布准备度落入 oracle 允许集合。

评分不比较标题、句子措辞、段落顺序或报告长度。

## 评分权重

| 维度 | 分值 |
|---|---:|
| 必需问题检出 | 35 |
| Claim 状态 | 20 |
| 证据类型与路径 | 20 |
| 严重性 | 10 |
| 结论边界 | 10 |
| 输出完整性 | 5 |

通过条件：总分至少 85、没有遗漏 blocking finding、没有虚构证据、没有超出案例阈值的高严重性误报。

## 运行顺序

1. 用 `validate_eval_fixtures.py` 检查案例结构。
2. 在隔离临时目录独立运行每个案例，不向被评测实例透露 oracle，也不让不同案例读取彼此输出。
3. 用 `validate_audit_output.py` 检查输出。
4. 用 `grade_audit_case.py` 评分。
5. 汇总失败类型，只有实际失败证明有必要时才修改 Skill。
6. 修改后重新运行所有案例，避免只修复单个样例。

## 发布门禁

版本发布必须满足：

- 所有 Python 单元测试通过。
- 所有 fixture 结构有效。
- Skill 快速校验通过。
- Clean control 无 `BLOCKER` 或 `MAJOR` 误报。
- 所有 blocking finding 被发现。
- 不存在虚构文件证据。
- Git 工作区差异检查通过。
