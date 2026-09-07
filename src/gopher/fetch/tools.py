"""MCP tools for fetching and digesting GitHub repositories."""

from pathlib import PurePosixPath

import httpx

from gopher.config import DIGEST_BUDGET
from gopher.fetch.github import (
    build_tree_string,
    fetch_file_content,
    fetch_tree,
    parse_repo_url,
)
from gopher.fetch.sieve import (
    HEADER_RESERVE,
    MAX_FILE_FRACTION,
    MAX_FILES,
    MIN_FILE_CHARS,
    TREE_BUDGET_FRACTION,
    file_priority_score,
    is_ignored,
)


def build_digest(repo_url: str, client: httpx.Client, budget: int = DIGEST_BUDGET) -> str:
    """Build the markdown digest using a caller-supplied HTTP client.

    Fills *budget* characters, tree first and then files in priority order,
    and stops. A digest larger than the caller can accept is rejected
    whole, so returning less is the only way to return anything at all.

    Split out from the tool so tests can hand it a mock transport and a
    small budget instead of reaching the network.
    """
    owner, repo = parse_repo_url(repo_url)

    tree = fetch_tree(owner, repo, client)
    repo_meta, default_branch = tree.meta, tree.branch

    filtered = [b for b in tree.blobs if not is_ignored(b["path"])]

    tree_str = build_tree_string(filtered, max_chars=int(budget * TREE_BUDGET_FRACTION))
    file_budget = max(budget - len(tree_str) - HEADER_RESERVE, 0)
    per_file_cap = int(file_budget * MAX_FILE_FRACTION)

    ranked = sorted(filtered, key=file_priority_score, reverse=True)

    file_sections: list[str] = []
    included_paths: list[str] = []
    spent = 0
    included = 0
    for item in ranked:
        if included >= MAX_FILES:
            break
        cap = min(per_file_cap, file_budget - spent)
        if cap < MIN_FILE_CHARS:
            break
        try:
            content = fetch_file_content(owner, repo, item["path"], client, max_chars=cap)
        except Exception as e:
            section = f"### `{item['path']}`\n\n> ⚠️ Could not fetch: {e}"
            file_sections.append(section)
            spent += len(section)
            continue
        if len(content.strip()) < MIN_FILE_CHARS:
            continue
        lang = PurePosixPath(item["path"]).suffix.lstrip(".")
        section = f"### `{item['path']}`\n\n```{lang}\n{content}\n```"
        file_sections.append(section)
        included_paths.append(item["path"])
        spent += len(section)
        included += 1

    omitted = max(len(ranked) - included, 0)

    stars = repo_meta.get("stargazers_count", "?")
    language = repo_meta.get("language") or "unknown"
    desc = repo_meta.get("description") or "_No description provided._"
    license_ = (repo_meta.get("license") or {}).get("spdx_id", "unknown")

    readme_note = ""
    if not any("readme" in p.lower() for p in included_paths):
        readme_note = (
            "\n> ℹ️ **No README detected.** File tree and key source files are shown below.\n"
        )

    budget_note = ""
    if omitted:
        budget_note = f", {omitted:,} omitted to fit {budget:,} chars"

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

## Files ({included} of {len(ranked)} shown{budget_note})

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
