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


def test_a_whole_drive_is_not_cut_short_by_the_file_cap():
    # The default cap was 2,000,000 entries; this machine's C:\ already holds 1,959,658
    # (measured), so a fuller disk stopped with partial results. Memory does not grow
    # with the count: only per-folder totals and files over 10 MB are kept.
    import inspect

    assert inspect.signature(service.analyze).parameters["max_files"].default >= 20_000_000


def test_a_slow_disk_gets_ten_minutes_before_the_time_cap():
    import inspect

    assert inspect.signature(service.analyze).parameters["max_seconds"].default >= 600


def test_scan_and_stop_lines_read_as_sentences():
    from diskcleaner_gui.text import scan_line

    assert scan_line(8, 0.04, "") == "8 files in under a second"
    assert scan_line(1_959_658, 16.4, "") == "1,959,658 files in 16.4 s"
    assert scan_line(1, 2.0, "cancelled") == (
        "Stopped: 1 file scanned; the lists show what was found"
    )
    assert scan_line(5, 600.0, "time_limit (600s)") == (
        "Stopped at the 600 s limit: 5 files scanned; the lists show what was found"
    )
    assert scan_line(20, 3.0, "file_limit (20000000 files)") == (
        "Stopped at the 20,000,000 file limit: 20 files scanned; the lists show what was found"
    )
