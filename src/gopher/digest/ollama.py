"""Local Ollama client and the fact-extraction prompt."""

import httpx

from gopher.config import OLLAMA_MODEL, OLLAMA_URL


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
        "Example output: {\"project_name\": \"GopherDigest\", \"deadline\": \"2026-04-15\"}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )

