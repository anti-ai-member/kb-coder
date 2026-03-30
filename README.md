让 bug 分析 agent 先：

1. 查日志
2. 归纳 top error / top tag / fingerprint
3. 再用 code KB 去找对应代码区域

## 代码侧

- `search_symbol`
- `search_voice_path`
- `get_symbol_context`
- `get_impact`
- `get_service_ipc`

## 日志侧

- `search_logs`
- `summarize_logs`
- `group_log_fingerprints`
- `find_suspicious_tags`
- `find_suspicious_files`
- `analyze_log_issue`
