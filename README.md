# Code KB + Log Index (English)

This directory provides a lightweight **code knowledge base (KB)** builder and a **source-level log call index**. The intended workflow for a bug-analysis agent is:

1. Look at runtime logs first (errors, suspicious tags, recurring fingerprints).
2. Summarize what’s frequent / high-impact.
3. Jump back into source using the code KB and the log-call index to find relevant code areas.

## Build the indexes (recommended)

Run the pipeline on a code directory:

```bash
python build_pipeline.py <code_directory>
```

Outputs are written to `<code_directory>/.code_kb/`:

- `files.jsonl`: file inventory (language, type, size, symbols, imports, …). Supports **Java, Kotlin, C, C++** (heuristics).
- `symbols.jsonl`: extracted symbol definitions (classes / methods / constants / …). Supports **Java, Kotlin, C, C++** (heuristics).
- `relations.jsonl`: basic relationships (e.g. `defines`, `imports`, `extends/implements`, weak call references; plus some Android binder heuristics).
- `log_index.jsonl`: extracted **log call sites** from source (currently Java/Kotlin patterns such as `Log.*`, `Timber.*`, `println`, etc.).
- `log_index_stats.json`: summary stats for the log index.

## Query the log index

The helper CLI lives in `tools/query_log_index.py`.

Examples:

```bash
# Search by keyword / tag / file / level, etc.
python tools/query_log_index.py --index <code_directory>/.code_kb/log_index.jsonl search --keyword "divide_by_zero" --limit 20

# Show summary for a filtered subset
python tools/query_log_index.py --index <code_directory>/.code_kb/log_index.jsonl summary --tag "VoiceService"

# Top N tags / classes / methods / files
python tools/query_log_index.py --index <code_directory>/.code_kb/log_index.jsonl top-tags --limit 30
python tools/query_log_index.py --index <code_directory>/.code_kb/log_index.jsonl top-files --limit 30
```

## Notes / limitations

- The C/C++ and Java/Kotlin parsers are **regex/heuristic-based**, not full compilers/ASTs. Expect occasional false positives/negatives (templates, macros, complex declarations, multi-line constructs, etc.).
- The log index is **source-level** and focuses on common Android logging styles; it does not parse runtime logcat output files.

## License

MIT. See `LICENSE`.
