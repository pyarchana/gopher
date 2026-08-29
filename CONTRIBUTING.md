# Contributing

Bug reports and pull requests are welcome.

## Setup

```bash
git clone https://github.com/areychana/gopherfetch.git
cd gopherfetch
uv venv
uv pip install -e ".[dev]"
```

## Running tests

```bash
uv run pytest
```

## Guidelines

- Keep the sieve logic in the `IGNORED_*` constants at the top of `server.py`
- New file priority rules go in `PRIORITY_NAMES` or `PRIORITY_DIRS`
- Keep the tool interface to a single clean output string — no side effects
