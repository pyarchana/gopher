"""Filesystem paths and environment configuration.

All three modules share one data directory. Override it with GOPHER_DATA_DIR.
"""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("GOPHER_DATA_DIR", "./data"))

CONTEXT_FILE = DATA_DIR / "context.json"
DIARY_FILE = DATA_DIR / "diary.md"
DIGEST_LOG = DATA_DIR / "digest_log.md"

OLLAMA_URL = os.environ.get("GOPHER_OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("GOPHER_OLLAMA_MODEL", "llama3.2")

#: Ceiling on the characters a single repo digest may return.
#:
#: A tool result goes into a model's context window and there is a hard
#: limit on how large one can be. Past it the whole call is rejected and
#: the caller gets nothing, not a truncated answer. Measured totals before
#: this existed ranged from 4,594 characters for a five file repo to
#: 228,310 for a large one, so the size had to be capped rather than left
#: to fall out of a fixed file count.
DIGEST_BUDGET = int(os.environ.get("GOPHER_DIGEST_BUDGET", "40000"))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
