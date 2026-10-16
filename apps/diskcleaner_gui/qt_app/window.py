"""The main window: a toolbar shell with a target pill and a page switch, three pages of cards.

Every call to the service runs on the worker; the status line says what is running at once and
what came of it after. Clean deletes only after a preview of the same selection and a yes.
"""

import os
import threading
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..text import plural
from .icons import ICON_SIZE, app_icon, dot_pixmap, icon
from .theme import THEME_ICONS, THEME_MODES, apply_theme
from .widgets import (
    EmptyState,
    Pill,
    card,
    floating,
    gap,
    plain_label,
    segmented,
    shade,
    tool_button,
)
from .worker import Worker

APP_NAME = "Disk Cleaner"
ORG = "oh-my-disk-cleaner"
CHOOSE = "Choose folder..."
THEME_TIPS = {mode: f"Theme: {mode.title()} (click to change)" for mode in THEME_MODES}
HINTS = {"browser_history": "Browser history (signs you out of sites)"}
PAGE_OF = {"analysis": 0, "preview": 1, "clean": 1, "dups": 2}  # whose status line a job writes


def load_service():
    from .. import service

    return service


class MainWindow(QMainWindow):
    def __init__(self, worker=None, settings=None, service=None):
        super().__init__()
        self.worker = worker or Worker()
        self.service = service or load_service()
        self.settings = settings if settings is not None else QSettings(ORG, APP_NAME)
        mode = self.settings.value("theme", "system")
        self.theme_mode = mode if mode in THEME_MODES else "system"
        self.t = apply_theme(QApplication.instance(), self.theme_mode)
        self._icons, self.cards, self.bars, self.empties = [], [], [], []
        self.jobs, self.busy, self.previewed, self.notes = {}, None, None, {}
        self.cancel, self.scanned = threading.Event(), 0
        self.targets = self._targets()
        self.target = self.targets[0][1] if self.targets else str(Path.home())
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self._toolbar()
        self.status = plain_label("", "hint")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analyze_view, self.clean_view, self.dup_view = (
            self._analyze_page(),
            self._clean_page(),
            self._dup_page(),
        )
        self.pages = QStackedWidget()
        for page in (self.analyze_view, self.clean_view, self.dup_view):
            self.pages.addWidget(page)
        ground = QWidget()
        ground.setObjectName("ground")
        outer = QVBoxLayout(ground)
        outer.setContentsMargins(16, 8, 16, 8)
        outer.addWidget(self.pages, 1)
        outer.addWidget(self.status)
        self.setCentralWidget(ground)
        self.ticker = QTimer(self, interval=200, timeout=self._tick)
        self.worker.finished.connect(self._finished)
        self.worker.failed.connect(self._failed)
        for button in self.findChildren(QAbstractButton):  # a click leaves no focus ring
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        for keys, action in (
            ("Ctrl+1", self.analyze_page),
            ("Ctrl+2", self.clean_page),
            ("Ctrl+3", self.dup_page),
        ):
            QShortcut(QKeySequence(keys), self, activated=action.trigger)
        self._show_target()
        self._update_actions()
        self.resize(1100, 720)

    # ------------------------------------------------------------------ layout
    def _toolbar(self):
        bar = QToolBar("Main")
        bar.setObjectName("shell")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        bar.setIconSize(ICON_SIZE)
        self.addToolBar(bar)
        bar.addWidget(plain_label(APP_NAME, "product"))
        bar.addWidget(gap())
        self.pill = Pill()
        self.pill.clicked.connect(self._target_menu)
        bar.addWidget(self.pill)
        bar.addWidget(gap())
        group = QActionGroup(self)
        group.setExclusive(True)
        pages = (
            ("Analyze", "analyze", "Analyze\nThe largest folders and files under the target"),
            ("Clean", "cleanup", "Clean\nPreview and remove temporary files, caches and logs"),
            ("Duplicates", "dups", "Duplicates\nFiles with the same content under the target"),
        )
        actions = []
        for index, (text, name, tip) in enumerate(pages):
            action = self._iconed(QAction(text, self, checkable=True), name, on="accent_ink")
            action.setChecked(index == 0)
            action.setToolTip(tip)
            action.triggered.connect(lambda _=False, i=index: self._open_page(i))
            group.addAction(action)
            actions.append(action)
        self.analyze_page, self.clean_page, self.dup_page = actions
        bar.addWidget(segmented(actions))
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)
        self.theme_action = QAction("Theme", self)
        self.theme_action.triggered.connect(self.next_theme)
        bar.addAction(self.theme_action)
        self.theme_button = bar.widgetForAction(self.theme_action)
        self.theme_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.theme_button.setAccessibleName("Theme")
        self.toolbar = bar
        self._theme_look()

    def _pane(self, title, body, chip=None):
        pane = QWidget()
        column = QVBoxLayout(pane)
        column.setContentsMargins(10, 8, 10, 8)
        head = QHBoxLayout()
        head.addWidget(plain_label(title, "title"))
        if chip:
            head.addWidget(chip)
        head.addStretch(1)
        column.addLayout(head)
        column.addWidget(body, 1)
        holder = card(pane, self.t)
        self.cards.append(holder)
        return holder

    def _table(self, headers, empty_icon, empty_title, empty_text):
        """A read-only table behind an empty state; returns (stack, table)."""
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # a click leaves no focus ring on the cell
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        empty = EmptyState(self.t, empty_icon, empty_title, empty_text)
        self.empties.append(empty)
        stack = QStackedWidget()
        stack.addWidget(empty)
        stack.addWidget(table)
        table.stack = stack
        return stack, table

    def _split(self, *widgets):
        split = QSplitter()
        split.setHandleWidth(4)  # the cards' shadow room already spaces them
        split.setChildrenCollapsible(False)
        for widget in widgets:
            split.addWidget(widget)
        return split

    def _action_bar(self, *actions):
        box = QFrame()
        box.setObjectName("bar")
        box.setGraphicsEffect(QGraphicsDropShadowEffect(box))
        row = QHBoxLayout(box)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(4)
        for action in actions:
            row.addWidget(tool_button(action))
        holder = floating(box, self.t)
        self.bars.append(holder)
        return holder

    def _page(self, split, bar):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(split, 1)
        column.addWidget(bar, 0, Qt.AlignmentFlag.AlignHCenter)
        return page

    def _action(self, text, name, tip, slot):
        action = self._iconed(QAction(text, self), name)
        action.setToolTip(tip)
        action.triggered.connect(slot)
        return action

    def _analyze_page(self):
        folders, self.folders = self._table(
            ["Name", "Size", "Path"], "analyze", "No scan yet", "Analyze lists what takes space."
        )
        files, self.files = self._table(
            ["Name", "Size", "Path"], "analyze", "No scan yet", "Files over 10 MB show here."
        )
        self.analyze_action = self._action(
            "Analyze", "analyze", "Analyze\nScans the target; Stop keeps what it found", self.analyze
        )
        self.stop_action = self._action("Stop", "stop", "Stop\nEnds the scan early", self.stop)
        split = self._split(self._pane("Largest folders", folders), self._pane("Largest files", files))
        return self._page(split, self._action_bar(self.analyze_action, self.stop_action))

    def _clean_page(self):
        self.categories = QListWidget()
        self.categories.setIconSize(ICON_SIZE)
        for key, text in self.service.CATEGORIES.items():
            item = QListWidgetItem(HINTS.get(key, text))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ticked = key in self.service.DEFAULT_CATEGORIES
            item.setCheckState(Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked)
            self.categories.addItem(item)
        self.categories.itemChanged.connect(lambda _item: self._update_actions())
        preview, self.preview = self._table(
            ["Category", "Items", "Size", "Location"],
            "preview",
            "Nothing previewed",
            "Preview shows what Clean would remove. Nothing is deleted yet.",
        )
        self.total = plain_label("", "chip")
        self.total.hide()
        self.preview_action = self._action(
            "Preview", "preview", "Preview\nCounts what Clean would remove; deletes nothing", self.run_preview
        )
        self.clean_action = self._action(
            "Clean", "clean", "Clean\nDeletes what the preview listed, after you confirm", self.run_clean
        )
        split = self._split(
            self._pane("What to clean", self.categories), self._pane("Preview", preview, self.total)
        )
        return self._page(split, self._action_bar(self.preview_action, self.clean_action))

    def _dup_page(self):
        groups, self.groups = self._table(
            ["Size", "Copies", "Reclaimable", "First copy"],
            "dups",
            "No search yet",
            "Find lists files with the same content. Nothing is deleted.",
        )
        self.groups.itemSelectionChanged.connect(self._show_copies)
        self.copies = QListWidget()
        self.copies.setIconSize(ICON_SIZE)
        self.find_action = self._action(
            "Find", "find", "Find\nLooks for duplicate files under the target", self.find
        )
        split = self._split(self._pane("Duplicate groups", groups), self._pane("Copies", self.copies))
        return self._page(split, self._action_bar(self.find_action))

    def showEvent(self, event):
        # Qt applies the toolbar's QSS padding only on a later stylesheet change (template note)
        if not self.toolbar.styleSheet():
            self.toolbar.setStyleSheet(" ")
        super().showEvent(event)

    def closeEvent(self, event):
        self.cancel.set()  # a running scan stops within 1000 files, so quitting never hangs
        super().closeEvent(event)

    # ------------------------------------------------------------------ icons and theme
    def _iconed(self, action, name, key="ink", on="accent"):
        self._icons.append((action, name, key, on))
        action.setIcon(icon(name, self.t[key], self.t[on]))
        return action

    def set_theme(self, mode, save=True):
        self.theme_mode = mode if mode in THEME_MODES else "system"
        if save:
            self.settings.setValue("theme", self.theme_mode)
        self.t = apply_theme(QApplication.instance(), self.theme_mode)
        for action, name, key, on in self._icons:
            action.setIcon(icon(name, self.t[key], self.t[on]))
        for holder in self.cards + self.bars:
            shade(holder.frame, self.t)
        for empty in self.empties:
            empty.retheme(self.t)
        self._theme_look()
        self._show_target()

    def next_theme(self):
        index = (THEME_MODES.index(self.theme_mode) + 1) % len(THEME_MODES)
        self.set_theme(THEME_MODES[index])

    def _theme_look(self):
        self.theme_action.setIcon(icon(THEME_ICONS[self.theme_mode], self.t["ink2"]))
        self.theme_action.setToolTip(THEME_TIPS[self.theme_mode])

    # ------------------------------------------------------------------ target pill
    def _targets(self):
        """(label, path) for each drive, then Downloads when it exists."""
        size = self.service.format_size
        found = [(f"{d.path}  {size(d.free)} free", d.path) for d in self.service.drives()]
        downloads = Path.home() / "Downloads"
        if downloads.is_dir():
            found.append(("Downloads", str(downloads)))
        return found

    def _label(self, path):
        """A drive's label, or a chosen folder's own name (the full path is in the tooltip)."""
        return next((label for label, p in self.targets if p == path), Path(path).name or path)

    def _show_target(self):
        ratio = self.devicePixelRatioF()
        self.pill.glyph.setPixmap(icon("target", self.t["ink2"]).pixmap(QSize(16, 16), ratio))
        self.pill.dot.setPixmap(dot_pixmap(self.t["ok"], 8, ratio=ratio))
        self.pill.text.setText(self._label(self.target))
        self.pill.setProperty("menu", True)  # there is always Choose folder...
        self.pill.chevron.setPixmap(icon("chevron-down", self.t["ink2"]).pixmap(QSize(14, 14), ratio))
        self.pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pill.setToolTip(f"{self.target}\nTarget of Analyze and Duplicates; click to switch")
        self.pill.setAccessibleName(f"Target: {self._label(self.target)}")
        self.pill.style().unpolish(self.pill)
        self.pill.style().polish(self.pill)

    def _target_menu(self):
        menu = QMenu(self)
        for label, path in self.targets:
            action = menu.addAction(icon("target", self.t["ink2"]), label)
            action.triggered.connect(lambda _=False, p=path: self.switch_target(p))
        menu.addSeparator()
        menu.addAction(icon("folder", self.t["ink2"]), CHOOSE).triggered.connect(self.choose_folder)
        menu.exec(self.pill.mapToGlobal(self.pill.rect().bottomLeft()))

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", self.target)
        if folder:
            self.switch_target(os.path.normpath(folder))

    def switch_target(self, path):
        """Moves to another target in place: same window, results kept until the next run."""
        self.target = path
        self._show_target()

    # ------------------------------------------------------------------ work
    def _open_page(self, index):
        self.pages.setCurrentIndex(index)
        self._say(*self.notes.get(index, ("", "")), page=index)

    def _say(self, text, tone="", page=None):
        """Keeps the note for its page and shows it when that page is open."""
        page = self.pages.currentIndex() if page is None else page
        self.notes[page] = (text, tone)
        if page != self.pages.currentIndex():
            return
        self.status.setText(text)
        self.status.setProperty("tone", tone)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _submit(self, kind, call, pending):
        """Shows the pending line now, then queues the call; one job runs at a time."""
        job = self.worker.reserve()
        self.jobs[job], self.busy = kind, kind
        self._say(pending, page=PAGE_OF[kind])
        self._update_actions()
        return self.worker.submit(call, job)

    def _finished(self, job, result):
        kind = self.jobs.pop(job, None)
        if kind is None:
            return
        self.busy = None
        self.ticker.stop()
        getattr(self, f"_show_{kind}")(result)
        self._update_actions()

    def _failed(self, job, text):
        kind = self.jobs.pop(job, None)
        if kind is None:
            return
        self.busy = None
        self.ticker.stop()
        self._say(text.splitlines()[0][:160] if text else "Failed", "bad", PAGE_OF[kind])
        self._update_actions()

    def _update_actions(self):
        idle = self.busy is None
        for action in (self.analyze_action, self.preview_action, self.find_action):
            action.setEnabled(idle)
        self.stop_action.setEnabled(self.busy == "analysis")
        self.clean_action.setEnabled(
            idle
            and self.previewed is not None
            and self.previewed[0] == self.ticked()
            and self.previewed[1].total_items > 0
        )

    def _fill(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(value)))
        table.stack.setCurrentIndex(1 if rows else 0)

    # analyze
    def analyze(self):
        if self.busy:
            return None
        self.cancel.clear()
        self.scanned = 0
        target = self.target
        self.ticker.start()

        def call():
            return self.service.analyze(target, cancel=self.cancel, progress=self._progress)

        return self._submit("analysis", call, f"Scanning {target}")

    def _progress(self, count):
        self.scanned = count  # read by the ticker on the UI thread

    def _tick(self):
        if self.busy == "analysis":
            self._say(f"Scanning: {plural(self.scanned, 'file')}", page=0)

    def stop(self):
        self.cancel.set()

    def _show_analysis(self, result):
        size = self.service.format_size
        self._fill(self.folders, [(e.name, size(e.size), e.path) for e in result.folders])
        self._fill(self.files, [(e.name, size(e.size), e.path) for e in result.files])
        if result.stop_reason:
            self._say(f"Stopped: {result.stop_reason}; {plural(result.files_scanned, 'file')}", page=0)
        else:
            self._say(f"{plural(result.files_scanned, 'file')} in {result.seconds} s", page=0)

    # clean
    def ticked(self):
        return {
            self.categories.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.categories.count())
            if self.categories.item(i).checkState() == Qt.CheckState.Checked
        }

    def set_ticked(self, key, on):
        for i in range(self.categories.count()):
            item = self.categories.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def run_preview(self):
        if self.busy:
            return None
        chosen = self.ticked()
        self.previewed = None

        def call():
            return chosen, self.service.clean(sorted(chosen), dry_run=True)

        return self._submit("preview", call, "Counting what Clean would remove; this can take minutes")

    def _show_preview(self, result):
        chosen, report = result
        self.previewed = (chosen, report)
        size, names = self.service.format_size, self.service.CATEGORIES
        rows = [(names[r.category], f"{r.items:,}", size(r.size), r.path) for r in report.rows]
        self._fill(self.preview, rows)
        self.total.setText(f"{size(report.total_size)} in {report.total_items:,} items")
        self.total.setVisible(bool(rows))
        self._say(
            f"Clean would remove {plural(report.total_items, 'item')} ({size(report.total_size)})",
            page=1,
        )

    def confirm_box(self, text, details):
        """The one irreversible step: buttons say what they do, and keeping files is the default."""
        box = QMessageBox(QMessageBox.Icon.Warning, "Delete files", text, parent=self)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setInformativeText(details)
        box.delete_button = box.addButton("Delete files", QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton("Keep files", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep)
        box.setEscapeButton(keep)
        return box

    def confirm(self, text, details):
        box = self.confirm_box(text, details)
        box.exec()
        return box.clickedButton() is box.delete_button

    def _details(self, report):
        """One line per category: what goes, and what cannot be got back."""
        size, names, lines = self.service.format_size, self.service.CATEGORIES, []
        for category in dict.fromkeys(row.category for row in report.rows):
            rows = [row for row in report.rows if row.category == category]
            line = f"{names[category]}: {plural(sum(r.items for r in rows), 'item')}, "
            line += size(sum(r.size for r in rows))
            if category == "recycle":
                line += " (emptied for good)"
            lines.append(line)
        return "\n".join(lines)

    def run_clean(self):
        if not self.clean_action.isEnabled():
            return None
        chosen, report = self.previewed
        places = len(report.rows)
        text = (
            f"Delete {plural(report.total_items, 'item')} ({self.service.format_size(report.total_size)}) "
            f"from {plural(places, 'location')}? This cannot be undone."
        )
        if not self.confirm(text, self._details(report)):
            return None
        self.previewed = None

        def call():
            return self.service.clean(sorted(chosen), dry_run=False)

        return self._submit("clean", call, "Cleaning")

    def _show_clean(self, report):
        errors = report.error_count
        self._say(
            f"Freed {self.service.format_size(report.total_size)} from "
            f"{plural(report.total_items, 'item')}; {plural(errors, 'error')}",
            "bad" if errors else "ok",
            1,
        )

    # duplicates
    def find(self):
        if self.busy:
            return None
        target = self.target
        return self._submit("dups", lambda: self.service.duplicates(target), f"Looking for duplicates in {target}")

    def _show_dups(self, groups):
        size = self.service.format_size
        self.found = groups
        self._fill(
            self.groups,
            [(size(g.size), len(g.paths), size(g.reclaimable), g.paths[0]) for g in groups],
        )
        self.copies.clear()
        total = sum(g.reclaimable for g in groups)
        text = f"{plural(len(groups), 'group')}; {size(total)} reclaimable" if groups else "No duplicates"
        self._say(text, page=2)

    def _show_copies(self):
        self.copies.clear()
        rows = self.groups.selectionModel().selectedRows()
        if rows:
            self.copies.addItems(self.found[rows[0].row()].paths)
