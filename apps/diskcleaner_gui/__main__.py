"""Starts the Toga app; Briefcase runs the package by its own name."""

import sys

from .toga_app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
