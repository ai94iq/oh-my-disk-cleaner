# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Contents

- [Unreleased](#unreleased)
- [2.0.0 - 2025-01-22](#200---2025-01-22)
- [1.0.0 - Previous Release](#100---previous-release)

## [Unreleased]

### Added
- A PySide6 desktop app in `apps/diskcleaner_gui/`, over a toolkit-free
  `service.py` that calls the scripts: Analyze, Clean
  (preview, then delete after a confirm) and Duplicates (report only).
- PyInstaller bundles (`packaging/qt/`); `gui.yml` builds and self-checks
  them and attaches them to the release of a `gui-vX.Y.Z` tag.
- `progressive_scan(should_stop=...)` stops a scan with reason `cancelled`;
  `clean_directory` also reports `space_freed_bytes`;
  `monitor_disk.get_mount_points()` is a module function.

### Security
- The skill imports only its bundled `diskcleaner` package. The bootstrap no
  longer searches the working directory, home, `DISK_CLEANER_SKILL_PATH`,
  `sys.path` or installed packages, any of which could replace the cleaner's
  code.
- One protected-path check, `is_protected` in `diskcleaner/core/safety.py`,
  is shared by the cleaner, `SafetyChecker` and the classifier. It compares by
  path component (`/usr-local` is not inside `/usr`). Config files can add
  protections but cannot remove the built-in ones.
- The wizard keeps a file when its backup fails, refuses protected paths and
  removes links without touching their targets. Its delete step used to call a
  missing method.
- Process killing (`process_manager.py`, `SafetyChecker.terminate_process`)
  is removed; locked files are skipped.
- CI actions and pre-commit hooks are pinned by commit SHA; workflows run with
  read-only permissions.
- Protection holds for every spelling of a path (`\\?\C:\...`,
  `\\localhost\C$\...`), compared by file identity.
- Cache cleaning no longer touches Firefox profiles (only `cache2`) or iPhone
  backups. Browser history (`History`, `WebCache`) is cleaned only with
  `--browser-history`.
- Folder cleanup checks every file inside, so executables, installers and disk
  images inside a cleaned folder are kept.
- The Windows lock check detects files open in other programs.

### Changed
- Python 3.11 or newer (3.10 reached end of life in October 2026); dev and
  optional dependency floors are the latest releases.
- The package exists once, under `skills/disk-cleaner/diskcleaner/`.
- Code and docs are English and plain ASCII; SKILL.md is rewritten as a short
  workflow guide.

### Removed
- `diskcleaner/optimization/delete.py` and `scripts/package_skill.py`
  (unused), the `.skill` archive, `README_zh.md`, the V2.1 summary and the
  duplicate install guides.

### Fixed
- `safe_print` no longer crashes without a console (`pythonw`, windowed
  bundles), where `sys.stdout` is None.
- `analyze_progressive.py` crashed on import; its folder totals now cover
  every top-level folder at full depth, sort on exact bytes, survive Ctrl+C,
  and `--include-windows` counts system folders.
- Directory walks no longer follow Windows junctions (double counting, loops).
- Broken links are removed as links, and a link's age is its own.
- Wizard backups older than `safety.backup_retention_days` (30) are pruned.
- The fake full-scan time estimate is gone; one size format everywhere; small
  and empty folders show in the progressive report.
- **Directory sizing undercounted deep trees** - `DiskAnalyzer._get_dir_size_fast`
  defaulted to `max_depth=1`, so the "Largest Directories" ranking stopped
  measuring after two levels and reported deeply nested content (Wine prefixes,
  `node_modules`, game installs) as near-zero. The size walk now defaults to the
  full tree; an explicit `max_depth` still bounds it for shallow estimates.

## [2.0.0] - 2025-01-22

### Added

#### Core Functionality
- **Smart Cleanup Engine** - Intelligent 3D file classification (type x risk x age)
- **Duplicate Detection** - Adaptive strategy automatically switches between fast and accurate modes
- **Incremental Scanning** - Cache-based optimization for 10x faster repeated scans
- **File Lock Detection** - Cross-platform file locking detection (handle.exe/lsof)
- **Process Manager** - Safe process termination for locked files
- **Interactive UI** - 5 view modes (by type, risk, age, duplicates, detailed)
- **Safety Checker** - Protected paths, file extensions, and 'YES' confirmation mechanism
- **Backup & Logging** - Automatic backup and cleanup logging

#### Platform-Specific Features
- **Windows Platform**
  - Windows Update cache detection
  - Recycle Bin cleanup
  - Prefetch cache management
  - Docker Desktop integration

- **Linux Platform**
  - Package manager cache cleanup (APT, YUM, DNF, Pacman)
  - Systemd journal log management
  - Old kernel version detection
  - Snap cache cleanup

- **macOS Platform**
  - Homebrew cache cleanup
  - Xcode derived data cleanup
  - iOS device backup detection
  - Thumbnail cache management

#### Automation
- **Scheduler** - Automated cleanup task scheduling
- **Task Persistence** - JSON-based task configuration
- **Multiple Cleanup Types** - smart, temp, cache, logs
- **Interval Scheduling** - Configurable time intervals (e.g., "24h")

### Changed
- **Refactored Architecture** - Modular design with `diskcleaner/` package
- **Enhanced Scripts** - All scripts now use core engine for consistency
- **Improved Safety** - Default dry-run mode, explicit confirmation required
- **Better Error Handling** - Comprehensive error messages and graceful failures
- **Cross-Platform** - Ensured Windows, Linux, macOS parity

### Testing
- **66 Test Cases** - Comprehensive test coverage
- **Platform Tests** - 17 cross-platform tests with appropriate skipif decorators
- **Integration Tests** - End-to-end workflow testing
- **100% Pass Rate** - All tests passing on all platforms

### Documentation
- **Enhanced README** - Updated with v2.0 features and examples
- **Usage Examples** - Added Python API examples
- **Platform Guides** - Platform-specific cleanup instructions
- **CHANGELOG** - This file

### Performance
- **10x Faster** - Incremental scanning on repeated runs
- **Adaptive Strategy** - Automatic optimization based on file count
- **Efficient Memory** - Streaming file processing for large directories

### Security
- **Protected Paths** - System directories, user profiles protected by default
- **Protected Extensions** - Executables, system files never deleted
- **File Lock Detection** - Prevents deletion of in-use files
- **Backup Before Delete** - Optional backup of files before deletion
- **Audit Logging** - Complete cleanup trail for accountability

### Developer Experience
- **Zero Dependencies** - Pure Python standard library
- **Type Hints** - Full type annotations for IDE support
- **Modular Design** - Easy to extend and customize
- **Well-Tested** - Comprehensive test suite with >54% coverage
- **CI/CD** - GitHub Actions for all platforms and Python versions

## [1.0.0] - Previous Release

### Features
- Basic disk space analysis
- Simple junk file cleaning
- Disk usage monitoring
- Cross-platform support (Windows, Linux, macOS)
