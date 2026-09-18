# 发布清单规范（release-manifest.json）

`release-manifest.json` 描述**目标论文仓库**的公开接口，供 `scripts/check_release_package.py` 做确定性检查，也为 `RELEASE_REVIEW` 工作流提供结构化输入。它描述的是被审计仓库，不是本 Skill 自身的发布清单。

## 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定为 `1.0` |
| `repository` | string | 相对仓库根目录，通常为 `.` |
| `documentation` | string[] | README 与必要说明文件 |
| `install` | object | 安装命令与环境文件 |
| `data_preparation` | object | 数据准备入口 |
| `training` | object | 训练入口 |
| `evaluation` | object | 评估入口 |
| `result_generation` | object | 结果生成入口 |
| `default_configs` | string[] | 默认配置文件（需可解析） |
| `checkpoints` | object | checkpoint 获取方式与可选路径 |
| `expected_outputs` | string[] | 预期结果产物 |
| `license` | string | 许可证标识；个人项目可填写 `UNLICENSED`，不得默认为不存在的许可证 |
| `data_restrictions` | string | 数据获取与再分发限制 |

## 入口对象

`install` 与四个入口（`data_preparation`、`training`、`evaluation`、`result_generation`）统一结构：

```json
{
  "command": "python src/train.py --config configs/train.json",
  "entry": "src/train.py"
}
```

- `command`：公开给用户的运行命令（自由文本，不执行），必须存在且不得包含本机绝对路径。
- `entry`：命令实际调用的入口文件，必须是仓库内存在的相对路径。`install` 使用 `environment_files` 替代 `entry`。

## checkpoints

```json
{
  "acquisition": "bundled",
  "paths": ["checkpoints/model.pt"]
}
```

- `acquisition`：如何获取 checkpoint 的说明。
- `paths`：随仓库分发、应在发布时存在的 checkpoint 路径；外部获取的 checkpoint 不要列入 `paths`。
- `acquisition` 包含下载、外部 URL 或模型托管服务时，`paths` 必须为空，并提供可复查的获取说明。
- `acquisition` 为 `bundled` 时，`paths` 必须列出仓库内文件。

## 检查器行为

`scripts/check_release_package.py` 只做确定性检查，**不执行目标仓库代码**，也不替代完整密钥扫描或安全审计：

- 所有声明路径存在且为安全的相对路径（无 `..`、无本机绝对路径）。
- 路径及其父目录不是指向仓库外的符号链接。
- 扫描整个仓库中的文件名，不仅检查 manifest 已声明路径；文件名不应匹配敏感模式（`.env`、私钥、凭据等）。
- 路径不含明显本机/私有路径提示（如盘符、`/home/`、`/Users/`）。
- 安装和四个入口命令不得包含本机绝对路径。
- `default_configs` 可解析（JSON、TOML、INI/CFG；YAML 需 PyYAML，缺失时跳过并提示）。
- 检查项缺失映射到 finding：`MISSING_RELEASE_ASSET`、`SENSITIVE_CONTENT_RISK`、`PRIVATE_DEPENDENCY`、`UNSAFE_PATH`、`INVALID_CONFIG`。

退出码：`0` 表示通过；`1` 表示存在检查失败；`2` 表示输入或清单格式无效。该检查是文件名和结构启发式检查，不等同于完整 secret scan。
