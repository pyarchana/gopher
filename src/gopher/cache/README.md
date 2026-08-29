# GopherCache

Persistent memory for Claude via two plain files:

- `data/context.json`: structured key-value store
- `data/diary.md`: append-only timestamped log

## Tools

| Tool | Description |
|---|---|
| `read_context()` | Get full context.json as JSON |
| `update_context(key, value)` | Set value at dot-notation path |
| `delete_context_key(key)` | Delete key by dot-notation path |
| `log_diary(entry, tag?)` | Append timestamped markdown entry |
| `read_diary(last_n?)` | Get last N diary entries |

## Setup

```bash
pip install "mcp[cli]"
python -m venv .venv
.venv\Scripts\activate
pip install "mcp[cli]"
python server.py
```
