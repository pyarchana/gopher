# Contributing

Bug reports and pull requests are welcome.

## Setup

```bash
git clone https://github.com/pyarchana/gopher.git
cd gopher
uv venv
uv pip install -e ".[dev]"
```

## Running tests

```bash
uv run pytest
```

If that fails with a file lock on `Scripts/gopher.exe`, you have the server
registered in a running Claude client, which holds the executable open so uv
cannot reinstall over it. Skip the reinstall:

```bash
uv run --no-sync pytest
```

## Linting

```bash
uvx ruff check .
uvx ruff format .
```

CI runs the tests on Python 3.11 through 3.14 and checks lint and formatting,
so it is worth running both locally before opening a pull request.

## Guidelines

- Keep the sieve logic in the `IGNORED_*` constants at the top of `src/gopher/fetch/sieve.py`
- Rules that promote a file go in `PRIORITY_NAMES`, `PRIORITY_DIRS` or `LANGUAGE_EXTENSIONS`
- Rules that demote one go in `TEST_DIRS`, `VENDOR_DIRS`, `EXAMPLE_DIRS` or `LOCALISABLE_DOCS`
- Measure a scoring change against several real repositories before and after. It is
  easy to talk yourself into a ranking rule that reads well and picks worse files
- Keep the tool interface to a single clean output string, no side effects
