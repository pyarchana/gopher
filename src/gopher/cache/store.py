"""Read/write layer for the context store and diary."""

import json
import os
import tempfile

from gopher.config import CONTEXT_FILE, ensure_data_dir


def read_context_raw() -> dict:
    if not CONTEXT_FILE.exists():
        return {}
    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
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
    fd, tmp = tempfile.mkstemp(
        dir=CONTEXT_FILE.parent, prefix=".context-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONTEXT_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_nested(obj: dict, keys: list[str], value: str) -> None:
    for key in keys[:-1]:
        obj = obj.setdefault(key, {})
    obj[keys[-1]] = value


def del_nested(obj: dict, keys: list[str]) -> bool:
    for key in keys[:-1]:
        if not isinstance(obj, dict) or key not in obj:
            return False
        obj = obj[key]
    if not isinstance(obj, dict) or keys[-1] not in obj:
        return False
    del obj[keys[-1]]
    return True
