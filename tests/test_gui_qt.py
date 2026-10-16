"""The PySide6 app: template invariants (icons, themes, popups, focus) and the cleanup rules."""

import os
import tempfile
import unittest

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from diskcleaner_gui import service as real  # noqa: E402
from gui_fakes import FakeService  # noqa: E402
from PySide6.QtCore import QEvent, QObject, QPoint, QSettings, Qt, Signal  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QMenu, QStyle, QToolTip  # noqa: E402


class FakeWorker(QObject):
    """Takes jobs without running them, so a test decides when each one ends."""

    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.jobs = []

    def reserve(self):
        return len(self.jobs) + 1

    def submit(self, call, job=None):
        self.jobs.append(call)
        return job or len(self.jobs)


class QtCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.mkdtemp()
        self.settings = QSettings(os.path.join(folder, "test.ini"), QSettings.Format.IniFormat)
        self.worker = FakeWorker()
        self.service = FakeService()
        self.window = self.new_window()

    def new_window(self, **kwargs):
        from diskcleaner_gui.qt_app.window import MainWindow

        kwargs.setdefault("worker", self.worker)
        kwargs.setdefault("service", self.service)
        window = MainWindow(settings=self.settings, **kwargs)
        self.addCleanup(self.dispose, window)
        return window

    def dispose(self, window):
        """Closes and deletes a window: live windows from earlier tests are restyled on every
        theme change and slow the suite to minutes (measured)."""
        window.close()
        window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def finish(self):
        """Runs the newest queued job and reports its result, as the worker thread would."""
        job = len(self.worker.jobs)
        self.worker.finished.emit(job, self.worker.jobs[-1]())
        return job


class TemplateInvariants(QtCase):
    @staticmethod
    def images(icon_):
        return [
            icon_.pixmap(32, 32, QIcon.Mode.Normal, state).toImage()
            for state in (QIcon.State.Off, QIcon.State.On)
        ]

    def test_checked_icon_is_drawn_in_its_own_color(self):
        from diskcleaner_gui.qt_app.icons import icon

        off, on = self.images(icon("analyze", "#000000", "#ff0000"))
        self.assertNotEqual(off, on)

    def test_stroke_lands_on_whole_device_pixels(self):
        from diskcleaner_gui.qt_app.icons import svg_bytes

        for pixels in (16, 20, 24, 32, 40):
            svg = svg_bytes("analyze", "#000", pixels=pixels)
            width = float(svg.split(b'stroke-width="')[1].split(b'"')[0])
            self.assertAlmostEqual(width * pixels / 24 % 1, 0, places=2)

    def test_every_icon_name_is_vendored(self):
        from diskcleaner_gui.qt_app.icons import ICON_NAMES
        from diskcleaner_gui.qt_app.lucide import ICONS

        self.assertEqual([n for n in ICON_NAMES.values() if n not in ICONS], [])

    def test_app_icon_is_drawn_for_every_size(self):
        from diskcleaner_gui.qt_app.icons import app_icon

        sizes = sorted(s.width() for s in app_icon().availableSizes())
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256])

    def test_text_has_enough_contrast_in_both_themes(self):
        from diskcleaner_gui.qt_app.theme import THEMES, contrast

        pairs = (
            ("ink", "panel", 7),
            ("ink2", "panel", 4.5),
            ("ink2", "ground", 4.5),
            ("accent_text", "accent_soft", 4.5),
            ("accent_ink", "accent", 4.5),
            ("ink3", "panel", 3),
            ("warn", "warn_soft", 4.5),
            ("ok", "ground", 4.5),
            ("bad_text", "ground", 4.5),
        )
        for name, t in THEMES.items():
            for fg, bg, need in pairs:
                with self.subTest(theme=name, fg=fg, bg=bg):
                    self.assertGreaterEqual(contrast(t[fg], t[bg]), need)

    def test_both_themes_have_the_same_tokens(self):
        from diskcleaner_gui.qt_app.theme import THEMES

        self.assertEqual(set(THEMES["light"]), set(THEMES["dark"]))

    def test_theme_button_cycles_and_persists(self):
        window = self.window
        self.assertEqual(window.theme_mode, "system")
        window.theme_action.trigger()
        self.assertEqual((window.theme_mode, self.settings.value("theme")), ("light", "light"))
        window.theme_action.trigger()
        self.assertEqual(window.theme_mode, "dark")
        self.assertEqual(self.new_window().theme_mode, "dark")

    def test_invalid_stored_theme_falls_back_to_system(self):
        self.settings.setValue("theme", "neon")
        self.assertEqual(self.new_window().theme_mode, "system")

    def test_dark_cards_use_an_edge_not_a_shadow(self):
        self.window.set_theme("dark")
        self.assertFalse(self.window.cards[0].frame.graphicsEffect().isEnabled())
        self.window.set_theme("light")
        self.assertTrue(self.window.cards[0].frame.graphicsEffect().isEnabled())

    def test_toolbar_keeps_its_height_across_themes(self):
        self.window.show()
        self.app.processEvents()
        height = self.window.toolbar.height()
        for mode in ("dark", "light"):
            self.window.set_theme(mode)
            self.app.processEvents()
            self.assertEqual(self.window.toolbar.height(), height)

    def test_menus_and_tooltips_are_see_through_and_quick(self):
        from diskcleaner_gui.qt_app.theme import TIP_DELAY

        menu = QMenu()
        menu.ensurePolished()
        self.assertTrue(menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        QToolTip.showText(QPoint(50, 50), "tip")
        tips = [w for w in self.app.topLevelWidgets() if w.metaObject().className() == "QTipLabel"]
        self.assertTrue(
            tips and all(w.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) for w in tips)
        )
        hint = self.app.style().styleHint(QStyle.StyleHint.SH_ToolTip_WakeUpDelay)
        self.assertEqual(hint, TIP_DELAY)

    def test_buttons_take_focus_by_keyboard_only(self):
        self.assertEqual(self.window.theme_button.focusPolicy(), Qt.FocusPolicy.TabFocus)

    def test_icon_only_buttons_have_a_name_and_a_tip(self):
        self.assertEqual(self.window.theme_button.accessibleName(), "Theme")
        self.assertTrue(self.window.theme_action.toolTip())

    def test_checked_boxes_are_drawn_from_the_theme_in_both_themes(self):
        # Styling only the unchecked box left Fusion's solid black square for checked ones
        for mode in ("light", "dark"):
            self.window.set_theme(mode)
            sheet = self.app.styleSheet()
            rule = sheet.split("QListWidget::indicator:checked", 1)[1].split("}", 1)[0]
            self.assertIn(self.window.t["accent"], rule)
            image = rule.split("url(", 1)[1].split(")", 1)[0]
            self.assertTrue(os.path.isfile(image), image)

    def test_the_target_pill_works_from_the_keyboard(self):
        pill = self.window.pill
        self.assertEqual(pill.focusPolicy(), Qt.FocusPolicy.TabFocus)
        self.assertEqual(pill.accessibleName(), "Target: C:\\  400 B free")
        opened = []
        pill.clicked.disconnect()  # the real menu's exec() would block the test
        pill.clicked.connect(lambda: opened.append(1))
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            QTest.keyClick(pill, key)
        self.assertEqual(opened, [1, 1])

    def test_labels_never_render_rich_text(self):
        from diskcleaner_gui.qt_app.widgets import plain_label

        self.assertEqual(plain_label("<b>x</b>").textFormat(), Qt.TextFormat.PlainText)


class Screens(QtCase):
    def test_pages_switch_in_place(self):
        self.window.clean_page.trigger()
        self.assertIs(self.window.pages.currentWidget(), self.window.clean_view)
        self.window.dup_page.trigger()
        self.assertIs(self.window.pages.currentWidget(), self.window.dup_view)

    def test_targets_are_the_drives_and_a_folder_choice(self):
        self.assertEqual(self.window.target, "C:\\")
        self.assertIn("400 B free", self.window.pill.text.text())
        self.assertTrue(self.window.pill.property("menu"))
        self.window.switch_target("D:\\")
        self.assertEqual(self.window.target, "D:\\")

    def test_analyze_shows_pending_at_once_then_fills_tables(self):
        self.window.analyze_action.trigger()
        self.assertIn("Scanning", self.window.status.text())
        self.assertFalse(self.window.analyze_action.isEnabled())
        self.assertTrue(self.window.stop_action.isEnabled())
        self.assertFalse(self.window.preview_action.isEnabled())  # one job at a time
        self.finish()
        self.assertEqual(self.window.folders.rowCount(), 2)
        self.assertEqual(self.window.folders.item(0, 0).text(), "big")
        self.assertEqual(self.window.files.rowCount(), 1)
        self.assertEqual(self.window.status.text(), "1,234 files in 1.5 s")
        self.assertTrue(self.window.analyze_action.isEnabled())
        self.assertFalse(self.window.stop_action.isEnabled())

    def test_stop_cancels_the_scan(self):
        self.window.analyze_action.trigger()
        self.window.stop_action.trigger()
        self.assertTrue(self.window.cancel.is_set())

    def test_close_cancels_a_running_scan(self):
        self.window.analyze_action.trigger()
        self.window.close()
        self.assertTrue(self.window.cancel.is_set())

    def test_each_page_keeps_its_own_status(self):
        self.window.dup_page.trigger()
        self.window.find_action.trigger()
        self.finish()
        self.window.analyze_page.trigger()
        self.assertEqual(self.window.status.text(), "")
        self.window.dup_page.trigger()
        self.assertEqual(self.window.status.text(), "1 group; 100 B reclaimable")

    def test_a_folder_target_shows_its_name_and_full_path_on_hover(self):
        folder = os.path.join(tempfile.gettempdir(), "A long folder name")
        self.window.switch_target(folder)
        self.assertEqual(self.window.pill.text.text(), "A long folder name")
        self.assertIn(folder, self.window.pill.toolTip())

    def test_table_clicks_leave_no_focus_ring(self):
        self.assertEqual(self.window.groups.focusPolicy(), Qt.FocusPolicy.TabFocus)

    def test_missing_path_shows_one_error_line(self):
        from diskcleaner_gui.qt_app.worker import Worker

        service = FakeService(error=ValueError("Not a folder: X:\\gone"))
        window = self.new_window(worker=Worker(), service=service)  # no thread: runs at once
        window.analyze_action.trigger()
        self.assertEqual(window.status.text(), "Not a folder: X:\\gone")
        self.assertEqual(window.status.property("tone"), "bad")
        self.assertTrue(window.analyze_action.isEnabled())

    def test_duplicates_list_groups_and_show_copies(self):
        self.window.dup_page.trigger()
        self.window.find_action.trigger()
        self.finish()
        self.assertEqual(self.service.calls[-1], ("duplicates", "C:\\"))
        self.assertEqual(self.window.groups.rowCount(), 1)
        self.assertEqual(self.window.groups.item(0, 2).text(), "100 B")  # reclaimable
        self.window.groups.selectRow(0)
        self.assertEqual(self.window.copies.count(), 3)


class Cleanup(QtCase):
    def setUp(self):
        super().setUp()
        self.window.clean_page.trigger()  # Clean's buttons and status live on its page

    def ticked(self):
        return self.window.ticked()

    def preview(self):
        self.window.preview_action.trigger()
        self.finish()

    def test_defaults_match_the_cli_and_leave_browser_history_off(self):
        self.assertEqual(self.ticked(), set(real.DEFAULT_CATEGORIES))

    def test_clean_disabled_until_preview(self):
        self.assertFalse(self.window.clean_action.isEnabled())
        self.preview()
        self.assertEqual(self.service.calls[-1][2], True)  # a dry run
        self.assertTrue(self.window.clean_action.isEnabled())
        self.assertEqual(self.window.preview.rowCount(), 1)

    def test_clean_disabled_after_selection_change(self):
        self.preview()
        self.window.set_ticked("logs", False)
        self.assertFalse(self.window.clean_action.isEnabled())
        self.preview()
        self.assertTrue(self.window.clean_action.isEnabled())

    def test_clean_disabled_when_preview_finds_nothing(self):
        self.service.items = 0
        self.preview()
        self.assertFalse(self.window.clean_action.isEnabled())

    def test_clean_asks_first_and_does_nothing_on_no(self):
        self.preview()
        asked = []
        self.window.confirm = lambda text, details: asked.append((text, details)) or False
        jobs = len(self.worker.jobs)
        self.window.clean_action.trigger()
        self.assertEqual(
            asked,
            [
                (
                    "Delete 3 items (300 B) from 1 location? This cannot be undone.",
                    "Temporary files: 3 items, 300 B",
                )
            ],
        )
        self.assertEqual(len(self.worker.jobs), jobs)
        self.assertNotIn(False, [call[2] for call in self.service.calls if call[0] == "clean"])

    def test_clean_on_yes_deletes_and_reports(self):
        self.preview()
        self.window.confirm = lambda text, details: True
        self.window.clean_action.trigger()
        self.finish()
        self.assertEqual(self.service.calls[-1], ("clean", tuple(sorted(self.ticked())), False))
        self.assertEqual(self.window.status.text(), "Freed 300 B from 3 items; 0 errors")
        self.assertEqual(self.window.status.property("tone"), "ok")
        self.assertFalse(self.window.clean_action.isEnabled())  # a new preview comes first

    def test_the_confirm_names_the_deletion_and_defaults_to_keeping_files(self):
        box = self.window.confirm_box("Delete 3 items?", "Temporary files: 3 items, 300 B")
        self.assertEqual(box.defaultButton().text(), "Keep files")
        self.assertIs(box.escapeButton(), box.defaultButton())
        texts = [button.text() for button in box.buttons()]
        self.assertIn("Delete files", texts)
        self.assertNotIn("Yes", texts)
        self.assertEqual(box.informativeText(), "Temporary files: 3 items, 300 B")

    def test_the_confirm_warns_that_the_recycle_bin_is_emptied_for_good(self):
        self.service.calls.clear()
        self.window.previewed = (
            {"recycle"},
            real.CleanReport(True, [real.CleanRow("recycle", "C:\\$Recycle.Bin", 2, 50, [])]),
        )
        self.window.set_ticked("temp", False)
        self.window.set_ticked("cache", False)
        self.window.set_ticked("logs", False)
        asked = []
        self.window.confirm = lambda text, details: asked.append(details) or False
        self.window.clean_action.trigger()
        self.assertIn("Recycle bin: 2 items, 50 B (emptied for good)", asked[0])


class WorkerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_jobs_run_in_order_off_the_ui_thread(self):
        import threading

        from diskcleaner_gui.qt_app.worker import Worker, start, stop

        worker, seen, threads = Worker(), [], []
        worker.finished.connect(lambda job, result: seen.append(result))
        thread = start(worker)
        try:
            for n in range(3):
                worker.submit(lambda n=n: (threads.append(threading.get_ident()), n)[1])
            for _ in range(100):
                if len(seen) == 3:
                    break
                QTest.qWait(20)
        finally:
            stop(thread)
        self.assertEqual(seen, [0, 1, 2])
        self.assertNotIn(threading.get_ident(), threads)

    def test_a_failing_job_reports_instead_of_raising(self):
        from diskcleaner_gui.qt_app.worker import Worker

        worker, errors = Worker(), []
        worker.failed.connect(lambda job, text: errors.append((job, text)))
        job = worker.submit(lambda: 1 / 0)
        self.assertEqual(errors, [(job, "division by zero")])


class SelfCheckTest(unittest.TestCase):
    def test_self_check_runs_the_real_service(self):
        from diskcleaner_gui.qt_app.__main__ import main

        report = os.path.join(tempfile.mkdtemp(), "report.txt")
        self.assertEqual(main(["--self-check", report]), 0)
        with open(report, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("theme dark: ok", text)
        self.assertIn("service: ok", text)
        self.assertNotIn("error", text)


class Hierarchy(QtCase):
    def test_each_page_has_one_primary_action_and_clean_reads_as_danger(self):
        buttons = self.window.buttons
        names = {action.text(): buttons[action].objectName() for action in buttons}
        self.assertEqual(names["Analyze"], "primary")
        self.assertEqual(names["Preview"], "primary")
        self.assertEqual(names["Find"], "primary")
        self.assertEqual(names["Clean"], "danger")
        self.assertEqual(names["Stop"], "")

    def test_the_preview_total_is_a_warning_not_a_reward(self):
        self.assertEqual(self.window.total.objectName(), "warn_chip")

    def test_danger_and_primary_text_has_contrast_in_both_themes(self):
        from diskcleaner_gui.qt_app.theme import THEMES, contrast

        for name, t in THEMES.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(contrast(t["bad_text"], t["bad_soft"]), 4.5)
                self.assertGreaterEqual(contrast(t["accent_ink"], t["accent"]), 4.5)


class StalePreview(QtCase):
    def setUp(self):
        super().setUp()
        self.window.clean_page.trigger()
        self.window.preview_action.trigger()
        self.finish()

    def test_changing_the_ticks_says_the_preview_is_out_of_date(self):
        self.window.set_ticked("logs", False)
        self.assertEqual(self.window.preview.stack.currentIndex(), 0)  # the empty state
        self.assertEqual(self.window.preview_empty.title.text(), "Preview is out of date")
        self.assertEqual(
            self.window.status.text(), "Selection changed; preview again before cleaning"
        )
        self.assertFalse(self.window.total.isVisibleTo(self.window))

    def test_ticking_back_brings_the_preview_back(self):
        self.window.set_ticked("logs", False)
        self.window.set_ticked("logs", True)
        self.assertEqual(self.window.preview.stack.currentIndex(), 1)
        self.assertTrue(self.window.clean_action.isEnabled())

    def test_after_a_clean_the_deleted_rows_are_gone(self):
        self.window.confirm = lambda text, details: True
        self.window.clean_action.trigger()
        self.finish()
        self.assertEqual(self.window.preview.rowCount(), 0)
        self.assertEqual(self.window.preview.stack.currentIndex(), 0)
        self.assertEqual(self.window.preview_empty.title.text(), "Cleaned")
        self.assertEqual(self.window.total.isVisibleTo(self.window), False)


class DarkFills(QtCase):
    def rule(self, selector):
        return self.app.styleSheet().split(selector + " {", 1)[1].split("}", 1)[0]

    def test_filled_controls_carry_white_text_in_both_themes(self):
        # Dark mode drew near-black text on light blue for the selected tab and the
        # main button (accent_ink on accent), which read as too dark (user report)
        from diskcleaner_gui.qt_app.theme import THEMES, contrast

        for name, t in THEMES.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(contrast(t["fill_ink"], t["fill"]), 4.5)
                self.assertGreaterEqual(contrast(t["fill"], t["panel"]), 3)
                self.window.set_theme(name)
                for selector in (
                    "QToolBar#shell QFrame#seg QToolButton:checked",
                    "QFrame#bar QToolButton#primary",
                ):
                    self.assertIn(f"background: {t['fill']}", self.rule(selector))
                    self.assertIn(f"color: {t['fill_ink']}", self.rule(selector))

    def test_a_running_main_button_stays_readable(self):
        self.window.set_theme("dark")
        t = self.window.t
        rule = self.rule("QFrame#bar QToolButton#primary:disabled")
        self.assertIn(f"background: {t['raised']}", rule)
        self.assertIn(f"color: {t['ink2']}", rule)


class Busy(QtCase):
    def test_a_scan_fills_the_tables_with_progress_until_it_ends(self):
        self.window.show()
        self.window.analyze_action.trigger()
        self.assertTrue(self.window.busy_bar.isVisible())
        empty = self.window.folders.stack.widget(0)
        self.assertEqual(empty.title.text(), "Scanning C:\\")
        self.window.scanned = 4321
        self.window._tick()
        self.assertEqual(empty.text.text(), "4,321 files so far")
        self.finish()
        self.assertFalse(self.window.busy_bar.isVisible())
        self.assertEqual(self.window.folders.stack.currentIndex(), 1)

    def test_preview_and_find_show_what_they_are_doing(self):
        self.window.show()
        self.window.clean_page.trigger()
        self.window.preview_action.trigger()
        self.assertTrue(self.window.busy_bar.isVisible())
        self.assertEqual(
            self.window.preview_empty.title.text(), "Counting what Clean would remove"
        )
        self.finish()
        self.window.dup_page.trigger()
        self.window.find_action.trigger()
        self.assertEqual(self.window.groups.stack.widget(0).title.text(), "Looking for duplicates")
        self.finish()
        self.assertFalse(self.window.busy_bar.isVisible())

    def test_a_failed_scan_ends_the_progress_and_restores_the_empty_state(self):
        from diskcleaner_gui.qt_app.worker import Worker

        window = self.new_window(worker=Worker(), service=FakeService(error=ValueError("gone")))
        window.show()
        window.analyze_action.trigger()
        self.assertFalse(window.busy_bar.isVisible())
        self.assertEqual(window.folders.stack.widget(0).title.text(), "No scan yet")


class Resize(QtCase):
    def test_the_page_switch_stays_on_screen_in_a_narrow_window(self):
        # At 640 px the toolbar overflowed and Qt hid the whole page switch (user report)
        self.window.show()
        for width in (1400, 1100, 800):
            with self.subTest(width=width):
                self.window.resize(width, 480)
                self.app.processEvents()
                for action in (self.window.analyze_page, self.window.clean_page):
                    button = self.window.toolbar.widgetForAction(action) or next(
                        b for b in self.window.findChildren(QAbstractButton)
                        if getattr(b, "defaultAction", lambda: None)() is action
                    )
                    self.assertTrue(button.isVisible())
                self.assertTrue(self.window.theme_button.isVisible())
                overflow = self.window.toolbar.findChild(QAbstractButton, "qt_toolbar_ext_button")
                self.assertFalse(overflow is not None and overflow.isVisible())

    @unittest.skipIf(
        os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "offscreen fonts measure ~2x wide, so 640 px cannot be judged there",
    )
    def test_640_px_keeps_everything_on_screen_on_a_real_display(self):
        self.window.show()
        self.window.resize(640, 480)
        self.app.processEvents()
        self.assertEqual(self.window.width(), 640)
        self.assertTrue(self.window.seg.isVisible() and self.window.theme_button.isVisible())
        self.assertFalse(self.window._toolbar_overflows())

    def test_full_labels_show_when_there_is_room(self):
        # Offscreen Qt has no real fonts: its text measures about twice as wide as on
        # Windows (product name 229 vs 116 px, measured), so "room" here is 1400 px
        self.window.show()
        self.window.resize(1400, 720)
        self.app.processEvents()
        self.assertTrue(self.window.product.isVisible())
        button = self.window.seg.findChildren(QAbstractButton)[0]
        self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def test_cards_stack_in_a_narrow_window_and_sit_side_by_side_in_a_wide_one(self):
        self.window.show()
        self.window.resize(700, 600)
        self.app.processEvents()
        self.assertTrue(all(s.orientation() == Qt.Orientation.Vertical for s in self.window.splits))
        self.window.resize(1100, 720)
        self.app.processEvents()
        self.assertTrue(
            all(s.orientation() == Qt.Orientation.Horizontal for s in self.window.splits)
        )

    def test_a_narrow_window_can_shrink_to_640_once_the_cards_stack(self):
        self.window.show()
        self.window.resize(700, 600)
        self.app.processEvents()
        self.window._say("a status line far longer than any window is wide " * 10)
        self.assertLessEqual(self.window.minimumSizeHint().width(), 640)


class SharpIcons(QtCase):
    def test_box_glyphs_land_on_whole_pixels_at_125_percent(self):
        # Stop (square) and Clean (trash-2) smeared each 2 px line over 3 px at 20 px,
        # the 16 px icon at 125%: 68% and 64% of their inked pixels were partial (measured)
        from diskcleaner_gui.qt_app.icons import soft_share, svg_bytes

        for name in ("stop", "clean"):
            with self.subTest(name=name):
                self.assertLessEqual(soft_share(svg_bytes(name, "#000", pixels=20), 20), 0.35)

    def test_no_glyph_gets_softer_at_common_scales(self):
        from diskcleaner_gui.qt_app.icons import ICON_NAMES, plain_svg, soft_share, svg_bytes

        drawn = [*ICON_NAMES, "chevron-down", "chevron-right", "check", "sun", "moon", "monitor"]
        for name in drawn:
            for pixels in (16, 20, 24, 32):
                with self.subTest(name=name, pixels=pixels):
                    snapped = soft_share(svg_bytes(name, "#000", pixels=pixels), pixels)
                    plain = soft_share(plain_svg(name, "#000", pixels=pixels), pixels)
                    self.assertLessEqual(snapped, plain)

    def test_the_icon_engine_draws_on_device_pixels(self):
        # A logical origin like 10 px is 12.5 device px at 125%: snapping must start there
        from diskcleaner_gui.qt_app.icons import device_origin

        self.assertEqual(device_origin(10, 1.25), 10.4)
        self.assertEqual(device_origin(8, 1.0), 8)


class DisabledIcons(QtCase):
    def test_a_disabled_icon_is_dimmed_not_faded_out(self):
        # At 40% the disabled Stop icon was grey 114 on 27 in dark mode (measured on screen)
        # and read as fuzzy (user report); dimmed icons still need text-level contrast
        from PySide6.QtGui import QColor

        from diskcleaner_gui.qt_app.icons import DISABLED_OPACITY
        from diskcleaner_gui.qt_app.theme import THEMES, contrast

        for name, t in THEMES.items():
            ink, panel = QColor(t["ink"]), QColor(t["panel"])
            mixed = QColor(
                *(
                    round(DISABLED_OPACITY * a + (1 - DISABLED_OPACITY) * b)
                    for a, b in (
                        (ink.red(), panel.red()),
                        (ink.green(), panel.green()),
                        (ink.blue(), panel.blue()),
                    )
                )
            )
            with self.subTest(theme=name):
                self.assertGreaterEqual(contrast(mixed.name(), t["panel"]), 4.5)
                self.assertLess(DISABLED_OPACITY, 1)  # still visibly dimmed


class IconTextAlignment(QtCase):
    def test_icons_beside_labels_drop_to_the_letters_centre(self):
        # Qt centres a label's line box (room for descenders) but an icon's glyph, so the
        # letters sat ~1 device px below their icons at 125% (measured: Clean 83.5 vs 82)
        from PySide6.QtGui import QFont, QFontMetricsF

        from diskcleaner_gui.qt_app.icons import LABEL_FONT_PX, text_centre_drop

        font = QFont(self.app.font())
        font.setPixelSize(LABEL_FONT_PX)
        metrics = QFontMetricsF(font)
        drop = metrics.ascent() - metrics.capHeight() / 2 - metrics.height() / 2
        for ratio in (1.0, 1.25, 1.5, 2.0):
            with self.subTest(ratio=ratio):
                got = text_centre_drop(ratio)
                self.assertAlmostEqual(got * ratio, round(got * ratio))  # whole device pixels
                self.assertLessEqual(abs(got - drop), 0.5 / ratio + 1e-9)

    @unittest.skipIf(
        os.environ.get("QT_QPA_PLATFORM") == "offscreen", "needs the real fonts of a display"
    )
    def test_page_switch_icons_and_labels_share_a_centre_on_screen(self):
        self.window.set_theme("dark")
        self.window.resize(1400, 720)
        self.window.show()
        self.app.processEvents()
        button = next(
            b for b in self.window.seg.findChildren(QAbstractButton) if b.text() == "Clean"
        )
        image = button.grab().toImage()
        width, height = image.width(), image.height()

        def lum(x, y):
            c = image.pixelColor(x, y)
            return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()

        background = lum(2, height // 2)
        inked = [
            x
            for x in range(width)
            if any(abs(lum(x, y) - background) > 60 for y in range(height))
        ]
        split = next(b for a, b in zip(inked, inked[1:]) if b - a >= 3)

        def centre(x0, x1):
            rows = [
                y
                for y in range(height)
                if any(abs(lum(x, y) - background) > 60 for x in range(x0, x1))
            ]
            return (min(rows) + max(rows)) / 2

        self.assertLessEqual(abs(centre(inked[0], split) - centre(split, inked[-1] + 1)), 0.5)
