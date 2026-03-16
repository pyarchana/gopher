import os
import re
import base64
import httpx
from pathlib import PurePosixPath
from fastmcp import FastMCP

mcp = FastMCP("GopherFetch")

IGNORED_DIRS = {
    ".git", ".github", ".idea", ".vscode",
    "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "dist", "build", ".next", ".nuxt", "out",
    "coverage", ".coverage", "htmlcov",
    "vendor", "target", "bin", "obj",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".tiff",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".mp4", ".mov", ".avi", ".mp3", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".class", ".pyc",
    ".pyd", ".wasm", ".bin", ".dat",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".lock", ".map", ".min.js",
}

IGNORED_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "Gemfile.lock", "composer.lock",
    ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes",
    ".editorconfig", ".prettierrc", ".eslintignore",
}

PRIORITY_NAMES = [
    "main.py", "app.py", "server.py", "index.py",
    "main.js", "index.js", "app.js", "server.js",
    "main.ts", "index.ts", "app.ts",
    "main.go", "main.rs", "main.cpp", "main.c",
    "Main.java",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "Cargo.toml", "go.mod", "pom.xml",
    "requirements.txt", "Pipfile",
    "README.md", "README.txt", "README.rst",
    ".env.example", "config.py", "settings.py", "config.js",
]

PRIORITY_DIRS = {"src", "lib", "contracts", "core", "api", "app"}

MAX_FILE_BYTES = 32_000
TOP_N_FILES    = 10


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    url = url.rstrip("/")
    m = re.search(r"github\.com[/:]([^/]+)/([^/\\.]+)", url)
    if not m:
        raise ValueError(f"Cannot parse GitHub repo URL: {url}")
    return m.group(1), m.group(2).removesuffix(".git")


def gh_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def is_ignored(path: str) -> bool:
    parts = PurePosixPath(path).parts
    for part in parts[:-1]:
        if part in IGNORED_DIRS:
            return True
    filename = parts[-1]
    if filename in IGNORED_FILENAMES:
        return True
    ext = PurePosixPath(filename).suffix.lower()
    if ext in IGNORED_EXTENSIONS:
        return True
    if filename.endswith(".min.js") or filename.endswith(".min.css"):
        return True
    return False


def file_priority_score(item: dict) -> int:
    """Higher score = more important. Used to pick TOP_N_FILES."""
    path  = item["path"]
    name  = item.get("name") or PurePosixPath(path).name
    size  = item.get("size", 0)
    score = 0
 
    if name in PRIORITY_NAMES:
        score += 1000
    parts = PurePosixPath(path).parts
    if any(p in PRIORITY_DIRS for p in parts):
        score += 300
    # reward reasonable size (not empty, not huge minified blob)
    if 200 < size < 20_000:
        score += size // 100
    elif size >= 20_000:
        score += 200   # still include, but don't over-rank
 
    return score



def fetch_tree(owner: str, repo: str, client: httpx.Client) -> list[dict]:
    """Return flat list of blob items via the Git Trees API."""
    repo_meta = client.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=gh_headers()
    )
    repo_meta.raise_for_status()
    default_branch = repo_meta.json().get("default_branch", "main")

    tree_resp = client.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
        headers=gh_headers(),
    )
    tree_resp.raise_for_status()
    data = tree_resp.json()

    blobs = [item for item in data.get("tree", []) if item["type"] == "blob"]
    return blobs, repo_meta.json(), default_branch


def fetch_file_content(owner: str, repo: str, path: str, client: httpx.Client) -> str:
    resp = client.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=gh_headers(),
    )
    resp.raise_for_status()
    data = resp.json()
    raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    if len(raw) > MAX_FILE_BYTES:
        raw = raw[:MAX_FILE_BYTES] + f"\n\n... [truncated — showing first {MAX_FILE_BYTES} chars] ..."
    return raw


def build_tree_string(blobs: list[dict]) -> str:
    """Render an ASCII directory tree from a flat blob list."""
    tree: dict = {}
    for b in blobs:
        parts = PurePosixPath(b["path"]).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    lines: list[str] = []

    def render(node: dict, prefix: str = ""):
        items = sorted(node.items(), key=lambda x: (x[1] is None, x[0]))
        for i, (name, child) in enumerate(items):
            connector = "└── " if i == len(items) - 1 else "├── "
            lines.append(prefix + connector + name)
            if child is not None:
                extension = "    " if i == len(items) - 1 else "│   "
                render(child, prefix + extension)

    render(tree)
    return "\n".join(lines)


@mcp.tool()
def fetch_github_repo(repo_url: str) -> str:
    """Fetch a GitHub repo and return a Markdown digest with directory tree and top files."""
    owner, repo = parse_repo_url(repo_url)

    with httpx.Client(timeout=30) as client:
        all_blobs, repo_meta, default_branch = fetch_tree(owner, repo, client)

        filtered = [b for b in all_blobs if not is_ignored(b["path"])]
        tree_str = build_tree_string(filtered)
        ranked = sorted(filtered, key=file_priority_score, reverse=True)
        top_files = ranked[:TOP_N_FILES]

        file_sections: list[str] = []
        for item in top_files:
            try:
                content = fetch_file_content(owner, repo, item["path"], client)
                lang = PurePosixPath(item["path"]).suffix.lstrip(".")
                file_sections.append(
                    f"### `{item['path']}`\n\n```{lang}\n{content}\n```"
                )
            except Exception as e:
                file_sections.append(f"### `{item['path']}`\n\n> ⚠️ Could not fetch: {e}")

    stars    = repo_meta.get("stargazers_count", "?")
    language = repo_meta.get("language") or "unknown"
    desc     = repo_meta.get("description") or "_No description provided._"
    license_ = (repo_meta.get("license") or {}).get("spdx_id", "unknown")

    readme_note = ""
    top_paths = {f["path"].lower() for f in top_files}
    if not any("readme" in p for p in top_paths):
        readme_note = "\n> ℹ️ **No README detected.** File tree and key source files are shown below.\n"

    output = f"""# {owner}/{repo}

> {desc}

| Field | Value |
|-------|-------|
| ⭐ Stars | {stars} |
| 🌐 Language | {language} |
| 📄 License | {license_} |
| 🌿 Branch | {default_branch} |
{readme_note}
---

## Directory Tree

```
{tree_str}
```

---

## Top {len(file_sections)} Files

{chr(10).join(file_sections)}
"""
    return output.strip()


if __name__ == "__main__":
    mcp.run(transport="stdio")
