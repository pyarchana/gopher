"""Filtering and ranking rules. This is the tuning surface for repo digests.

New ignore rules go in the IGNORED_* sets. Ranking is split between
things that promote a file (PRIORITY_NAMES, PRIORITY_DIRS,
LANGUAGE_EXTENSIONS) and things that demote one (TEST_DIRS, VENDOR_DIRS,
EXAMPLE_DIRS, LOCALISABLE_DOCS).

Scoring changes are easy to talk yourself into and hard to judge by
reading. Measure a change against several real repositories before and
after, rather than reasoning about it.
"""

import re
from pathlib import PurePosixPath

# fmt: off
# These are grouped by kind on purpose: images, then fonts, then media,
# archives, binaries, documents. The line breaks carry the meaning, and
# CONTRIBUTING.md sends contributors here to add rules. Letting the
# formatter flatten them into one entry per line would lose that.
IGNORED_DIRS = {
    ".git", ".github", ".idea", ".vscode",
    "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "dist", "build", ".next", ".nuxt", "out",
    "coverage", ".coverage", "htmlcov",
    "vendor", "target", "bin", "obj",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".tiff",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".mp4", ".mov", ".avi", ".mp3", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".class", ".pyc",
    ".pyd", ".wasm", ".bin", ".dat",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".lock", ".map", ".min.js",
}

IGNORED_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "Gemfile.lock", "composer.lock",
    ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes",
    ".editorconfig", ".prettierrc", ".eslintignore",
}

PRIORITY_NAMES = [
    "main.py", "app.py", "server.py", "index.py",
    "main.js", "index.js", "app.js", "server.js",
    "main.ts", "index.ts", "app.ts",
    "main.go", "main.rs", "main.cpp", "main.c",
    "Main.java",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "Cargo.toml", "go.mod", "pom.xml",
    "requirements.txt", "Pipfile",
    "README.md", "README.txt", "README.rst",
    ".env.example", "config.py", "settings.py", "config.js",
]
# fmt: on

PRIORITY_DIRS = {"src", "lib", "contracts", "core", "api", "app"}

# fmt: off
#: Directories holding fixtures rather than the project's own code. Heavily
#: demoted: uv's digest once spent 89,000 characters on other projects'
#: dependency files pulled from test/ecosystem/.
TEST_DIRS = {
    "test", "tests", "testing", "spec", "specs",
    "fixture", "fixtures", "testdata", "test_data",
    "benchmark", "benchmarks", "bench",
}

#: Vendored copies of other people's code. Never the answer to "what is
#: this repository".
VENDOR_DIRS = {"vendor", "third_party", "thirdparty", "external", "extern", "deps"}

#: Demoted, but only gently. An examples directory is sometimes the best
#: documentation a project has.
EXAMPLE_DIRS = {"example", "examples", "sample", "samples", "demo", "demos"}

#: Extensions that count as the repository's primary language, keyed by the
#: name GitHub reports in the repo metadata.
LANGUAGE_EXTENSIONS = {
    "python": {".py", ".pyi"},
    "rust": {".rs"},
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx", ".mjs"},
    "go": {".go"},
    "java": {".java"},
    "kotlin": {".kt", ".kts"},
    "c++": {".cpp", ".cc", ".cxx", ".hpp"},
    "c": {".c", ".h"},
    "c#": {".cs"},
    "ruby": {".rb"},
    "php": {".php"},
    "swift": {".swift"},
    "shell": {".sh", ".bash"},
}

#: Documents that commonly ship translated copies. Only these get the
#: locale check, so a source file like `parse-db.py` is not mistaken for
#: a translation of `parse`.
LOCALISABLE_DOCS = {"readme", "contributing", "changelog", "license", "code_of_conduct"}
# fmt: on

#: A trailing locale tag: README-ja, README-zh_TW, README-pt_BR, README-fa-ir.
LOCALE_SUFFIX = re.compile(r"^(.*?)[-_][a-z]{2}(?:[-_][a-z]{2,4})?$", re.IGNORECASE)

# How the digest budget in config.DIGEST_BUDGET gets divided up. These are
# fractions rather than fixed sizes so that changing the budget moves all
# of them together.

#: Share of the budget the directory tree may occupy. Measured at 65,530
#: characters for astral-sh/uv and 57,306 for the MCP python-sdk, which is
#: why the tree needs a cap of its own and not just the file content.
TREE_BUDGET_FRACTION = 0.25

#: Most of the remaining budget any single file may take. Without this one
#: large file crowds out everything else: seven translated copies of the
#: same README once filled 224,000 characters of a single digest.
MAX_FILE_FRACTION = 0.40

#: Ceiling on files fetched, regardless of budget. Each one is an API call,
#: and unauthenticated GitHub allows only 60 an hour.
MAX_FILES = 30

#: Below this a file contributes nothing worth an API call.
MIN_FILE_CHARS = 50

#: Held back for everything that is neither tree nor file content: the
#: title, description, metadata table, and the partial-listing and missing
#: README notices. Measured at roughly 460 characters, with headroom for a
#: long repo description.
HEADER_RESERVE = 1_200


def is_ignored(path: str) -> bool:
    parts = PurePosixPath(path).parts
    for part in parts[:-1]:
        if part in IGNORED_DIRS:
            return True
    filename = parts[-1]
    if filename in IGNORED_FILENAMES:
        return True
    ext = PurePosixPath(filename).suffix.lower()
    if ext in IGNORED_EXTENSIONS:
        return True
    return filename.endswith((".min.js", ".min.css"))


def _is_translation(stem: str) -> bool:
    """True for a locale-tagged copy of a document, like README-ja."""
    m = LOCALE_SUFFIX.match(stem)
    return bool(m) and m.group(1).lower() in LOCALISABLE_DOCS


def file_priority_score(item: dict, meta: dict | None = None) -> int:
    """Higher score means more worth including in a digest.

    *meta* is the repository payload from the API. Only ``language`` is
    used, to favour files written in whatever the repository is mostly
    written in.
    """
    path = item["path"]
    name = item.get("name") or PurePosixPath(path).name
    size = item.get("size", 0)
    parts = PurePosixPath(path).parts
    dirs = {p.lower() for p in parts[:-1]}
    depth = len(parts) - 1
    score = 0

    # A priority name is worth less the deeper it sits. The root
    # pyproject.toml describes the project; test/ecosystem/pandas/
    # pyproject.toml describes pandas.
    if name in PRIORITY_NAMES:
        score += 1000 // (1 + depth)

    if any(p in PRIORITY_DIRS for p in parts):
        score += 300

    # Files in the repository's own language say more about it than its
    # build files do, which is how a Rust project ended up digested as a
    # list of Python dependencies.
    language = (meta or {}).get("language") or ""
    suffixes = LANGUAGE_EXTENSIONS.get(language.lower())
    if suffixes and PurePosixPath(name).suffix.lower() in suffixes:
        score += 250

    # reward reasonable size (not empty, not huge minified blob)
    if 200 < size < 20_000:
        score += size // 100
    elif size >= 20_000:
        score += 200  # still include, but don't over-rank

    if dirs & VENDOR_DIRS:
        score -= 900
    if dirs & TEST_DIRS:
        score -= 700
    if dirs & EXAMPLE_DIRS:
        score -= 250
    if _is_translation(PurePosixPath(name).stem):
        score -= 700

    return score
