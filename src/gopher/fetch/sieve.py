"""Filtering and ranking rules. This is the tuning surface for repo digests.

New ignore rules go in the IGNORED_* sets; new ranking rules go in
PRIORITY_NAMES or PRIORITY_DIRS.
"""

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


def file_priority_score(item: dict) -> int:
    """Higher score = more important. Used to pick TOP_N_FILES."""
    path = item["path"]
    name = item.get("name") or PurePosixPath(path).name
    size = item.get("size", 0)
    score = 0

    if name in PRIORITY_NAMES:
        score += 1000
    parts = PurePosixPath(path).parts
    if any(p in PRIORITY_DIRS for p in parts):
        score += 300
    # reward reasonable size (not empty, not huge minified blob)
    if 200 < size < 20_000:
        score += size // 100
    elif size >= 20_000:
        score += 200  # still include, but don't over-rank

    return score
