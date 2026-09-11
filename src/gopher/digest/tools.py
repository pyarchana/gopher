"""MCP tools for digesting transcripts into the context store."""

import json
from datetime import UTC, datetime
from pathlib import Path

from gopher.cache.store import (
    ContextKeyConflict,
    get_nested,
    read_context_raw,
    set_nested,
    write_context,
)
from gopher.config import DIGEST_LOG, ensure_data_dir
from gopher.digest.ollama import build_extract_prompt, call_ollama, parse_facts


def append_log(entry: str) -> None:
    ensure_data_dir()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(DIGEST_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp}\n\n{entry}\n")


def _extract(transcript_path: str) -> dict[str, str]:
    """Read a transcript and pull facts out of it, writing nothing."""
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = transcript_file.read_text(encoding="utf-8")
    return parse_facts(call_ollama(build_extract_prompt(transcript)))


def digest_transcript(transcript_path: str) -> str:
    """Read a transcript, extract facts with the local model, and merge them
    into the context store.

    The destination is not a parameter. It is always the configured store,
    so this tool cannot be pointed at an arbitrary file.

    A fact that would overwrite an existing value is applied and recorded
    with what it replaced. A fact that would destroy a section is refused
    and reported, without stopping the rest of the batch.
    """
    facts = _extract(transcript_path)

    context = read_context_raw()
    added: list[str] = []
    overwritten: list[dict] = []
    refused: list[dict] = []

    for key, value in facts.items():
        keys = key.split(".")
        previous = get_nested(context, keys)
        try:
            set_nested(context, keys, value)
        except ContextKeyConflict as exc:
            refused.append({"key": key, "reason": str(exc)})
            continue
        if previous is None:
            added.append(key)
        elif previous != value:
            overwritten.append({"key": key, "was": previous, "now": value})

    write_context(context)

    lines = [
        f"**Transcript:** `{transcript_path}`  ",
        f"**Added:** {added or 'none'}  ",
    ]
    if overwritten:
        lines.append("**Replaced:**  ")
        lines += [f"- `{o['key']}`: {o['was']!r} -> {o['now']!r}  " for o in overwritten]
    if refused:
        lines.append("**Refused:**  ")
        lines += [f"- `{r['key']}`: {r['reason']}  " for r in refused]
    append_log("\n".join(lines))

    return json.dumps(
        {
            "status": "ok",
            "added": added,
            "overwritten": overwritten,
            "refused": refused,
        },
        indent=2,
        ensure_ascii=False,
    )


def summarize_only(transcript_path: str) -> str:
    """Extract facts from a transcript and return them without writing.

    Runs the same validation the write path does, so what this shows is
    what a digest would actually store.
    """
    return json.dumps(_extract(transcript_path), indent=2, ensure_ascii=False)


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
