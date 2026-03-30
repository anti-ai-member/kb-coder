#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


# -------------------------
# regex patterns
# -------------------------

IMPORT_PAT = re.compile(r'^\s*import\s+([^\s;]+)', re.MULTILINE)
PACKAGE_PAT = re.compile(r'^\s*package\s+([a-zA-Z0-9_.]+)', re.MULTILINE)

JAVA_CLASS_DECL_PAT = re.compile(
    r'\b(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)'
    r'(?:\s+extends\s+([A-Za-z0-9_$.<>]+))?'
    r'(?:\s+implements\s+([A-Za-z0-9_$.<>,\s]+))?'
)

KOTLIN_CLASS_DECL_PAT = re.compile(
    r'\b(class|interface|object)\s+([A-Za-z_][A-Za-z0-9_]*)'
    r'(?:\s*\((.*?)\))?'
    r'(?:\s*:\s*([^{]+))?'
)

# obj.method(...)
METHOD_CALL_PAT = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(')

# simpleMethod(...)
SIMPLE_CALL_PAT = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')

# Binder / Stub / asInterface hints
AIDL_HINT_PAT = re.compile(r'\b([A-Z][A-Za-z0-9_]*)(?:\.Stub|Stub|Binder|asInterface)\b')

ONBIND_PAT = re.compile(r'\bonBind\s*\(')


CONTROL_WORDS = {
    "if", "for", "while", "switch", "catch", "return", "throw", "new", "when",
    "synchronized", "try", "else", "do", "super", "this"
}


# -------------------------
# IO helpers
# -------------------------

def load_jsonl(path: Path) -> List[Dict]:
    items: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def write_jsonl(path: Path, items: List[Dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def safe_read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            pass
    return ""


# -------------------------
# utility
# -------------------------

def make_relation(
    from_symbol: str,
    to_symbol: str,
    rel_type: str,
    file_path: str,
    module: str,
    line: int,
    confidence: str,
    meta: Optional[Dict] = None
) -> Dict:
    return {
        "from": from_symbol,
        "to": to_symbol,
        "type": rel_type,
        "file": file_path,
        "line": line,
        "module": module,
        "confidence": confidence,
        "meta": meta or {}
    }


def dedupe_relations(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for item in items:
        key = (
            item["from"],
            item["to"],
            item["type"],
            item["file"],
            item["line"]
        )
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def should_process_file(file_item: Dict) -> bool:
    if file_item.get("is_generated"):
        return False
    if file_item.get("file_type") not in {"source", "aidl"}:
        return False
    if file_item.get("language") not in {"java", "kotlin", "aidl"}:
        return False
    return True


def short_type_name(full_name: str) -> str:
    """
    com.xx.voice.SessionManager -> SessionManager
    List<String> -> List
    """
    name = full_name.strip()
    if not name:
        return name
    if "." in name:
        name = name.split(".")[-1]
    if "<" in name:
        name = name.split("<", 1)[0]
    if "(" in name:
        name = name.split("(", 1)[0]
    return name.strip()


def split_kotlin_parents(parent_expr: str) -> List[str]:
    """
    Service(), IVoiceCallback, BaseController<T>
    -> ["Service", "IVoiceCallback", "BaseController"]
    """
    out = []
    for raw in parent_expr.split(","):
        p = raw.strip()
        if not p:
            continue
        if "(" in p:
            p = p.split("(", 1)[0].strip()
        if "<" in p:
            p = p.split("<", 1)[0].strip()
        out.append(p)
    return out


# -------------------------
# symbol indexes
# -------------------------

def build_symbol_indexes(symbols: List[Dict]) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]], Dict[str, Dict]]:
    by_name: Dict[str, List[Dict]] = defaultdict(list)
    by_file: Dict[str, List[Dict]] = defaultdict(list)
    by_symbol: Dict[str, Dict] = {}

    for s in symbols:
        name = s.get("name")
        if name:
            by_name[name].append(s)
        by_file[s["file"]].append(s)
        by_symbol[s["symbol"]] = s

    return by_name, by_file, by_symbol


def group_methods_by_file(symbols: List[Dict]) -> Dict[str, List[Dict]]:
    result: Dict[str, List[Dict]] = defaultdict(list)
    for s in symbols:
        if s.get("kind") in {"method", "aidl_method"}:
            result[s["file"]].append(s)
    return result


# -------------------------
# relation extractors
# -------------------------

def extract_defines_relations(symbols: List[Dict]) -> List[Dict]:
    relations: List[Dict] = []
    for s in symbols:
        container = s.get("container")
        if container:
            relations.append(
                make_relation(
                    from_symbol=container,
                    to_symbol=s["symbol"],
                    rel_type="defines",
                    file_path=s["file"],
                    module=s.get("module", ""),
                    line=s.get("line", 0),
                    confidence="high"
                )
            )
    return relations


def extract_import_relations(file_item: Dict, repo_root: Path, file_symbols: List[Dict]) -> List[Dict]:
    """
    from class/object/interface -> imported type
    第一版默认从文件中的第一个顶层 class/interface/object/enum 发起
    """
    path = repo_root / file_item["path"]
    text = safe_read_text(path)
    if not text:
        return []

    top_symbols = [s for s in file_symbols if s.get("kind") in {"class", "interface", "enum", "object"} and not s.get("container")]
    if not top_symbols:
        return []

    from_symbol = top_symbols[0]["symbol"]
    results: List[Dict] = []

    for idx, raw in enumerate(text.splitlines(), start=1):
        m = re.match(r'^\s*import\s+([^\s;]+)', raw)
        if not m:
            continue
        imported = m.group(1).strip()

        results.append(
            make_relation(
                from_symbol=from_symbol,
                to_symbol=imported,
                rel_type="imports",
                file_path=file_item["path"],
                module=file_item.get("module", ""),
                line=idx,
                confidence="high"
            )
        )

    return results


def extract_inheritance_relations(file_item: Dict, repo_root: Path, file_symbols: List[Dict]) -> List[Dict]:
    path = repo_root / file_item["path"]
    text = safe_read_text(path)
    if not text:
        return []

    symbol_name_to_symbol = {}
    for s in file_symbols:
        if s.get("kind") in {"class", "interface", "enum", "object"}:
            symbol_name_to_symbol[s["name"]] = s["symbol"]

    results: List[Dict] = []

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        if file_item["language"] == "java":
            m = JAVA_CLASS_DECL_PAT.search(line)
            if not m:
                continue

            name = m.group(2)
            extends_name = m.group(3)
            implements_part = m.group(4)
            from_symbol = symbol_name_to_symbol.get(name, name)

            if extends_name:
                results.append(
                    make_relation(
                        from_symbol=from_symbol,
                        to_symbol=short_type_name(extends_name),
                        rel_type="extends",
                        file_path=file_item["path"],
                        module=file_item.get("module", ""),
                        line=idx,
                        confidence="high"
                    )
                )

            if implements_part:
                for iface in [x.strip() for x in implements_part.split(",") if x.strip()]:
                    results.append(
                        make_relation(
                            from_symbol=from_symbol,
                            to_symbol=short_type_name(iface),
                            rel_type="implements",
                            file_path=file_item["path"],
                            module=file_item.get("module", ""),
                            line=idx,
                            confidence="high"
                        )
                    )

        elif file_item["language"] == "kotlin":
            m = KOTLIN_CLASS_DECL_PAT.search(line)
            if not m:
                continue

            name = m.group(2)
            parents_expr = m.group(4)
            from_symbol = symbol_name_to_symbol.get(name, name)

            if parents_expr:
                parents = split_kotlin_parents(parents_expr)
                for parent in parents:
                    # 第一版启发式区分
                    rel_type = "extends"
                    if parent.startswith("I") or "Listener" in parent or "Callback" in parent:
                        rel_type = "implements"

                    results.append(
                        make_relation(
                            from_symbol=from_symbol,
                            to_symbol=short_type_name(parent),
                            rel_type=rel_type,
                            file_path=file_item["path"],
                            module=file_item.get("module", ""),
                            line=idx,
                            confidence="high"
                        )
                    )

    return results


def extract_method_body_chunks(file_text: str, methods_in_file: List[Dict]) -> Dict[str, str]:
    """
    MVP:
    当前方法起始行 到 下一个方法起始行之前，作为方法块
    不完全精确，但第一版够用
    """
    chunks: Dict[str, str] = {}
    if not methods_in_file:
        return chunks

    lines = file_text.splitlines()
    methods_sorted = sorted(methods_in_file, key=lambda x: x.get("line", 0))

    for i, method in enumerate(methods_sorted):
        start = max(method.get("line", 1) - 1, 0)
        end = len(lines)
        if i + 1 < len(methods_sorted):
            end = max(methods_sorted[i + 1].get("line", len(lines)) - 1, start)
        chunks[method["symbol"]] = "\n".join(lines[start:end])

    return chunks


def extract_reference_relations(
    file_item: Dict,
    repo_root: Path,
    methods_in_file: List[Dict],
    symbol_by_name: Dict[str, List[Dict]],
    symbols_by_file: Dict[str, List[Dict]]
) -> List[Dict]:
    """
    第一版做弱引用：
    1. obj.method(...) -> references_symbol: obj.method
    2. simpleMethod(...) -> references_symbol: 命中的同文件/同名候选 method
    """
    path = repo_root / file_item["path"]
    text = safe_read_text(path)
    if not text or not methods_in_file:
        return []

    results: List[Dict] = []
    chunks = extract_method_body_chunks(text, methods_in_file)

    same_file_symbols = symbols_by_file.get(file_item["path"], [])
    same_file_methods_by_name: Dict[str, List[Dict]] = defaultdict(list)
    for s in same_file_symbols:
        if s.get("kind") in {"method", "aidl_method"}:
            same_file_methods_by_name[s["name"]].append(s)

    for method in methods_in_file:
        from_symbol = method["symbol"]
        start_line = method.get("line", 0)
        body = chunks.get(from_symbol, "")

        # 1) obj.method(...)
        for m in METHOD_CALL_PAT.finditer(body):
            left = m.group(1)
            right = m.group(2)

            if left in {"this", "super"}:
                # this.foo() / super.foo() 更像类内调用
                # 优先连到同文件同名方法
                for cand in same_file_methods_by_name.get(right, [])[:3]:
                    results.append(
                        make_relation(
                            from_symbol=from_symbol,
                            to_symbol=cand["symbol"],
                            rel_type="references_symbol",
                            file_path=file_item["path"],
                            module=file_item.get("module", ""),
                            line=start_line,
                            confidence="medium",
                            meta={"raw_text": m.group(0)}
                        )
                    )
                continue

            results.append(
                make_relation(
                    from_symbol=from_symbol,
                    to_symbol=f"{left}.{right}",
                    rel_type="references_symbol",
                    file_path=file_item["path"],
                    module=file_item.get("module", ""),
                    line=start_line,
                    confidence="medium",
                    meta={"raw_text": m.group(0)}
                )
            )

        # 2) simpleMethod(...)
        for m in SIMPLE_CALL_PAT.finditer(body):
            callee = m.group(1)

            if callee in CONTROL_WORDS:
                continue

            # 优先同文件同名方法
            local_cands = same_file_methods_by_name.get(callee, [])
            if local_cands:
                for cand in local_cands[:3]:
                    results.append(
                        make_relation(
                            from_symbol=from_symbol,
                            to_symbol=cand["symbol"],
                            rel_type="references_symbol",
                            file_path=file_item["path"],
                            module=file_item.get("module", ""),
                            line=start_line,
                            confidence="high" if cand["symbol"] != from_symbol else "medium",
                            meta={"raw_text": m.group(0), "scope": "same_file"}
                        )
                    )
                continue

            # 再退化到全局同名 method
            global_cands = [
                s for s in symbol_by_name.get(callee, [])
                if s.get("kind") in {"method", "aidl_method"}
            ]
            for cand in global_cands[:3]:
                results.append(
                    make_relation(
                        from_symbol=from_symbol,
                        to_symbol=cand["symbol"],
                        rel_type="references_symbol",
                        file_path=file_item["path"],
                        module=file_item.get("module", ""),
                        line=start_line,
                        confidence="low",
                        meta={"raw_text": m.group(0), "scope": "global_name_match"}
                    )
                )

    return results


def extract_aidl_bind_relations(file_item: Dict, repo_root: Path, file_symbols: List[Dict]) -> List[Dict]:
    """
    启发式：
    - 类像 Service
    - 文件里出现 onBind
    - 出现 IVoiceService.Stub / Binder / asInterface
    -> 建立 uses_binder / binds_to
    """
    path = repo_root / file_item["path"]
    text = safe_read_text(path)
    if not text:
        return []

    top_classes = [s for s in file_symbols if s.get("kind") in {"class", "object"} and not s.get("container")]
    if not top_classes:
        return []

    service_candidates = []
    for s in top_classes:
        name_lower = s["name"].lower()
        sig_lower = (s.get("signature") or "").lower()
        tags = set(s.get("tags", []))

        if (
            "service" in name_lower or
            "extends service" in sig_lower or
            ": service(" in sig_lower or
            "service" in tags
        ):
            service_candidates.append(s)

    if not service_candidates:
        return []

    has_onbind = bool(ONBIND_PAT.search(text))
    aidl_hits = set(AIDL_HINT_PAT.findall(text))

    if not has_onbind and not aidl_hits:
        return []

    results: List[Dict] = []

    for svc in service_candidates:
        for idx, raw in enumerate(text.splitlines(), start=1):
            raw_stripped = raw.strip()
            if "Stub" in raw or "Binder" in raw or "asInterface" in raw:
                for aidl_name in aidl_hits:
                    results.append(
                        make_relation(
                            from_symbol=svc["symbol"],
                            to_symbol=aidl_name,
                            rel_type="uses_binder",
                            file_path=file_item["path"],
                            module=file_item.get("module", ""),
                            line=idx,
                            confidence="medium",
                            meta={"raw_text": raw_stripped}
                        )
                    )
                    if has_onbind:
                        results.append(
                            make_relation(
                                from_symbol=svc["symbol"],
                                to_symbol=aidl_name,
                                rel_type="binds_to",
                                file_path=file_item["path"],
                                module=file_item.get("module", ""),
                                line=idx,
                                confidence="medium",
                                meta={"raw_text": raw_stripped}
                            )
                        )

    return results


# -------------------------
# main build
# -------------------------

def build_relations(
    files_jsonl: str,
    symbols_jsonl: str,
    repo_root: str,
    output_jsonl: str
) -> None:
    files = load_jsonl(Path(files_jsonl))
    symbols = load_jsonl(Path(symbols_jsonl))
    repo_root_path = Path(repo_root)

    symbol_by_name, symbols_by_file, _ = build_symbol_indexes(symbols)
    methods_by_file = group_methods_by_file(symbols)

    all_relations: List[Dict] = []

    # 1) defines
    all_relations.extend(extract_defines_relations(symbols))

    # 2) per file relations
    for file_item in files:
        if not should_process_file(file_item):
            continue

        file_symbols = symbols_by_file.get(file_item["path"], [])

        # imports
        all_relations.extend(
            extract_import_relations(file_item, repo_root_path, file_symbols)
        )

        # extends / implements
        if file_item["language"] in {"java", "kotlin"}:
            all_relations.extend(
                extract_inheritance_relations(file_item, repo_root_path, file_symbols)
            )

        # binder / aidl hints
        if file_item["language"] in {"java", "kotlin"}:
            all_relations.extend(
                extract_aidl_bind_relations(file_item, repo_root_path, file_symbols)
            )

        # weak references
        if file_item["language"] in {"java", "kotlin"}:
            all_relations.extend(
                extract_reference_relations(
                    file_item=file_item,
                    repo_root=repo_root_path,
                    methods_in_file=methods_by_file.get(file_item["path"], []),
                    symbol_by_name=symbol_by_name,
                    symbols_by_file=symbols_by_file
                )
            )

    all_relations = dedupe_relations(all_relations)
    write_jsonl(Path(output_jsonl), all_relations)

    print(f"files: {len(files)}")
    print(f"symbols: {len(symbols)}")
    print(f"relations: {len(all_relations)}")
    print(f"output: {output_jsonl}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage:")
        print("  python build_relations.py <files.jsonl> <symbols.jsonl> <repo_root> <relations.jsonl>")
        sys.exit(1)

    build_relations(
        files_jsonl=sys.argv[1],
        symbols_jsonl=sys.argv[2],
        repo_root=sys.argv[3],
        output_jsonl=sys.argv[4]
    )