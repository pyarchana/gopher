"""MCP tools for fetching and digesting GitHub repositories."""

from pathlib import PurePosixPath

import httpx

from gopher.fetch.github import (
    build_tree_string,
    fetch_file_content,
    fetch_tree,
    parse_repo_url,
)
from gopher.fetch.sieve import TOP_N_FILES, file_priority_score, is_ignored


def build_digest(repo_url: str, client: httpx.Client) -> str:
    """Build the markdown digest using a caller-supplied HTTP client.

    Split out from the tool so tests can hand it a mock transport instead
    of reaching the network.
    """
    owner, repo = parse_repo_url(repo_url)

    tree = fetch_tree(owner, repo, client)
    repo_meta, default_branch = tree.meta, tree.branch

    filtered = [b for b in tree.blobs if not is_ignored(b["path"])]
    tree_str = build_tree_string(filtered)
    ranked = sorted(filtered, key=file_priority_score, reverse=True)
    top_files = ranked[:TOP_N_FILES]

    file_sections: list[str] = []
    for item in top_files:
        try:
            content = fetch_file_content(owner, repo, item["path"], client)
            lang = PurePosixPath(item["path"]).suffix.lstrip(".")
            file_sections.append(f"### `{item['path']}`\n\n```{lang}\n{content}\n```")
        except Exception as e:
            file_sections.append(f"### `{item['path']}`\n\n> ⚠️ Could not fetch: {e}")

    stars = repo_meta.get("stargazers_count", "?")
    language = repo_meta.get("language") or "unknown"
    desc = repo_meta.get("description") or "_No description provided._"
    license_ = (repo_meta.get("license") or {}).get("spdx_id", "unknown")

    readme_note = ""
    top_paths = {f["path"].lower() for f in top_files}
    if not any("readme" in p for p in top_paths):
        readme_note = (
            "\n> ℹ️ **No README detected.** File tree and key source files are shown below.\n"
        )

    # A capped listing rendered as a full tree is a wrong answer wearing the
    # costume of a right one, so say so before showing anything.
    truncated_note = ""
    tree_heading = "Directory Tree"
    if tree.truncated:
        tree_heading = "Directory Tree (partial)"
        truncated_note = (
            "\n> ⚠️ **Partial listing.** GitHub capped the file tree for this repository, "
            f"so what follows is an arbitrary prefix of it rather than the whole thing. "
            f"{len(tree.blobs):,} files came back before the cap, and the ranking below "
            "only saw those.\n"
        )

    output = f"""# {owner}/{repo}

> {desc}

| Field | Value |
|-------|-------|
| ⭐ Stars | {stars} |
| 🌐 Language | {language} |
| 📄 License | {license_} |
| 🌿 Branch | {default_branch} |
{truncated_note}{readme_note}
---

## {tree_heading}

```
{tree_str}
```

---

## Top {len(file_sections)} Files

{chr(10).join(file_sections)}
"""
    return output.strip()


def fetch_github_repo(repo_url: str) -> str:
    """Fetch a GitHub repo and return a Markdown digest with directory tree and top files."""
    with httpx.Client(timeout=30) as client:
        return build_digest(repo_url, client)


def register(mcp) -> None:
    """Attach this module's tools to the shared FastMCP instance."""
    mcp.tool()(fetch_github_repo)
