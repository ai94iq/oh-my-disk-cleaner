# PyInstaller spec for the Qt desktop bundle:
#     pyinstaller --noconfirm packaging/qt/app.spec        (build_bundle.py runs it for you)
# Windows: one DiskCleaner.exe. Linux: a DiskCleaner folder. macOS: DiskCleaner.app.
# The skill tree is shipped as DATA (not in the PYZ) so skill_bootstrap finds a valid root.
import ast
import importlib.metadata
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(SPECPATH))
APPS = os.path.join(ROOT, "apps")
SKILL = os.path.join(ROOT, "skills", "disk-cleaner")
sys.path.insert(0, APPS)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import diskcleaner_gui  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from diskcleaner_gui.qt_app.icons import app_icon  # noqa: E402

NAME = "DiskCleaner"
qt = QGuiApplication.instance() or QGuiApplication([])
ICON = os.path.join(workpath, "app.png")      # PyInstaller makes the .ico or .icns from it
os.makedirs(workpath, exist_ok=True)
app_icon().pixmap(256, 256).save(ICON)

# The skill tree as data: SKILL.md, scripts/*.py, diskcleaner/**/*.py.
skill_files = [os.path.join(SKILL, "SKILL.md")]
for folder in ("scripts", "diskcleaner"):
    for base, dirs, files in os.walk(os.path.join(SKILL, folder)):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        skill_files += [os.path.join(base, f) for f in files if f.endswith(".py")]
datas = [(f, "skills/disk-cleaner/" + os.path.dirname(os.path.relpath(f, SKILL)).replace("\\", "/")
          .rstrip("/")) for f in skill_files]
datas = [(src, dest.rstrip("/")) for src, dest in datas]

# Skill code is not frozen, so its imports are not seen: add every imported top-level module.
script_names = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(SKILL, "scripts"))}
hidden = set()
for src in skill_files:
    if src.endswith(".py"):
        for node in ast.walk(ast.parse(open(src, encoding="utf-8").read())):
            if isinstance(node, ast.Import):
                hidden.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                hidden.add(node.module.split(".")[0])
hidden -= script_names | {"diskcleaner", "__future__"}
hidden = {m for m in hidden if importlib.util.find_spec(m)}   # optional ones (blake3, xxhash) may be absent

# Licenses of everything shipped: the packages' own files, plus Qt's LGPL (PySide6 wheels carry none).
LICENSED = ("PySide6_Essentials", "shiboken6")
licenses = [(os.path.join(ROOT, "LICENSE"), "licenses/oh-my-disk-cleaner"),
            (os.path.join(SPECPATH, "licenses", "LGPL-3.0.txt"), "licenses/Qt-PySide6"),
            (os.path.join(SPECPATH, "licenses", "GPL-3.0.txt"), "licenses/Qt-PySide6")]
for dist in LICENSED:
    for file in importlib.metadata.distribution(dist).files or []:
        if any(k in file.name.upper() for k in ("LICENSE", "COPYING")) and file.suffix not in (".py", ".pyc"):
            licenses.append((str(file.locate()), f"licenses/{dist}"))

# Qt modules the app never loads; each one left out saves megabytes.
EXCLUDES = ["tkinter", "PIL", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
            "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
            "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtCharts",
            "PySide6.QtDesigner"]
# Skill modules must stay out of the PYZ (they are read from the data copy).
EXCLUDES += sorted(script_names | {"diskcleaner"})

a = Analysis([os.path.join(SPECPATH, "entry.py")], pathex=[APPS], datas=datas + licenses,
             hiddenimports=sorted(hidden), excludes=EXCLUDES)
pyz = PYZ(a.pure)
if sys.platform == "win32":
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, name=NAME, console=False, icon=ICON, upx=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, icon=ICON, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)
    if sys.platform == "darwin":
        app = BUNDLE(coll, name=f"{NAME}.app", icon=ICON, bundle_identifier="io.github.disk-cleaner",
                     version=diskcleaner_gui.__version__, info_plist={"NSHighResolutionCapable": True})
