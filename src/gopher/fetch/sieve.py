"""Filtering and ranking rules. This is the tuning surface for repo digests.

New ignore rules go in the IGNORED_* sets; new ranking rules go in
PRIORITY_NAMES or PRIORITY_DIRS.
"""

from pathlib import PurePosixPath

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

PRIORITY_DIRS = {"src", "lib", "contracts", "core", "api", "app"}

MAX_FILE_BYTES = 32_000
TOP_N_FILES    = 10

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
    path  = item["path"]
    name  = item.get("name") or PurePosixPath(path).name
    size  = item.get("size", 0)
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
        score += 200   # still include, but don't over-rank
 
    return score


