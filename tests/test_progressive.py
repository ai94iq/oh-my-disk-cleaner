"""Tests for skills/disk-cleaner/scripts/analyze_progressive.py."""

import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "disk-cleaner"
    / "scripts"
    / "analyze_progressive.py"
)


def test_script_starts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert "--max-files" in result.stdout
