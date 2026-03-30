#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from .query_log_index import LogIndexMap


class LogTools:
    """封装对「源码日志调用索引」的查询；索引由 build_log_index.py 从 .java/.kt 扫描生成。"""

    def __init__(self, index_path: str) -> None:
        self.index = LogIndexMap(index_path)

    @staticmethod
    def _filter_kwargs(
        *,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        label: Optional[str] = None,
        file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """MCP 的 label 对应索引里的 message_token 过滤。"""
        return {
            "keyword": keyword,
            "level": level,
            "tag": tag,
            "token": label,
            "file": file,
        }

    def search_logs(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        label: Optional[str] = None,
        file: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        fk = self._filter_kwargs(
            keyword=keyword, level=level, tag=tag, label=label, file=file
        )
        results = self.index.search(**fk, limit=limit)
        return {
            "query": {
                "keyword": keyword,
                "level": level,
                "tag": tag,
                "label": label,
                "file": file,
                "limit": limit,
            },
            "count": len(results),
            "results": [self._compact_record(r) for r in results],
        }

    def summarize_logs(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        label: Optional[str] = None,
        file: Optional[str] = None,
    ) -> Dict[str, Any]:
        fk = self._filter_kwargs(
            keyword=keyword, level=level, tag=tag, label=label, file=file
        )
        summary = self.index.summary(**fk)
        return {
            "query": {
                "keyword": keyword,
                "level": level,
                "tag": tag,
                "label": label,
                "file": file,
            },
            "summary": summary,
        }

    def group_log_fingerprints(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        label: Optional[str] = None,
        file: Optional[str] = None,
        limit: int = 15,
    ) -> Dict[str, Any]:
        fk = self._filter_kwargs(
            keyword=keyword, level=level, tag=tag, label=label, file=file
        )
        raw = self.index.group_by_message_template(**fk, limit=limit)
        groups = [
            {
                "group_key": f"{g.get('tag') or ''} | {g.get('message_template') or ''}",
                "count": g["count"],
                "sample": g.get("sample"),
            }
            for g in raw
        ]
        return {
            "query": {
                "keyword": keyword,
                "level": level,
                "tag": tag,
                "label": label,
                "file": file,
                "limit": limit,
            },
            "count": len(groups),
            "groups": groups,
        }

    def find_suspicious_tags(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        label: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        fk = self._filter_kwargs(
            keyword=keyword, level=level, tag=None, label=label, file=None
        )
        rows = self.index.filter_records(**fk)
        c = Counter(str(r["tag"]) for r in rows if r.get("tag"))
        top_tags = c.most_common(limit)
        return {
            "query": {
                "keyword": keyword,
                "level": level,
                "label": label,
                "limit": limit,
            },
            "tags": [{"tag": t, "count": n} for t, n in top_tags],
        }

    def find_suspicious_files(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        label: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        fk = self._filter_kwargs(
            keyword=keyword, level=level, tag=None, label=label, file=None
        )
        rows = self.index.filter_records(**fk)
        c = Counter(str(r["file"]) for r in rows if r.get("file"))
        top_files = c.most_common(limit)
        return {
            "query": {
                "keyword": keyword,
                "level": level,
                "label": label,
                "limit": limit,
            },
            "files": [{"file": f, "count": n} for f, n in top_files],
        }

    def analyze_log_issue(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        label: Optional[str] = None,
        file: Optional[str] = None,
        sample_limit: int = 10,
        group_limit: int = 10,
    ) -> Dict[str, Any]:
        summary = self.summarize_logs(
            keyword=keyword,
            level=level,
            tag=tag,
            label=label,
            file=file,
        )
        groups = self.group_log_fingerprints(
            keyword=keyword,
            level=level,
            tag=tag,
            label=label,
            file=file,
            limit=group_limit,
        )
        samples = self.search_logs(
            keyword=keyword,
            level=level,
            tag=tag,
            label=label,
            file=file,
            limit=sample_limit,
        )
        suspicious_tags = self.find_suspicious_tags(
            keyword=keyword,
            level=level,
            label=label,
            limit=10,
        )
        suspicious_files = self.find_suspicious_files(
            keyword=keyword,
            level=level,
            label=label,
            limit=10,
        )
        return {
            "query": {
                "keyword": keyword,
                "level": level,
                "tag": tag,
                "label": label,
                "file": file,
            },
            "summary": summary["summary"],
            "top_groups": groups["groups"],
            "sample_records": samples["results"],
            "top_tags": suspicious_tags["tags"],
            "top_files": suspicious_files["files"],
        }

    def _compact_record(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": r.get("id"),
            "file": r.get("file"),
            "line_no": r.get("line_no"),
            "language": r.get("language"),
            "level": r.get("level"),
            "tag": r.get("tag"),
            "log_method": r.get("log_method"),
            "class_name": r.get("class_name"),
            "method_name": r.get("method_name"),
            "qualified_class_name": r.get("qualified_class_name"),
            "message_preview": r.get("message_preview"),
            "message_template": r.get("message_template"),
            "message_tokens": list(r.get("message_tokens") or []),
            "raw_call": r.get("raw_call"),
        }
