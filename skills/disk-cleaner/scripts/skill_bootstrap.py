#!/usr/bin/env python3
"""
Skill bootstrap: make the scripts import the diskcleaner package that ships
next to them.

The skill root is always the parent of this scripts/ folder. Nothing else is
searched (no working directory, home, environment variable or installed
package), so a stray or planted "diskcleaner" folder can never be imported in
its place.
"""

import os
import platform
import sys
from pathlib import Path
from typing import Optional, Tuple

SKILL_ROOT = Path(__file__).resolve().parent.parent


def safe_print(message: str, file=None):
    """Print, replacing characters the console cannot encode."""
    if file is None:
        file = sys.stdout
    if file is None:  # pythonw and windowed bundles have no console
        return
    try:
        print(message, file=file)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode("ascii"), file=file)
    file.flush()


class SkillBootstrap:
    """Puts the skill root first on sys.path and checks the package imports."""

    def __init__(self):
        self.skill_root: Optional[Path] = None
        self.platform = platform.system().lower()
        self.python_version = sys.version_info
        self.debug = os.environ.get("DISK_CLEANER_DEBUG", "").lower() == "true"

    def log(self, message: str) -> None:
        """Debug log output"""
        if self.debug:
            safe_print(f"[Bootstrap] {message}", file=sys.stderr)

    def detect_skill_root(self) -> Optional[Path]:
        """Return the skill root (parent of scripts/), or None if it is incomplete."""
        if self.skill_root is None and self._is_valid_skill_root(SKILL_ROOT):
            self.skill_root = SKILL_ROOT
        return self.skill_root

    def _is_valid_skill_root(self, path: Path) -> bool:
        """Check if path is a valid skill root directory"""
        indicators = [
            path / "SKILL.md",
            path / "scripts",
            path / "diskcleaner" / "__init__.py",
            path / "diskcleaner" / "core" / "progress.py",
        ]
        return all(indicator.exists() for indicator in indicators)

    def setup_import_path(self) -> bool:
        """Put the skill root first on sys.path; return whether the package imports."""
        skill_root = self.detect_skill_root()
        if not skill_root:
            self.log(f"Skill folder is incomplete: {SKILL_ROOT}")
            return False

        skill_root_str = str(skill_root)
        if skill_root_str in sys.path:
            sys.path.remove(skill_root_str)
        sys.path.insert(0, skill_root_str)
        self.log(f"Added to sys.path: {skill_root_str}")
        self._evict_foreign_package(skill_root)
        return self._verify_import()

    def _evict_foreign_package(self, skill_root: Path) -> None:
        """Forget any diskcleaner modules imported from outside the skill root."""
        for name in [n for n in sys.modules if n == "diskcleaner" or n.startswith("diskcleaner.")]:
            module_file = getattr(sys.modules[name], "__file__", None)
            if not module_file or not Path(module_file).resolve().is_relative_to(skill_root):
                self.log(f"Evicting foreign module {name} from {module_file}")
                del sys.modules[name]

    def _verify_import(self) -> bool:
        """Verify diskcleaner module can be imported correctly"""
        try:
            from diskcleaner.core.progress import ProgressBar  # noqa: F401
            from diskcleaner.core.scanner import DirectoryScanner  # noqa: F401
        except ImportError as e:
            self.log(f"Import failed: {e}")
            return False
        return True

    def diagnose_import_failure(self) -> str:
        """Short report for when the package cannot be imported."""
        version = ".".join(str(part) for part in self.python_version[:3])
        lines = [
            "DISK CLEANER SKILL DIAGNOSTIC",
            f"  Platform: {self.platform}",
            f"  Python: {version} ({sys.executable})",
            f"  Skill root: {SKILL_ROOT}",
        ]
        if not self._is_valid_skill_root(SKILL_ROOT):
            lines.append(
                "  [X] Skill folder is incomplete: it needs SKILL.md, scripts/ and diskcleaner/."
            )
            lines.append("      Re-clone or re-copy the whole skill folder.")
        else:
            lines.append("  [X] diskcleaner/ exists but does not import; run with --debug.")
        return "\n".join(lines)

    def setup_stdout_encoding(self) -> None:
        """Never crash on characters the console cannot show."""
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")


# Global bootstrap instance
_bootstrap_instance: Optional[SkillBootstrap] = None


def get_bootstrap() -> SkillBootstrap:
    """Get bootstrap instance (singleton pattern)"""
    global _bootstrap_instance
    if _bootstrap_instance is None:
        _bootstrap_instance = SkillBootstrap()
    return _bootstrap_instance


def setup_skill_environment(
    require_modules: bool = True, fix_encoding: bool = True
) -> Tuple[bool, Optional[SkillBootstrap]]:
    """
    Setup skill runtime environment

    Args:
        require_modules: If True, print diagnostics when the package does not import
        fix_encoding: If True, make stdout/stderr replace unencodable characters

    Returns:
        (Success flag, bootstrap instance)
    """
    bootstrap = get_bootstrap()
    if fix_encoding:
        bootstrap.setup_stdout_encoding()

    success = bootstrap.setup_import_path()
    if require_modules and not success:
        print(bootstrap.diagnose_import_failure(), file=sys.stderr)
    return success, bootstrap


def import_diskcleaner_modules():
    """
    Import the commonly used diskcleaner classes from the bundled package.

    Returns:
        (Success flag, modules dictionary)
    """
    success, bootstrap = setup_skill_environment(require_modules=False)
    if not success:
        return False, {}

    try:
        from diskcleaner.config import Config
        from diskcleaner.core.cache import CacheManager
        from diskcleaner.core.classifier import FileClassifier
        from diskcleaner.core.duplicate_finder import DuplicateFinder
        from diskcleaner.core.progress import ProgressBar
        from diskcleaner.core.safety import SafetyChecker
        from diskcleaner.core.scanner import DirectoryScanner
    except ImportError as e:
        bootstrap.log(f"Module import failed: {e}")
        return False, {}

    return True, {
        "ProgressBar": ProgressBar,
        "DirectoryScanner": DirectoryScanner,
        "Config": Config,
        "CacheManager": CacheManager,
        "FileClassifier": FileClassifier,
        "SafetyChecker": SafetyChecker,
        "DuplicateFinder": DuplicateFinder,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Disk Cleaner skill package diagnostic tool")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    parser.add_argument("--test-import", action="store_true", help="Test module import")
    args = parser.parse_args()

    if args.debug:
        os.environ["DISK_CLEANER_DEBUG"] = "true"

    success, modules = import_diskcleaner_modules()
    if success:
        safe_print("[OK] Module import successful!")
        for name in modules:
            safe_print(f"  - {name}")
    else:
        safe_print("[X] Module import failed!")
        safe_print(get_bootstrap().diagnose_import_failure())
        sys.exit(1)
