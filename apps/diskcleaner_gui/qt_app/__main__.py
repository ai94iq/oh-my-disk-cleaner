"""Starts Disk Cleaner.

    python -m diskcleaner_gui.qt_app                       open the window
    python -m diskcleaner_gui.qt_app --theme dark          start in a theme (system, light, dark) without saving it
    python -m diskcleaner_gui.qt_app --self-check REPORT   build the window offscreen, write a report, exit 0 when sound
    python -m diskcleaner_gui.qt_app --screenshots DIR     light and dark screenshots plus review.html, for a visual review
"""
import argparse
import os
import sys


def parse(argv):
    parser = argparse.ArgumentParser(prog="diskcleaner_gui.qt_app", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--theme", choices=("system", "light", "dark"))
    parser.add_argument("--self-check", metavar="REPORT")
    parser.add_argument("--screenshots", metavar="DIR")
    return parser.parse_args(argv)


def self_check(report):
    """What a packaged bundle must prove without a display: Qt, SVG icons, the window in both
    themes, and the bundled scripts answering a real scan and a dry-run preview."""
    from PySide6.QtCore import QSettings

    from ..selfcheck import check_service
    from . import __version__
    from .window import MainWindow

    lines, ok = [f"version: {__version__}"], True
    try:
        ini = os.path.join(os.path.dirname(os.path.abspath(report)), "self-check.ini")
        window = MainWindow(settings=QSettings(ini, QSettings.Format.IniFormat))
        for mode in ("light", "dark"):
            window.set_theme(mode)
            lines.append(f"theme {mode}: ok")
        sizes = sorted(s.width() for s in window.windowIcon().availableSizes())
        lines.append(f"icon sizes: {sizes}")
        lines.append(check_service())
    except Exception as err:  # the report says why; the exit code says that it failed
        lines.append(f"error: {type(err).__name__}: {err}")
        ok = False
    with open(report, "w", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
    return 0 if ok else 1


def screenshots(folder):
    """Each page in light and dark on one HTML page, filled from a real scan of a sample folder."""
    import tempfile

    from PySide6.QtCore import QSettings

    from .window import MainWindow

    from .window import load_service

    real = load_service()

    class Sample:
        """The real service, except a canned preview: a real one walks this machine's temp
        folders and took 209 s here (measured)."""

        def __getattr__(self, name):
            return getattr(real, name)

        def clean(self, categories, dry_run):
            rows = [
                real.CleanRow("temp", os.path.join(tempfile.gettempdir()), 1008, 2_640_000_000, []),
                real.CleanRow("cache", "Browser cache", 5, 8_660_000, []),
            ]
            return real.CleanReport(dry_run, rows)

    os.makedirs(folder, exist_ok=True)
    ini = os.path.join(folder, "screens.ini")
    window = MainWindow(settings=QSettings(ini, QSettings.Format.IniFormat), service=Sample())
    window.show()
    from ..selfcheck import sample_tree

    with tempfile.TemporaryDirectory() as sample:
        window.switch_target(sample_tree(sample))
        window.analyze()  # the worker thread is not started, so each job runs at once
        window.run_preview()
        window.find()
        window.groups.selectRow(0)
    shots = []
    for page, action in (
        ("analyze", window.analyze_page),
        ("clean", window.clean_page),
        ("duplicates", window.dup_page),
    ):
        action.trigger()
        for mode in ("light", "dark"):
            window.set_theme(mode, save=False)
            window.repaint()
            name = f"{page}-{mode}.png"
            window.grab().save(os.path.join(folder, name))
            shots.append(
                f'<figure><img src="{name}" alt="{page} {mode}"><figcaption>{page} {mode}'
                "</figcaption></figure>"
            )
    page = os.path.join(folder, "review.html")
    with open(page, "w", encoding="utf-8") as out:
        out.write(
            "<!doctype html><meta charset=utf-8><title>Disk Cleaner screens</title><style>"
            "body{font:14px sans-serif;margin:16px}img{max-width:100%;border:1px solid #ccc}"
            "</style>" + "".join(shots)
        )
    return page


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    if args.self_check:           # no display needed; --screenshots needs one, offscreen Qt has no fonts
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is missing: pip install -e .[qt]", file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Disk Cleaner")
    if args.self_check:
        return self_check(args.self_check)
    if args.screenshots:
        print(screenshots(args.screenshots))
        return 0
    from .window import MainWindow
    from .worker import start, stop
    window = MainWindow()
    if args.theme:
        window.set_theme(args.theme, save=False)
    thread = start(window.worker)
    window.show()
    code = app.exec()
    stop(thread)
    if thread.isRunning():
        # A preview can walk temp folders for minutes and cannot be interrupted; deleting a
        # running QThread aborts the process, so leave without tearing it down.
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
