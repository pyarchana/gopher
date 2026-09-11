import json

import pytest

from gopher.cache import store
from gopher.digest import ollama, tools


@pytest.fixture
def digest_env(tmp_path, monkeypatch):
    """Point the store, the log, and the model at throwaway things."""
    monkeypatch.setattr(store, "CONTEXT_FILE", tmp_path / "context.json")
    monkeypatch.setattr(store, "ensure_data_dir", lambda: None)
    monkeypatch.setattr(tools, "DIGEST_LOG", tmp_path / "digest_log.md")
    monkeypatch.setattr(tools, "ensure_data_dir", lambda: None)

    transcript = tmp_path / "transcript.md"
    transcript.write_text("a conversation", encoding="utf-8")

    def reply(text):
        monkeypatch.setattr(tools, "call_ollama", lambda _prompt: text)

    return transcript, reply, tmp_path


# parse_facts


def test_accepts_a_flat_object():
    assert ollama.parse_facts('{"a": "1", "b": "2"}') == {"a": "1", "b": "2"}


def test_strips_markdown_fences():
    assert ollama.parse_facts('```json\n{"a": "1"}\n```') == {"a": "1"}


def test_stringifies_numbers_and_booleans():
    """A model answering {"count": 3} plainly meant the fact."""
    got = ollama.parse_facts('{"count": 3, "ratio": 1.5, "done": true, "open": false}')
    assert got == {"count": "3", "ratio": "1.5", "done": "true", "open": "false"}


def test_refuses_prose():
    with pytest.raises(ollama.InvalidFacts, match="did not return JSON"):
        ollama.parse_facts("Sure! Here are the facts I found:")


def test_refuses_a_list():
    with pytest.raises(ollama.InvalidFacts, match="returned a list"):
        ollama.parse_facts('["a", "b"]')


def test_refuses_a_nested_object_and_names_the_key():
    with pytest.raises(ollama.InvalidFacts, match="'project'"):
        ollama.parse_facts('{"project": {"name": "gopher"}}')


def test_refuses_a_list_valued_fact():
    with pytest.raises(ollama.InvalidFacts, match="holds a list"):
        ollama.parse_facts('{"tags": ["a", "b"]}')


# digest_transcript (#8)


def test_writes_to_the_configured_store_not_a_supplied_path(digest_env):
    """The regression test for #8.

    digest_transcript used to take the destination as an argument, so the
    model chose which file on disk to overwrite with JSON.
    """
    transcript, reply, _ = digest_env
    reply('{"project": "gopher"}')

    tools.digest_transcript(str(transcript))

    assert store.read_context_raw() == {"project": "gopher"}
    import inspect

    assert list(inspect.signature(tools.digest_transcript).parameters) == ["transcript_path"]


def test_new_facts_are_reported_as_added(digest_env):
    transcript, reply, _ = digest_env
    reply('{"a": "1", "b": "2"}')

    result = json.loads(tools.digest_transcript(str(transcript)))
    assert sorted(result["added"]) == ["a", "b"]
    assert result["overwritten"] == []


def test_an_overwrite_is_recorded_with_both_values(digest_env):
    transcript, reply, tmp_path = digest_env
    reply('{"status": "draft"}')
    tools.digest_transcript(str(transcript))

    reply('{"status": "submitted"}')
    result = json.loads(tools.digest_transcript(str(transcript)))

    assert result["overwritten"] == [{"key": "status", "was": "draft", "now": "submitted"}]
    log = (tmp_path / "digest_log.md").read_text(encoding="utf-8")
    assert "'draft' -> 'submitted'" in log


def test_an_unchanged_value_is_not_reported_as_an_overwrite(digest_env):
    transcript, reply, _ = digest_env
    reply('{"status": "draft"}')
    tools.digest_transcript(str(transcript))
    result = json.loads(tools.digest_transcript(str(transcript)))

    assert result["overwritten"] == []
    assert result["added"] == []


def test_a_fact_that_would_destroy_a_section_is_refused(digest_env):
    transcript, reply, _ = digest_env
    store.write_context({"projects": {"gopher": "active"}})

    reply('{"projects": "none", "other": "kept"}')
    result = json.loads(tools.digest_transcript(str(transcript)))

    assert [r["key"] for r in result["refused"]] == ["projects"]
    assert result["added"] == ["other"]
    # the rest of the batch still landed, and the section survived
    assert store.read_context_raw()["projects"] == {"gopher": "active"}
    assert store.read_context_raw()["other"] == "kept"


def test_invalid_model_output_writes_nothing(digest_env):
    transcript, reply, _ = digest_env
    store.write_context({"existing": "value"})

    reply("I could not find any facts.")
    with pytest.raises(ollama.InvalidFacts):
        tools.digest_transcript(str(transcript))

    assert store.read_context_raw() == {"existing": "value"}


def test_a_missing_transcript_is_reported_before_calling_the_model(digest_env):
    _, reply, tmp_path = digest_env
    reply('{"a": "1"}')

    with pytest.raises(FileNotFoundError):
        tools.digest_transcript(str(tmp_path / "nope.md"))


def test_dot_paths_in_fact_keys_nest_properly(digest_env):
    transcript, reply, _ = digest_env
    reply('{"projects.gopher.status": "active"}')

    tools.digest_transcript(str(transcript))
    assert store.read_context_raw() == {"projects": {"gopher": {"status": "active"}}}


# summarize_only


def test_summarize_writes_nothing(digest_env):
    transcript, reply, _ = digest_env
    reply('{"a": "1"}')

    out = tools.summarize_only(str(transcript))

    assert json.loads(out) == {"a": "1"}
    assert store.read_context_raw() == {}


def test_summarize_applies_the_same_validation(digest_env):
    """A preview that accepts what the write path rejects is not a preview."""
    transcript, reply, _ = digest_env
    reply('{"project": {"nested": "thing"}}')

    with pytest.raises(ollama.InvalidFacts):
        tools.summarize_only(str(transcript))
