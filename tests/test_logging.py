"""Limits that bite must reach the person running gopher, not just the model (#22)."""

import logging

import httpx
import pytest

from gopher import server
from gopher.fetch import tools

LOGGER = "gopher.fetch.tools"


def _client(n_files, file_text):
    tree = {
        "tree": [
            {"path": f"src/m{i}/f{i}.py", "type": "blob", "size": len(file_text)}
            for i in range(n_files)
        ]
    }

    def handle(request: httpx.Request) -> httpx.Response:
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json=tree)
        if "/contents/" in request.url.path:
            return httpx.Response(200, content=file_text.encode())
        return httpx.Response(200, json={"default_branch": "main"})

    return httpx.Client(transport=httpx.MockTransport(handle))


def _digest(n_files, file_text, budget):
    with _client(n_files, file_text) as c:
        return tools.build_digest("https://github.com/o/r", c, budget=budget)


@pytest.fixture
def restore_logging():
    """Undo configure_logging after a test.

    Tests call configure_logging in their own body rather than here. pytest
    swaps sys.stderr between fixture setup and the test, so a handler created
    during setup keeps writing to a stream that has since been closed.
    """
    yield
    logger = logging.getLogger("gopher")
    for h in [h for h in logger.handlers if h.get_name() == server._HANDLER_NAME]:
        logger.removeHandler(h)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)


# when it logs


def test_logs_when_the_budget_stops_the_file_list(caplog):
    """The regression test for #22. Before this, nothing logged at all."""
    with caplog.at_level(logging.INFO, logger=LOGGER):
        _digest(n_files=200, file_text="x" * 5_000, budget=10_000)

    line = caplog.text
    assert "o/r: digest limited to 10,000 chars" in line
    assert "stopped by the budget" in line


def test_logs_when_the_tree_is_cut(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        _digest(n_files=5_000, file_text="x" * 100, budget=20_000)

    assert "tree " in caplog.text
    assert " entries" in caplog.text


def test_logs_how_far_over_budget_the_repo_is(caplog):
    """Jo Do's point: 10% over and 10x over need different responses."""
    with caplog.at_level(logging.INFO, logger=LOGGER):
        _digest(n_files=200, file_text="x" * 5_000, budget=10_000)

    # 200 files of 5,000 bytes against a 10,000 character budget
    assert "1,000,000 bytes, 100.0x the budget" in caplog.text


def test_logs_trimmed_files(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        _digest(n_files=3, file_text="y" * 500_000, budget=20_000)

    assert "trimmed" in caplog.text


# when it does not


def test_silent_when_nothing_was_cut(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        _digest(n_files=2, file_text="real content comfortably above the floor " * 3, budget=40_000)

    assert caplog.text == ""


def test_silent_when_files_were_skipped_for_being_empty(caplog):
    """Skipped is not limited. Saying 'limited' here would be false."""
    with caplog.at_level(logging.INFO, logger=LOGGER):
        out = _digest(n_files=2, file_text="tiny", budget=40_000)

    assert "0 of 2 shown" in out
    assert caplog.text == ""


# where it goes


def test_log_lines_go_to_stderr_and_never_stdout(capsys, restore_logging):
    """stdout is the protocol channel on a stdio server."""
    server.configure_logging()
    _digest(n_files=200, file_text="x" * 5_000, budget=10_000)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "gopher: o/r: digest limited to 10,000 chars" in captured.err


def test_configure_logging_is_idempotent(restore_logging):
    server.configure_logging()
    logger = server.configure_logging()

    ours = [h for h in logger.handlers if h.get_name() == server._HANDLER_NAME]
    assert len(ours) == 1


def test_importing_gopher_configures_nothing():
    """A library import, or the test suite, should print nothing."""
    logger = logging.getLogger("gopher")
    assert not any(h.get_name() == server._HANDLER_NAME for h in logger.handlers)
