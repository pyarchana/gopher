import base64

import httpx

from gopher.fetch import github, tools


def _handler(tree_payload, meta=None, file_text="hello"):
    """Route the three GitHub endpoints the fetch path uses."""
    meta = meta or {"default_branch": "main", "stargazers_count": 3, "language": "Python"}
    encoded = base64.b64encode(file_text.encode()).decode()

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/git/trees/" in path:
            return httpx.Response(200, json=tree_payload)
        if "/contents/" in path:
            return httpx.Response(200, json={"content": encoded})
        return httpx.Response(200, json=meta)

    return handle


def _client(tree_payload, **kw):
    return httpx.Client(transport=httpx.MockTransport(_handler(tree_payload, **kw)))


def _blobs(*paths):
    return [{"path": p, "type": "blob", "size": 500} for p in paths]


# fetch_tree


def test_reports_not_truncated_when_the_api_says_so():
    payload = {"tree": _blobs("main.py"), "truncated": False}
    with _client(payload) as c:
        assert github.fetch_tree("o", "r", c).truncated is False


def test_reports_truncated_when_the_api_says_so():
    """The regression test for #4.

    The old implementation read data["tree"] and never looked at this
    flag, so a capped listing was rendered as a complete directory tree
    with nothing to indicate otherwise.
    """
    payload = {"tree": _blobs("main.py"), "truncated": True}
    with _client(payload) as c:
        assert github.fetch_tree("o", "r", c).truncated is True


def test_missing_truncated_key_is_treated_as_complete():
    with _client({"tree": _blobs("main.py")}) as c:
        assert github.fetch_tree("o", "r", c).truncated is False


def test_only_blobs_are_returned():
    payload = {
        "tree": [
            {"path": "src", "type": "tree"},
            {"path": "src/main.py", "type": "blob", "size": 100},
            {"path": "sub", "type": "commit"},
        ]
    }
    with _client(payload) as c:
        result = github.fetch_tree("o", "r", c)
    assert [b["path"] for b in result.blobs] == ["src/main.py"]


def test_branch_and_meta_come_from_the_repo_endpoint():
    payload = {"tree": _blobs("main.py")}
    meta = {"default_branch": "develop", "stargazers_count": 9}
    with _client(payload, meta=meta) as c:
        result = github.fetch_tree("o", "r", c)
    assert result.branch == "develop"
    assert result.meta["stargazers_count"] == 9


# the digest tells the truth about it


def _digest(tree_payload, **kw):
    with _client(tree_payload, **kw) as c:
        return tools.build_digest("https://github.com/o/r", c)


def test_digest_warns_when_the_listing_was_capped():
    out = _digest({"tree": _blobs("main.py", "README.md"), "truncated": True})

    assert "Partial listing" in out
    assert "Directory Tree (partial)" in out


def test_digest_says_nothing_when_the_listing_is_complete():
    out = _digest({"tree": _blobs("main.py", "README.md"), "truncated": False})

    assert "Partial listing" not in out
    assert "## Directory Tree" in out
    assert "(partial)" not in out


def test_the_warning_reports_how_many_files_were_seen():
    out = _digest({"tree": _blobs("a.py", "b.py", "c.py"), "truncated": True})

    assert "3 files came back before the cap" in out


def test_the_warning_comes_before_the_tree():
    """It is only useful if it is read first."""
    out = _digest({"tree": _blobs("main.py"), "truncated": True})

    assert out.index("Partial listing") < out.index("Directory Tree")
