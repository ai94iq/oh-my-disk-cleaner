"""A disk cleaner never kills processes: locked files are reported and skipped."""

import importlib
import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "disk-cleaner"
KILL_PATTERN = re.compile(r"taskkill|kill -9|\"kill\"|terminate_process|os\.kill\(")


def test_no_process_kill_code():
    hits = [
        f"{path.relative_to(SKILL)}:{number}"
        for path in SKILL.rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if KILL_PATTERN.search(line)
    ]
    assert hits == []


def test_process_manager_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("diskcleaner.core.process_manager")
