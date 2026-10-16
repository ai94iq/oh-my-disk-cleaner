# Interactive wizard

`scripts/interactive_wizard.py` walks a person through a cleanup in the
terminal: pick a scan mode, review files by type, risk or age, select them,
then confirm. It reads from the keyboard, so an agent should use the
non-interactive scripts in [SKILL.md](../SKILL.md) instead.

## Contents

- [Run it](#run-it)
- [Scan modes](#scan-modes)
- [Risk levels](#risk-levels)
- [Confirmation steps](#confirmation-steps)
- [What the cleanup does](#what-the-cleanup-does)
- [Configuration](#configuration)
- [Tests](#tests)

## Run it

```bash
python scripts/interactive_wizard.py                 # current folder
python scripts/interactive_wizard.py ~/Downloads     # a given folder
```

## Scan modes

| Mode | Limit | Use for |
|---|---|---|
| 1. Quick | 10,000 files or 1 second | A fast look at common temp locations |
| 2. Standard | 100,000 files or 120 seconds, cached | Most folders (recommended) |
| 3. Deep | No file or time limit, cached | A thorough cleanup; can take long |
| 4. Progressive | Cached incremental scan | Repeat scans of the same folder |
| 5. Custom | Limits you type in | Large trees with known bounds |

## Risk levels

| Tag | Level | Files | Selection |
|---|---|---|---|
| `[OK]` | Safe | Temp and build artifacts, logs, caches | Can be selected in one step |
| `[!]` | Needs confirmation | Downloads, media, documents and anything unclassified | Select by hand |
| `[X]` | Protected | Matches a protected path, extension or pattern (`*.db`, `*.conf` and similar) | Needs `I UNDERSTAND` |

Protected paths (system folders, the home folder) and protected extensions
(executables, installers, disk images) are refused at delete time even if
selected. Config files can add protections but cannot remove the built-in
ones.

## Confirmation steps

1. A summary groups the selected files by risk with counts and sizes.
2. If any risky file is selected, type `I UNDERSTAND`.
3. Type `YES` to delete. Anything else cancels.

## What the cleanup does

For each selected path:

- A regular file is copied to `~/.disk-cleaner/backup/<date>/` first. If
  the copy fails, the file is kept and reported.
- Protected paths are refused.
- A link or junction is removed as a link; its target is not touched.
- Each deletion is logged to `~/.disk-cleaner/logs/cleanup.log`.

Backups are not pruned automatically; delete old dated folders under
`~/.disk-cleaner/backup/` once the result is confirmed.

## Configuration

Settings are read from `~/.disk-cleaner/config.yaml`, then from
`.disk-cleaner.yaml` in the scanned folder. Example:

```yaml
protected:
  paths: [important-project/, database/]
  patterns: ["*.db", "*.sqlite"]
safety:
  check_file_locks: true
  verify_permissions: true
scan:
  use_incremental: true
  cache_ttl: 7
```

## Tests

```bash
python scripts/test_wizard.py
python -m pytest tests/test_interactive.py tests/test_interactive_cleanup.py
```
