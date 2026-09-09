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


# the budget (#5)


def _big_repo(n_files=200, file_chars=5_000):
    payload = {"tree": _blobs(*[f"src/mod{i}/file{i}.py" for i in range(n_files)])}
    return payload, "x" * file_chars


def _digest_within(budget, n_files=200, file_chars=5_000):
    payload, text = _big_repo(n_files, file_chars)
    with _client(payload, file_text=text) as c:
        return tools.build_digest("https://github.com/o/r", c, budget=budget)


def test_digest_stays_within_budget():
    """The regression test for #5.

    With a fixed count of 10 files this returned whatever those 10 happened
    to weigh. Measured against real repos that ranged from 4,594 characters
    to 228,310, and anything over the client's limit was rejected whole.
    """
    for budget in (10_000, 20_000, 40_000):
        out = _digest_within(budget)
        assert len(out) <= budget, f"{len(out)} exceeded {budget}"


def test_a_bigger_budget_returns_more():
    small = _digest_within(10_000)
    large = _digest_within(40_000)
    assert len(large) > len(small)


def test_the_tree_alone_cannot_eat_the_budget():
    """uv's tree measured 65,530 characters on its own."""
    out = _digest_within(20_000, n_files=5_000)
    tree_block = out.split("```")[1]
    assert len(tree_block) <= 20_000 * 0.25 + 200
    assert "more entries, omitted" in tree_block


def test_omitted_files_are_counted_in_the_heading():
    out = _digest_within(10_000, n_files=200)
    assert "omitted to fit 10,000 chars" in out


def test_a_small_repo_omits_nothing_and_says_nothing():
    payload = {"tree": _blobs("main.py", "README.md")}
    with _client(payload, file_text="real content, comfortably above the minimum floor" * 3) as c:
        out = tools.build_digest("https://github.com/o/r", c, budget=40_000)

    assert "omitted" not in out
    assert "2 of 2 shown" in out


def test_one_huge_file_cannot_crowd_out_the_rest():
    """Seven translated READMEs once filled 224,000 characters of one digest."""
    payload = {"tree": _blobs("a.md", "b.md", "c.md", "d.md")}
    with _client(payload, file_text="y" * 500_000) as c:
        out = tools.build_digest("https://github.com/o/r", c, budget=20_000)

    assert len(out) <= 20_000
    assert out.count("### `") >= 2, "one file consumed everything"


def test_files_below_the_floor_are_skipped():
    payload = {"tree": _blobs("main.py", "README.md")}
    with _client(payload, file_text="") as c:
        out = tools.build_digest("https://github.com/o/r", c, budget=40_000)

    assert "0 of 2 shown" in out


def test_the_file_count_is_no_longer_fixed_at_ten():
    out = _digest_within(40_000, n_files=200, file_chars=300)
    assert out.count("### `") > 10


# files the contents endpoint will not serve (#15)


def _oversized_handler(blob_text, calls):
    """Mimic GitHub refusing a file over 1MB, then serving it as a blob."""

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if "/git/blobs/" in path:
            return httpx.Response(
                200,
                json={
                    "content": base64.b64encode(blob_text.encode()).decode(),
                    "encoding": "base64",
                },
            )
        if "/contents/" in path:
            # what GitHub actually returns: 200, empty body, encoding "none"
            return httpx.Response(
                200, json={"content": "", "encoding": "none", "size": 1_616_144, "sha": "abc123"}
            )
        return httpx.Response(200, json={"default_branch": "main"})

    return handle


def test_a_file_too_large_for_contents_falls_back_to_blobs():
    """The regression test for #15.

    punkpeye/awesome-mcp-servers has a 1,616,144 byte README. The contents
    endpoint answered 200 with an empty body, the decode produced "", and
    the highest-ranked file in that repo silently vanished.
    """
    calls: list[str] = []
    with httpx.Client(
        transport=httpx.MockTransport(_oversized_handler("real content", calls))
    ) as c:
        got = github.fetch_file_content("o", "r", "README.md", c)

    assert got == "real content"
    assert any("/git/blobs/abc123" in p for p in calls)


def test_the_fallback_still_respects_the_cap():
    calls: list[str] = []
    with httpx.Client(transport=httpx.MockTransport(_oversized_handler("z" * 5_000, calls))) as c:
        got = github.fetch_file_content("o", "r", "README.md", c, max_chars=100)

    assert got.startswith("z" * 100)
    assert "trimmed, showing first 100 of 5,000 chars" in got


def test_a_normal_file_does_not_touch_the_blobs_endpoint():
    """The fallback is an extra API call, so it must not fire routinely."""
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "/contents/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "content": base64.b64encode(b"small file").decode(),
                    "encoding": "base64",
                    "size": 10,
                },
            )
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(handle)) as c:
        assert github.fetch_file_content("o", "r", "a.py", c) == "small file"

    assert not any("/git/blobs/" in p for p in calls)


def test_a_genuinely_empty_file_is_not_mistaken_for_an_oversized_one():
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "/contents/" in request.url.path:
            return httpx.Response(200, json={"content": "", "encoding": "base64", "size": 0})
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(handle)) as c:
        assert github.fetch_file_content("o", "r", "empty.py", c) == ""

    assert not any("/git/blobs/" in p for p in calls)
