# GopherFetch

I kept running into repos with no README and no easy way to understand what they did without cloning them and digging around manually. So i built GopherFetch, it is basically an MCP sever that connects directly to claude desktop and does that digging for you.
Just give it a GitHub URL. It fetches the file tree, filters out all the noise (binaries, lock files, `node_modules`, the usual), ranks the files that actually matter and returns a clean Markdown digest. No README?? It builds one for itself.
It runs locally as of now over stdio, connects claude desktop in under a minuter and works on any public repo.

Built with [FastMCP] and the GitHub REST API.

---

## What it does

Exposes a single tool: `fetch_github_repo`

Give it a GitHub URL and get back a Markdown digest containing a full directory tree and the contents of the top 10 most important files, auto-ranked by name and location.

The server filters out binaries, lock files, and boilerplate directories like `node_modules`, `venv`, and `dist` before ranking. If a repo has no README, it falls back gracefully to the file tree and source files.

---

## Installation

Requires [uv]

```bash
git clone https://github.com/areychana/gopherfetch.git
cd gopherfetch

uv venv
uv pip install -e .
```

---

## Claude Desktop setup

Add this to your `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "gopherfetch": {
      "command": "uv",
      "args": [
        "run",
        "--project", "/absolute/path/to/gopherfetch",
        "python", "server.py"
      ],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

---

## GitHub Token

Optional but recommended. Without a token the GitHub API allows 60 requests per hour. With one it allows 5,000.

Generate a token at https://github.com/settings/tokens. No special scopes are needed for public repos.

Set it in the config above or export it in your shell:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

---

## Usage

Once connected, ask Claude naturally:

```
Fetch https://github.com/owner/repo and explain what it does.
```

---

## License

MIT License - see LICENSE file.
