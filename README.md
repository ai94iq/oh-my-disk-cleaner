<p align="center">
  <img src="logo.png" alt="Disk Cleaner logo" width="180">
</p>

# oh-my-disk-cleaner

Finds what is using disk space and frees it safely on Windows, macOS and
Linux. It works as an agent skill (`skills/disk-cleaner/`) and as plain
Python scripts. Fork of [gccszs/disk-cleaner](https://github.com/gccszs/disk-cleaner),
hardened and simplified.

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Use](#use)
- [Safety](#safety)
- [Layout](#layout)
- [Development](#development)
- [License](#license)

## Requirements

- Python 3.11 or newer. The standard library is enough.
- Optional speedups: `pip install -r skills/disk-cleaner/requirements-optional.txt`
  (psutil, xxhash, blake3).

## Install

Clone, then make the skill folder visible to your agent. For Claude Code:

```bash
git clone https://github.com/ai94iq/oh-my-disk-cleaner.git
```

```powershell
# Windows: a junction keeps the skill in step with git pull
New-Item -ItemType Junction -Path $HOME\.claude\skills\disk-cleaner -Target <clone>\skills\disk-cleaner
```

```bash
# macOS and Linux
ln -s <clone>/skills/disk-cleaner ~/.claude/skills/disk-cleaner
```

Check it with `python skills/disk-cleaner/scripts/check_skill.py`.

## Use

```bash
cd skills/disk-cleaner

# Largest folders and files on a whole drive
python scripts/analyze_progressive.py --path C:\ --max-files 5000000 --max-seconds 120

# Preview junk cleanup (dry run unless --force)
python scripts/clean_disk.py --temp --cache --logs

# Duplicates, growth trend, free-space alerts
python scripts/find_duplicates.py --path ~/Downloads
python scripts/analyze_growth.py --capture
python scripts/monitor_disk.py --warning 80 --critical 90
```

`monitor_disk.py` exits 0 when every drive is fine, 1 at the warning
threshold and 2 at the critical one. [SKILL.md](skills/disk-cleaner/SKILL.md)
lists every script with its key flags, and the workflow an agent follows.

## Safety

- Nothing is deleted without `--force` (or `YES` in the wizard).
- Browser history is cleaned only when asked for with `--browser-history`.
- Filesystem roots, the home folder, system folders and executables,
  installers and disk images are protected by one shared check,
  `is_protected` in `diskcleaner/core/safety.py`. Config files can add
  protections but cannot remove the built-in ones.
- Links and junctions are removed as links; their targets are never touched.
- `clean_disk.py --path` accepts only junk-named folders unless
  `--allow-unsafe-path` is given, and `--force` needs `--confirm-path` with
  the exact absolute path.
- No process is ever stopped or killed; locked files are skipped.
- The scripts import only the `diskcleaner/` package bundled next to them.

## Layout

- `skills/disk-cleaner/SKILL.md`: the skill: workflow, scripts, safety rules
- `skills/disk-cleaner/scripts/`: command-line scripts
- `skills/disk-cleaner/diskcleaner/`: the package the scripts import (the only copy)
- `skills/disk-cleaner/references/`, `skills/disk-cleaner/docs/`: reference pages
- `tests/`: pytest suite; `tests/benchmarks/` holds slow performance runs
- `docs/ARCHIVE_FEATURE.md`: the file organizer's archive rules

## Development

```bash
pip install -e ".[dev]"
python -m pytest --ignore=tests/benchmarks
pre-commit run --all-files
```

Code and docs are plain ASCII; `tests/test_ascii.py` enforces it. Commit
messages follow `oh-my-disk-cleaner: <type>: <title>`. Changes are listed in
[CHANGELOG.md](CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE). The scripts change files on your disk: read
the preview before you confirm a cleanup.
