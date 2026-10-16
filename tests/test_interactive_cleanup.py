"""The wizard's delete step: backup first, never delete protected paths or link targets."""

import os
from pathlib import Path

import pytest

from diskcleaner.core import InteractiveCleanupUI, SmartCleanupEngine
from diskcleaner.core.safety import SafetyChecker


@pytest.fixture
def ui(tmp_path, monkeypatch):
    # Backups and logs go under a fake home, never the real one
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    work = tmp_path / "work"
    work.mkdir()
    return InteractiveCleanupUI(SmartCleanupEngine(str(work), cache_enabled=False))


def make_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / "work" / name
    path.write_text("data", encoding="utf-8")
    return path


def test_deletes_after_backup(ui, tmp_path):
    target = make_file(tmp_path, "old.log")

    assert ui._execute_cleanup([str(target)], backup=True) is True

    assert not target.exists()
    backups = list((tmp_path / "home" / ".disk-cleaner" / "backup").rglob("old.log"))
    assert len(backups) == 1


def test_keeps_file_when_backup_fails(ui, tmp_path, monkeypatch):
    target = make_file(tmp_path, "old.log")
    monkeypatch.setattr(SafetyChecker, "create_backup", lambda self, path: None)

    assert ui._execute_cleanup([str(target)], backup=True) is False

    assert target.exists()


def test_refuses_protected(ui, tmp_path):
    target = make_file(tmp_path, "tool.exe")

    assert ui._execute_cleanup([str(target)], backup=False) is False

    assert target.exists()


def test_symlink_removes_link_only(ui, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    kept = outside / "keep.txt"
    kept.write_text("keep", encoding="utf-8")
    link = tmp_path / "work" / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Cannot create a symlink here: {error}")

    assert ui._execute_cleanup([str(link)], backup=False) is True

    assert not os.path.lexists(link)
    assert kept.exists()


def test_refuses_protected_pattern(ui, tmp_path):
    target = make_file(tmp_path, "app.db")

    assert ui._execute_cleanup([str(target)], backup=False) is False

    assert target.exists()


def test_refuses_link_inside_protected_folder(ui, tmp_path, monkeypatch):
    from diskcleaner.config import Config

    keep = tmp_path / "work" / "keep"
    keep.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = keep / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Cannot create a symlink here: {error}")
    real_load = Config.load

    def load_protecting_keep(*args, **kwargs):
        config = real_load(*args, **kwargs)
        config.set("protected.paths", [str(keep)])
        return config

    monkeypatch.setattr(Config, "load", staticmethod(load_protecting_keep))

    assert ui._execute_cleanup([str(link)], backup=False) is False

    assert os.path.lexists(link)


def test_confirmed_cleanup_runs(ui, tmp_path, monkeypatch):
    target = make_file(tmp_path, "old.log")
    monkeypatch.setattr("builtins.input", lambda prompt="": "YES")

    assert ui.confirm_and_cleanup([str(target)], dry_run=False, backup=True) is True

    assert not target.exists()
