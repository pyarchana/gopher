# GopherDigest

An MCP server that reads conversation transcripts from disk, sends them to a local [Ollama](https://ollama.com) instance for fact extraction, and merges the results into a [GopherCache](https://github.com/your-org/gophercache) `context.json` file.

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally on `http://localhost:11434`
- The `llama3.2` model pulled in Ollama:

```bash
ollama pull llama3.2
```

> **Ollama must be running before any tool is called.** Start it with `ollama serve` if it is not already running as a background service.

## Installation

```bash
# Clone / enter the repo
cd gopherdigest

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package
pip install -e .
```

Copy `.env.example` to `.env` and adjust if needed:

```bash
cp .env.example .env
```

## Tools

| Tool | Description |
|---|---|
| `digest_transcript(transcript_path, gophercache_context_path)` | Extracts facts from a transcript and merges them into `context.json`. Logs to `data/digest_log.md`. |
| `summarize_only(transcript_path)` | Returns extracted facts as raw JSON text — no writes, safe for preview. |
| `read_digest_log()` | Returns the full contents of `data/digest_log.md`. |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GOPHERDIGEST_DATA_DIR` | `./data` | Directory where `digest_log.md` is written. |

## Claude Desktop configuration

Add the following to your Claude Desktop `claude_desktop_config.json` (usually at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "gopherdigest": {
      "command": "python",
      "args": ["-m", "gopherdigest.server"],
      "cwd": "/absolute/path/to/gopherdigest",
      "env": {
        "GOPHERDIGEST_DATA_DIR": "./data"
      }
    }
  }
}
```

Replace `/absolute/path/to/gopherdigest` with the actual path where you cloned this repo.

If you installed into a virtual environment, point `command` at the venv interpreter instead:

```json
{
  "mcpServers": {
    "gopherdigest": {
      "command": "/absolute/path/to/gopherdigest/.venv/bin/python",
      "args": ["-m", "gopherdigest.server"],
      "cwd": "/absolute/path/to/gopherdigest"
    }
  }
}
```

## Running the server manually (for testing)

```bash
python -m gopherdigest.server
```

Or via the installed script:

```bash
gopherdigest
```
