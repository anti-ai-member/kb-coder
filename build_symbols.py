#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional


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
    r'(?:[\w<>\[\],.?]+\s+)+'   # 返回值
    r'([A-Za-z_][A-Za-z0-9_]*)\s*'
    r'\('
)

KOTLIN_FUN_PAT = re.compile(
    r'^\s*(?:override\s+)?(?:suspend\s+)?fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('
)

JAVA_CONST_PAT = re.compile(
    r'^\s*(?:public|private|protected)?\s*'
    r'(?:static\s+final|final\s+static)\s+'
    r'[\w<>\[\],.?"]+\s+'
    r'([A-Z_][A-Z0-9_]*)\b'
)

KOTLIN_CONST_PAT = re.compile(
    r'^\s*(?:public|private|internal)?\s*const\s+val\s+([A-Z_][A-Z0-9_]*)\b'
)

KOTLIN_VAL_PAT = re.compile(
    r'^\s*(?:public|private|internal)?\s*(?:val|var)\s+([A-Z_][A-Z0-9_]*)\b'
)

AIDL_INTERFACE_PAT = re.compile(
    r'^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{?'
)

AIDL_METHOD_PAT = re.compile(
    r'^\s*(?:oneway\s+)?([A-Za-z_][A-Za-z0-9_<>\[\].]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;]*)\)\s*;'
)

CONTROL_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "throw", "else", "when"
}


def load_jsonl(path: Path) -> List[Dict]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def safe_read_text(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    return ""


def get_package(text: str) -> Optional[str]:
    m = PACKAGE_PAT.search(text)
    return m.group(1) if m else None


def guess_visibility(line: str, language: str) -> str:
    if re.search(r'\bpublic\b', line):
        return "public"
    if re.search(r'\bprotected\b', line):
        return "protected"
    if re.search(r'\bprivate\b', line):
        return "private"
    if language == "kotlin" and re.search(r'\binternal\b', line):
        return "internal"
    return "default"


def looks_like_comment(line: str) -> bool:
    s = line.strip()
    return (
        s.startswith("//") or
        s.startswith("*") or
        s.startswith("/*") or
        s.startswith("*/")
    )


def looks_like_control_statement(line: str) -> bool:
    s = line.strip()
    for kw in CONTROL_KEYWORDS:
        if s.startswith(kw + " ") or s.startswith(kw + "("):
            return True
    return False


def infer_tags(name: str, kind: str, signature: str, file_path: str) -> List[str]:
    tags = set()
    low_name = name.lower()
    low_sig = signature.lower()
    low_path = file_path.lower()

    if kind in {"class", "object", "interface"}:
        if "service" in low_name:
            tags.add("service")
        if "manager" in low_name:
            tags.add("manager")
        if "controller" in low_name:
            tags.add("controller")
        if "dispatcher" in low_name:
            tags.add("dispatcher")
        if "client" in low_name:
            tags.add("client")
        if "callback" in low_name:
            tags.add("callback")
        if "listener" in low_name:
            tags.add("listener")
        if "receiver" in low_name:
            tags.add("receiver")
        if "binder" in low_name or "stub" in low_name:
            tags.add("binder")
        if "session" in low_name:
            tags.add("session")
        if "voice" in low_name:
            tags.add("voice")
        if "asr" in low_name:
            tags.add("asr")
        if "tts" in low_name:
            tags.add("tts")
        if "nlu" in low_name:
            tags.add("nlu")

    if kind == "method":
        if name.startswith("on"):
            tags.add("callback_method")
        if name.startswith("start") or name.startswith("init") or name.startswith("bind"):
            tags.add("lifecycle_or_start")
        if name.startswith("stop") or name.startswith("release") or name.startswith("destroy"):
            tags.add("lifecycle_or_stop")
        if "dispatch" in low_name:
            tags.add("dispatch")
        if "callback" in low_name:
            tags.add("callback")
        if "message" in low_name or "msg" in low_name:
            tags.add("message")
        if "session" in low_name:
            tags.add("session")
        if "voice" in low_name:
            tags.add("voice")

    if kind in {"aidl_interface", "aidl_method"}:
        tags.add("ipc")

    if "androidmanifest.xml" in low_path:
        tags.add("manifest")
    if ".aidl" in low_path:
        tags.add("aidl")

    if "extends service" in low_sig or ": service(" in low_sig:
        tags.add("service_entry")
    if "broadcastreceiver" in low_sig:
        tags.add("receiver")

    return sorted(tags)


def build_symbol_record(
    *,
    symbol: str,
    kind: str,
    name: str,
    qualified_name: str,
    file_item: Dict,
    line: int,
    end_line: Optional[int],
    signature: str,
    container: Optional[str],
    visibility: str,
    tags: List[str]
) -> Dict:
    return {
        "symbol": symbol,
        "kind": kind,
        "name": name,
        "qualified_name": qualified_name,
        "file": file_item["path"],
        "module": file_item.get("module", ""),
        "language": file_item.get("language", "unknown"),
        "line": line,
        "end_line": end_line,
        "signature": signature.strip(),
        "container": container,
        "visibility": visibility,
        "is_definition": True,
        "tags": tags,
        "summary": ""
    }


def extract_java_kotlin_symbols(file_item: Dict, repo_root: Path) -> List[Dict]:
    file_path = repo_root / file_item["path"]
    text = safe_read_text(file_path)
    if not text:
        return []

    language = file_item["language"]
    package_name = get_package(text)
    lines = text.splitlines()

    results: List[Dict] = []
    class_stack: List[Dict] = []
    brace_depth = 0

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        if not line or looks_like_comment(line):
            brace_depth += raw_line.count("{")
            brace_depth -= raw_line.count("}")
            while class_stack and brace_depth < class_stack[-1]["brace_depth"]:
                class_stack.pop()
            continue

        # 1) class/interface/enum/object
        class_match = CLASS_PAT.search(line)
        if class_match:
            kind = class_match.group(1)
            name = class_match.group(2)

            container = class_stack[-1]["symbol"] if class_stack else None
            symbol = f"{container}.{name}" if container else name
            qualified_name = f"{package_name}.{symbol}" if package_name else symbol
            visibility = guess_visibility(line, language)
            tags = infer_tags(name, kind, line, file_item["path"])

            results.append(build_symbol_record(
                symbol=symbol,
                kind=kind,
                name=name,
                qualified_name=qualified_name,
                file_item=file_item,
                line=idx,
                end_line=None,
                signature=line,
                container=container,
                visibility=visibility,
                tags=tags
            ))

            open_count = raw_line.count("{")
            close_count = raw_line.count("}")
            predicted_depth = brace_depth + open_count - close_count
            if open_count > 0:
                stack_depth = predicted_depth
            else:
                stack_depth = brace_depth + 1

            class_stack.append({
                "name": name,
                "symbol": symbol,
                "brace_depth": stack_depth
            })

        # 2) method / fun
        method_name = None
        if language == "java":
            m = JAVA_METHOD_PAT.search(line)
            if m and not looks_like_control_statement(line):
                method_name = m.group(1)
        elif language == "kotlin":
            m = KOTLIN_FUN_PAT.search(line)
            if m:
                method_name = m.group(1)

        if method_name and class_stack:
            if method_name not in CONTROL_KEYWORDS:
                container = class_stack[-1]["symbol"]
                symbol = f"{container}.{method_name}"
                qualified_name = f"{package_name}.{symbol}" if package_name else symbol
                visibility = guess_visibility(line, language)
                tags = infer_tags(method_name, "method", line, file_item["path"])

                results.append(build_symbol_record(
                    symbol=symbol,
                    kind="method",
                    name=method_name,
                    qualified_name=qualified_name,
                    file_item=file_item,
                    line=idx,
                    end_line=None,
                    signature=line,
                    container=container,
                    visibility=visibility,
                    tags=tags
                ))

        # 3) constants
        const_names = []
        if language == "java":
            const_names.extend(JAVA_CONST_PAT.findall(line))
        elif language == "kotlin":
            const_names.extend(KOTLIN_CONST_PAT.findall(line))
            const_names.extend(KOTLIN_VAL_PAT.findall(line))

        for const_name in const_names:
            container = class_stack[-1]["symbol"] if class_stack else None
            symbol = f"{container}.{const_name}" if container else const_name
            qualified_name = f"{package_name}.{symbol}" if package_name else symbol
            visibility = guess_visibility(line, language)
            tags = infer_tags(const_name, "constant", line, file_item["path"])

            results.append(build_symbol_record(
                symbol=symbol,
                kind="constant",
                name=const_name,
                qualified_name=qualified_name,
                file_item=file_item,
                line=idx,
                end_line=None,
                signature=line,
                container=container,
                visibility=visibility,
                tags=tags
            ))

        # 4) brace update
        brace_depth += raw_line.count("{")
        brace_depth -= raw_line.count("}")

        while class_stack and brace_depth < class_stack[-1]["brace_depth"]:
            class_stack.pop()

    return dedupe_symbols(results)


def extract_aidl_symbols(file_item: Dict, repo_root: Path) -> List[Dict]:
    file_path = repo_root / file_item["path"]
    text = safe_read_text(file_path)
    if not text:
        return []

    package_name = get_package(text)
    lines = text.splitlines()
    results: List[Dict] = []

    current_interface = None
    current_qn = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or looks_like_comment(line):
            continue

        im = AIDL_INTERFACE_PAT.search(line)
        if im:
            name = im.group(1)
            current_interface = name
            current_qn = f"{package_name}.{name}" if package_name else name

            results.append(build_symbol_record(
                symbol=name,
                kind="aidl_interface",
                name=name,
                qualified_name=current_qn,
                file_item=file_item,
                line=idx,
                end_line=None,
                signature=line,
                container=None,
                visibility="public",
                tags=infer_tags(name, "aidl_interface", line, file_item["path"])
            ))
            continue

        mm = AIDL_METHOD_PAT.search(line)
        if mm and current_interface:
            return_type = mm.group(1)
            method_name = mm.group(2)
            params = mm.group(3)

            symbol = f"{current_interface}.{method_name}"
            qn = f"{current_qn}.{method_name}" if current_qn else symbol
            signature = f"{return_type} {method_name}({params})"

            results.append(build_symbol_record(
                symbol=symbol,
                kind="aidl_method",
                name=method_name,
                qualified_name=qn,
                file_item=file_item,
                line=idx,
                end_line=None,
                signature=signature,
                container=current_interface,
                visibility="public",
                tags=infer_tags(method_name, "aidl_method", signature, file_item["path"])
            ))

    return dedupe_symbols(results)


def dedupe_symbols(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for item in items:
        key = (
            item["symbol"],
            item["kind"],
            item["file"],
            item["line"]
        )
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def should_process(file_item: Dict) -> bool:
    if file_item.get("is_generated"):
        return False
    if file_item.get("file_type") not in {"source", "aidl"}:
        return False
    if file_item.get("language") not in {"java", "kotlin", "aidl"}:
        return False
    return True


def build_symbols(files_jsonl_path: str, repo_root: str, output_path: str) -> None:
    files = load_jsonl(Path(files_jsonl_path))
    repo_root_path = Path(repo_root)

    total_files = 0
    total_symbols = 0

    with Path(output_path).open("w", encoding="utf-8") as out:
        for file_item in files:
            if not should_process(file_item):
                continue

            total_files += 1
            lang = file_item["language"]

            if lang in {"java", "kotlin"}:
                symbols = extract_java_kotlin_symbols(file_item, repo_root_path)
            elif lang == "aidl":
                symbols = extract_aidl_symbols(file_item, repo_root_path)
            else:
                symbols = []

            for s in symbols:
                out.write(json.dumps(s, ensure_ascii=False) + "\n")
                total_symbols += 1

    print(f"Processed files: {total_files}")
    print(f"Generated symbols: {total_symbols}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage:")
        print("  python build_symbols.py <files.jsonl> <repo_root> <symbols.jsonl>")
        sys.exit(1)

    files_jsonl = sys.argv[1]
    repo_root = sys.argv[2]
    output_jsonl = sys.argv[3]

    build_symbols(files_jsonl, repo_root, output_jsonl)