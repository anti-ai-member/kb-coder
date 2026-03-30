#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from typing import Dict, List, Any, Optional

from .query_kb import CodeKnowledgeBase


class KBTools:
    def __init__(self, files_path: str, symbols_path: str, relations_path: str):
        self.kb = CodeKnowledgeBase(files_path, symbols_path, relations_path)

    # -------------------------------------------------
    # Tool 1: 搜索候选符号
    # -------------------------------------------------
    def search_symbol(self, keyword: str, top_k: int = 10) -> Dict[str, Any]:
        results = self.kb.find_symbols(keyword)[:top_k]

        return {
            "query": keyword,
            "count": len(results),
            "results": [
                self._compact_symbol(s) for s in results
            ]
        }

    # -------------------------------------------------
    # Tool 2: 获取某个符号的局部上下文
    # -------------------------------------------------
    def get_symbol_context(
        self,
        symbol: str,
        member_limit: int = 20,
        rel_limit: int = 20
    ) -> Dict[str, Any]:
        s = self.kb.get_symbol(symbol)
        if not s:
            return {
                "found": False,
                "symbol": symbol,
                "message": "symbol not found"
            }

        file_info = self.kb.get_file_of_symbol(symbol)
        members = self.kb.get_container_members(symbol) if s["kind"] in {
            "class", "interface", "object", "enum", "aidl_interface"
        } else []

        outgoing = self.kb.find_outgoing_relations(symbol)[:rel_limit]
        incoming = self.kb.find_incoming_relations(symbol)[:rel_limit]
        deps = self.kb.find_dependencies(symbol)[:rel_limit]

        return {
            "found": True,
            "symbol": self._compact_symbol(s),
            "file": self._compact_file(file_info) if file_info else None,
            "members": [self._compact_symbol(x) for x in members[:member_limit]],
            "dependencies": [self._compact_relation(x) for x in deps],
            "outgoing_relations": [self._compact_relation(x) for x in outgoing],
            "incoming_relations": [self._compact_relation(x) for x in incoming],
        }

    # -------------------------------------------------
    # Tool 3: 获取影响面
    # -------------------------------------------------
    def get_impact(
        self,
        symbol: str,
        incoming_limit: int = 20,
        outgoing_limit: int = 20
    ) -> Dict[str, Any]:
        s = self.kb.get_symbol(symbol)
        if not s:
            return {
                "found": False,
                "symbol": symbol,
                "message": "symbol not found"
            }

        incoming_refs = self.kb.find_incoming_refs(symbol)[:incoming_limit]
        outgoing_refs = self.kb.find_outgoing_refs(symbol)[:outgoing_limit]
        deps = self.kb.find_dependencies(symbol)[:outgoing_limit]

        callers = self._unique_relation_targets(incoming_refs, key_field="from")
        callees = self._unique_relation_targets(outgoing_refs, key_field="to")

        return {
            "found": True,
            "symbol": self._compact_symbol(s),
            "summary": {
                "incoming_ref_count": len(incoming_refs),
                "outgoing_ref_count": len(outgoing_refs),
                "dependency_count": len(deps),
            },
            "incoming_refs": [self._compact_relation(x) for x in incoming_refs],
            "outgoing_refs": [self._compact_relation(x) for x in outgoing_refs],
            "dependencies": [self._compact_relation(x) for x in deps],
            "callers_preview": callers[:15],
            "callees_preview": callees[:15],
        }

    # -------------------------------------------------
    # Tool 4: 获取 Service 和 IPC 关系
    # -------------------------------------------------
    def get_service_ipc(self, service_symbol: str) -> Dict[str, Any]:
        s = self.kb.get_symbol(service_symbol)
        if not s:
            return {
                "found": False,
                "symbol": service_symbol,
                "message": "service symbol not found"
            }

        bindings = self.kb.find_service_bindings(service_symbol)
        deps = self.kb.find_dependencies(service_symbol)
        members = self.kb.get_container_members(service_symbol)

        lifecycle_methods = [
            m for m in members
            if m["name"] in {"onCreate", "onStartCommand", "onBind", "onUnbind", "onDestroy"}
        ]

        return {
            "found": True,
            "service": self._compact_symbol(s),
            "bindings": [self._compact_relation(x) for x in bindings],
            "dependencies": [self._compact_relation(x) for x in deps],
            "lifecycle_methods": [self._compact_symbol(x) for x in lifecycle_methods],
            "member_preview": [self._compact_symbol(x) for x in members[:20]],
        }

    # -------------------------------------------------
    # Tool 5: 面向语音链路的搜索
    # -------------------------------------------------
    def search_voice_path(self, keyword: str, top_k: int = 15) -> Dict[str, Any]:
        """
        适合语音服务项目：
        优先给 service / manager / dispatcher / controller / binder / callback 相关结果加权
        """
        raw = self.kb.find_symbols(keyword)

        def score(s: Dict[str, Any]) -> int:
            score_val = 0
            tags = set(s.get("tags", []))
            kind = s.get("kind", "")
            name = s.get("name", "").lower()
            sym = s.get("symbol", "").lower()

            for t in ["service", "manager", "dispatcher", "controller", "binder", "callback", "listener", "voice", "session", "ipc"]:
                if t in tags:
                    score_val += 10

            if kind in {"class", "interface", "object", "aidl_interface"}:
                score_val += 8
            elif kind in {"method", "aidl_method"}:
                score_val += 4

            for key in ["voice", "asr", "tts", "nlu", "wake", "session", "command", "dispatch"]:
                if key in name:
                    score_val += 6
                if key in sym:
                    score_val += 3

            return -score_val  # 倒序

        ranked = sorted(raw, key=score)[:top_k]

        expanded = []
        for s in ranked:
            expanded.append({
                "symbol": self._compact_symbol(s),
                "dependencies": [self._compact_relation(x) for x in self.kb.find_dependencies(s["symbol"])[:8]],
                "bindings": [self._compact_relation(x) for x in self.kb.find_service_bindings(s["symbol"])[:8]],
                "members_preview": [self._compact_symbol(x) for x in self.kb.get_container_members(s["symbol"])[:8]]
            })

        return {
            "query": keyword,
            "count": len(expanded),
            "results": expanded
        }

    # -------------------------------------------------
    # 内部辅助
    # -------------------------------------------------
    def _compact_symbol(self, s: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": s.get("symbol"),
            "name": s.get("name"),
            "kind": s.get("kind"),
            "module": s.get("module"),
            "file": s.get("file"),
            "line": s.get("line"),
            "container": s.get("container"),
            "signature": s.get("signature"),
            "tags": s.get("tags", []),
        }

    def _compact_file(self, f: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "path": f.get("path"),
            "module": f.get("module"),
            "language": f.get("language"),
            "file_type": f.get("file_type"),
            "summary": f.get("summary"),
            "lines": f.get("lines"),
        }

    def _compact_relation(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": r.get("type"),
            "from": r.get("from"),
            "to": r.get("to"),
            "file": r.get("file"),
            "line": r.get("line"),
            "confidence": r.get("confidence"),
            "meta": r.get("meta", {}),
        }

    def _unique_relation_targets(self, rels: List[Dict[str, Any]], key_field: str) -> List[str]:
        out = []
        seen = set()
        for r in rels:
            val = r.get(key_field)
            if val and val not in seen:
                seen.add(val)
                out.append(val)
        return out


# -------------------------------------------------
# 简单 CLI，方便本地调试
# -------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Agent-oriented KB tools")
    parser.add_argument("--files", required=True)
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--relations", required=True)

    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("search-symbol")
    p1.add_argument("keyword")
    p1.add_argument("--top-k", type=int, default=10)

    p2 = sub.add_parser("symbol-context")
    p2.add_argument("symbol")
    p2.add_argument("--member-limit", type=int, default=20)
    p2.add_argument("--rel-limit", type=int, default=20)

    p3 = sub.add_parser("impact")
    p3.add_argument("symbol")
    p3.add_argument("--incoming-limit", type=int, default=20)
    p3.add_argument("--outgoing-limit", type=int, default=20)

    p4 = sub.add_parser("service-ipc")
    p4.add_argument("service_symbol")

    p5 = sub.add_parser("voice-path")
    p5.add_argument("keyword")
    p5.add_argument("--top-k", type=int, default=15)

    args = parser.parse_args()

    tools = KBTools(args.files, args.symbols, args.relations)

    if args.cmd == "search-symbol":
        result = tools.search_symbol(args.keyword, args.top_k)
    elif args.cmd == "symbol-context":
        result = tools.get_symbol_context(args.symbol, args.member_limit, args.rel_limit)
    elif args.cmd == "impact":
        result = tools.get_impact(args.symbol, args.incoming_limit, args.outgoing_limit)
    elif args.cmd == "service-ipc":
        result = tools.get_service_ipc(args.service_symbol)
    elif args.cmd == "voice-path":
        result = tools.search_voice_path(args.keyword, args.top_k)
    else:
        raise ValueError(f"unknown cmd: {args.cmd}")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()