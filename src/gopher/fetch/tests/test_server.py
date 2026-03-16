import pytest
from server import parse_repo_url, is_ignored, file_priority_score


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
