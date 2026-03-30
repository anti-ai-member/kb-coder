#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


class CodeKnowledgeBase:
    def __init__(self, files_path: str, symbols_path: str, relations_path: str):
        self.files = load_jsonl(Path(files_path))
        self.symbols = load_jsonl(Path(symbols_path))
        self.relations = load_jsonl(Path(relations_path))

        self.files_by_path: Dict[str, Dict] = {}
        self.symbols_by_symbol: Dict[str, Dict] = {}
        self.symbols_by_name: Dict[str, List[Dict]] = defaultdict(list)
        self.symbols_by_file: Dict[str, List[Dict]] = defaultdict(list)
        self.symbols_by_module: Dict[str, List[Dict]] = defaultdict(list)
        self.symbols_by_tag: Dict[str, List[Dict]] = defaultdict(list)

        self.relations_from: Dict[str, List[Dict]] = defaultdict(list)
        self.relations_to: Dict[str, List[Dict]] = defaultdict(list)
        self.relations_by_type: Dict[str, List[Dict]] = defaultdict(list)

        self._build_indexes()

    def _build_indexes(self):
        for f in self.files:
            self.files_by_path[f["path"]] = f

        for s in self.symbols:
            self.symbols_by_symbol[s["symbol"]] = s
            self.symbols_by_name[s["name"]].append(s)
            self.symbols_by_file[s["file"]].append(s)
            self.symbols_by_module[s["module"]].append(s)
            for tag in s.get("tags", []):
                self.symbols_by_tag[tag].append(s)

        for r in self.relations:
            self.relations_from[r["from"]].append(r)
            self.relations_to[r["to"]].append(r)
            self.relations_by_type[r["type"]].append(r)

    # -------------------------
    # 基础查询
    # -------------------------

    def find_symbols(self, query: str) -> List[Dict]:
        """
        按 symbol / qualified_name / name 模糊查询
        """
        q = query.lower().strip()
        results = []

        for s in self.symbols:
            haystacks = [
                s.get("symbol", ""),
                s.get("qualified_name", ""),
                s.get("name", ""),
                s.get("file", "")
            ]
            if any(q in h.lower() for h in haystacks):
                results.append(s)

        return self._sort_symbol_results(results)

    def get_symbol(self, symbol: str) -> Dict | None:
        return self.symbols_by_symbol.get(symbol)

    def get_file_of_symbol(self, symbol: str) -> Dict | None:
        s = self.symbols_by_symbol.get(symbol)
        if not s:
            return None
        return self.files_by_path.get(s["file"])

    def get_container_members(self, container_symbol: str) -> List[Dict]:
        """
        某个类/接口下面有哪些成员（方法/常量）
        """
        results = []
        for s in self.symbols:
            if s.get("container") == container_symbol:
                results.append(s)
        return sorted(results, key=lambda x: (x.get("line", 0), x.get("name", "")))

    def list_module_symbols(self, module: str, kinds: List[str] | None = None) -> List[Dict]:
        results = self.symbols_by_module.get(module, [])
        if kinds:
            results = [s for s in results if s.get("kind") in kinds]
        return self._sort_symbol_results(results)

    def list_symbols_by_tag(self, tag: str) -> List[Dict]:
        return self._sort_symbol_results(self.symbols_by_tag.get(tag, []))

    # -------------------------
    # 关系查询
    # -------------------------

    def find_outgoing_relations(self, symbol: str, rel_type: str | None = None) -> List[Dict]:
        rels = self.relations_from.get(symbol, [])
        if rel_type:
            rels = [r for r in rels if r["type"] == rel_type]
        return sorted(rels, key=lambda x: (x.get("type", ""), x.get("line", 0), x.get("to", "")))

    def find_incoming_relations(self, symbol: str, rel_type: str | None = None) -> List[Dict]:
        rels = self.relations_to.get(symbol, [])
        if rel_type:
            rels = [r for r in rels if r["type"] == rel_type]
        return sorted(rels, key=lambda x: (x.get("type", ""), x.get("line", 0), x.get("from", "")))

    def find_outgoing_refs(self, symbol: str) -> List[Dict]:
        return self.find_outgoing_relations(symbol, "references_symbol")

    def find_incoming_refs(self, symbol: str) -> List[Dict]:
        return self.find_incoming_relations(symbol, "references_symbol")

    def find_dependencies(self, symbol: str) -> List[Dict]:
        """
        看一个类/文件依赖了谁：imports / extends / implements / uses_binder / binds_to
        """
        rel_types = {"imports", "extends", "implements", "uses_binder", "binds_to"}
        rels = self.relations_from.get(symbol, [])
        rels = [r for r in rels if r["type"] in rel_types]
        return sorted(rels, key=lambda x: (x["type"], x.get("to", "")))

    def find_service_bindings(self, service_symbol: str) -> List[Dict]:
        rels = self.relations_from.get(service_symbol, [])
        rels = [r for r in rels if r["type"] in {"uses_binder", "binds_to"}]
        return sorted(rels, key=lambda x: (x["type"], x.get("to", "")))

    # -------------------------
    # 组合查询
    # -------------------------

    def explain_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        给 agent 用的简洁摘要
        """
        s = self.symbols_by_symbol.get(symbol)
        if not s:
            return {"found": False, "symbol": symbol}

        file_info = self.files_by_path.get(s["file"])
        members = self.get_container_members(symbol) if s["kind"] in {"class", "interface", "object", "enum", "aidl_interface"} else []
        outgoing = self.find_outgoing_relations(symbol)
        incoming = self.find_incoming_relations(symbol)

        return {
            "found": True,
            "symbol": s,
            "file": file_info,
            "members_count": len(members),
            "members_preview": members[:20],
            "outgoing_relations_preview": outgoing[:20],
            "incoming_relations_preview": incoming[:20],
        }

    def find_related_symbols(self, query: str) -> Dict[str, Any]:
        """
        给 agent 快速找一批候选
        """
        matched = self.find_symbols(query)[:20]

        expanded = []
        seen = set()

        for s in matched:
            key = s["symbol"]
            if key not in seen:
                seen.add(key)
                expanded.append({
                    "symbol": s,
                    "outgoing_preview": self.find_outgoing_relations(key)[:10],
                    "incoming_preview": self.find_incoming_relations(key)[:10],
                })

        return {
            "query": query,
            "matched_count": len(matched),
            "matches": expanded
        }

    # -------------------------
    # 排序 / 格式化
    # -------------------------

    def _sort_symbol_results(self, results: List[Dict]) -> List[Dict]:
        def score(s: Dict) -> tuple:
            kind_rank = {
                "class": 0,
                "interface": 1,
                "object": 2,
                "enum": 3,
                "aidl_interface": 4,
                "method": 5,
                "aidl_method": 6,
                "constant": 7
            }.get(s.get("kind", ""), 99)

            return (
                kind_rank,
                s.get("module", ""),
                s.get("file", ""),
                s.get("line", 0)
            )

        return sorted(results, key=score)

    def print_symbol_brief(self, symbols: List[Dict], limit: int = 20):
        for s in symbols[:limit]:
            print(
                f"[{s.get('kind')}] {s.get('symbol')}  "
                f"(module={s.get('module')}, file={s.get('file')}, line={s.get('line')})"
            )

    def print_rel_brief(self, rels: List[Dict], limit: int = 20):
        for r in rels[:limit]:
            print(
                f"[{r.get('type')}] {r.get('from')} -> {r.get('to')}  "
                f"(file={r.get('file')}, line={r.get('line')}, confidence={r.get('confidence')})"
            )


def build_parser():
    parser = argparse.ArgumentParser(description="Query code knowledge base")
    parser.add_argument("--files", required=True, help="Path to files.jsonl")
    parser.add_argument("--symbols", required=True, help="Path to symbols.jsonl")
    parser.add_argument("--relations", required=True, help="Path to relations.jsonl")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("find-symbols", help="Find symbols by keyword")
    p1.add_argument("query")

    p2 = sub.add_parser("symbol", help="Explain one exact symbol")
    p2.add_argument("symbol")

    p3 = sub.add_parser("members", help="List members of a container symbol")
    p3.add_argument("container")

    p4 = sub.add_parser("incoming", help="Find incoming relations")
    p4.add_argument("symbol")
    p4.add_argument("--type", default=None)

    p5 = sub.add_parser("outgoing", help="Find outgoing relations")
    p5.add_argument("symbol")
    p5.add_argument("--type", default=None)

    p6 = sub.add_parser("deps", help="Find dependencies of a symbol")
    p6.add_argument("symbol")

    p7 = sub.add_parser("bindings", help="Find binder/AIDL bindings of a service")
    p7.add_argument("service")

    p8 = sub.add_parser("tag", help="List symbols by tag")
    p8.add_argument("tag")

    p9 = sub.add_parser("module", help="List symbols by module")
    p9.add_argument("module")
    p9.add_argument("--kinds", nargs="*", default=None)

    p10 = sub.add_parser("related", help="Find related symbols by fuzzy query")
    p10.add_argument("query")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    kb = CodeKnowledgeBase(args.files, args.symbols, args.relations)

    if args.cmd == "find-symbols":
        results = kb.find_symbols(args.query)
        kb.print_symbol_brief(results, limit=50)

    elif args.cmd == "symbol":
        result = kb.explain_symbol(args.symbol)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "members":
        results = kb.get_container_members(args.container)
        kb.print_symbol_brief(results, limit=100)

    elif args.cmd == "incoming":
        results = kb.find_incoming_relations(args.symbol, args.type)
        kb.print_rel_brief(results, limit=100)

    elif args.cmd == "outgoing":
        results = kb.find_outgoing_relations(args.symbol, args.type)
        kb.print_rel_brief(results, limit=100)

    elif args.cmd == "deps":
        results = kb.find_dependencies(args.symbol)
        kb.print_rel_brief(results, limit=100)

    elif args.cmd == "bindings":
        results = kb.find_service_bindings(args.service)
        kb.print_rel_brief(results, limit=100)

    elif args.cmd == "tag":
        results = kb.list_symbols_by_tag(args.tag)
        kb.print_symbol_brief(results, limit=100)

    elif args.cmd == "module":
        results = kb.list_module_symbols(args.module, args.kinds)
        kb.print_symbol_brief(results, limit=100)

    elif args.cmd == "related":
        result = kb.find_related_symbols(args.query)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()