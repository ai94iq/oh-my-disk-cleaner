"""CLI options that did nothing are gone, so --help only lists working features."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "disk-cleaner" / "scripts"


def help_text(script: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_scheduler_has_no_install_command():
    assert "install" not in help_text("scheduler.py")


def test_check_skill_has_no_fix_flag():
    assert "--fix" not in help_text("check_skill.py")
