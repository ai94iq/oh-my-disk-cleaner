"""The toolkit-free service both desktop apps call."""

import threading
from pathlib import Path

import pytest

from diskcleaner_gui import service


def test_analyze_lists_largest(tmp_path):
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "f.bin").write_bytes(b"x" * 11 * 1024 * 1024)
    (tmp_path / "small").mkdir()
    (tmp_path / "small" / "f.bin").write_bytes(b"x" * 1024)

    result = service.analyze(str(tmp_path))

    assert [entry.name for entry in result.folders] == ["big", "small"]
    assert [entry.name for entry in result.files] == ["f.bin"]
    assert result.files[0].size == 11 * 1024 * 1024
    assert result.files_scanned >= 2
    assert result.stop_reason == ""


def test_analyze_cancel(tmp_path):
    (tmp_path / "f.bin").write_bytes(b"x")
    cancel = threading.Event()
    cancel.set()
    assert service.analyze(str(tmp_path), cancel=cancel).stop_reason == "cancelled"


def test_analyze_missing_path_raises(tmp_path):
    with pytest.raises(ValueError):
        service.analyze(str(tmp_path / "missing"))


def test_clean_preview_never_deletes(tmp_path, monkeypatch):
    junk = tmp_path / "temp"
    junk.mkdir()
    (junk / "f.tmp").write_bytes(b"x" * 100)
    monkeypatch.setattr(
        service.clean_disk.DiskCleaner,
        "get_cleanable_locations",
        lambda self: {"temp": [str(junk)]},
    )

    report = service.clean(["temp"], dry_run=True)

    assert report.dry_run is True
    assert report.total_items == 1
    assert report.total_size == 100
    assert report.rows[0].category == "temp"
    assert (junk / "f.tmp").exists()


def test_clean_unknown_category_raises():
    with pytest.raises(ValueError):
        service.clean(["everything"], dry_run=True)


def test_duplicates_groups(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"same content")
    (tmp_path / "b.txt").write_bytes(b"same content")
    (tmp_path / "c.txt").write_bytes(b"other content")

    groups = service.duplicates(str(tmp_path))

    assert len(groups) == 1
    assert sorted(Path(p).name for p in groups[0].paths) == ["a.txt", "b.txt"]
    assert groups[0].reclaimable == groups[0].size == len(b"same content")


def test_duplicates_missing_path_raises(tmp_path):
    with pytest.raises(ValueError):
        service.duplicates(str(tmp_path / "missing"))


def test_drives_nonempty():
    found = service.drives()
    assert found
    assert all(drive.total >= drive.used for drive in found)


def test_browser_history_is_not_default():
    assert "browser_history" in service.CATEGORIES
    assert "browser_history" not in service.DEFAULT_CATEGORIES
