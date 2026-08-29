"""MCP tools for digesting transcripts into the context store."""

import json
from datetime import datetime, timezone
from pathlib import Path

from gopher.config import DIGEST_LOG, ensure_data_dir
from gopher.digest.ollama import build_extract_prompt, call_ollama


def append_log(entry: str) -> None:
    ensure_data_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(DIGEST_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp}\n\n{entry}\n")


def digest_transcript(transcript_path: str, gophercache_context_path: str) -> str:
    """Read a transcript file, extract structured facts via Ollama, and merge them into GopherCache context.json."""
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = transcript_file.read_text(encoding="utf-8")
    prompt = build_extract_prompt(transcript)
    raw = call_ollama(prompt)

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
    append_log(log_entry)

    return json.dumps(
        {
            "status": "ok",
            "keys_merged": keys_added,
            "context_path": str(context_file),
        }
    )


def summarize_only(transcript_path: str) -> str:
    """Read a transcript and return extracted facts as JSON text without writing anywhere."""
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = transcript_file.read_text(encoding="utf-8")
    prompt = build_extract_prompt(transcript)
    return call_ollama(prompt)


def read_digest_log() -> str:
    """Return the full contents of the digest log."""
    if not DIGEST_LOG.exists():
        return "(No digest log found. Run digest_transcript first.)"
    return DIGEST_LOG.read_text(encoding="utf-8")


def register(mcp) -> None:
    """Attach this module's tools to the shared FastMCP instance."""
    mcp.tool()(digest_transcript)
    mcp.tool()(summarize_only)
    mcp.tool()(read_digest_log)
