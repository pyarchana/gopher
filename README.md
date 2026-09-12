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
| `search_context(query, limit?)` | Find facts whose key or value contains `query` |
| `read_context(prefix?)` | Return the whole store, or just one section |
| `update_context(key, value)` | Set a value at a dot path, e.g. `projects.gopher.status` |
| `delete_context_key(key)` | Delete a key by dot path |
| `log_diary(entry, tag?)` | Append a timestamped Markdown entry |
| `read_diary(last_n?)` | Read back the last N diary entries |
| `digest_transcript(transcript_path)` | Extract facts from a transcript, merge into the context store |
| `summarize_only(transcript_path)` | Same extraction and validation, returns JSON without writing anything |
| `read_digest_log()` | Full contents of the digest log |

### Reading memory back

Three ways in, in order of how much they cost you:

```
search_context("deadline")        # you know what, not where
read_context("projects.gopher")   # you know where
read_context()                    # everything, for when the store is small
```

`search_context` is a case-insensitive substring match over key paths and
values. Hits on the key rank above hits on the value, results are capped at
`limit` (20 by default), and the reply says how many matched in total so you
can tell when you are seeing a slice.

No embeddings, no index, no extra dependency. On a store of a few hundred
facts substring matching is enough, and something cleverer can wait for
evidence that it is not.

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
      "args": ["run", "--project", "/absolute/path/to/gopher", "gopher"]
    }
  }
}
```

Restart Claude Desktop afterwards.

For Claude Code, register it once and it is available in every session:

```bash
claude mcp add gopher --scope user -- uv run --project /absolute/path/to/gopher gopher
```

---

## Configuration

Settings come from a `.env` file in the project root, which the server loads on
startup:

```bash
cp .env.example .env
```

Put your `GITHUB_TOKEN` there rather than in `claude_desktop_config.json`. The
config file gets screenshotted, synced between machines and pasted into issues;
`.env` is gitignored and stays put. Anything set in the client config still wins
if you prefer that route.

| Variable | Default | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | none | Optional. Raises the GitHub rate limit from 60 to 5,000 requests/hour. |
| `GOPHER_DATA_DIR` | `./data` | Where `context.json`, `diary.md`, and `digest_log.md` live. |
| `GOPHER_DIGEST_BUDGET` | `40000` | Maximum characters a repo digest may return. Raise it if your client accepts larger tool results, lower it to save context. |
| `GOPHER_OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama endpoint. |
| `GOPHER_OLLAMA_MODEL` | `llama3.2` | Model used for fact extraction. |

---

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

CI runs all three on every push and pull request, against Python 3.11 through 3.14.

---

## License

MIT, see [LICENSE](LICENSE).
