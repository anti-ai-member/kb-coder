#!/usr/bin/env python3
"""
按顺序执行 build_files -> build_symbols -> build_relations，生成三个 jsonl。

用法:
  python build_pipeline.py <代码目录>

输出（在 <代码目录>/.code_kb/ 下）:
  files.jsonl, symbols.jsonl, relations.jsonl
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python build_pipeline.py <code_directory>")
        sys.exit(1)

    repo = Path(sys.argv[1]).resolve()
    if not repo.is_dir():
        print(f"Not a directory: {repo}", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    out_dir = repo / ".code_kb"
    out_dir.mkdir(parents=True, exist_ok=True)

    files_jsonl = out_dir / "files.jsonl"
    symbols_jsonl = out_dir / "symbols.jsonl"
    relations_jsonl = out_dir / "relations.jsonl"

    py = sys.executable
    steps: list[tuple[str, ...]] = [
        (py, str(script_dir / "build_files.py"), str(repo), str(files_jsonl)),
        (py, str(script_dir / "build_symbols.py"), str(files_jsonl), str(repo), str(symbols_jsonl)),
        (
            py,
            str(script_dir / "build_relations.py"),
            str(files_jsonl),
            str(symbols_jsonl),
            str(repo),
            str(relations_jsonl),
        ),
    ]

    for cmd in steps:
        print("->", " ".join(cmd))
        r = subprocess.run(cmd, cwd=str(script_dir))
        if r.returncode != 0:
            sys.exit(r.returncode)

    print("Done:")
    print(f"  {files_jsonl}")
    print(f"  {symbols_jsonl}")
    print(f"  {relations_jsonl}")


if __name__ == "__main__":
    main()
