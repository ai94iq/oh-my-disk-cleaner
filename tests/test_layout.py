"""The skill folder holds the only copy of the diskcleaner package."""

from pathlib import Path

import diskcleaner

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "disk-cleaner"


def test_tests_import_the_skill_package():
    assert Path(diskcleaner.__file__).resolve().is_relative_to(SKILL)


def test_no_second_package_copy():
    assert not (REPO / "diskcleaner").exists()
