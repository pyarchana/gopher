import json
import os
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GopherCache")

DATA_DIR = Path(os.environ.get("GOPHERCACHE_DATA_DIR", "./data"))
CONTEXT_FILE = DATA_DIR / "context.json"
DIARY_FILE = DATA_DIR / "diary.md"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_context_raw() -> dict:
    if not CONTEXT_FILE.exists():
        return {}
    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_context(data: dict) -> None:
    _ensure_data_dir()
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _set_nested(obj: dict, keys: list[str], value: str) -> None:
    for key in keys[:-1]:
        obj = obj.setdefault(key, {})
    obj[keys[-1]] = value


def _del_nested(obj: dict, keys: list[str]) -> bool:
    for key in keys[:-1]:
        if not isinstance(obj, dict) or key not in obj:
            return False
        obj = obj[key]
    if not isinstance(obj, dict) or keys[-1] not in obj:
        return False
    del obj[keys[-1]]
    return True


@mcp.tool()
def read_context() -> str:
    """Read and return the full context store as a JSON string."""
    data = _read_context_raw()
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def update_context(key: str, value: str) -> str:
    """Write a value at a dot-notation path (e.g. 'projects.gophercache.status').
    Creates nested keys automatically."""
    keys = key.split(".")
    data = _read_context_raw()
    _set_nested(data, keys, value)
    _write_context(data)
    return f"Set {key} = {value!r}"


@mcp.tool()
def delete_context_key(key: str) -> str:
    """Delete a key by dot-notation path (e.g. 'projects.gophercache.status')."""
    keys = key.split(".")
    data = _read_context_raw()
    if _del_nested(data, keys):
        _write_context(data)
        return f"Deleted {key}"
    return f"Key not found: {key}"


@mcp.tool()
def log_diary(entry: str, tag: str = "") -> str:
    """Append a timestamped markdown entry to the diary.
    Optional tag (e.g. 'GSOC', 'GATE') appears in the header."""
    _ensure_data_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag_part = f" [{tag}]" if tag else ""
    block = f"\n## {timestamp}{tag_part}\n\n{entry}\n"
    with open(DIARY_FILE, "a", encoding="utf-8") as f:
        f.write(block)
    return f"Logged diary entry at {timestamp}"


@mcp.tool()
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


if __name__ == "__main__":
    mcp.run()
