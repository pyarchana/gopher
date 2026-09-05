# Gopher

[![CI](https://github.com/pyarchana/gopher/actions/workflows/ci.yml/badge.svg)](https://github.com/pyarchana/gopher/actions/workflows/ci.yml)

One MCP server that fetches, caches, and digests context for Claude.

Gopher is three things that used to be three separate servers:

- **fetch**: point it at a GitHub repo and get back a clean Markdown digest: full directory tree, plus the contents of the files that actually matter. Filters out binaries, lock files, `node_modules`, `venv`, and the rest of the noise, then ranks what's left. No README? It builds one for you.
- **cache**: persistent memory across conversations, stored as two plain files you can read yourself: a structured `context.json` and an append-only `diary.md`.
- **digest**: reads a conversation transcript, extracts the facts with a local Ollama model, and merges them into the cache.

Everything runs locally over stdio. Nothing leaves your machine except GitHub API calls.

---

## Tools

| Tool | What it does |
|---|---|
| `fetch_github_repo(repo_url)` | Markdown digest of a public repo, tree plus top files |
| `read_context()` | Return the whole context store as JSON |
| `update_context(key, value)` | Set a value at a dot path, e.g. `projects.gopher.status` |
| `delete_context_key(key)` | Delete a key by dot path |
| `log_diary(entry, tag?)` | Append a timestamped Markdown entry |
| `read_diary(last_n?)` | Read back the last N diary entries |
| `digest_transcript(transcript_path, context_path)` | Extract facts from a transcript, merge into the context store |
| `summarize_only(transcript_path)` | Same extraction, returns JSON without writing anything |
| `read_digest_log()` | Full contents of the digest log |

---

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/pyarchana/gopher.git
cd gopher
uv venv
uv pip install -e ".[dev]"
```

The digest tools additionally need [Ollama](https://ollama.com) running locally with `llama3.2` pulled:

```bash
ollama pull llama3.2
```

Fetch and cache work without it.

---

## Claude Desktop

Add this to `claude_desktop_config.json` (`%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "gopher": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/to/gopher", "gopher"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
```

Restart Claude Desktop afterwards.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | none | Optional. Raises the GitHub rate limit from 60 to 5,000 requests/hour. |
| `GOPHER_DATA_DIR` | `./data` | Where `context.json`, `diary.md`, and `digest_log.md` live. |
| `GOPHER_OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama endpoint. |
| `GOPHER_OLLAMA_MODEL` | `llama3.2` | Model used for fact extraction. |

---

## Development

```bash
uv run pytest
uvx ruff check .
uvx ruff format .
```

CI runs all three on every push and pull request, against Python 3.11 through 3.14.

---

## License

MIT, see [LICENSE](LICENSE).
