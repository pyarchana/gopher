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


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
