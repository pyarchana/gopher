"""Local Ollama client, the fact-extraction prompt, and parsing its reply."""

import json

import httpx

from gopher.config import OLLAMA_MODEL, OLLAMA_URL


class InvalidFacts(ValueError):
    """The model returned something that is not a flat map of facts.

    Raised rather than coerced. A 3B model asked for JSON will sometimes
    return prose, a list, or nested objects, and writing any of those into
    the context store corrupts it in ways only discovered much later.
    """


def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
    return response.json()["response"].strip()


def build_extract_prompt(transcript: str) -> str:
    return (
        "You are a fact extractor. Read the following conversation transcript and "
        "extract all notable facts, decisions, names, dates, tasks, and key information. "
        "Return ONLY a flat JSON object (no markdown fences, no preamble, no explanation) "
        "where each key is a short snake_case identifier and each value is a concise string. "
        'Example output: {"project_name": "example", "deadline": "2026-04-15"}\n\n'
        f"TRANSCRIPT:\n{transcript}"
    )


def parse_facts(raw: str) -> dict[str, str]:
    """Turn a model reply into a flat map of facts, or refuse it.

    Numbers and booleans are accepted and stringified, since a model
    answering `{"count": 3}` plainly meant the fact. Lists and nested
    objects are refused: the store is a dot-path tree and burying a
    structure under one key makes it unreachable.
    """
    cleaned = raw.strip()

    # Models ignore "no markdown fences" often enough to be worth handling.
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines() if not line.startswith("```")
        ).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InvalidFacts(
            f"model did not return JSON ({exc.msg}). First 200 characters of the "
            f"reply: {raw[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidFacts(
            f"model returned a {type(parsed).__name__}, not an object of facts. "
            f"First 200 characters: {raw[:200]!r}"
        )

    facts: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not key.strip():
            raise InvalidFacts(f"fact key {key!r} is not a usable name")
        if isinstance(value, bool):
            facts[key] = "true" if value else "false"
        elif isinstance(value, str | int | float):
            facts[key] = str(value)
        else:
            raise InvalidFacts(
                f"fact {key!r} holds a {type(value).__name__}, but the context store "
                "takes flat values. Nothing was written."
            )
    return facts
