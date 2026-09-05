import json

import pytest

from gopher.cache import store, tools


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    """Point the store at a throwaway context.json."""
    path = tmp_path / "context.json"
    monkeypatch.setattr(store, "CONTEXT_FILE", path)
    monkeypatch.setattr(store, "ensure_data_dir", lambda: None)
    return path


def _explode(*args, **kwargs):
    raise RuntimeError("disk full")


# read / write round trip


def test_read_missing_file_returns_empty(ctx):
    assert store.read_context_raw() == {}


def test_write_then_read_round_trips(ctx):
    store.write_context({"projects": {"gopher": "active"}})
    assert store.read_context_raw() == {"projects": {"gopher": "active"}}


def test_write_is_valid_json_on_disk(ctx):
    store.write_context({"a": "1"})
    assert json.loads(ctx.read_text(encoding="utf-8")) == {"a": "1"}


def test_write_preserves_non_ascii(ctx):
    store.write_context({"greeting": "नमस्ते"})
    assert store.read_context_raw() == {"greeting": "नमस्ते"}


# atomicity


def test_successful_write_leaves_no_temp_files(ctx):
    store.write_context({"a": "1"})
    assert sorted(p.name for p in ctx.parent.iterdir()) == ["context.json"]


def test_failed_write_preserves_the_previous_store(ctx, monkeypatch):
    """The regression test for #1.

    A write that dies partway must not destroy what was already there.
    Against the old implementation this fails, because opening with "w"
    truncated the file before serialising a single byte.
    """
    store.write_context({"good": "data"})

    monkeypatch.setattr(store.json, "dump", _explode)
    with pytest.raises(RuntimeError):
        store.write_context({"replacement": "data"})

    assert store.read_context_raw() == {"good": "data"}


def test_failed_write_cleans_up_its_temp_file(ctx, monkeypatch):
    store.write_context({"good": "data"})

    monkeypatch.setattr(store.json, "dump", _explode)
    with pytest.raises(RuntimeError):
        store.write_context({"replacement": "data"})

    assert sorted(p.name for p in ctx.parent.iterdir()) == ["context.json"]


def test_failed_first_write_leaves_no_store_behind(ctx, monkeypatch):
    monkeypatch.setattr(store.json, "dump", _explode)
    with pytest.raises(RuntimeError):
        store.write_context({"a": "1"})

    assert not ctx.exists()
    assert list(ctx.parent.iterdir()) == []


# set_nested: the normal cases


def test_creates_missing_sections():
    data = {}
    store.set_nested(data, ["projects", "gopher", "status"], "active")
    assert data == {"projects": {"gopher": {"status": "active"}}}


def test_overwrites_a_value_with_another_value():
    data = {"a": "old"}
    store.set_nested(data, ["a"], "new")
    assert data == {"a": "new"}


def test_adds_a_sibling_without_disturbing_others():
    data = {"projects": {"gopher": "active"}}
    store.set_nested(data, ["projects", "precedent"], "submitted")
    assert data == {"projects": {"gopher": "active", "precedent": "submitted"}}


# set_nested: refusals (#2)


def test_writing_through_a_value_is_refused():
    """The regression test for #2.

    The old implementation raised TypeError here, and AttributeError on
    paths a level deeper, both from inside setdefault and neither naming
    the key that actually caused it.
    """
    data = {"projects": "gopher"}
    with pytest.raises(store.ContextKeyConflict) as exc:
        store.set_nested(data, ["projects", "status"], "active")

    assert "'projects'" in str(exc.value)
    assert "delete_context_key" in str(exc.value)


def test_refused_write_leaves_the_original_value_intact():
    data = {"projects": "gopher"}
    with pytest.raises(store.ContextKeyConflict):
        store.set_nested(data, ["projects", "status"], "active")

    assert data == {"projects": "gopher"}


def test_deep_collision_names_the_offending_prefix():
    data = {"a": {"b": "scalar"}}
    with pytest.raises(store.ContextKeyConflict) as exc:
        store.set_nested(data, ["a", "b", "c", "d"], "x")

    assert "'a.b'" in str(exc.value)


def test_overwriting_a_section_with_a_value_is_refused():
    data = {"projects": {"gopher": "active", "precedent": "submitted"}}
    with pytest.raises(store.ContextKeyConflict) as exc:
        store.set_nested(data, ["projects"], "none")

    assert "'projects'" in str(exc.value)
    assert "2 key(s)" in str(exc.value)


def test_refused_overwrite_leaves_the_section_intact():
    data = {"projects": {"gopher": "active"}}
    with pytest.raises(store.ContextKeyConflict):
        store.set_nested(data, ["projects"], "none")

    assert data == {"projects": {"gopher": "active"}}


# the conflict surfaces through the tool, not just the helper


def test_update_context_tool_reports_the_conflict(ctx):
    tools.update_context("projects", "gopher")
    with pytest.raises(store.ContextKeyConflict):
        tools.update_context("projects.status", "active")

    assert store.read_context_raw() == {"projects": "gopher"}


# diary


@pytest.fixture
def diary(tmp_path, monkeypatch):
    """Point the diary at a throwaway file."""
    path = tmp_path / "diary.md"
    monkeypatch.setattr(store, "DIARY_FILE", path)
    monkeypatch.setattr(store, "ensure_data_dir", lambda: None)
    return path


def test_missing_diary_reads_as_empty(diary):
    assert store.split_entries(store.read_diary_raw()) == []
    assert tools.read_diary() == "(diary is empty)"


def test_entries_are_split_one_per_header(diary):
    tools.log_diary("first")
    tools.log_diary("second")
    tools.log_diary("third")

    assert len(store.split_entries(store.read_diary_raw())) == 3


def test_an_entry_containing_an_h2_stays_one_entry(diary):
    """The regression test for #3.

    The old implementation split on the literal "\\n## ", so this produced
    two entries and the timestamp header was severed from its own body.
    """
    tools.log_diary("## Notes\n\nsomething worth keeping")

    entries = store.split_entries(store.read_diary_raw())
    assert len(entries) == 1
    assert "## Notes" in entries[0]
    assert "something worth keeping" in entries[0]


def test_several_headings_in_one_body_still_one_entry(diary):
    tools.log_diary("## One\n\ntext\n\n## Two\n\nmore\n\n### Three\n\nend")

    assert len(store.split_entries(store.read_diary_raw())) == 1


def test_tagged_headers_are_recognised(diary):
    tools.log_diary("body", tag="GSOC")
    tools.log_diary("body", tag="GATE")

    entries = store.split_entries(store.read_diary_raw())
    assert len(entries) == 2
    assert "[GSOC]" in entries[0]
    assert "[GATE]" in entries[1]


def test_read_diary_returns_the_last_n(diary):
    for i in range(5):
        tools.log_diary(f"entry {i}")

    out = tools.read_diary(2)
    assert "entry 3" in out
    assert "entry 4" in out
    assert "entry 0" not in out


def test_read_diary_asking_for_more_than_exists(diary):
    tools.log_diary("only one")
    assert "only one" in tools.read_diary(50)


def test_read_diary_zero_returns_nothing(diary):
    """entries[-0:] is entries[0:], so the old code returned everything."""
    tools.log_diary("secret")
    assert "secret" not in tools.read_diary(0)


def test_text_before_the_first_header_is_not_an_entry(diary):
    diary.write_text("hand written preamble\n", encoding="utf-8")
    tools.log_diary("real entry")

    entries = store.split_entries(store.read_diary_raw())
    assert len(entries) == 1
    assert "preamble" not in entries[0]
