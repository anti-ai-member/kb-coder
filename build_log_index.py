#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Optional


IGNORE_DIRS = {
    ".git", ".idea", ".gradle", "build", "out", "dist", "target",
    "node_modules", "__pycache__"
}

SOURCE_EXTS = {".java", ".kt"}

PACKAGE_PAT = re.compile(r'^\s*package\s+([a-zA-Z0-9_.]+)', re.MULTILINE)

CLASS_PAT = re.compile(
    r'\b(class|interface|enum|object)\s+([A-Za-z_][A-Za-z0-9_]*)'
)

JAVA_METHOD_PAT = re.compile(
    r'^\s*'
    r'(?:@[\w.]+(?:\([^)]*\))?\s*)*'
    r'(?:public|private|protected)?\s*'
    r'(?:static\s+)?'
    r'(?:final\s+)?'
    r'(?:synchronized\s+)?'
    r'(?:abstract\s+)?'
    r'(?:native\s+)?'
    r'(?:default\s+)?'
    r'(?:[\w<>\[\],.?]+\s+)+'
    r'([A-Za-z_][A-Za-z0-9_]*)\s*\('
)

KOTLIN_FUN_PAT = re.compile(
    r'^\s*(?:override\s+)?(?:suspend\s+)?fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('
)

CONST_STRING_PAT = re.compile(
    r'^\s*(?:public|private|protected|internal)?\s*'
    r'(?:static\s+final\s+|final\s+static\s+|const\s+val\s+|val\s+|var\s+)?'
    r'(?:String\s+)?'
    r'([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]*)"'
)

# 常见日志调用
LOG_CALL_PATTERNS = [
    # Log.d(TAG, "...")
    re.compile(r'\b(Log|Slog)\.(v|d|i|w|e|wtf)\s*\((.*)\)\s*;?'),
    # Timber.d("...")
    re.compile(r'\bTimber\.(v|d|i|w|e|wtf)\s*\((.*)\)\s*;?'),
    # Timber.tag("X").d("...")
    re.compile(r'\bTimber\.tag\s*\((.*?)\)\.(v|d|i|w|e|wtf)\s*\((.*)\)\s*;?'),
    # System.out.println("...")
    re.compile(r'\bSystem\.out\.println\s*\((.*)\)\s*;?'),
    re.compile(r'^\s*println\s*\((.*)\)\s*;?'),
    # 启发式：Logger.d(...), L.e(...)
    re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\.(v|d|i|w|e)\s*\((.*)\)\s*;?'),
]

LEVEL_MAP = {
    "v": "VERBOSE",
    "d": "DEBUG",
    "i": "INFO",
    "w": "WARN",
    "e": "ERROR",
    "wtf": "FATAL",
    "println": "INFO",
}

CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "return", "throw", "when"}


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def safe_read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc, errors="replace")
        except Exception:
            pass
    return ""


def get_package(text: str) -> Optional[str]:
    m = PACKAGE_PAT.search(text)
    return m.group(1) if m else None


def tokenize_message(msg: str) -> List[str]:
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]+', msg.lower())
    stop = {
        "the", "and", "for", "with", "this", "that", "from",
        "tag", "log", "debug", "error", "warn", "info"
    }
    out = []
    seen = set()
    for t in tokens:
        if t in stop:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:20]


def split_top_level_args(arg_text: str) -> List[str]:
    args = []
    buf = []
    depth = 0
    in_str = False
    escape = False

    for ch in arg_text:
        if in_str:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            buf.append(ch)
            continue

        if ch in "([{":
            depth += 1
            buf.append(ch)
            continue

        if ch in ")]}":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue

        if ch == ',' and depth == 0:
            args.append(''.join(buf).strip())
            buf = []
            continue

        buf.append(ch)

    if buf:
        args.append(''.join(buf).strip())

    return args


def extract_string_literals(expr: str) -> List[str]:
    return re.findall(r'"([^"]*)"', expr)


def normalize_message_expr(expr: str) -> str:
    literals = extract_string_literals(expr)
    if literals:
        joined = " ".join(x.strip() for x in literals if x.strip())
        joined = re.sub(r'\s+', ' ', joined).strip()
        if joined:
            return joined

    # 没有字符串字面量时，退化成表达式模板
    text = expr.strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:200]


def infer_preview(template: str) -> str:
    preview = re.sub(r'%[sdifbcoxeg]', '', template, flags=re.IGNORECASE)
    preview = re.sub(r'\s+', ' ', preview).strip()
    return preview[:120]


def level_from_method(method_name: str) -> str:
    return LEVEL_MAP.get(method_name.lower(), "INFO")


def hash_id(file: str, line_no: int, raw_call: str) -> str:
    return hashlib.md5(f"{file}:{line_no}:{raw_call}".encode("utf-8")).hexdigest()


def detect_log_call(line: str) -> Optional[Dict]:
    s = line.strip()
    for pat in LOG_CALL_PATTERNS:
        m = pat.search(s)
        if not m:
            continue

        if "System.out.println" in s:
            return {
                "logger": "System.out",
                "method": "println",
                "tag_expr": None,
                "msg_expr": m.group(1).strip()
            }

        if s.startswith("println(") or s.startswith("println "):
            return {
                "logger": "println",
                "method": "println",
                "tag_expr": None,
                "msg_expr": m.group(1).strip()
            }

        if "Timber.tag" in s:
            return {
                "logger": "Timber",
                "method": m.group(2),
                "tag_expr": m.group(1).strip(),
                "msg_expr": m.group(3).strip()
            }

        if s.startswith("Timber."):
            return {
                "logger": "Timber",
                "method": m.group(1),
                "tag_expr": None,
                "msg_expr": m.group(2).strip()
            }

        if s.startswith("Log.") or s.startswith("Slog."):
            logger = m.group(1)
            method = m.group(2)
            arg_text = m.group(3).strip()
            args = split_top_level_args(arg_text)

            tag_expr = args[0] if len(args) >= 1 else None
            msg_expr = args[1] if len(args) >= 2 else None

            return {
                "logger": logger,
                "method": method,
                "tag_expr": tag_expr,
                "msg_expr": msg_expr
            }

        # 自定义 Logger.d(...)
        logger = m.group(1)
        method = m.group(2)
        arg_text = m.group(3).strip()
        args = split_top_level_args(arg_text)

        tag_expr = args[0] if len(args) >= 1 else None
        msg_expr = args[1] if len(args) >= 2 else args[0] if len(args) == 1 else None

        return {
            "logger": logger,
            "method": method,
            "tag_expr": tag_expr,
            "msg_expr": msg_expr
        }

    return None


def resolve_tag(tag_expr: Optional[str], const_map: Dict[str, str], class_name: Optional[str]) -> Optional[str]:
    if not tag_expr:
        return class_name

    tag_expr = tag_expr.strip()

    # "VoiceService"
    m = re.match(r'^"([^"]*)"$', tag_expr)
    if m:
        return m.group(1)

    # TAG
    if tag_expr in const_map:
        return const_map[tag_expr]

    # SomeClass.TAG
    m = re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.([A-Z_][A-Z0-9_]*)$', tag_expr)
    if m and m.group(1) in const_map:
        return const_map[m.group(1)]

    # this.TAG / Companion.TAG 等复杂写法先退化
    return tag_expr[:80]


def detect_language(path: Path) -> str:
    if path.suffix.lower() == ".java":
        return "java"
    if path.suffix.lower() == ".kt":
        return "kotlin"
    return "unknown"


def collect_string_constants(lines: List[str]) -> Dict[str, str]:
    const_map = {}
    for line in lines:
        m = CONST_STRING_PAT.match(line.strip())
        if m:
            const_map[m.group(1)] = m.group(2)
    return const_map


def scan_source_file(file_path: Path, root: Path) -> List[Dict]:
    text = safe_read_text(file_path)
    if not text:
        return []

    language = detect_language(file_path)
    package_name = get_package(text)
    lines = text.splitlines()
    const_map = collect_string_constants(lines)

    results = []

    class_stack: List[Dict] = []
    method_stack: List[Dict] = []
    brace_depth = 0

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # class enter
        cm = CLASS_PAT.search(line)
        if cm:
            class_name = cm.group(2)
            qualified = f"{package_name}.{class_name}" if package_name else class_name
            class_stack.append({
                "name": class_name,
                "qualified_name": qualified,
                "brace_depth": None,
            })

        # method enter
        method_name = None
        if language == "java":
            mm = JAVA_METHOD_PAT.search(line)
            if mm and mm.group(1) not in CONTROL_WORDS:
                method_name = mm.group(1)
        elif language == "kotlin":
            mm = KOTLIN_FUN_PAT.search(line)
            if mm:
                method_name = mm.group(1)

        if method_name:
            method_stack.append({
                "name": method_name,
                "brace_depth": None,
            })

        # detect log call
        log_call = detect_log_call(line)
        if log_call:
            class_name = class_stack[-1]["name"] if class_stack else None
            method_name = method_stack[-1]["name"] if method_stack else None

            tag = resolve_tag(log_call.get("tag_expr"), const_map, class_name)
            msg_expr = log_call.get("msg_expr") or ""
            message_template = normalize_message_expr(msg_expr)
            message_preview = infer_preview(message_template)
            message_tokens = tokenize_message(message_preview or message_template)

            log_method = f'{log_call["logger"]}.{log_call["method"]}'
            level = level_from_method(log_call["method"])

            rel_file = str(file_path.relative_to(root)).replace("\\", "/")
            raw_call = raw_line.strip()

            results.append({
                "id": hash_id(rel_file, idx, raw_call),
                "tag": tag,
                "message_template": message_template,
                "message_preview": message_preview,
                "message_tokens": message_tokens,
                "class_name": class_name,
                "method_name": method_name,
                "qualified_class_name": class_stack[-1]["qualified_name"] if class_stack else None,
                "file": rel_file,
                "line_no": idx,
                "language": language,
                "log_method": log_method,
                "level": level,
                "raw_call": raw_call,
            })

        # brace handling
        open_count = raw_line.count("{")
        close_count = raw_line.count("}")

        if open_count > 0:
            for stack in (class_stack, method_stack):
                if stack and stack[-1]["brace_depth"] is None:
                    stack[-1]["brace_depth"] = brace_depth + open_count - close_count

        brace_depth += open_count
        brace_depth -= close_count

        while class_stack and class_stack[-1]["brace_depth"] is not None and brace_depth < class_stack[-1]["brace_depth"]:
            class_stack.pop()

        while method_stack and method_stack[-1]["brace_depth"] is not None and brace_depth < method_stack[-1]["brace_depth"]:
            method_stack.pop()

    return results


def iter_source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_ignore(path):
            continue
        if path.suffix.lower() in SOURCE_EXTS:
            yield path


def build_log_index_map(repo_root: str, output_jsonl: str, stats_json: str):
    root = Path(repo_root)
    if not root.exists():
        raise FileNotFoundError(f"repo root not found: {repo_root}")

    all_records = []
    level_counter = {}
    method_counter = {}
    tag_counter = {}

    total_files = 0

    for path in iter_source_files(root):
        total_files += 1
        recs = scan_source_file(path, root)
        all_records.extend(recs)

        for r in recs:
            level_counter[r["level"]] = level_counter.get(r["level"], 0) + 1
            method_counter[r["log_method"]] = method_counter.get(r["log_method"], 0) + 1
            if r["tag"]:
                tag_counter[r["tag"]] = tag_counter.get(r["tag"], 0) + 1

    with open(output_jsonl, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats = {
        "repo_root": str(root),
        "total_source_files": total_files,
        "total_log_calls": len(all_records),
        "top_levels": sorted(level_counter.items(), key=lambda x: x[1], reverse=True)[:20],
        "top_log_methods": sorted(method_counter.items(), key=lambda x: x[1], reverse=True)[:20],
        "top_tags": sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:50],
    }

    with open(stats_json, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"Scanned source files: {total_files}")
    print(f"Indexed log calls: {len(all_records)}")
    print(f"Output JSONL: {output_jsonl}")
    print(f"Stats JSON: {stats_json}")


def main():
    if len(sys.argv) != 4:
        print("Usage:")
        print("  python build_log_index.py <repo_root> <output_jsonl> <stats_json>")
        sys.exit(1)

    repo_root = sys.argv[1]
    output_jsonl = sys.argv[2]
    stats_json = sys.argv[3]

    build_log_index_map(repo_root, output_jsonl, stats_json)


if __name__ == "__main__":
    main()