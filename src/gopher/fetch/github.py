"""GitHub REST API access and directory-tree rendering."""

import base64
import os
import re
from pathlib import PurePosixPath
from typing import NamedTuple

import httpx


class RepoTree(NamedTuple):
    """A repository's file list, plus what we know about its completeness."""

    blobs: list[dict]
    meta: dict
    branch: str
    truncated: bool
    """True when GitHub capped the tree and blobs is only part of the repo."""


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


def fetch_tree(owner: str, repo: str, client: httpx.Client) -> RepoTree:
    """Return the repository's blobs via the Git Trees API.

    GitHub caps a recursive tree response and sets ``truncated`` when it
    does, at which point the list is some arbitrary prefix of the repo.
    That flag is carried out on the result rather than dropped, because a
    partial file list rendered as a complete directory tree is a wrong
    answer that looks like a right one.
    """
    repo_meta = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=gh_headers())
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
    return RepoTree(
        blobs=blobs,
        meta=repo_meta.json(),
        branch=default_branch,
        truncated=bool(data.get("truncated", False)),
    )


def fetch_file_content(
    owner: str, repo: str, path: str, client: httpx.Client, max_chars: int | None = None
) -> str:
    """Fetch one file, optionally trimmed to *max_chars*.

    Sizing is the caller's decision because only the caller knows how much
    of the digest budget is left.
    """
    resp = client.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=gh_headers(),
    )
    resp.raise_for_status()
    data = resp.json()
    raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    if max_chars is not None and len(raw) > max_chars:
        raw = (
            raw[:max_chars]
            + f"\n\n... [trimmed, showing first {max_chars:,} of {len(raw):,} chars]"
        )
    return raw


def build_tree_string(blobs: list[dict], max_chars: int | None = None) -> str:
    """Render an ASCII directory tree from a flat blob list.

    With *max_chars* the render stops at a line boundary and says how many
    entries it left out, rather than letting the tree alone consume the
    whole digest.
    """
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

    if max_chars is None:
        return "\n".join(lines)

    kept: list[str] = []
    used = 0
    for i, line in enumerate(lines):
        if used + len(line) + 1 > max_chars:
            kept.append(f"... and {len(lines) - i:,} more entries, omitted to fit the digest")
            break
        kept.append(line)
        used += len(line) + 1
    return "\n".join(kept)
