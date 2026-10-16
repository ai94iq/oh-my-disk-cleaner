#!/usr/bin/env python3
"""
Progressive Disk Analyzer

Analysis tool optimized for large disks:
1. Quick sampling estimation (0.5-1 second)
2. Display the sample's scan rate
3. Progressive result display
4. Can interrupt anytime to view partial results
"""

import argparse
import contextlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Use smart bootstrap module import
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from skill_bootstrap import import_diskcleaner_modules, safe_print

    # Also fixes stdout encoding via setup_skill_environment
    IMPORT_SUCCESS, MODULES = import_diskcleaner_modules()

    if IMPORT_SUCCESS:
        DirectoryScanner = MODULES.get("DirectoryScanner")
        Config = MODULES.get("Config")
    else:
        DirectoryScanner = None
        Config = None

except Exception as e:
    print(f"Warning: Import failed - {e}", file=sys.stderr)
    safe_print = print
    DirectoryScanner = None
    Config = None


class ProgressiveDiskAnalyzer:
    """Progressive disk analyzer - provides real-time feedback and early results"""

    def __init__(self, target_path: str = None, include_windows: bool = False):
        self.target_path = Path(target_path or self._get_default_path()).resolve()
        self.include_windows = include_windows
        self.platform = sys.platform
        self.results_shown = 0
        self.start_time = None
        self.last_update_time = 0

    def _get_default_path(self) -> str:
        """Get default scan path"""
        if sys.platform == "win32":
            return "C:\\"
        else:
            return "/"

    def quick_sample(self, sample_time: float = 1.0) -> Dict:
        """
        Quick sampling analysis - estimate directory characteristics within 1 second

        Returns:
            Dictionary containing estimation information
        """
        safe_print(f"\n[*] Quick sampling analysis... ({sample_time}s)")

        file_count = 0
        total_size = 0
        sample_dirs = 0
        start = time.time()

        try:
            # Use os.scandir for quick sampling
            for root, dirs, files in os.walk(str(self.target_path)):
                if time.time() - start > sample_time:
                    break

                sample_dirs += len(dirs)
                file_count += len(files)

                # Sample file sizes (max 100)
                for i, f in enumerate(files[:100]):
                    try:
                        file_path = Path(root) / f
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                    except (OSError, PermissionError):
                        pass

        except Exception as e:
            safe_print(f"Sampling error: {e}")

        elapsed = time.time() - start

        # Scan rate over the sample (a full-scan time cannot be known from it)
        if elapsed > 0:
            files_per_second = file_count / elapsed
        else:
            files_per_second = 0

        result = {
            "sample_file_count": file_count,
            "sample_size_gb": round(total_size / (1024**3), 2),
            "sample_dirs": sample_dirs,
            "files_per_second": round(files_per_second, 0),
        }

        # Display sampling results
        safe_print("\n[i] Sampling results:")
        safe_print(f"   Files found: {file_count:,}")
        safe_print(f"   Directories: {sample_dirs:,}")
        safe_print(f"   Scan speed: {result['files_per_second']:,} files/sec")

        return result

    def progressive_scan(
        self, max_files: int = None, max_seconds: int = None, show_progress: bool = True
    ) -> Dict:
        """
        Progressive scan - display results in real-time

        Args:
            max_files: Maximum file count limit
            max_seconds: Maximum time limit (seconds)
            show_progress: Whether to show progress

        Returns:
            Scan result dictionary
        """
        if DirectoryScanner is None:
            raise SystemExit(
                "[X] The bundled diskcleaner package did not import; run scripts/check_skill.py"
            )

        # Set limits
        if max_files is None:
            max_files = 50000  # Default 50k files
        if max_seconds is None:
            max_seconds = 30  # Default 30 seconds

        safe_print("\n[*] Progressive scan started")
        safe_print(f"   Limits: {max_files:,} files or {max_seconds} seconds")
        safe_print("   Press Ctrl+C anytime to interrupt and view partial results\n")

        self.start_time = time.time()
        results = {"directories": [], "files": []}
        # Bytes per top-level folder, summed from every file the scan sees
        dir_totals: Dict[str, int] = {}
        root_prefix = os.path.join(str(self.target_path), "")  # ends with one separator
        file_count = 0
        interrupted = False
        scanner = DirectoryScanner(
            str(self.target_path),
            max_files=max_files,
            max_seconds=max_seconds,
            include_windows=self.include_windows,
            cache_enabled=False,
        )

        try:
            last_display_time = 0
            display_interval = 2.0  # Display progress every 2 seconds

            for file_info in scanner.scan_generator():
                file_count += 1
                elapsed = time.time() - self.start_time

                # Progressive progress display
                if show_progress and elapsed - last_display_time > display_interval:
                    self._show_progress(file_count, elapsed, scanner.stopped_early)
                    last_display_time = elapsed

                # Collect large files (>10MB)
                if not file_info.is_dir and file_info.size > 10 * 1024 * 1024:
                    results["files"].append(
                        {
                            "path": file_info.path,
                            "name": file_info.name,
                            "size_gb": round(file_info.size / (1024**3), 2),
                            "size_mb": round(file_info.size / (1024**2), 2),
                        }
                    )

                # Add the file to its top-level folder's total. String slicing,
                # not Path(): this runs once per file, millions of times.
                if not file_info.is_dir:
                    top, sep, _ = file_info.path[len(root_prefix) :].partition(os.sep)
                    if sep:
                        dir_totals[top] = dir_totals.get(top, 0) + file_info.size

        except KeyboardInterrupt:
            interrupted = True
            safe_print("\n\n[!] Scan interrupted by user, showing partial results")

        elapsed = time.time() - self.start_time
        self._show_progress(file_count, elapsed, True)

        # Sort on exact bytes; rounded GB would tie every folder under ~5 MB
        largest_dirs = sorted(dir_totals.items(), key=lambda item: item[1], reverse=True)
        results["directories"] = [
            {
                "path": str(self.target_path / name),
                "name": name,
                "size_gb": round(size / (1024**3), 2),
                "size_mb": round(size / (1024**2), 2),
            }
            for name, size in largest_dirs[:50]
        ]
        results["files"].sort(key=lambda x: x["size_mb"], reverse=True)
        results["files"] = results["files"][:50]

        stopped_early = interrupted or scanner.stopped_early
        results["scan_info"] = {
            "files_scanned": file_count,
            "scan_time_seconds": round(elapsed, 1),
            "stopped_early": stopped_early,
            "stop_reason": "interrupted" if interrupted else (scanner.stop_reason or ""),
        }
        return results

    def _show_progress(self, file_count: int, elapsed: float, complete: bool = False):
        """Display scan progress"""
        if complete:
            safe_print(f"\n[OK] Scan complete: {file_count:,} files, {elapsed:.1f} seconds")
        else:
            safe_print(f"   Scanning: {file_count:,} files, {elapsed:.1f} seconds... (continuing)")

    def format_report(self, results: Dict) -> str:
        """Format report"""
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append(f"DISK ANALYSIS REPORT - {self.target_path}")
        lines.append("=" * 60)

        # Scan info
        if "scan_info" in results:
            info = results["scan_info"]
            lines.append("\n[i] Scan Info:")
            lines.append(f"   Files scanned: {info.get('files_scanned', 0):,}")
            lines.append(f"   Time: {info.get('scan_time_seconds', 0):.1f} seconds")
            if info.get("stopped_early"):
                lines.append(f"   Stopped early: {info.get('stop_reason', 'Unknown')}")

        # Large directories
        if results.get("directories"):
            lines.append("\n[DIR] Largest Directories:")
            for i, d in enumerate(results["directories"][:20], 1):
                size_str = f"{d['size_gb']} GB" if d["size_gb"] > 0 else f"{d['size_mb']} MB"
                lines.append(f"   {i}. {d['name']}: {size_str}")

        # Large files
        if results.get("files"):
            lines.append("\n[FILE] Largest Files:")
            for i, f in enumerate(results["files"][:20], 1):
                size_str = f"{f['size_gb']} GB" if f["size_gb"] > 0 else f"{f['size_mb']} MB"
                # Shorten path
                path_str = f"...{f['path'][-50:]}" if len(f["path"]) > 50 else f["path"]
                lines.append(f"   {i}. {f['name']}: {size_str}")
                lines.append(f"      {path_str}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Progressive disk analyzer - suitable for large disks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick sampling (1 second)
  python scripts/analyze_progressive.py --sample

  # Progressive scan (30 second limit)
  python scripts/analyze_progressive.py --max-seconds 30

  # Limit file count (fast)
  python scripts/analyze_progressive.py --max-files 10000

  # Full scan (long time)
  python scripts/analyze_progressive.py --max-seconds 300

  # Custom path
  python scripts/analyze_progressive.py --path "D:\\Projects" --sample
        """,
    )

    parser.add_argument("--path", "-p", help="Scan path")
    parser.add_argument("--sample", action="store_true", help="Quick sample only (1 second)")
    parser.add_argument(
        "--max-files", type=int, default=50000, help="Maximum file count limit (default: 50000)"
    )
    parser.add_argument(
        "--max-seconds", type=int, default=30, help="Maximum time limit-seconds (default: 30)"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress")
    parser.add_argument(
        "--include-windows",
        action="store_true",
        help="Include Windows system directories (C:\\Windows, Program Files, etc.) in scan",
    )

    args = parser.parse_args()

    analyzer = ProgressiveDiskAnalyzer(args.path, include_windows=args.include_windows)
    if not analyzer.target_path.is_dir():
        print(f"[X] Not a folder: {analyzer.target_path}", file=sys.stderr)
        return 2

    # With --json, stdout carries only the JSON; progress text goes to stderr
    stdout = sys.stdout
    try:
        with contextlib.redirect_stdout(sys.stderr if args.json else stdout):
            if args.sample:
                results = analyzer.quick_sample(sample_time=1.0)
            else:
                analyzer.quick_sample(sample_time=1.0)
                results = analyzer.progressive_scan(
                    max_files=args.max_files,
                    max_seconds=args.max_seconds,
                    show_progress=not args.no_progress,
                )
    except OSError as error:
        excluded = isinstance(error, PermissionError) and not args.include_windows
        hint = " (system folders need --include-windows)" if excluded else ""
        print(f"[X] Cannot scan {analyzer.target_path}: {error}{hint}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False), file=stdout)
    elif not args.sample:
        print(analyzer.format_report(results))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        safe_print("\n\n[*] User interrupted")
        sys.exit(0)
