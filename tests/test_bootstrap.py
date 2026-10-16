"""skill_bootstrap loads only the diskcleaner package that ships with the skill."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "disk-cleaner"
SCRIPTS = SKILL / "scripts"


def load_bootstrap():
    spec = importlib.util.spec_from_file_location(
        "skill_bootstrap_under_test", SCRIPTS / "skill_bootstrap.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plant_fake_skill(root: Path) -> Path:
    """A folder that looks like a skill root and holds a hostile diskcleaner."""
    (root / "scripts").mkdir(parents=True)
    (root / "SKILL.md").write_text("fake", encoding="utf-8")
    core = root / "diskcleaner" / "core"
    core.mkdir(parents=True)
    (root / "diskcleaner" / "__init__.py").write_text("PLANTED = True\n", encoding="utf-8")
    (core / "__init__.py").write_text("", encoding="utf-8")
    (core / "progress.py").write_text("", encoding="utf-8")
    return root


def test_ignores_planted_package_in_cwd_and_env(tmp_path, monkeypatch):
    fake = plant_fake_skill(tmp_path / "fake")
    monkeypatch.chdir(fake)
    monkeypatch.setenv("DISK_CLEANER_SKILL_PATH", str(fake))

    root = load_bootstrap().SkillBootstrap().detect_skill_root()

    assert root.resolve() == SKILL


# check_skill.py is the diagnostic for a broken install: it loads the bootstrap
# inside a try when run, so importing it loads no diskcleaner at all
SCRIPT_NAMES = sorted(
    p.stem for p in SCRIPTS.glob("*.py") if p.stem not in {"skill_bootstrap", "check_skill"}
)


@pytest.mark.parametrize("script", SCRIPT_NAMES)
def test_scripts_ignore_planted_modules_when_imported(script, tmp_path):
    fake = plant_fake_skill(tmp_path / "fake")
    (fake / "skill_bootstrap.py").write_text(
        "raise SystemExit('PLANTED BOOTSTRAP')\n", encoding="utf-8"
    )
    code = (
        "import sys; sys.path.append(sys.argv[1]);"
        "import diskcleaner;"  # a foreign copy already loaded, as a host program might
        f"import {script};"
        "import diskcleaner; print(diskcleaner.__file__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(SCRIPTS)],
        cwd=fake,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(result.stdout.strip().splitlines()[-1]).resolve().is_relative_to(SKILL)


def test_import_resolves_inside_skill(tmp_path):
    fake = plant_fake_skill(tmp_path / "fake")
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import skill_bootstrap; ok, _ = skill_bootstrap.import_diskcleaner_modules();"
        "import diskcleaner; print(ok); print(diskcleaner.__file__)"
    )
    env = dict(os.environ, DISK_CLEANER_SKILL_PATH=str(fake), PYTHONPATH=str(fake))

    result = subprocess.run(
        [sys.executable, "-c", code, str(SCRIPTS)],
        cwd=fake,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    ok, module_file = result.stdout.split()[:2]
    assert ok == "True"
    assert Path(module_file).resolve().is_relative_to(SKILL)


def test_safe_print_without_console(monkeypatch):
    # pythonw and windowed bundles have no console: sys.stdout is None
    bootstrap = load_bootstrap()
    monkeypatch.setattr(sys, "stdout", None)
    bootstrap.safe_print("x")
