import pytest

from gopher.fetch.github import parse_repo_url
from gopher.fetch.sieve import file_priority_score, is_ignored

# parse_repo_url


def test_parse_https_url():
    owner, repo = parse_repo_url("https://github.com/openai/gpt-2")
    assert owner == "openai"
    assert repo == "gpt-2"


def test_parse_https_url_trailing_slash():
    owner, repo = parse_repo_url("https://github.com/owner/repo/")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_git_ssh_url():
    owner, repo = parse_repo_url("git@github.com:owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_invalid_url():
    with pytest.raises(ValueError):
        parse_repo_url("https://gitlab.com/owner/repo")


# is_ignored


def test_ignores_node_modules():
    assert is_ignored("node_modules/lodash/index.js") is True


def test_ignores_venv():
    assert is_ignored("venv/lib/python3.11/site.py") is True


def test_ignores_image():
    assert is_ignored("assets/logo.png") is True


def test_ignores_lock_file():
    assert is_ignored("package-lock.json") is True


def test_ignores_minified():
    assert is_ignored("static/app.min.js") is True


def test_does_not_ignore_source():
    assert is_ignored("src/main.py") is False


def test_does_not_ignore_config():
    assert is_ignored("pyproject.toml") is False


# file_priority_score


def test_main_py_scores_high():
    item = {"name": "main.py", "path": "main.py", "size": 1000}
    assert file_priority_score(item) >= 1000


def test_src_dir_adds_score():
    item = {"name": "utils.py", "path": "src/utils.py", "size": 500}
    score = file_priority_score(item)
    item_no_src = {"name": "utils.py", "path": "utils.py", "size": 500}
    score_no_src = file_priority_score(item_no_src)
    assert score > score_no_src


def test_reasonable_size_scores_higher_than_empty():
    big = {"name": "app.py", "path": "app.py", "size": 5000}
    empty = {"name": "app.py", "path": "app.py", "size": 0}
    assert file_priority_score(big) > file_priority_score(empty)


# ranking corrections (#14)


def _f(path, size=5_000):
    from pathlib import PurePosixPath

    return {"name": PurePosixPath(path).name, "path": path, "size": size}


def test_a_priority_name_is_worth_less_the_deeper_it_sits():
    root = _f("pyproject.toml")
    nested = _f("src/subpackage/pyproject.toml")
    assert file_priority_score(root) > file_priority_score(nested)


def test_uv_case_the_real_manifest_beats_a_test_fixture():
    """astral-sh/uv once digested as pandas' and airflow's dependency lists."""
    real = _f("Cargo.toml")
    fixture = _f("test/ecosystem/pandas/pyproject.toml", size=27_517)
    assert file_priority_score(real) > file_priority_score(fixture)


def test_test_directories_are_demoted():
    src = _f("src/thing.py")
    test = _f("tests/thing.py")
    assert file_priority_score(src) > file_priority_score(test)


def test_vendored_code_is_demoted_hardest():
    vendored = _f("third_party/thing.py")
    tested = _f("tests/thing.py")
    example = _f("examples/thing.py")
    assert file_priority_score(vendored) < file_priority_score(tested)
    assert file_priority_score(tested) < file_priority_score(example)


def test_examples_are_demoted_only_gently():
    """Sometimes an examples directory is the best documentation there is."""
    example = _f("examples/demo.py")
    plain = _f("src/thing.py")
    assert file_priority_score(plain) - file_priority_score(example) < 700


def test_awesome_case_a_readme_beats_its_translations():
    """One digest once spent 224,000 characters on seven of these."""
    original = _f("README.md")
    for translated in ("README-ja.md", "README-zh_TW.md", "README-pt_BR.md", "README-fa-ir.md"):
        assert file_priority_score(original) > file_priority_score(_f(translated))


def test_a_source_file_is_not_mistaken_for_a_translation():
    """parse-db.py looks locale-suffixed but is not a translated document."""
    a = _f("src/parse-db.py")
    b = _f("src/parse.py")
    assert abs(file_priority_score(a) - file_priority_score(b)) < 100


def test_the_repository_language_is_favoured():
    rust_repo = {"language": "Rust"}
    rs = _f("crates/thing/src/lib.rs")
    toml = _f("crates/thing/thing.toml")
    assert file_priority_score(rs, rust_repo) > file_priority_score(toml, rust_repo)


def test_language_bonus_needs_metadata():
    item = _f("src/lib.rs")
    assert file_priority_score(item, {"language": "Rust"}) > file_priority_score(item)


def test_an_unknown_language_changes_nothing():
    item = _f("src/thing.py")
    assert file_priority_score(item, {"language": "Brainfuck"}) == file_priority_score(item)
