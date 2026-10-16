"""--sample reports what it measured and never a made-up full-scan estimate."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "disk-cleaner" / "scripts"


@pytest.mark.parametrize("script", ["analyze_disk.py", "analyze_progressive.py"])
def test_sample_has_no_fake_estimate(script, tmp_path):
    (tmp_path / "f.bin").write_bytes(b"x" * 1024)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--path", str(tmp_path), "--sample", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    sample = json.loads(result.stdout[result.stdout.index("{") :])
    assert sample["sample_file_count"] >= 1
    assert "estimated_time_seconds" not in sample
    assert "Estimated" not in result.stdout + result.stderr


def test_quick_profiler_has_no_fake_estimate():
    from diskcleaner.optimization.scan import ScanProfile

    assert "estimated_time" not in ScanProfile.__dataclass_fields__
