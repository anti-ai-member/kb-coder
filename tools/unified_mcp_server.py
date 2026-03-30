#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified MCP server (stdio). Run from repo root:

  uv run unified-mcp-server

Or:

  uv run python -m tools.unified_mcp_server

  # 也可直接跑本文件（会先以包名重新加载，相对导入才合法）：
  uv run python tools/unified_mcp_server.py

Optional env (defaults under project root):

  CODE_KB_ROOT       — project root (parent of kb/, logs/)
  KB_*_JSONL         — 代码知识库 files/symbols/relations
  LOG_INDEX_JSONL    — 源码日志索引（build_log_index.py 扫描 .java/.kt 生成）
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    _repo_root = Path(__file__).resolve().parent.parent
    _root_s = str(_repo_root)
    if _root_s not in sys.path:
        sys.path.insert(0, _root_s)
    from tools.unified_mcp_server import main_sync

    main_sync()
    raise SystemExit

import asyncio
import json
import logging
import os
from typing import Any, Dict

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from .kb_tools import KBTools
from .log_tools import LogTools


# ---------------------------------
# logging: NEVER write to stdout in stdio mode
# ---------------------------------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("unified-mcp-server")


# ---------------------------------
# Paths
# ---------------------------------
def _project_root() -> Path:
    env = (os.environ.get("CODE_KB_ROOT") or "").strip()
    if env:
        return Path(env).resolve()
    # tools/unified_mcp_server.py -> repo root
    return Path(__file__).resolve().parent.parent


BASE_DIR = _project_root()
KB_DIR = BASE_DIR / "kb"
LOG_DIR = BASE_DIR / "logs"

FILES_JSONL = Path(os.getenv("KB_FILES_JSONL", str(KB_DIR / "files.jsonl")))
SYMBOLS_JSONL = Path(os.getenv("KB_SYMBOLS_JSONL", str(KB_DIR / "symbols.jsonl")))
RELATIONS_JSONL = Path(os.getenv("KB_RELATIONS_JSONL", str(KB_DIR / "relations.jsonl")))
LOG_INDEX_JSONL = Path(os.getenv("LOG_INDEX_JSONL", str(LOG_DIR / "log_index.jsonl")))


def ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")


ensure_exists(FILES_JSONL)
ensure_exists(SYMBOLS_JSONL)
ensure_exists(RELATIONS_JSONL)
ensure_exists(LOG_INDEX_JSONL)

kb = KBTools(
    files_path=str(FILES_JSONL),
    symbols_path=str(SYMBOLS_JSONL),
    relations_path=str(RELATIONS_JSONL),
)

logs = LogTools(
    index_path=str(LOG_INDEX_JSONL),
)

server = Server("bug-analysis-unified-server")


def to_text_result(data: Any) -> list[types.TextContent]:
    return [
        types.TextContent(
            type="text",
            text=json.dumps(data, ensure_ascii=False, indent=2),
        )
    ]


def get_required_str(arguments: Dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid string parameter: {key}")
    return value.strip()


def get_optional_str(arguments: Dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = arguments.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Invalid string parameter: {key}")
    value = value.strip()
    return value if value else None


def get_optional_int(arguments: Dict[str, Any], key: str, default: int | None = None) -> int | None:
    value = arguments.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid integer parameter: {key}")
    return value


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # -------------------------
        # code tools
        # -------------------------
        types.Tool(
            name="search_symbol",
            description="Search candidate code symbols by keyword.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "top_k": {"type": "integer", "default": 10}
                },
                "required": ["keyword"]
            },
        ),
        types.Tool(
            name="get_symbol_context",
            description="Get compact structural context for a code symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "member_limit": {"type": "integer", "default": 20},
                    "rel_limit": {"type": "integer", "default": 20}
                },
                "required": ["symbol"]
            },
        ),
        types.Tool(
            name="get_impact",
            description="Analyze likely impact of changing a code symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "incoming_limit": {"type": "integer", "default": 20},
                    "outgoing_limit": {"type": "integer", "default": 20}
                },
                "required": ["symbol"]
            },
        ),
        types.Tool(
            name="get_service_ipc",
            description="Inspect Service / Binder / AIDL relationships for a service-like symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_symbol": {"type": "string"}
                },
                "required": ["service_symbol"]
            },
        ),
        types.Tool(
            name="search_voice_path",
            description="Search code symbols with ranking biased toward service / manager / dispatcher / callback style architecture.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "top_k": {"type": "integer", "default": 15}
                },
                "required": ["keyword"]
            },
        ),

        # -------------------------
        # log tools
        # -------------------------
        types.Tool(
            name="search_logs",
            description="Search indexed source log calls (Log/Timber/println in .java/.kt). Filters: keyword, level (e.g. DEBUG), tag, label (message_token substring), file path substring.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "level": {"type": "string"},
                    "tag": {"type": "string"},
                    "label": {"type": "string"},
                    "file": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": []
            },
        ),
        types.Tool(
            name="summarize_logs",
            description="Summarize matching source log index rows: counts by level, tag, message_token, file, unique_groups.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "level": {"type": "string"},
                    "tag": {"type": "string"},
                    "label": {"type": "string"},
                    "file": {"type": "string"}
                },
                "required": []
            },
        ),
        types.Tool(
            name="group_log_fingerprints",
            description="Group matching rows by stable group_key (record id or message template) to find duplicate log call patterns in source.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "level": {"type": "string"},
                    "tag": {"type": "string"},
                    "label": {"type": "string"},
                    "file": {"type": "string"},
                    "limit": {"type": "integer", "default": 15}
                },
                "required": []
            },
        ),
        types.Tool(
            name="find_suspicious_tags",
            description="Top Log tags among matching indexed source log calls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "level": {"type": "string"},
                    "label": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": []
            },
        ),
        types.Tool(
            name="find_suspicious_files",
            description="Top source files by count of matching indexed log calls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "level": {"type": "string"},
                    "label": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": []
            },
        ),
        types.Tool(
            name="analyze_log_issue",
            description="Combined view over source log index: summary stats, top_groups, sample_records, top_tags, top_files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "level": {"type": "string"},
                    "tag": {"type": "string"},
                    "label": {"type": "string"},
                    "file": {"type": "string"},
                    "sample_limit": {"type": "integer", "default": 10},
                    "group_limit": {"type": "integer", "default": 10}
                },
                "required": []
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[types.TextContent]:
    arguments = arguments or {}

    logger.info("Tool call: %s args=%s", name, arguments)

    # -------------------------
    # code tools
    # -------------------------
    if name == "search_symbol":
        keyword = get_required_str(arguments, "keyword")
        top_k = get_optional_int(arguments, "top_k", 10) or 10
        return to_text_result(kb.search_symbol(keyword=keyword, top_k=top_k))

    if name == "get_symbol_context":
        symbol = get_required_str(arguments, "symbol")
        member_limit = get_optional_int(arguments, "member_limit", 20) or 20
        rel_limit = get_optional_int(arguments, "rel_limit", 20) or 20
        return to_text_result(
            kb.get_symbol_context(
                symbol=symbol,
                member_limit=member_limit,
                rel_limit=rel_limit,
            )
        )

    if name == "get_impact":
        symbol = get_required_str(arguments, "symbol")
        incoming_limit = get_optional_int(arguments, "incoming_limit", 20) or 20
        outgoing_limit = get_optional_int(arguments, "outgoing_limit", 20) or 20
        return to_text_result(
            kb.get_impact(
                symbol=symbol,
                incoming_limit=incoming_limit,
                outgoing_limit=outgoing_limit,
            )
        )

    if name == "get_service_ipc":
        service_symbol = get_required_str(arguments, "service_symbol")
        return to_text_result(
            kb.get_service_ipc(service_symbol=service_symbol)
        )

    if name == "search_voice_path":
        keyword = get_required_str(arguments, "keyword")
        top_k = get_optional_int(arguments, "top_k", 15) or 15
        return to_text_result(
            kb.search_voice_path(keyword=keyword, top_k=top_k)
        )

    # -------------------------
    # log tools
    # -------------------------
    if name == "search_logs":
        return to_text_result(
            logs.search_logs(
                keyword=get_optional_str(arguments, "keyword"),
                level=get_optional_str(arguments, "level"),
                tag=get_optional_str(arguments, "tag"),
                label=get_optional_str(arguments, "label"),
                file=get_optional_str(arguments, "file"),
                limit=get_optional_int(arguments, "limit", 20) or 20,
            )
        )

    if name == "summarize_logs":
        return to_text_result(
            logs.summarize_logs(
                keyword=get_optional_str(arguments, "keyword"),
                level=get_optional_str(arguments, "level"),
                tag=get_optional_str(arguments, "tag"),
                label=get_optional_str(arguments, "label"),
                file=get_optional_str(arguments, "file"),
            )
        )

    if name == "group_log_fingerprints":
        return to_text_result(
            logs.group_log_fingerprints(
                keyword=get_optional_str(arguments, "keyword"),
                level=get_optional_str(arguments, "level"),
                tag=get_optional_str(arguments, "tag"),
                label=get_optional_str(arguments, "label"),
                file=get_optional_str(arguments, "file"),
                limit=get_optional_int(arguments, "limit", 15) or 15,
            )
        )

    if name == "find_suspicious_tags":
        return to_text_result(
            logs.find_suspicious_tags(
                keyword=get_optional_str(arguments, "keyword"),
                level=get_optional_str(arguments, "level"),
                label=get_optional_str(arguments, "label"),
                limit=get_optional_int(arguments, "limit", 20) or 20,
            )
        )

    if name == "find_suspicious_files":
        return to_text_result(
            logs.find_suspicious_files(
                keyword=get_optional_str(arguments, "keyword"),
                level=get_optional_str(arguments, "level"),
                label=get_optional_str(arguments, "label"),
                limit=get_optional_int(arguments, "limit", 20) or 20,
            )
        )

    if name == "analyze_log_issue":
        return to_text_result(
            logs.analyze_log_issue(
                keyword=get_optional_str(arguments, "keyword"),
                level=get_optional_str(arguments, "level"),
                tag=get_optional_str(arguments, "tag"),
                label=get_optional_str(arguments, "label"),
                file=get_optional_str(arguments, "file"),
                sample_limit=get_optional_int(arguments, "sample_limit", 10) or 10,
                group_limit=get_optional_int(arguments, "group_limit", 10) or 10,
            )
        )

    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    logger.info("Starting unified MCP server")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bug-analysis-unified-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main_sync() -> None:
    """Console entry point for uv / setuptools scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()