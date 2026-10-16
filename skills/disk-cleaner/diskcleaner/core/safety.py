"""
Safety checker for file deletion operations.

Provides safety checks before deletion: protected paths and extensions,
file lock detection and permission verification. Locked files are reported
and skipped; this module never terminates processes.
"""

import os
import platform
import shutil
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from diskcleaner.config import Config
from diskcleaner.config.defaults import get_protected_extensions, get_protected_paths
from diskcleaner.core.scanner import FileInfo


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
    """
    protected_paths = [*get_protected_paths(), *(protected_paths or [])]
    protected_extensions = [*get_protected_extensions(), *(protected_extensions or [])]

    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return True

    if is_root_or_home(resolved):
        return True
    if resolved.suffix.lower() in {ext.lower() for ext in protected_extensions}:
        return True

    for protected in protected_paths:
        try:
            protected_path = Path(protected).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved == protected_path or protected_path in resolved.parents:
            return True
    return False


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
        """
        Check if filename matches protected pattern.

        Args:
            filename: File name to check.

        Returns:
            True if pattern matches.
        """
        import fnmatch

        for pattern in self.protected_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False

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
        try:
            # Try to open file with exclusive access
            # This will fail if another process has it open
            fd = os.open(path, os.O_EXCL | os.O_RDWR)
            os.close(fd)
            return False
        except (OSError, IOError):
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
