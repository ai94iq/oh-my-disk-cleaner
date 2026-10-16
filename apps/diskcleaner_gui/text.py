"""Copy the desktop app shows."""

import re


def plural(count, word):
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def scan_line(files, seconds, stop_reason):
    """How a scan ended, as a sentence: the scanner's stop reasons are codes."""
    if not stop_reason:
        took = "under a second" if seconds < 1 else f"{seconds} s"
        return f"{plural(files, 'file')} in {took}"
    limit = re.match(r"(time|file)_limit \((\d+)", stop_reason)
    if limit is None:
        why = "Stopped"
    elif limit.group(1) == "time":
        why = f"Stopped at the {int(limit.group(2))} s limit"
    else:
        why = f"Stopped at the {int(limit.group(2)):,} file limit"
    return f"{why}: {plural(files, 'file')} scanned; the lists show what was found"
