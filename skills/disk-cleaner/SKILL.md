---
name: disk-cleaner
description: Analyzes disk usage and safely frees space on Windows, macOS and Linux. Finds the largest folders and files on a drive or partition, previews and cleans temp files, caches, logs and the recycle bin, finds duplicate files, tracks disk growth and monitors free space. Use when the user asks to free up disk space, scan a drive or partition, find what is using space, find large files or duplicates, or clean temp or cache files.
---

# Disk cleaner

Python scripts in `scripts/` plus the `diskcleaner/` package they import.
Run them; there is nothing to install. Every script prints `--help`.

## Contents

- [Requirements](#requirements)
- [Analyze a drive](#analyze-a-drive)
- [Clean safely](#clean-safely)
- [Scripts](#scripts)
- [Safety rules](#safety-rules)
- [Reading the numbers](#reading-the-numbers)
- [References](#references)

## Requirements

- Python 3.11 or newer (the oldest release still getting security fixes).
- Optional speedups, never required: `pip install -r requirements-optional.txt`
  (psutil, xxhash, blake3). Ask the user before installing anything.
- Paths below are relative to this skill folder. On Windows use `python`,
  elsewhere `python3`.

## Analyze a drive

1. Optional: a one-second `--sample` shows how many files it reached and
   the scan rate. It cannot predict the full scan time.

2. Scan. For a whole drive use the progressive scanner with the file cap
   raised, otherwise it stops at its 50,000-file default within a second:

   ```bash
   python scripts/analyze_progressive.py --path C:\ --max-files 5000000 --max-seconds 120 --no-progress
   ```

   Add `--include-windows` to count `C:\Windows`, `Program Files` and
   `ProgramData`; without it the scanner skips them.

3. Drill into a large folder with the same command and a narrower `--path`.

4. Report to the user with this template, largest first, one row per
   finding, and change nothing yet:

   ```markdown
   | GB | What | How to remove it | Risk |
   |---|---|---|---|
   | 27.9 | `.gradle\caches` | Delete the folder | Safe. Downloads again on the next build. |
   ```

## Clean safely

1. Preview. `clean_disk.py` is a dry run unless `--force` is given:

   ```bash
   python scripts/clean_disk.py --temp --cache --logs
   ```

2. Show the preview and wait for an explicit yes.
3. Run the same command with `--force`.

Browser history and the legacy Windows web cache (`History`, `WebCache`)
are user data and never part of a default run. Offer them separately and
use `--browser-history` only when the user asks for it.

For a custom folder, `--path` deletes its contents recursively. It accepts
only junk-named folders (`temp`, `cache`, `logs`, `trash` and similar)
with no project markers such as `.git` or `package.json`, unless
`--allow-unsafe-path` is given, and `--force` also needs `--confirm-path`
with the exact absolute path. Prefer the
owning tool (Steam, Ubisoft Connect, Android Studio Device Manager,
`npm cache clean --force`, Windows Storage settings) over deleting
application folders by hand.

## Scripts

| Script | Purpose | Key flags |
|---|---|---|
| `analyze_disk.py` | Largest folders and files | `--path`, `--top`, `--sample`, `--include-windows`, `--json` |
| `analyze_progressive.py` | Whole-drive scan with live progress | `--path`, `--max-files`, `--max-seconds`, `--include-windows` |
| `clean_disk.py` | Temp, cache, log and recycle-bin cleanup | `--temp`, `--cache`, `--logs`, `--recycle`, `--browser-history`, `--force` |
| `find_duplicates.py` | Duplicate files | `--path`, `--strategy {adaptive,fast,accurate}` |
| `analyze_growth.py` | Usage snapshots and growth trend | `--capture`, `--history`, `--cleanup DAYS` |
| `monitor_disk.py` | Free-space thresholds per drive | `--warning`, `--critical`, `--watch` |
| `organize_files.py` | Sort a folder into subfolders | `--strategy`, `--preview`, `--execute` |
| `interactive_wizard.py` | Guided cleanup in the terminal (needs a human at the keyboard) | `path` |
| `scheduler.py` | Saved folders to re-analyze on a schedule; reports only, never deletes | `add`, `list`, `remove`, `run` |
| `check_skill.py` | Self-test of this skill folder | none |
| `qq_cleanup_macos.zsh` | QQ pictures and emoji cache on macOS | see [QQ cleanup](references/qq_cleanup_macos.md) |

## Safety rules

- Never delete without showing a preview and getting an explicit yes.
- Never kill or stop processes. Locked files are reported and skipped.
- Roots, the home folder, system folders and executables, installers and
  disk images (`.exe`, `.dll`, `.msi`, `.iso`, `.vhdx` and similar) are
  protected; the rules live in `diskcleaner/core/safety.py` (`is_protected`).
- Links and junctions are removed as links; their targets are never
  entered or deleted.
- The scripts only import the `diskcleaner/` package next to them.
- Do not spawn sub-agents for scanning; one scan per drive is fast enough.

## Reading the numbers

- Sizes are logical file sizes. A sparse file (emulator and VM disk images)
  can be listed at hundreds of GB while using far less. On Windows check with
  `fsutil sparse queryrange <file>` before recommending its removal.
- Folder totals on a drive count every file the scan reached. A scan that
  stopped early (`Stopped early: file_limit` or `time_limit`) undercounts;
  raise the limit and rerun.

## References

- [Temp and cache locations per platform](references/temp_locations.md)
- [Interactive wizard walkthrough](docs/WIZARD_USAGE.md)
- [QQ media cleanup on macOS](references/qq_cleanup_macos.md)
