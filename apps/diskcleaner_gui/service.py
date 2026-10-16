"""What the desktop apps can do, with no GUI toolkit imported.

Every call goes through the skill's own scripts, so the GUIs share their safety checks
(is_protected, dry runs, links removed as links) instead of copying them. Calls block; the apps
run them off the UI thread.
"""

import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[2] / "skills" / "disk-cleaner" / "scripts",  # a clone of the repo
    Path(getattr(sys, "_MEIPASS", "")) / "skills" / "disk-cleaner" / "scripts",  # PyInstaller
    _HERE.parents[1] / "disk-cleaner" / "scripts",  # Briefcase
]
SCRIPTS = next((path for path in _CANDIDATES if (path / "clean_disk.py").is_file()), None)
if SCRIPTS is None:
    raise ImportError(
        "The disk-cleaner scripts are missing; looked in: " + ", ".join(map(str, _CANDIDATES))
    )
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_progressive  # noqa: E402
import clean_disk  # noqa: E402
import find_duplicates as _find_duplicates  # noqa: E402
import monitor_disk  # noqa: E402
from diskcleaner.core.units import format_size  # noqa: E402,F401

CATEGORIES = {
    "temp": "Temporary files",
    "cache": "App caches",
    "logs": "Log files",
    "recycle": "Recycle bin",
    "downloads_old": "Downloads older than 90 days",
    "browser_history": "Browser history",
}
DEFAULT_CATEGORIES = ("temp", "cache", "logs", "recycle")  # the set clean_all runs
_METHODS = {
    "temp": "clean_temp_files",
    "cache": "clean_cache_files",
    "logs": "clean_log_files",
    "recycle": "clean_recycle_bin",
    "downloads_old": "clean_old_downloads",
    "browser_history": "clean_browser_history",
}


@dataclass(frozen=True)
class Drive:
    path: str
    total: int
    used: int
    free: int


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    size: int


@dataclass
class Analysis:
    folders: list
    files: list
    files_scanned: int
    seconds: float
    stop_reason: str


@dataclass
class CleanRow:
    category: str
    path: str
    items: int
    size: int
    errors: list


@dataclass
class CleanReport:
    dry_run: bool
    rows: list

    @property
    def total_size(self) -> int:
        return sum(row.size for row in self.rows)

    @property
    def total_items(self) -> int:
        return sum(row.items for row in self.rows)

    @property
    def error_count(self) -> int:
        return sum(len(row.errors) for row in self.rows)


@dataclass
class DupGroup:
    size: int
    paths: list

    @property
    def reclaimable(self) -> int:
        return self.size * (len(self.paths) - 1)


def _directory(path: str) -> Path:
    folder = Path(path).expanduser()
    if not folder.is_dir():
        raise ValueError(f"Not a folder: {path}")
    return folder


def drives() -> list:
    found = []
    for mount in monitor_disk.get_mount_points():
        try:
            usage = shutil.disk_usage(mount)
        except OSError:
            continue
        found.append(Drive(mount, usage.total, usage.used, usage.free))
    return found


def analyze(
    path: str,
    *,
    max_files: int = 2_000_000,
    max_seconds: int = 120,
    cancel: Optional[threading.Event] = None,
    progress: Optional[Callable[[int], None]] = None,
) -> Analysis:
    folder = _directory(path)

    def should_stop(count: int) -> bool:
        if progress:
            progress(count)
        return bool(cancel and cancel.is_set())

    analyzer = analyze_progressive.ProgressiveDiskAnalyzer(str(folder))
    results = analyzer.progressive_scan(
        max_files=max_files, max_seconds=max_seconds, show_progress=False, should_stop=should_stop
    )
    info = results["scan_info"]
    return Analysis(
        folders=[Entry(d["name"], d["path"], d["size_bytes"]) for d in results["directories"]],
        files=[Entry(f["name"], f["path"], f["size_bytes"]) for f in results["files"]],
        files_scanned=info["files_scanned"],
        seconds=info["scan_time_seconds"],
        stop_reason=info["stop_reason"],
    )


def clean(categories: Iterable[str], *, dry_run: bool) -> CleanReport:
    chosen = list(categories)
    unknown = [name for name in chosen if name not in _METHODS]
    if unknown:
        raise ValueError(f"Unknown cleanup category: {', '.join(unknown)}")
    cleaner = clean_disk.DiskCleaner(dry_run=dry_run, show_progress=False)
    rows = []
    for name in chosen:
        result = getattr(cleaner, _METHODS[name])(show_progress=False)
        for location in result["locations"]:
            rows.append(
                CleanRow(
                    name,
                    location["path"],
                    location["files_deleted"],
                    location.get("space_freed_bytes", 0),
                    list(location["errors"]),
                )
            )
    return CleanReport(dry_run, rows)


def duplicates(path: str, *, max_seconds: int = 300) -> list:
    # ponytail: no cancel, the scan is bounded by max_seconds; add one when people wait on it
    folder = _directory(path)
    groups, _ = _find_duplicates.find_duplicates(
        str(folder), show_progress=False, max_seconds=max_seconds
    )
    found = [DupGroup(group.size, [info.path for info in group.files]) for group in groups]
    return sorted(found, key=lambda group: group.reclaimable, reverse=True)
