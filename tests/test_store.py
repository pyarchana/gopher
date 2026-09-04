import json

import pytest

from gopher.cache import store


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
