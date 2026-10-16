"""
Pytest configuration for cross-platform testing.
"""

import sys
from pathlib import Path

import pytest

# Tests import the package the skill ships, not an installed copy.
SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "disk-cleaner"
sys.path.insert(0, str(SKILL_DIR))
# The desktop apps (apps/diskcleaner_gui) import from the repo, not an install.
sys.path.insert(0, str(SKILL_DIR.parent.parent / "apps"))


def pytest_collection_modifyitems(config, items):
    """
    Modify collected test items.

    This ensures that benchmark scripts that don't contain actual tests
    don't cause issues on non-Windows platforms.
    """
    # You can add custom collection logic here if needed
    pass


@pytest.fixture(scope="session")
def platform_info():
    """Fixture providing platform information."""
    import platform

    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
