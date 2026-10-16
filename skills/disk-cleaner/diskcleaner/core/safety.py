"""
Safety checker for file deletion operations.

Provides safety checks before deletion: protected paths and extensions,
file lock detection and permission verification. Locked files are reported
and skipped; this module never terminates processes.
"""

import fnmatch
import functools
import os
import platform
import shutil
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from diskcleaner.config import Config
from diskcleaner.config.defaults import (
    get_protected_extensions,
    get_protected_paths,
    get_protected_patterns,
)
from diskcleaner.core.scanner import FileInfo


def _identity(path: Union[str, Path]) -> Optional[Tuple[int, int]]:
    """(device, file id) of an existing path, or None. Same folder, same identity,
    whatever spelling reaches it (\\\\?\\C:\\..., \\\\localhost\\C$\\..., subst drives)."""
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino) if st.st_ino else None


# Parent folders repeat across a scan, so their identities are cached
_parent_identity = functools.lru_cache(maxsize=8192)(_identity)


def _as_list(entries) -> list:
    """Config values may be one string ("paths: C:\\x") instead of a list; never split it."""
    if entries is None:
        return []
    if isinstance(entries, (str, Path)):
        return [entries]
    return list(entries)


def _resolve_all(paths: Iterable[Union[str, Path]]) -> List[Path]:
    """Resolve each non-blank entry; blank entries (a YAML "[]" parses to [""]) are dropped."""
    resolved = []
    for entry in _as_list(paths):
        if not str(entry).strip():
            continue
        try:
            resolved.append(Path(entry).expanduser().resolve())
        except (OSError, RuntimeError, ValueError):
            continue
    return resolved


def _norm(path: Path) -> str:
    """Case-normalised text of a resolved path, for prefix comparison."""
    return os.path.normcase(str(path))


def _within(path_text: str, protected_text: str) -> bool:
    """True when path_text is protected_text or inside it, by whole components."""
    if path_text == protected_text:
        return True
    prefix = protected_text if protected_text.endswith(os.sep) else protected_text + os.sep
    return path_text.startswith(prefix)


@functools.lru_cache(maxsize=1)
def _builtin_protection() -> Tuple[Tuple[str, ...], frozenset, frozenset]:
    """Built-in protected paths (normalised text), their identities and extensions, once."""
    paths = _resolve_all(get_protected_paths())
    identities = frozenset(i for i in map(_identity, paths) if i)
    extensions = frozenset(ext.lower() for ext in get_protected_extensions())
    return tuple(map(_norm, paths)), identities, extensions


def matches_protected_pattern(filename: str, patterns: Optional[Iterable[str]] = None) -> bool:
    """
    Return whether a file name matches a protected pattern (*.db, config.* ...).

    Like the path lists, given patterns add to the built-in ones and never
    replace them; blank entries are ignored.
    """
    all_patterns = [*get_protected_patterns(), *(p for p in _as_list(patterns) if str(p).strip())]
    return any(fnmatch.fnmatch(filename, pattern) for pattern in all_patterns)


def is_root_or_home(path: Path) -> bool:
    """Return whether a resolved path is a filesystem root or the home folder."""
    if path.anchor and path == Path(path.anchor):
        return True
    try:
        home = Path(os.path.expanduser("~")).resolve()
    except (OSError, RuntimeError, ValueError):
        return True
    return path == home


def is_protected(
    path: Union[str, Path],
    protected_paths: Optional[Iterable[Union[str, Path]]] = None,
    protected_extensions: Optional[Iterable[str]] = None,
) -> bool:
    """
    Return whether a path must never be deleted.

    Protected: filesystem roots, the home folder, each protected path and
    everything under it, and files with a protected extension. The path is
    resolved first, so a link is judged by its target. Comparison is by path
    component, so /usr-local is not inside /usr. The given lists add to the
    built-in ones and can never remove them, so a config file (including a
    .disk-cleaner.yaml inside the folder being cleaned) cannot unprotect
    system paths. A path that cannot be resolved counts as protected.

    Paths are compared twice: by text (works for paths that do not exist yet)
    and by file identity of the path and each parent (catches other spellings
    of the same folder, such as \\\\?\\C:\\Windows or \\\\localhost\\C$\\Windows).
    """
    builtin_paths, builtin_ids, builtin_exts = _builtin_protection()
    extra_paths = _resolve_all(protected_paths or [])
    extensions = builtin_exts | {ext.lower() for ext in _as_list(protected_extensions) if ext}

    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return True

    if is_root_or_home(resolved):
        return True
    if resolved.suffix.lower() in extensions:
        return True

    resolved_text = _norm(resolved)
    for protected_text in (*builtin_paths, *map(_norm, extra_paths)):
        if _within(resolved_text, protected_text):
            return True

    # Home is protected itself, not its contents; protected paths cover their subtree
    own_id = _identity(resolved)
    if own_id and own_id == _identity(os.path.expanduser("~")):
        return True
    subtree_ids = set(builtin_ids)
    subtree_ids.update(i for i in map(_identity, extra_paths) if i)
    if own_id in subtree_ids:
        return True
    return any(_parent_identity(str(parent)) in subtree_ids for parent in resolved.parents)


class FileStatus(Enum):
    """Status of a file for deletion."""

    SAFE = "safe"
    LOCKED = "locked"
    NO_PERMISSION = "no_permission"
    PROTECTED = "protected"
    ERROR = "error"


class SafetyChecker:
    """
    Performs safety checks before file deletion.

    Features:
    - Protected path and extension checking
    - File lock detection (cross-platform)
    - Permission verification
    - Backup creation (optional)
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize safety checker.

        Args:
            config: Configuration object.
        """
        self.config = config or Config.load()
        self.platform = platform.system()

        # Load settings
        self.check_locks = self.config.check_file_locks
        self.verify_perms = self.config.verify_permissions
        self.backup_enabled = self.config.get("safety.backup_before_delete", False)

        # Protected paths and extensions
        self.protected_paths = self.config.protected_paths
        self.protected_extensions = self.config.protected_extensions
        self.protected_patterns = self.config.protected_patterns

        # Backup directory
        self.backup_dir = Path.home() / ".disk-cleaner" / "backup"

    def verify_all(self, files: List[FileInfo]) -> List[Tuple[FileInfo, FileStatus]]:
        """
        Verify all files are safe to delete.

        Args:
            files: List of FileInfo objects.

        Returns:
            List of (FileInfo, FileStatus) tuples.
        """
        results = []

        for file in files:
            if file.is_dir:
                # Skip directories for now (handle separately)
                continue

            status = self.verify_file(file)
            results.append((file, status))

        return results

    def verify_file(self, file: FileInfo) -> FileStatus:
        """
        Verify if a single file is safe to delete.

        Args:
            file: FileInfo object.

        Returns:
            FileStatus indicating if file is safe to delete.
        """
        if is_protected(file.path, self.protected_paths, self.protected_extensions):
            return FileStatus.PROTECTED

        # Check protected patterns
        if self._is_protected_pattern(file.name):
            return FileStatus.PROTECTED

        # Check file locks
        if self.check_locks:
            if self._is_locked(file.path):
                return FileStatus.LOCKED

        # Check permissions
        if self.verify_perms:
            if not self._has_write_permission(file.path):
                return FileStatus.NO_PERMISSION

        return FileStatus.SAFE

    def _is_protected_pattern(self, filename: str) -> bool:
        """Check if filename matches a protected pattern (built-in or configured)."""
        return matches_protected_pattern(filename, self.protected_patterns)

    def _is_locked(self, path: str) -> bool:
        """
        Check if file is locked by a process.

        Args:
            path: File path to check.

        Returns:
            True if file is locked.
        """
        if self.platform == "Windows":
            return self._is_locked_windows(path)
        elif self.platform in ["Linux", "Darwin"]:
            return self._is_locked_unix(path)

        return False

    def _is_locked_windows(self, path: str) -> bool:
        """
        Check if file is locked on Windows.

        Args:
            path: File path to check.

        Returns:
            True if file is locked.
        """
        # Renaming a file onto itself needs delete access, which Windows refuses
        # while another handle has it open without FILE_SHARE_DELETE (the usual
        # case). O_EXCL without O_CREAT detects nothing.
        try:
            os.rename(path, path)
            return False
        except OSError:
            return True

    def _is_locked_unix(self, path: str) -> bool:
        """
        Check if file is locked on Unix/Linux/macOS.

        Uses lsof command to detect open files.

        Args:
            path: File path to check.

        Returns:
            True if file is locked.
        """
        try:
            # Use lsof to check if file is open
            result = subprocess.run(
                ["lsof", "-t", path],
                capture_output=True,
                timeout=5,
                text=True,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # lsof not available or timeout, assume not locked
            return False

    def _has_write_permission(self, path: str) -> bool:
        """
        Check if we have write permission for file.

        Args:
            path: File path to check.

        Returns:
            True if we have write permission.
        """
        return os.access(path, os.W_OK)

    def create_backup(self, file_path: str) -> Optional[str]:
        """
        Create backup of a file before deletion.

        Args:
            file_path: Path to file to backup.

        Returns:
            Path to backup file, or None if failed.
        """
        try:
            # Create backup directory for today
            today = datetime.now().strftime("%Y-%m-%d")
            backup_dir = self.backup_dir / today
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup filename
            original_name = Path(file_path).name
            backup_path = backup_dir / original_name

            # Handle duplicate names
            counter = 1
            while backup_path.exists():
                stem = Path(file_path).stem
                suffix = Path(file_path).suffix
                backup_path = backup_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            # Copy file
            shutil.copy2(file_path, backup_path)

            # Log backup
            self._log_backup(file_path, backup_path)

            return str(backup_path)

        except (OSError, IOError):
            # Log error but don't fail
            return None

    def _log_backup(self, original: str, backup: str) -> None:
        """
        Log backup operation.

        Args:
            original: Original file path.
            backup: Backup file path.
        """
        log_dir = Path.home() / ".disk-cleaner" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "backup.log"

        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {original} -> {backup}\n"

        try:
            with open(str(log_file), "a", encoding="utf-8") as f:
                f.write(log_entry)
        except (OSError, IOError):
            pass
