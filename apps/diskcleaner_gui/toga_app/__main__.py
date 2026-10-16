"""Starts the Toga app.

    python -m diskcleaner_gui.toga_app                       open the window
    python -m diskcleaner_gui.toga_app --self-check REPORT   prove the bundled scripts answer
"""

import argparse
import os
import sys


def self_check(report):
    """Runs a real scan, duplicate search and dry run on a sample folder; no window needed."""
    from .. import __version__
    from ..selfcheck import check_service

    lines, ok = [f"version: {__version__}"], True
    try:
        lines.append(check_service())
    except Exception as err:  # the report says why; the exit code says that it failed
        lines.append(f"error: {type(err).__name__}: {err}")
        ok = False
    with open(report, "w", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="diskcleaner_gui.toga_app",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--self-check", metavar="REPORT")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_check:
        return self_check(args.self_check)
    from .app import DiskCleanerApp

    DiskCleanerApp().main_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
