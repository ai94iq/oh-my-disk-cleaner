"""Builds the Qt desktop bundle for this platform, checks it, and packs it for a release. Run exactly:

    python packaging/qt/build_bundle.py OUT_DIR [--no-install]

Steps: the build tools at pinned versions (skipped when they are already importable at those
versions), this project, PyInstaller with packaging/qt/app.spec (build files go under
OUT_DIR/.build, never the repo), the bundle's own --self-check (exit 0, both themes, the service),
then the pack: DiskCleaner-<version>-windows-x64.exe, -linux-x64.tar.gz or -macos-<arch>.dmg.
"""
import argparse
import ast
import importlib.metadata
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAME = "DiskCleaner"
TOOLS = ["pyinstaller==6.22.3", "pillow==12.3.0"]     # pinned for repeatable bundles; bump on purpose
REQUIRED = ["theme dark: ok", "service: ok"]


def version():
    path = os.path.join(ROOT, "apps", "diskcleaner_gui", "__init__.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    return next(n.value.value for n in tree.body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "__version__")


def pip(*args):
    subprocess.run([sys.executable, "-m", "pip", *args], check=True)


def tools_ready():
    try:
        return all(importlib.metadata.version(t.split("==")[0]) == t.split("==")[1] for t in TOOLS)
    except importlib.metadata.PackageNotFoundError:
        return False


def executable(dist):
    if sys.platform == "win32":
        return os.path.join(dist, f"{NAME}.exe")
    if sys.platform == "darwin":
        return os.path.join(dist, f"{NAME}.app", "Contents", "MacOS", NAME)
    return os.path.join(dist, NAME, NAME)


def self_check(dist):
    """Runs the built bundle headless: a broken bundle fails here, not on a user's machine."""
    with tempfile.TemporaryDirectory() as work:
        report = os.path.join(work, "self-check.txt")
        code = subprocess.run([executable(dist), "--self-check", report],
                              env=dict(os.environ, QT_QPA_PLATFORM="offscreen")).returncode
        text = open(report, encoding="utf-8").read() if os.path.exists(report) else ""
    print(text)
    if code or not all(r in text for r in REQUIRED):
        raise SystemExit(f"The bundle failed its self-check (exit {code}).")


def pack(out, dist):
    os.makedirs(out, exist_ok=True)
    stem = f"{NAME}-{version()}"
    if sys.platform == "win32":
        target = os.path.join(out, f"{stem}-windows-x64.exe")
        shutil.copy(executable(dist), target)
    elif sys.platform == "darwin":
        arch = "arm64" if platform.machine() == "arm64" else "x64"
        target = os.path.join(out, f"{stem}-macos-{arch}.dmg")
        subprocess.run(["hdiutil", "create", "-volname", "Disk Cleaner", "-srcfolder",
                        os.path.join(dist, f"{NAME}.app"), "-ov", "-format", "UDZO", target], check=True)
    else:
        target = os.path.join(out, f"{stem}-linux-x64.tar.gz")
        with tarfile.open(target, "w:gz") as tar:
            tar.add(os.path.join(dist, NAME), arcname=f"{stem}-linux-x64")
    print(f"{target}: {os.path.getsize(target) / 2 ** 20:.0f} MB")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    parser.add_argument("--no-install", action="store_true", help="never pip install (default: only when needed)")
    args = parser.parse_args(argv)
    out = os.path.abspath(args.out)
    work, dist = os.path.join(out, ".build", "work"), os.path.join(out, ".build", "dist")
    if not args.no_install and not tools_ready():
        pip("install", "-q", "-U", "pip", *TOOLS)
    if not args.no_install:
        pip("install", "-q", "-e", ROOT) if importlib.util.find_spec("diskcleaner_gui") is None else None
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
                    "--workpath", work, "--distpath", dist,
                    os.path.join(ROOT, "packaging", "qt", "app.spec")], check=True, cwd=ROOT)
    self_check(dist)
    pack(out, dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
