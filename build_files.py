import os
import re
import json
import sys
from pathlib import Path

IGNORE_DIRS = {
    ".git", ".idea", ".gradle", "build", "out", "dist", "target", "node_modules", ".code_kb"
}

BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".jar", ".aar", ".so", ".zip", ".apk", ".mp4"
}

def should_ignore(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    return path.suffix.lower() in BINARY_EXTS

def guess_language(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".xml": "xml",
        ".aidl": "aidl",
        ".py": "python",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".c": "c",
        ".h": "c_header",
        ".sh": "shell",
        ".md": "markdown"
    }.get(ext, "unknown")

def guess_file_type(path: Path) -> str:
    p = str(path).replace("\\", "/")
    name = path.name

    if "build/generated" in p or name in {"R.java", "BuildConfig.java"}:
        return "generated"
    if "/src/test/" in p or "/src/androidTest/" in p or name.endswith("Test.java") or name.endswith("Test.kt"):
        return "test"
    if name == "AndroidManifest.xml":
        return "manifest"
    if name.startswith("build.gradle") or name == "settings.gradle" or name.endswith(".gradle.kts"):
        return "gradle"
    if path.suffix.lower() == ".aidl":
        return "aidl"
    if path.suffix.lower() == ".xml":
        return "resource_xml"
    if path.suffix.lower() in {".java", ".kt", ".cpp", ".c", ".h", ".py"}:
        return "source"
    if path.suffix.lower() in {".sh"}:
        return "script"
    if path.suffix.lower() in {".md", ".txt"}:
        return "doc"
    return "unknown"

def guess_module(path: Path) -> str:
    return path.parts[0] if len(path.parts) > 0 else "root"

def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return ""
    except Exception:
        return ""

def extract_symbols(text: str, language: str) -> list[str]:
    symbols = []
    if language in {"java", "kotlin"}:
        patterns = [
            r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bobject\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bfun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            r"\b(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?[A-Za-z_<>\[\], ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
        ]
        for p in patterns:
            symbols.extend(re.findall(p, text))
    elif language == "python":
        symbols.extend(re.findall(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", text))
        symbols.extend(re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text))

    # 去重保序
    seen = set()
    result = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result[:50]

def extract_imports(text: str, language: str) -> list[str]:
    imports = []
    if language in {"java", "kotlin"}:
        imports = re.findall(r"^\s*import\s+([^\s;]+)", text, flags=re.MULTILINE)
    elif language == "python":
        imports.extend(re.findall(r"^\s*import\s+([^\s]+)", text, flags=re.MULTILINE))
        imports.extend(re.findall(r"^\s*from\s+([^\s]+)\s+import", text, flags=re.MULTILINE))
    return imports[:50]

def build_summary(path: Path, symbols: list[str], imports: list[str], file_type: str) -> str:
    name = path.stem
    if file_type == "manifest":
        return "Android 应用清单文件"
    if file_type == "gradle":
        return "Gradle 构建配置文件"
    if file_type == "aidl":
        return "AIDL 接口定义文件"
    if file_type == "test":
        return f"{name} 的测试文件"
    if "Service" in name:
        return f"{name}，可能是服务入口或后台服务实现"
    if "Manager" in name:
        return f"{name}，可能负责状态或资源管理"
    if "Activity" in name:
        return f"{name}，可能是界面入口"
    if "Fragment" in name:
        return f"{name}，可能是界面片段"
    if symbols:
        return f"{name}，包含符号: {', '.join(symbols[:3])}"
    return f"{name} 文件"

def process_file(root: Path, path: Path) -> dict | None:
    rel_path = path.relative_to(root)

    if should_ignore(rel_path):
        return None

    text = safe_read_text(path)
    language = guess_language(path)
    file_type = guess_file_type(rel_path)

    try:
        size = path.stat().st_size
    except Exception:
        size = 0

    lines = text.count("\n") + 1 if text else 0
    symbols = extract_symbols(text, language)
    imports = extract_imports(text, language)

    return {
        "path": str(rel_path).replace("\\", "/"),
        "module": guess_module(rel_path),
        "language": language,
        "file_type": file_type,
        "ext": path.suffix.lower(),
        "size": size,
        "lines": lines,
        "is_test": file_type == "test",
        "is_generated": file_type == "generated",
        "symbols": symbols,
        "imports": imports,
        "xml_refs": [],
        "manifest_refs": [],
        "summary": build_summary(rel_path, symbols, imports, file_type),
        "tags": []
    }

def build_files_jsonl(repo_root: str, output_file: str):
    root = Path(repo_root)
    with open(output_file, "w", encoding="utf-8") as out:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            item = process_file(root, path)
            if item:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage:")
        print("  python build_files.py <repo_root> <files.jsonl>")
        sys.exit(1)
    build_files_jsonl(sys.argv[1], sys.argv[2])