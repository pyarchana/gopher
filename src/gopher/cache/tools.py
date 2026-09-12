"""MCP tools for persistent context and the diary."""

import json
from datetime import datetime

from gopher.cache.store import (
    append_diary,
    del_nested,
    get_nested,
    read_context_raw,
    read_diary_raw,
    search,
    set_nested,
    split_entries,
    write_context,
)


def read_context(prefix: str = "") -> str:
    """Read the context store as JSON.

    With no argument this returns everything, which is fine while the store
    is small and wasteful once it is not. Pass a dot path to read one
    section, or use search_context when you know what you are looking for
    but not where it lives."""
    data = read_context_raw()
    if prefix:
        node = get_nested(data, prefix.split("."))
        if node is None:
            return f"Nothing stored at {prefix!r}"
        data = node if isinstance(node, dict) else {prefix: node}
    return json.dumps(data, indent=2, ensure_ascii=False)


def search_context(query: str, limit: int = 20) -> str:
    """Find stored facts whose key path or value contains *query*.

    Case-insensitive substring match. Matches on the key come before
    matches on the value. Returns at most *limit* hits and says how many
    there were in total, so you know when you are seeing a slice."""
    hits, total = search(read_context_raw(), query, limit)
    return json.dumps(
        {
            "query": query,
            "matches": hits,
            "shown": len(hits),
            "total": total,
        },
        indent=2,
        ensure_ascii=False,
    )


def update_context(key: str, value: str) -> str:
    """Write a value at a dot-notation path (e.g. 'projects.gopher.status').

    Creates missing sections along the way. Refuses, rather than discarding
    data, if a key on the path already holds a value instead of a section,
    or if the final key holds a section that a value would replace. Delete
    the named key first if you meant to change its shape."""
    keys = key.split(".")
    data = read_context_raw()
    set_nested(data, keys, value)
    write_context(data)
    return f"Set {key} = {value!r}"


def delete_context_key(key: str) -> str:
    """Delete a key by dot-notation path (e.g. 'projects.gopher.status')."""
    keys = key.split(".")
    data = read_context_raw()
    if del_nested(data, keys):
        write_context(data)
        return f"Deleted {key}"
    return f"Key not found: {key}"


def log_diary(entry: str, tag: str = "") -> str:
    """Append a timestamped markdown entry to the diary.

    The entry body may contain its own markdown, headings included.
    Optional tag (e.g. 'GSOC', 'GATE') appears in the header."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag_part = f" [{tag}]" if tag else ""
    append_diary(f"\n## {timestamp}{tag_part}\n\n{entry}\n")
    return f"Logged diary entry at {timestamp}"


def read_diary(last_n: int = 10) -> str:
    """Return the last N entries from the diary (default 10)."""
    entries = split_entries(read_diary_raw())
    if not entries:
        return "(diary is empty)"
    if last_n <= 0:
        return "(no entries requested)"
    return "\n\n".join(entries[-last_n:])


def register(mcp) -> None:
    """Attach this module's tools to the shared FastMCP instance."""
    mcp.tool()(read_context)
    mcp.tool()(search_context)
    mcp.tool()(update_context)
    mcp.tool()(delete_context_key)
    mcp.tool()(log_diary)
    mcp.tool()(read_diary)
