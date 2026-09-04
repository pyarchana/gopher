"""MCP tools for persistent context and the diary."""

import json
from datetime import datetime

from gopher.cache.store import (
    del_nested,
    read_context_raw,
    set_nested,
    write_context,
)
from gopher.config import DIARY_FILE, ensure_data_dir


def read_context() -> str:
    """Read and return the full context store as a JSON string."""
    data = read_context_raw()
    return json.dumps(data, indent=2, ensure_ascii=False)


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
    Optional tag (e.g. 'GSOC', 'GATE') appears in the header."""
    ensure_data_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag_part = f" [{tag}]" if tag else ""
    block = f"\n## {timestamp}{tag_part}\n\n{entry}\n"
    with open(DIARY_FILE, "a", encoding="utf-8") as f:
        f.write(block)
    return f"Logged diary entry at {timestamp}"


def read_diary(last_n: int = 10) -> str:
    """Return the last N entries from the diary (default 10)."""
    if not DIARY_FILE.exists():
        return "(diary is empty)"
    with open(DIARY_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # Entries start with "## "
    parts = content.split("\n## ")
    if not parts:
        return "(diary is empty)"
    # Re-attach the header marker to all except the first split fragment
    entries = [parts[0]] + ["## " + p for p in parts[1:]]
    # Drop any empty leading fragment before the first entry
    entries = [e for e in entries if e.strip()]
    tail = entries[-last_n:]
    return "\n".join(tail).strip()


def register(mcp) -> None:
    """Attach this module's tools to the shared FastMCP instance."""
    mcp.tool()(read_context)
    mcp.tool()(update_context)
    mcp.tool()(delete_context_key)
    mcp.tool()(log_diary)
    mcp.tool()(read_diary)
