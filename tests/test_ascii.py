"""Code and docs are plain ASCII: no emojis, symbols, box drawing or em/en dashes."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".py", ".md", ".txt", ".zsh", ".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist"}
NON_ASCII = re.compile(r"[^\x00-\x7F]")
PROSE_DOUBLE_DASH = re.compile(r"\w -- \w")


def text_files():
    for path in REPO.rglob("*"):
        if path.is_file() and not SKIP_DIRS.intersection(path.relative_to(REPO).parts):
            if path.suffix in TEXT_SUFFIXES or path.name == "Makefile":
                yield path


def test_all_text_is_ascii():
    hits = [
        f"{path.relative_to(REPO)}:{number}: {line.strip()[:60]}"
        for path in text_files()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if NON_ASCII.search(line)
    ]
    assert hits == [], f"{len(hits)} non-ASCII lines:\n" + "\n".join(hits[:40])


def test_markdown_has_no_double_dash_prose():
    hits = [
        f"{path.relative_to(REPO)}:{number}"
        for path in text_files()
        if path.suffix == ".md"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if PROSE_DOUBLE_DASH.search(line) and not line.lstrip().startswith(("`", "|"))
    ]
    assert hits == []
