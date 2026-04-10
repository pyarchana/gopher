import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

DATA_DIR = Path(os.environ.get("GOPHERDIGEST_DATA_DIR", "./data"))
DIGEST_LOG = DATA_DIR / "digest_log.md"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

mcp = FastMCP("GopherDigest")


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
    return response.json()["response"].strip()


def _build_extract_prompt(transcript: str) -> str:
    return (
        "You are a fact extractor. Read the following conversation transcript and "
        "extract all notable facts, decisions, names, dates, tasks, and key information. "
        "Return ONLY a flat JSON object (no markdown fences, no preamble, no explanation) "
        "where each key is a short snake_case identifier and each value is a concise string. "
        "Example output: {\"project_name\": \"GopherDigest\", \"deadline\": \"2026-04-15\"}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )


def _append_log(entry: str) -> None:
    _ensure_data_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(DIGEST_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp}\n\n{entry}\n")


@mcp.tool()
def digest_transcript(transcript_path: str, gophercache_context_path: str) -> str:
    """Read a transcript file, extract structured facts via Ollama, and merge them into GopherCache context.json."""
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = transcript_file.read_text(encoding="utf-8")
    prompt = _build_extract_prompt(transcript)
    raw = _call_ollama(prompt)

    # Strip any accidental markdown fences the model may have included
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    try:
        new_facts: dict = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Ollama did not return valid JSON. Raw response:\n{raw}"
        ) from exc

    context_file = Path(gophercache_context_path)
    if context_file.exists():
        existing: dict = json.loads(context_file.read_text(encoding="utf-8"))
    else:
        existing = {}

    existing.update(new_facts)
    context_file.parent.mkdir(parents=True, exist_ok=True)
    context_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    keys_added = list(new_facts.keys())
    log_entry = (
        f"**Transcript:** `{transcript_path}`  \n"
        f"**Context written to:** `{gophercache_context_path}`  \n"
        f"**Keys merged:** {keys_added}"
    )
    _append_log(log_entry)

    return json.dumps(
        {
            "status": "ok",
            "keys_merged": keys_added,
            "context_path": str(context_file),
        }
    )


@mcp.tool()
def summarize_only(transcript_path: str) -> str:
    """Read a transcript and return extracted facts as JSON text without writing anywhere."""
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = transcript_file.read_text(encoding="utf-8")
    prompt = _build_extract_prompt(transcript)
    return _call_ollama(prompt)


@mcp.tool()
def read_digest_log() -> str:
    """Return the full contents of the digest log."""
    if not DIGEST_LOG.exists():
        return "(No digest log found. Run digest_transcript first.)"
    return DIGEST_LOG.read_text(encoding="utf-8")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
