# stata-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![npm version](https://img.shields.io/npm/v/stata-cli.svg)](https://www.npmjs.com/package/stata-cli)

[中文版](README.zh.md) | [English](README.md)

通过 PyStata 在终端中使用 [Stata](https://www.stata.com/) 的命令行工具 — 为人类用户和 AI Agent 而设计。支持运行代码、`.do` 文件、查看数据、浏览帮助、导出图表，内置守护进程模式实现亚秒级执行。

[安装](#安装与快速开始) · [AI Agent](#ai-agent-快速开始) · [命令](#命令) · [守护进程](#守护进程模式) · [进阶](#进阶用法) · [贡献](#贡献)

## 为什么选择 stata-cli？

- **Agent 原生设计** — 结构化 JSON 输出、退出码、内置 [SKILL.md](SKILL.md) 定义 — AI Agent 无需额外配置即可操作 Stata
- **亚秒级执行** — 守护进程模式在后台保持 PyStata 常驻，启动时间从 ~2-3 秒降至 ~85 毫秒（35 倍加速）
- **功能全覆盖** — 运行代码、执行 `.do` 文件、查看数据、浏览帮助、导出图表、中断执行 — 一个工具搞定一切
- **AI 友好优化** — 精简输出模式、Token 限制管理、结构化 JSON 响应、图表自动命名 — 专为 Agent 工具调用设计
- **开源无门槛** — MIT 协议，开箱即用，`pip install` 即可
- **秒级上手** — 自动检测 Stata 安装路径，从安装到第一条命令只需 2 步

## 功能概览

| 类别 | 能力 |
|------|------|
| **运行代码** | 执行内联 Stata 代码、多行代码块，或从 stdin 管道输入 |
| **Do 文件** | 运行 `.do` 文件，支持 `///` 续行符和图表自动命名 |
| **数据查看** | 以 JSON 格式查看当前数据集，支持 `if` 条件过滤和行数限制 |
| **帮助系统** | 浏览 Stata 帮助主题，自动将 SMCL 标记转换为纯文本 |
| **图表导出** | 自动检测并导出图表为 PNG，保存至 `~/.stata-cli/graphs/` |
| **守护进程** | 后台常驻进程，通过 Unix socket 实现亚秒级执行 |
| **输出控制** | 精简模式、JSON 输出、Token 限制管理（超限时保存完整输出到文件） |
| **中断执行** | 发送 break 信号停止正在运行的命令 |

## 安装与快速开始

### 环境要求

- **Stata 17+**（提供 PyStata 库）
- Python 3.10+

### 快速开始（人类用户）

#### 安装

选择以下 **任一** 方式：

**方式一 — pip 安装（推荐）：**

```bash
pip install stata-cli
```

**方式二 — npm / npx（无需 Python 环境）：**

```bash
# 一次性使用
npx stata-cli run "display 1+1"

# 全局安装
npm install -g stata-cli
```

npm 包是一个轻量包装器，会自动调用 `uvx`、`pipx` 或 `python3`。

**方式三 — 从源码安装：**

```bash
git clone https://github.com/ashuiGordon/stata-cli.git
cd stata-cli
pip install -e ".[data]"
```

#### 使用

```bash
# 1. 验证 Stata 路径
stata-cli detect

# 2. 运行第一条命令
stata-cli run "display 1+1"

# 3. 启动守护进程加速执行
stata-cli daemon start
stata-cli run "sysuse auto, clear"    # ~85ms！
```

## AI Agent 快速开始

> 以下步骤面向通过 Bash 工具调用 `stata-cli` 的 AI Agent。

**第 1 步 — 安装**

```bash
pip install stata-cli
```

**第 2 步 — 验证 Stata 路径**

```bash
stata-cli detect
```

**第 3 步 — 启动守护进程（推荐）**

```bash
stata-cli daemon start
```

**第 4 步 — 运行命令**

```bash
# 内联代码
stata-cli run "sysuse auto, clear
regress price mpg weight
predict yhat"

# 结构化 JSON 输出
stata-cli --json run "summarize price"

# 查看数据
stata-cli data --if "price>10000" --rows 50

# 查询命令语法
stata-cli help regress
```

## 命令

### `run` — 执行 Stata 代码

```bash
stata-cli run "sysuse auto, clear"

# 多行代码
stata-cli run "sysuse auto, clear
summarize price mpg
regress price mpg weight"

# 从 stdin 管道输入
echo "display 42" | stata-cli run -
```

### `do` — 执行 .do 文件

```bash
stata-cli do analysis.do
stata-cli --compact do long_script.do
```

Do 文件会自动预处理：`///` 续行符会被合并，未命名的图表命令会自动添加名称以确保导出。

### `data` — 查看当前数据集

```bash
stata-cli data
stata-cli data --if "price>5000" --rows 50
```

以 JSON 格式返回当前数据集，包含列名、数据、类型和行数统计。

### `help` — 浏览 Stata 帮助

```bash
stata-cli help regress
stata-cli help summarize
```

以纯文本显示帮助内容（SMCL 标记自动转换）。

### `stop` — 中断执行

```bash
stata-cli stop
```

向正在运行的 Stata 命令发送 break 信号（守护进程模式）。

### `detect` — 检测 Stata 路径

```bash
stata-cli detect
```

打印自动检测到的 Stata 安装路径。

## 守护进程模式

守护进程在后台保持 PyStata 常驻 — 执行时间从 **~2-3 秒降至 ~85 毫秒**（35 倍加速）。

```bash
stata-cli daemon start       # 启动后台守护进程
stata-cli run "display 1"    # 快速执行 — 自动路由至守护进程
stata-cli daemon status      # 查看状态（PID、运行时间、空闲时间）
stata-cli daemon restart     # 重启（重置 Stata 状态）
stata-cli daemon stop        # 关闭
```

| 命令 | 说明 |
|------|------|
| `daemon start` | 启动后台守护进程 |
| `daemon stop` | 优雅关闭 |
| `daemon status` | 显示 PID、Stata 路径、运行时间、空闲时间 |
| `daemon restart` | 先关闭再启动（重置 Stata 状态） |

命令会在守护进程运行时自动路由。使用 `--no-daemon` 强制直接执行。

守护进程在空闲 1 小时后自动关闭（可通过 `--idle-timeout` 配置）。

## 进阶用法

### 全局选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--stata-path PATH` | Stata 安装目录 | 自动检测 |
| `--edition [mp\|se\|be]` | Stata 版本 | `mp` |
| `--compact` | 精简输出（去除冗余信息） | 关闭 |
| `--json` | 结构化 JSON 输出 | 关闭 |
| `--timeout SECONDS` | 执行超时（秒） | 600 |
| `--max-tokens N` | 最大输出 Token 数（0=不限） | 0 |
| `--no-daemon` | 强制直接执行 | 关闭 |
| `--graphs-dir PATH` | 图表导出目录 | `~/.stata-cli/graphs/` |

### JSON 输出

```bash
stata-cli --json run "display 1+1"
```

```json
{
  "success": true,
  "output": ". display 1+1\n2",
  "error": "",
  "execution_time": 0.04,
  "return_code": 0,
  "extra": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 命令是否成功 |
| `output` | string | Stata 输出文本 |
| `error` | string | 错误信息（如有） |
| `execution_time` | float | 执行耗时（秒） |
| `return_code` | int | Stata 返回码（0 = 正常） |
| `extra` | dict | 可能包含 `graphs` 列表及导出文件路径 |

### 图表导出

Stata 代码创建图表时，会自动检测并导出为 PNG：

```bash
stata-cli run "sysuse auto, clear
scatter price mpg"
```

```
[graph] graph1: /Users/you/.stata-cli/graphs/exec-.../graph1.png
```

在 JSON 模式下，图表路径出现在 `extra.graphs` 中。

### Token 限制管理

对于长输出，使用 `--max-tokens` 截断并将完整输出保存到文件：

```bash
stata-cli --max-tokens 500 run "sysuse auto, clear
describe"
```

当输出超过限制时，会显示预览内容及完整输出的文件路径。

### 环境变量

| 变量 | 说明 |
|------|------|
| `STATA_PATH` | 覆盖 Stata 安装路径 |
| `STATA_CLI_GRAPHS_DIR` | 覆盖图表导出目录 |

### 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | Stata 命令错误 |
| 2 | CLI 用法错误 |
| 3 | 未找到 Stata / 初始化失败 |

## Agent 使用示例

```bash
# 完整分析工作流
stata-cli run "sysuse auto, clear
summarize price mpg
regress price mpg weight
predict yhat
list make price yhat in 1/5"

# 加载数据后检查
stata-cli data --if "price>10000"

# 查询命令语法
stata-cli help anova

# 精简模式减少噪音
stata-cli --compact run "sysuse auto, clear
describe"

# JSON 模式用于结构化解析
stata-cli --json run "display 1+1"
```

## 贡献

欢迎社区贡献！如果发现 bug 或有功能建议，请提交 [Issue](https://github.com/ashuiGordon/stata-cli/issues) 或 [Pull Request](https://github.com/ashuiGordon/stata-cli/pulls)。

对于较大的改动，建议先通过 Issue 与我们讨论。

## 许可证

本项目采用 **MIT 许可证**。
