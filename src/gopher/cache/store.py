"""Read/write layer for the context store and diary."""

import contextlib
import json
import os
import re
import tempfile

from gopher.config import CONTEXT_FILE, DIARY_FILE, ensure_data_dir

#: An entry header, as written by log_diary: "## <timestamp>" with an
#: optional " [TAG]". Anchoring on the timestamp is what stops an H2 inside
#: an entry body from being mistaken for the start of a new entry.
ENTRY_HEADER = re.compile(
    r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: \[[^\n]*\])?$",
    re.MULTILINE,
)


def append_diary(block: str) -> None:
    ensure_data_dir()
    with open(DIARY_FILE, "a", encoding="utf-8") as f:
        f.write(block)


def read_diary_raw() -> str:
    if not DIARY_FILE.exists():
        return ""
    return DIARY_FILE.read_text(encoding="utf-8")


def split_entries(content: str) -> list[str]:
    """Split diary text into entries, one per timestamped header.

    Splits only on headers that match the format log_diary writes, so an
    entry whose body contains its own markdown headings stays intact.

    Text before the first header is not part of any entry and is skipped;
    that only happens if the file has been hand edited.
    """
    starts = [m.start() for m in ENTRY_HEADER.finditer(content)]
    if not starts:
        return []
    bounds = [*starts, len(content)]
    return [content[bounds[i] : bounds[i + 1]].strip() for i in range(len(starts))]


def read_context_raw() -> dict:
    if not CONTEXT_FILE.exists():
        return {}
    with open(CONTEXT_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_context(data: dict) -> None:
    """Replace the context store, atomically.

    The store is the only state a user cannot regenerate, so a write must
    never be able to leave it half finished. Serialising into a temp file
    and committing with os.replace means a reader sees either the previous
    file or the new one, never a truncated one. os.replace is atomic on
    both POSIX and Windows.

    The temp file goes in the target's own directory because os.replace
    cannot rename across filesystems.
    """
    ensure_data_dir()
    fd, tmp = tempfile.mkstemp(dir=CONTEXT_FILE.parent, prefix=".context-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONTEXT_FILE)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


class ContextKeyConflict(Exception):
    """A write was refused because it would have destroyed existing data.

    Raised rather than resolved silently. Both cases mean the caller is
    treating a stored value as the wrong shape, and guessing which of the
    two values they meant to keep is not the store's decision to make.
    """


def set_nested(obj: dict, keys: list[str], value: str) -> None:
    """Set *value* at the dot path *keys*, creating sections as needed.

    Refuses, rather than destroying data, in two cases:

    - a key along the path holds a value instead of a section, so
      descending through it would mean discarding that value
    - the final key holds a section, so writing a value there would mean
      discarding everything under it

    Overwriting a value with another value is the normal case and is
    always allowed.
    """
    for depth, key in enumerate(keys[:-1]):
        node = obj.get(key)
        if node is None:
            node = obj[key] = {}
        elif not isinstance(node, dict):
            path = ".".join(keys[: depth + 1])
            raise ContextKeyConflict(
                f"cannot set {'.'.join(keys)!r}: {path!r} holds a value, not a "
                f"section. Delete it first with delete_context_key({path!r})."
            )
        obj = node

    last = keys[-1]
    if isinstance(obj.get(last), dict):
        path = ".".join(keys)
        raise ContextKeyConflict(
            f"cannot set {path!r} to a value: it holds a section with "
            f"{len(obj[last])} key(s) under it, which would be discarded. "
            f"Delete it first with delete_context_key({path!r})."
        )
    obj[last] = value


#: Longest value a single search hit will show. The store is meant to hold
#: short facts, but nothing stops a digest writing a long one, and a search
#: result that returns more than the caller can accept is the failure this
#: whole tool exists to avoid.
MAX_HIT_CHARS = 500


def flatten(obj: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Every leaf in the store as (dot path, value) pairs.

    Sections disappear; only the values under them come back, addressed by
    the same dot paths update_context and delete_context_key accept.
    """
    out: list[tuple[str, str]] = []
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.extend(flatten(value, path))
        else:
            out.append((path, str(value)))
    return out


def search(data: dict, query: str, limit: int) -> tuple[list[dict], int]:
    """Case-insensitive substring search over key paths and values.

    Returns the hits to show and how many there were in total, so a caller
    can say what it left out.

    Substring rather than embeddings on purpose. It needs no model, no
    index and no extra dependency, and on a store of a few hundred facts it
    is enough. Reach for something cleverer when there is evidence this is
    the limitation, not before.
    """
    needle = query.strip().lower()
    if not needle:
        return [], 0

    hits: list[dict] = []
    for path, value in flatten(data):
        in_key = needle in path.lower()
        in_value = needle in value.lower()
        if not (in_key or in_value):
            continue
        shown = value
        if len(shown) > MAX_HIT_CHARS:
            shown = shown[:MAX_HIT_CHARS] + f"... [{len(value):,} chars total]"
        hits.append(
            {
                "key": path,
                "value": shown,
                "matched": "key" if in_key else "value",
            }
        )

    # A key match is a stronger signal than a value that happens to mention
    # the word, so those come first.
    hits.sort(key=lambda h: (h["matched"] != "key", h["key"]))
    return hits[:limit], len(hits)


def get_nested(obj: dict, keys: list[str]):
    """Return whatever sits at the dot path, or None if nothing does.

    A section comes back as the dict itself, so callers can tell a value
    apart from a subtree.
    """
    for key in keys:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def del_nested(obj: dict, keys: list[str]) -> bool:
    for key in keys[:-1]:
        if not isinstance(obj, dict) or key not in obj:
            return False
        obj = obj[key]
    if not isinstance(obj, dict) or keys[-1] not in obj:
        return False
    del obj[keys[-1]]
    return True
