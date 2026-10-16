"""One protected-path check shared by the cleaner, SafetyChecker and the classifier."""

import os
from pathlib import Path

import pytest

from diskcleaner.config import Config
from diskcleaner.config.defaults import get_protected_paths
from diskcleaner.core.classifier import FileClassifier, RiskLevel
from diskcleaner.core.safety import (
    FileStatus,
    SafetyChecker,
    is_protected,
    matches_protected_pattern,
)
from diskcleaner.core.scanner import FileInfo


def file_info(path: Path) -> FileInfo:
    return FileInfo(path=str(path), name=path.name, size=1, mtime=0.0, is_dir=False, is_link=False)


def config_protecting(tmp_path: Path) -> Config:
    config = Config.load()
    config.set("protected.paths", [str(tmp_path / "usr")])
    return config


def test_sibling_prefix_not_protected(tmp_path):
    assert is_protected(tmp_path / "usr-local" / "x", [tmp_path / "usr"], []) is False


def test_child_protected(tmp_path):
    assert is_protected(tmp_path / "usr" / "x", [tmp_path / "usr"], []) is True


def test_protected_path_itself(tmp_path):
    assert is_protected(tmp_path / "usr", [tmp_path / "usr"], []) is True


def test_root_and_home_protected():
    home = Path(os.path.expanduser("~"))
    assert is_protected(home, [], []) is True
    assert is_protected(Path(home.anchor), [], []) is True


def test_extension_protected_case_insensitive(tmp_path):
    assert is_protected(tmp_path / "a.DLL", [], [".dll"]) is True
    assert is_protected(tmp_path / "a.txt", [], [".dll"]) is False


def test_defaults_used_when_lists_omitted(tmp_path):
    assert is_protected(tmp_path / "a.exe") is True
    assert is_protected(tmp_path / "a.txt") is False


def windows_aliases(path: str):
    """Other spellings Windows accepts for the same local path."""
    drive, rest = path[0], path[2:]
    return [f"\\\\?\\{path}", f"\\\\localhost\\{drive}$\\{rest.lstrip(chr(92))}"]


@pytest.mark.skipif(os.name != "nt", reason="Windows path aliases")
def test_windows_path_aliases_stay_protected():
    system_root = os.environ.get("SystemRoot", "C:\\Windows")
    home = os.path.expanduser("~")
    for target in (os.path.join(system_root, "win.ini"), home):
        for alias in windows_aliases(target):
            assert is_protected(alias, [], []) is True, alias


@pytest.mark.skipif(os.name != "nt", reason="Windows path aliases")
def test_alias_of_user_protected_folder_is_protected(tmp_path):
    keep = tmp_path / "keep"
    (keep / "sub").mkdir(parents=True)
    alias = windows_aliases(str(keep / "sub"))[0]
    assert is_protected(alias, [keep], []) is True


def test_builtin_lists_are_built_once_not_per_call(tmp_path, monkeypatch):
    # Rebuilding and resolving the defaults on every call cost ~2 ms each, minutes
    # over a large scan. Count the rebuilds instead of timing (CI runners vary).
    import diskcleaner.core.safety as safety

    is_protected(tmp_path / "warm.log", [], [])
    calls = []
    real = safety.get_protected_paths
    monkeypatch.setattr(safety, "get_protected_paths", lambda: calls.append(1) or real())

    for _ in range(100):
        is_protected(tmp_path / "a.log", [], [])

    assert calls == []


def test_config_cannot_remove_builtin_protection(tmp_path):
    # Empty lists, e.g. from a planted .disk-cleaner.yaml, still protect defaults
    system_dir = Path(get_protected_paths()[0])
    assert is_protected(system_dir / "x.txt", [], []) is True
    assert is_protected(tmp_path / "tool.exe", [], []) is True


def test_project_config_cannot_unprotect(tmp_path):
    (tmp_path / ".disk-cleaner.yaml").write_text(
        "protected:\n  paths: []\nsafety:\n  protected_extensions: []\n", encoding="utf-8"
    )
    checker = SafetyChecker(config=Config.load(str(tmp_path)))
    checker.check_locks = False
    checker.verify_perms = False
    assert checker.verify_file(file_info(tmp_path / "tool.exe")) == FileStatus.PROTECTED


def test_project_config_cannot_drop_protected_patterns(tmp_path):
    (tmp_path / ".disk-cleaner.yaml").write_text("protected:\n  patterns: []\n", encoding="utf-8")
    config = Config.load(str(tmp_path))
    checker = SafetyChecker(config=config)
    checker.check_locks = False
    checker.verify_perms = False
    classifier = FileClassifier(config=config)
    db = file_info(tmp_path / "app.db")

    assert checker.verify_file(db) == FileStatus.PROTECTED
    assert classifier._classify_risk(db) == RiskLevel.PROTECTED


def test_scalar_config_value_is_one_entry(tmp_path):
    keep = tmp_path / "keep"
    # "paths: C:\x" without brackets parses to a plain string, not a list
    assert is_protected(keep / "f.txt", str(keep), []) is True
    assert is_protected(tmp_path / "other.txt", str(keep), []) is False
    assert matches_protected_pattern("x.special", "*.special") is True
    assert matches_protected_pattern("x.txt", "*.special") is False


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing rules")
def test_windows_lock_check_sees_an_open_file(tmp_path):
    target = tmp_path / "in_use.log"
    target.write_text("x", encoding="utf-8")
    checker = SafetyChecker()

    assert checker._is_locked(str(target)) is False
    with open(target, "r+", encoding="utf-8"):
        assert checker._is_locked(str(target)) is True
    assert checker._is_locked(str(target)) is False


def test_backups_older_than_retention_are_pruned(tmp_path):
    from datetime import date, timedelta

    checker = SafetyChecker()
    checker.backup_dir = tmp_path / "backup"
    old = checker.backup_dir / "2020-01-01"
    recent = checker.backup_dir / (date.today() - timedelta(days=5)).isoformat()
    other = checker.backup_dir / "not-a-date"
    for folder in (old, recent, other):
        folder.mkdir(parents=True)
        (folder / "f.txt").write_text("x", encoding="utf-8")
    source = tmp_path / "doc.txt"
    source.write_text("data", encoding="utf-8")

    assert checker.create_backup(str(source))

    assert not old.exists()
    assert recent.exists()
    assert other.exists()


def test_windows_defaults_follow_environment(monkeypatch):
    monkeypatch.setenv("SystemRoot", r"X:\Win")
    assert r"X:\Win" in get_protected_paths()


def test_safety_checker_sibling_not_protected(tmp_path):
    checker = SafetyChecker(config=config_protecting(tmp_path))
    checker.check_locks = False
    checker.verify_perms = False
    assert checker.verify_file(file_info(tmp_path / "usr-local" / "x")) == FileStatus.SAFE
    assert checker.verify_file(file_info(tmp_path / "usr" / "x")) == FileStatus.PROTECTED


def test_classifier_sibling_not_protected(tmp_path):
    classifier = FileClassifier(config=config_protecting(tmp_path))
    sibling = classifier._classify_risk(file_info(tmp_path / "usr-local" / "x.txt"))
    child = classifier._classify_risk(file_info(tmp_path / "usr" / "x.txt"))
    assert sibling != RiskLevel.PROTECTED
    assert child == RiskLevel.PROTECTED
