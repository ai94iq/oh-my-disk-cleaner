"""The Toga app on the dummy backend: the same rules as the Qt app."""

import os
import tempfile

import pytest

pytest.importorskip("toga_dummy")
os.environ["TOGA_BACKEND"] = "toga_dummy"

from gui_fakes import FakeService  # noqa: E402

from diskcleaner_gui import service as real  # noqa: E402


@pytest.fixture
def app():
    from diskcleaner_gui.toga_app.app import DiskCleanerApp

    return DiskCleanerApp(service=FakeService())


def run(app, coroutine):
    return app.loop.run_until_complete(coroutine)


def answer(app, *responses):
    """Prepared answers for the dummy backend's ConfirmDialog."""
    app.main_window._impl.dialog_responses = {"ConfirmDialog": list(responses)}


def test_targets_are_the_drives_and_downloads(app):
    labels = [row.value for row in app.target.items]
    assert labels[0] == "C:\\  400 B free"
    assert app.target_path() == "C:\\"


def test_analyze_fills_tables_and_status(app):
    run(app, app.analyze(None))
    assert [row.name for row in app.folders.data] == ["big", "small"]
    assert [row.size for row in app.files.data] == ["800 B"]
    assert app.analyze_status.text == "1,234 files in 1.5 s"
    assert app.analyze_button.enabled and not app.stop_button.enabled


def test_stop_sets_cancel(app):
    app.stop(None)
    assert app.cancel.is_set()


def test_exit_cancels_and_lets_the_app_close(app):
    assert app.on_exit(None) is True
    assert app.cancel.is_set()


def test_missing_path_shows_one_error_line(app):
    app.service = FakeService(error=ValueError("Not a folder: X:\\gone"))
    run(app, app.analyze(None))
    assert app.analyze_status.text == "Not a folder: X:\\gone"
    assert app.analyze_button.enabled


def test_defaults_match_the_cli_and_leave_browser_history_off(app):
    assert app.ticked() == set(real.DEFAULT_CATEGORIES)


def test_clean_disabled_until_preview(app):
    assert not app.clean_button.enabled
    run(app, app.preview(None))
    assert app.service.calls[-1][2] is True  # a dry run
    assert app.clean_button.enabled
    assert len(app.preview_table.data) == 1


def test_clean_disabled_after_selection_change(app):
    run(app, app.preview(None))
    app.switches["logs"].value = False
    assert not app.clean_button.enabled
    run(app, app.preview(None))
    assert app.clean_button.enabled


def test_clean_disabled_when_preview_finds_nothing(app):
    app.service.items = 0
    run(app, app.preview(None))
    assert not app.clean_button.enabled


def test_clean_asks_first_and_does_nothing_on_no(app):
    run(app, app.preview(None))
    answer(app, False)
    run(app, app.clean(None))
    assert [call[2] for call in app.service.calls if call[0] == "clean"] == [True]


def test_clean_on_yes_deletes_and_reports(app):
    run(app, app.preview(None))
    answer(app, True)
    run(app, app.clean(None))
    assert app.service.calls[-1] == ("clean", tuple(sorted(app.ticked())), False)
    assert app.clean_status.text == "Freed 300 B from 3 items; 0 errors"
    assert not app.clean_button.enabled  # a new preview comes first


def test_duplicates_list_groups_and_show_copies(app):
    run(app, app.find(None))
    assert app.service.calls[-1] == ("duplicates", "C:\\")
    assert [row.reclaimable for row in app.groups.data] == ["100 B"]
    app.groups._impl.simulate_selection(0)
    assert [row.path for row in app.copies.data] == ["C:\\a\\x.txt", "C:\\b\\x.txt", "C:\\c\\x.txt"]
    assert app.dup_status.text == "1 group; 100 B reclaimable"


def test_self_check_runs_the_real_service():
    from diskcleaner_gui.toga_app.__main__ import main

    report = os.path.join(tempfile.mkdtemp(), "report.txt")
    assert main(["--self-check", report]) == 0
    text = open(report, encoding="utf-8").read()
    assert "service: ok" in text
    assert "error" not in text


def test_target_selection_is_wide_enough_for_a_drive_label(app):
    assert app.target.style.width == 240


def test_progress_bars_show_only_while_a_job_runs(app):
    bars = (app.analyze_bar, app.clean_bar, app.dup_bar)
    assert all(bar.style.visibility == "hidden" for bar in bars)
    seen = []
    app.service.analyze = lambda *a, **k: seen.append(app.analyze_bar.style.visibility) or 1 / 0
    run(app, app.analyze(None))
    assert seen == ["visible"]
    assert app.analyze_bar.style.visibility == "hidden"
