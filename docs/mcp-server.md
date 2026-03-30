# code-kb 统一 MCP Server 配置说明

基于 **stdio** 的 MCP 服务（服务名 `bug-analysis-unified-server`），提供代码知识库查询与源码日志索引查询。

## 1. 能力概览

| 类别 | 工具名 |
|------|--------|
| 代码知识库 | `search_symbol`, `get_symbol_context`, `get_impact`, `get_service_ipc`, `search_voice_path` |
| 源码日志索引 | `search_logs`, `summarize_logs`, `group_log_fingerprints`, `find_suspicious_tags`, `find_suspicious_files`, `analyze_log_issue` |

## 2. 前置条件

启动时会检查以下 **四个 JSONL 文件必须存在**，否则进程退出并报 `FileNotFoundError`：

| 文件 | 典型生成方式 |
|------|----------------|
| `kb/files.jsonl` | `build_pipeline.py` 或 `build_files.py` |
| `kb/symbols.jsonl` | `build_pipeline.py` 或 `build_symbols.py` |
| `kb/relations.jsonl` | `build_pipeline.py` 或 `build_relations.py` |
| `logs/log_index.jsonl` | `build_log_index.py`（扫描 `.java` / `.kt` 中的 Log / Timber / println 等） |

默认路径相对于 **`CODE_KB_ROOT`**（见下节），也可通过环境变量逐项覆盖。

## 3. 启动命令

在 **本仓库根目录**（含 `pyproject.toml`）下执行（需已 `uv sync`）：

```bash
uv run unified-mcp-server
```

等价：

```bash
uv run python -m tools.unified_mcp_server
```

说明：MCP 使用 **stdin/stdout** 传输协议；服务日志应只写 **stderr**，勿向 stdout 输出普通文本。

## 4. 环境变量

| 变量 | 含义 | 默认 |
|------|------|------|
| `CODE_KB_ROOT` | 项目根目录（其下通常有 `kb/`、`logs/`） | 未设置时：安装包内 `tools` 目录的上一级，即本仓库根目录 |
| `KB_FILES_JSONL` | 文件索引 | `<根>/kb/files.jsonl` |
| `KB_SYMBOLS_JSONL` | 符号索引 | `<根>/kb/symbols.jsonl` |
| `KB_RELATIONS_JSONL` | 关系索引 | `<根>/kb/relations.jsonl` |
| `LOG_INDEX_JSONL` | 源码日志索引 | `<根>/logs/log_index.jsonl` |

可将四个 JSONL 指向任意路径（例如某子工程 `.code_kb/` 下的产物），以便 MCP 只服务该代码库。

## 5. Cursor 配置示例

将路径改为你本机的 **code-kb 仓库根目录**。

### 5.1 用 `uv`（建议在 Cursor 里加 `--directory`）

Cursor 有时**不会**把 MCP 里的 `cwd` 传给子进程，导致 `uv run` 找不到工程，出现 `Failed to spawn: unified-mcp-server`。解决办法：在参数里写死项目根 **`--directory`**，并用 **`uv.exe` 绝对路径**（GUI 里 PATH 常不含 `~\.local\bin`）：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "C:\\Users\\HuangXin\\.local\\bin\\uv.exe",
      "args": [
        "run",
        "--directory",
        "D:\\workspace\\ai\\code-kb",
        "unified-mcp-server"
      ],
      "env": {
        "CODE_KB_ROOT": "D:\\workspace\\ai\\code-kb"
      }
    }
  }
}
```

其中 `uv.exe` 路径在 PowerShell 里用 `where.exe uv` 查看；用户名、盘符按你本机修改。

等价环境变量（可选）：`UV_PROJECT=D:\workspace\ai\code-kb` 或 `UV_WORKING_DIR=...`（与 `--directory` 类似）。

### 5.2 简化写法（依赖 cwd 正确时）

若你的 MCP 客户端**确实**会把 `cwd` 设为仓库根，可简写为：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "uv",
      "args": ["run", "unified-mcp-server"],
      "cwd": "d:\\workspace\\ai\\code-kb",
      "env": {
        "CODE_KB_ROOT": "d:\\workspace\\ai\\code-kb"
      }
    }
  }
}
```

自定义知识库与日志索引路径示例：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "uv",
      "args": ["run", "unified-mcp-server"],
      "cwd": "d:\\workspace\\ai\\code-kb",
      "env": {
        "CODE_KB_ROOT": "d:\\workspace\\ai\\code-kb",
        "KB_FILES_JSONL": "d:\\workspace\\ai\\code-kb\\code_demo_project\\.code_kb\\files.jsonl",
        "KB_SYMBOLS_JSONL": "d:\\workspace\\ai\\code-kb\\code_demo_project\\.code_kb\\symbols.jsonl",
        "KB_RELATIONS_JSONL": "d:\\workspace\\ai\\code-kb\\code_demo_project\\.code_kb\\relations.jsonl",
        "LOG_INDEX_JSONL": "d:\\workspace\\ai\\code-kb\\logs\\log_index.jsonl"
      }
    }
  }
}
```

**要点：** `cwd` 必须指向本仓库根目录，以便 `uv` 读取 `pyproject.toml` 并使用项目虚拟环境。

### 5.3 用 Node 包装（`mcp-stdio.mjs`）

仓库提供 **`scripts/mcp-stdio.mjs`**：由 Node 启动 **`.venv` 里的 Python**（`-m tools.unified_mcp_server`），**stdio 原样继承**。

前置：**本仓库已执行 `uv sync`**（存在 `.venv`）。

#### 推荐：`node` + 脚本绝对路径（兼容 Chatbox 等客户端）

部分客户端会把 `npx` 的「目录参数」和自身安装路径错误拼接，并把 `D:\...` 里的反斜杠弄丢，出现：

`...\Chatbox\D:workspaceaicode-kb\package.json` → **ENOENT**。

**请改用 `node` 直接跑脚本**（路径用 **正斜杠** 最稳）：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "C:\\Program Files\\nodejs\\node.exe",
      "args": ["D:/workspace/ai/code-kb/scripts/mcp-stdio.mjs"],
      "env": {
        "CODE_KB_ROOT": "D:/workspace/ai/code-kb"
      }
    }
  }
}
```

`node.exe` 路径以本机为准（PowerShell：`where.exe node`）。`CODE_KB_ROOT` 与脚本内默认根目录一致时可省略 `env`。

#### 备选：`npx` + 仓库根目录（Cursor 等若路径未被破坏可用）

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "npx",
      "args": ["--yes", "D:/workspace/ai/code-kb"],
      "env": {
        "CODE_KB_ROOT": "D:/workspace/ai/code-kb"
      }
    }
  }
}
```

目录参数建议写 **`D:/workspace/ai/code-kb`**（正斜杠），降低被错误拼接的概率。

- 未安装 `.venv` 时，包装脚本会退回到 PATH 里的 `python` / `python3`；也可设置 **`CODE_KB_PYTHON`** 为解释器绝对路径。

**命令行自测：**

```bash
node D:/workspace/ai/code-kb/scripts/mcp-stdio.mjs
```

```bash
npx --yes D:/workspace/ai/code-kb
```

若需发布到 npm 后再 `npx -y code-kb-mcp`，需去掉 `package.json` 里的 `"private": true` 并修改包名避免冲突。

## 6. Claude Desktop 配置示例（Windows）

在 Claude Desktop 的 MCP 配置（如 `%APPDATA%\Claude\claude_desktop_config.json`）的 `mcpServers` 中增加：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "uv",
      "args": ["run", "unified-mcp-server"],
      "cwd": "d:\\workspace\\ai\\code-kb"
    }
  }
}
```

若 `uv` 不在 PATH 中，请将 `command` 改为 `uv.exe` 的绝对路径。

## 7. 推荐工作流

1. `uv sync`
2. 生成代码索引：`uv run python build_pipeline.py <目标代码目录>`
3. 生成日志索引：`uv run python build_log_index.py <repo_root> <输出/log_index.jsonl> <输出/log_index_stats.json>`
4. 确认上述四个 JSONL 路径与 MCP 的 `env` 一致后启动 MCP

## 8. 故障排查

| 现象 | 可能原因 |
|------|----------|
| 启动即退出 / `FileNotFoundError` | 某个 `KB_*` 或 `LOG_INDEX_JSONL` 不存在 |
| 找不到命令 | `uv` 未安装或未加入 PATH；或 `cwd` 不是仓库根 |
| 工具返回空结果 | 索引文件为空，或路径指向错误工程 |

### Windows / Cursor：`program not found` 或 `Failed to spawn: uv`

图形界面（Cursor）拉起的子进程 **PATH 经常比 PowerShell 里短**，例如没有 `C:\Users\<你>\.local\bin`，因此写 `"command": "uv"` 会失败。

**做法一（推荐）：** 把 `uv` 写成**本机绝对路径**（在 PowerShell 里执行 `where.exe uv` 查看）：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "C:\\Users\\HuangXin\\.local\\bin\\uv.exe",
      "args": ["run", "unified-mcp-server"],
      "cwd": "D:\\workspace\\ai\\code-kb"
    }
  }
}
```

**做法二（不依赖 uv 是否在 PATH）：** 直接用仓库里的虚拟环境 Python 跑模块：

```json
{
  "mcpServers": {
    "code-kb": {
      "command": "D:\\workspace\\ai\\code-kb\\.venv\\Scripts\\python.exe",
      "args": ["-m", "tools.unified_mcp_server"],
      "cwd": "D:\\workspace\\ai\\code-kb"
    }
  }
}
```

若 `.venv` 尚未创建，先在 `D:\workspace\ai\code-kb` 执行：`uv sync`。

## 9. 实现位置

- 入口：`tools/unified_mcp_server.py`
- 控制台脚本：`pyproject.toml` 中 `unified-mcp-server = tools.unified_mcp_server:main_sync`
