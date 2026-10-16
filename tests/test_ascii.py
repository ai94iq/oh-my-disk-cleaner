"""Code and docs are plain ASCII: no emojis, symbols, box drawing or em/en dashes."""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".py", ".md", ".txt", ".zsh", ".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"}
NON_ASCII = re.compile(r"[^\x00-\x7F]")
PROSE_DOUBLE_DASH = re.compile(r"\w -- \w")


def text_files():
    """Tracked and new (not ignored) files, so a local .venv or build output is skipped."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    for name in filter(None, listed.split("\0")):
        path = REPO / name
        if path.is_file() and (
            path.suffix in TEXT_SUFFIXES or path.name in {"Makefile", ".flake8"}
        ):
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
