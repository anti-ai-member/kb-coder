#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any, Optional


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


class LogIndexMap:
    def __init__(self, index_path: str):
        self.records = load_jsonl(Path(index_path))

    # -------------------------
    # 基础匹配
    # -------------------------

    def _match_keyword(self, record: Dict[str, Any], keyword: str) -> bool:
        q = keyword.lower().strip()
        haystacks = [
            record.get("tag") or "",
            record.get("message_template") or "",
            record.get("message_preview") or "",
            record.get("class_name") or "",
            record.get("method_name") or "",
            record.get("qualified_class_name") or "",
            record.get("file") or "",
            record.get("raw_call") or "",
            " ".join(record.get("message_tokens", [])),
        ]
        return any(q in h.lower() for h in haystacks)

    def _match_token(self, record: Dict[str, Any], token: str) -> bool:
        q = token.lower().strip()
        return q in [x.lower() for x in record.get("message_tokens", [])]

    def filter_records(
        self,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None,
        file: Optional[str] = None,
        language: Optional[str] = None,
        level: Optional[str] = None,
        log_method: Optional[str] = None,
        token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []

        for r in self.records:
            if keyword and not self._match_keyword(r, keyword):
                continue
            if tag and tag.lower() not in (r.get("tag") or "").lower():
                continue
            if class_name and class_name.lower() not in (r.get("class_name") or "").lower():
                continue
            if method_name and method_name.lower() not in (r.get("method_name") or "").lower():
                continue
            if file and file.lower() not in (r.get("file") or "").lower():
                continue
            if language and language.lower() != (r.get("language") or "").lower():
                continue
            if level and level.upper() != (r.get("level") or "").upper():
                continue
            if log_method and log_method.lower() not in (r.get("log_method") or "").lower():
                continue
            if token and not self._match_token(r, token):
                continue

            results.append(r)

        return results

    # -------------------------
    # 查询
    # -------------------------

    def search(
        self,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None,
        file: Optional[str] = None,
        language: Optional[str] = None,
        level: Optional[str] = None,
        log_method: Optional[str] = None,
        token: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = self.filter_records(
            keyword=keyword,
            tag=tag,
            class_name=class_name,
            method_name=method_name,
            file=file,
            language=language,
            level=level,
            log_method=log_method,
            token=token,
        )
        return results[:limit]

    def summary(
        self,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None,
        file: Optional[str] = None,
        language: Optional[str] = None,
        level: Optional[str] = None,
        log_method: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        results = self.filter_records(
            keyword=keyword,
            tag=tag,
            class_name=class_name,
            method_name=method_name,
            file=file,
            language=language,
            level=level,
            log_method=log_method,
            token=token,
        )

        tag_counter = Counter()
        class_counter = Counter()
        method_counter = Counter()
        file_counter = Counter()
        level_counter = Counter()
        log_method_counter = Counter()
        token_counter = Counter()

        for r in results:
            if r.get("tag"):
                tag_counter[r["tag"]] += 1
            if r.get("class_name"):
                class_counter[r["class_name"]] += 1
            if r.get("method_name"):
                method_counter[r["method_name"]] += 1
            if r.get("file"):
                file_counter[r["file"]] += 1
            if r.get("level"):
                level_counter[r["level"]] += 1
            if r.get("log_method"):
                log_method_counter[r["log_method"]] += 1
            for t in r.get("message_tokens", []):
                token_counter[t] += 1

        return {
            "count": len(results),
            "top_tags": tag_counter.most_common(20),
            "top_classes": class_counter.most_common(20),
            "top_methods": method_counter.most_common(20),
            "top_files": file_counter.most_common(20),
            "top_levels": level_counter.most_common(20),
            "top_log_methods": log_method_counter.most_common(20),
            "top_tokens": token_counter.most_common(30),
        }

    def top_tags(self, limit: int = 50) -> List[List[Any]]:
        counter = Counter()
        for r in self.records:
            if r.get("tag"):
                counter[r["tag"]] += 1
        return counter.most_common(limit)

    def top_classes(self, limit: int = 50) -> List[List[Any]]:
        counter = Counter()
        for r in self.records:
            if r.get("class_name"):
                counter[r["class_name"]] += 1
        return counter.most_common(limit)

    def top_methods(self, limit: int = 50) -> List[List[Any]]:
        counter = Counter()
        for r in self.records:
            if r.get("method_name"):
                counter[r["method_name"]] += 1
        return counter.most_common(limit)

    def top_files(self, limit: int = 50) -> List[List[Any]]:
        counter = Counter()
        for r in self.records:
            if r.get("file"):
                counter[r["file"]] += 1
        return counter.most_common(limit)

    def group_by_message_template(
        self,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None,
        file: Optional[str] = None,
        language: Optional[str] = None,
        level: Optional[str] = None,
        log_method: Optional[str] = None,
        token: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = self.filter_records(
            keyword=keyword,
            tag=tag,
            class_name=class_name,
            method_name=method_name,
            file=file,
            language=language,
            level=level,
            log_method=log_method,
            token=token,
        )

        groups: Dict[str, Dict[str, Any]] = {}

        for r in results:
            key = (r.get("tag") or "") + " | " + (r.get("message_template") or "")
            if key not in groups:
                groups[key] = {
                    "tag": r.get("tag"),
                    "message_template": r.get("message_template"),
                    "count": 0,
                    "sample": r,
                    "classes": Counter(),
                    "methods": Counter(),
                    "files": Counter(),
                    "levels": Counter(),
                }

            groups[key]["count"] += 1
            if r.get("class_name"):
                groups[key]["classes"][r["class_name"]] += 1
            if r.get("method_name"):
                groups[key]["methods"][r["method_name"]] += 1
            if r.get("file"):
                groups[key]["files"][r["file"]] += 1
            if r.get("level"):
                groups[key]["levels"][r["level"]] += 1

        items = []
        for _, g in groups.items():
            items.append({
                "tag": g["tag"],
                "message_template": g["message_template"],
                "count": g["count"],
                "sample": self._compact_record(g["sample"]),
                "top_classes": g["classes"].most_common(10),
                "top_methods": g["methods"].most_common(10),
                "top_files": g["files"].most_common(10),
                "top_levels": g["levels"].most_common(10),
            })

        items.sort(key=lambda x: x["count"], reverse=True)
        return items[:limit]

    # -------------------------
    # 输出辅助
    # -------------------------

    def _compact_record(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "tag": r.get("tag"),
            "message_template": r.get("message_template"),
            "message_preview": r.get("message_preview"),
            "class_name": r.get("class_name"),
            "method_name": r.get("method_name"),
            "qualified_class_name": r.get("qualified_class_name"),
            "file": r.get("file"),
            "line_no": r.get("line_no"),
            "language": r.get("language"),
            "log_method": r.get("log_method"),
            "level": r.get("level"),
        }

    def print_records(self, records: List[Dict[str, Any]], limit: int = 50):
        for r in records[:limit]:
            print(json.dumps(self._compact_record(r), ensure_ascii=False, indent=2))

    def print_json(self, data: Any):
        print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query Android source log index map")
    parser.add_argument("--index", required=True, help="Path to log_index_map.jsonl")

    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common_filters(p):
        p.add_argument("--keyword", default=None)
        p.add_argument("--tag", default=None)
        p.add_argument("--class-name", default=None)
        p.add_argument("--method-name", default=None)
        p.add_argument("--file", default=None)
        p.add_argument("--language", default=None)
        p.add_argument("--level", default=None)
        p.add_argument("--log-method", default=None)
        p.add_argument("--token", default=None)

    p1 = sub.add_parser("search", help="Search log mapping records")
    add_common_filters(p1)
    p1.add_argument("--limit", type=int, default=50)

    p2 = sub.add_parser("summary", help="Summary of filtered log mapping records")
    add_common_filters(p2)

    p3 = sub.add_parser("group-template", help="Group by tag + message_template")
    add_common_filters(p3)
    p3.add_argument("--limit", type=int, default=50)

    p4 = sub.add_parser("top-tags", help="Top tags")
    p4.add_argument("--limit", type=int, default=50)

    p5 = sub.add_parser("top-classes", help="Top classes")
    p5.add_argument("--limit", type=int, default=50)

    p6 = sub.add_parser("top-methods", help="Top methods")
    p6.add_argument("--limit", type=int, default=50)

    p7 = sub.add_parser("top-files", help="Top files")
    p7.add_argument("--limit", type=int, default=50)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    idx = LogIndexMap(args.index)

    if args.cmd == "search":
        results = idx.search(
            keyword=args.keyword,
            tag=args.tag,
            class_name=args.class_name,
            method_name=args.method_name,
            file=args.file,
            language=args.language,
            level=args.level,
            log_method=args.log_method,
            token=args.token,
            limit=args.limit,
        )
        idx.print_records(results, limit=args.limit)

    elif args.cmd == "summary":
        result = idx.summary(
            keyword=args.keyword,
            tag=args.tag,
            class_name=args.class_name,
            method_name=args.method_name,
            file=args.file,
            language=args.language,
            level=args.level,
            log_method=args.log_method,
            token=args.token,
        )
        idx.print_json(result)

    elif args.cmd == "group-template":
        result = idx.group_by_message_template(
            keyword=args.keyword,
            tag=args.tag,
            class_name=args.class_name,
            method_name=args.method_name,
            file=args.file,
            language=args.language,
            level=args.level,
            log_method=args.log_method,
            token=args.token,
            limit=args.limit,
        )
        idx.print_json(result)

    elif args.cmd == "top-tags":
        idx.print_json(idx.top_tags(limit=args.limit))

    elif args.cmd == "top-classes":
        idx.print_json(idx.top_classes(limit=args.limit))

    elif args.cmd == "top-methods":
        idx.print_json(idx.top_methods(limit=args.limit))

    elif args.cmd == "top-files":
        idx.print_json(idx.top_files(limit=args.limit))


if __name__ == "__main__":
    main()