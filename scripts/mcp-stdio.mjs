#!/usr/bin/env node
/**
 * 将 Cursor / MCP 客户端的 stdio 原样交给本仓库的 Python MCP 进程。
 * 用法：在仓库根执行 npx .   或由客户端配置 npx + 本目录路径。
 *
 * 依赖：仓库根已 uv sync（存在 .venv），或系统 PATH 中有 python 且能在 cwd 下执行 -m tools.unified_mcp_server。
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const isWin = process.platform === "win32";

const venvPython = isWin
  ? join(repoRoot, ".venv", "Scripts", "python.exe")
  : join(repoRoot, ".venv", "bin", "python");

const codeKbRoot = (process.env.CODE_KB_ROOT || repoRoot).trim() || repoRoot;

let command;
let args;

if (existsSync(venvPython)) {
  command = venvPython;
  args = ["-m", "tools.unified_mcp_server"];
} else {
  command = process.env.CODE_KB_PYTHON || (isWin ? "python" : "python3");
  args = ["-m", "tools.unified_mcp_server"];
}

const child = spawn(command, args, {
  cwd: repoRoot,
  stdio: "inherit",
  env: { ...process.env, CODE_KB_ROOT: codeKbRoot },
  windowsHide: true,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code === null || code === undefined ? 1 : code);
});

child.on("error", (err) => {
  console.error("[code-kb-mcp]", err.message);
  console.error(
    "[code-kb-mcp] 提示：在仓库根执行 uv sync 生成 .venv，或设置环境变量 CODE_KB_PYTHON 指向 python 可执行文件。"
  );
  process.exit(1);
});
