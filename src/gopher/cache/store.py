"""Read/write layer for the context store and diary."""

import json

from gopher.config import CONTEXT_FILE, ensure_data_dir


def read_context_raw() -> dict:
    if not CONTEXT_FILE.exists():
        return {}
    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def write_context(data: dict) -> None:
    ensure_data_dir()
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
