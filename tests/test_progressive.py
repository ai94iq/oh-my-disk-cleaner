"""Tests for skills/disk-cleaner/scripts/analyze_progressive.py."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

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


def run_script(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120
    )


def test_bad_path_is_a_one_line_error(tmp_path):
    for bad in (tmp_path / "missing", tmp_path / "file.txt"):
        if bad.name == "file.txt":
            bad.write_text("x", encoding="utf-8")
        result = run_script("--path", str(bad), "--no-progress")
        assert result.returncode == 2
        assert "Traceback" not in result.stderr
        assert str(bad) in result.stderr


def test_json_output_is_valid_json(tmp_path):
    import json

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f.bin").write_bytes(b"x" * 2048)

    for extra in ((), ("--sample",)):
        result = run_script("--path", str(tmp_path), "--json", *extra)
        assert result.returncode == 0, result.stderr
        json.loads(result.stdout)


def load_script():
    spec = importlib.util.spec_from_file_location("analyze_progressive_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dir_totals_full_depth(tmp_path):
    # The big folder sorts last by name, so only a size sort puts it first
    deep = tmp_path / "zbig" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "f.bin").write_bytes(b"x" * 3 * 1024 * 1024)
    (tmp_path / "asmall").mkdir()
    (tmp_path / "asmall" / "f.bin").write_bytes(b"x" * 1024 * 1024)

    analyzer = load_script().ProgressiveDiskAnalyzer(str(tmp_path))
    results = analyzer.progressive_scan(max_files=10**6, max_seconds=30, show_progress=False)

    sizes = {d["name"]: d["size_mb"] for d in results["directories"]}
    assert results["directories"][0]["name"] == "zbig"
    assert 2.9 <= sizes["zbig"] <= 3.1
    assert 0.9 <= sizes["asmall"] <= 1.1


def make_junction(link: Path, target: Path):
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True
    )
    if created.returncode != 0:
        pytest.skip(f"Cannot create a junction: {created.stderr.strip()}")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
def test_junctions_are_not_followed(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "f.bin").write_bytes(b"x" * 1024 * 1024)
    make_junction(tmp_path / "alias", tmp_path / "data")
    loop_dir = tmp_path / "cyc" / "d"
    loop_dir.mkdir(parents=True)
    (loop_dir / "g.bin").write_bytes(b"x" * 1024 * 1024)
    make_junction(loop_dir / "loop", tmp_path / "cyc")

    analyzer = load_script().ProgressiveDiskAnalyzer(str(tmp_path))
    results = analyzer.progressive_scan(max_files=10**6, max_seconds=30, show_progress=False)

    sizes = {d["name"]: d["size_mb"] for d in results["directories"]}
    assert 0.9 <= sizes["data"] <= 1.1
    assert sizes.get("alias", 0) < 0.1
    assert 0.9 <= sizes["cyc"] <= 1.1


def test_include_windows_reaches_the_scanner(tmp_path, monkeypatch):
    module = load_script()
    seen = {}

    class RecordingScanner:
        stopped_early = False
        stop_reason = ""

        def __init__(self, path, **kwargs):
            seen.update(kwargs)

        def scan_generator(self):
            return iter(())

    monkeypatch.setattr(module, "DirectoryScanner", RecordingScanner)
    analyzer = module.ProgressiveDiskAnalyzer(str(tmp_path), include_windows=True)
    analyzer.progressive_scan(max_files=10, max_seconds=1, show_progress=False)

    assert seen["include_windows"] is True
