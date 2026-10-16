"""One size formatter for every report."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "disk-cleaner" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from diskcleaner.core.units import format_size  # noqa: E402

SAMPLES = [0, 512, 2048, 5 * 1024**2 + 1, 3 * 1024**3, 2 * 1024**4]


def test_format_size_values():
    assert [format_size(b) for b in SAMPLES] == [
        "0 B",
        "512 B",
        "2.00 KB",
        "5.00 MB",
        "3.00 GB",
        "2.00 TB",
    ]


def all_formatters():
    import find_duplicates
    import interactive_wizard

    from diskcleaner.core.growth_analyzer import format_size as growth
    from diskcleaner.core.interactive import InteractiveCleanupUI
    from diskcleaner.core.organizer import FileOrganizer
    from diskcleaner.core.smart_cleanup import SmartCleanupEngine

    return {
        "growth_analyzer": growth,
        "interactive": lambda b: InteractiveCleanupUI._format_size(None, b),
        "organizer": lambda b: FileOrganizer._format_size(None, b),
        "smart_cleanup": lambda b: SmartCleanupEngine._format_size(None, b),
        "find_duplicates": find_duplicates.format_size,
        "interactive_wizard": lambda b: interactive_wizard.InteractiveWizard._format_size(None, b),
    }


@pytest.mark.parametrize("name", sorted(all_formatters()))
def test_every_report_uses_the_same_format(name):
    formatter = all_formatters()[name]
    assert [formatter(b) for b in SAMPLES] == [format_size(b) for b in SAMPLES]
