"""Entry point of the desktop bundle (PyInstaller): the same as python -m diskcleaner_gui.qt_app."""
import sys

from diskcleaner_gui.qt_app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
