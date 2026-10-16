"""The Toga app: native widgets, the same three pages and rules as the PySide6 app.

Service calls run on daemon threads, so quitting never waits on a preview that walks temp
folders for minutes. Clean deletes only after a preview of the same selection and a yes.
"""

import asyncio
import threading
from pathlib import Path

import toga
from toga.sources import AccessorColumn
from toga.style import Pack

from ..text import plural

APP_NAME = "Disk Cleaner"
APP_ID = "io.github.ai94iq.diskcleaner"
HINTS = {"browser_history": "Browser history (signs you out of sites)"}
TONES = {"": None, "ok": "#137538", "bad": "#b4232a"}  # the Qt theme's light ok and bad_text
COLUMN = Pack(direction="column", flex=1, margin=8)
ROW = Pack(direction="row", margin_bottom=8)


def _bar():
    """A spinner that takes no room until a job runs."""
    return toga.ProgressBar(max=None, style=Pack(margin_left=8, width=160, visibility="hidden"))


def load_service():
    from .. import service

    return service


class DiskCleanerApp(toga.App):
    def __init__(self, service=None, **kwargs):
        self.service = service or load_service()  # set first: the dummy backend starts up in init
        self.cancel, self.scanned, self.busy, self.previewed = threading.Event(), 0, None, None
        kwargs.setdefault("formal_name", APP_NAME)
        kwargs.setdefault("app_id", APP_ID)
        super().__init__(**kwargs)

    # ------------------------------------------------------------------ layout
    def startup(self):
        size = self.service.format_size
        self.targets = [(f"{d.path}  {size(d.free)} free", d.path) for d in self.service.drives()]
        downloads = Path.home() / "Downloads"
        if downloads.is_dir():
            self.targets.append(("Downloads", str(downloads)))
        self.target = toga.Selection(
            items=[label for label, _ in self.targets], style=Pack(width=240)
        )
        header = toga.Box(
            children=[
                toga.Label(
                    APP_NAME, style=Pack(font_weight="bold", font_size=14, margin_right=12)
                ),
                toga.Label("Target:", style=Pack(margin_right=4)),
                self.target,
                toga.Button(
                    "Choose folder...", on_press=self.choose_folder, style=Pack(margin_left=8)
                ),
            ],
            style=Pack(direction="row", margin=8),
        )
        pages = toga.OptionContainer(
            content=[
                ("Analyze", self._analyze_page()),
                ("Clean", self._clean_page()),
                ("Duplicates", self._dup_page()),
            ],
            style=Pack(flex=1),
        )
        self.main_window = toga.MainWindow(title=APP_NAME, size=(1100, 720))
        self.main_window.content = toga.Box(
            children=[header, pages], style=Pack(direction="column", flex=1)
        )
        self._update_buttons()
        self.main_window.show()

    def _table(self, headings, accessors, **kwargs):
        columns = [AccessorColumn(h, a) for h, a in zip(headings, accessors)]
        return toga.Table(columns=columns, style=Pack(flex=1), **kwargs)

    def _page(self, buttons, body, status):
        self_bar = toga.Box(children=buttons, style=ROW)
        return toga.Box(children=[self_bar, body, status], style=COLUMN)

    def _analyze_page(self):
        self.analyze_button = toga.Button("Analyze", on_press=self.analyze)
        self.stop_button = toga.Button("Stop", on_press=self.stop, style=Pack(margin_left=4))
        self.analyze_bar = _bar()
        self.folders = self._table(["Name", "Size", "Path"], ["name", "size", "path"])
        self.files = self._table(["Name", "Size", "Path"], ["name", "size", "path"])
        body = toga.Box(
            children=[
                self._titled("Largest folders", self.folders),
                self._titled("Largest files", self.files),
            ],
            style=Pack(direction="row", flex=1),
        )
        self.analyze_status = toga.Label(
            "Analyze lists the largest folders and files under the target."
        )
        buttons = [self.analyze_button, self.stop_button, self.analyze_bar]
        return self._page(buttons, body, self.analyze_status)

    def _clean_page(self):
        self.switches = {}
        column = []
        for key, text in self.service.CATEGORIES.items():
            switch = toga.Switch(
                HINTS.get(key, text),
                value=key in self.service.DEFAULT_CATEGORIES,
                on_change=lambda widget: self._update_buttons(),
                style=Pack(margin_bottom=6),
            )
            self.switches[key] = switch
            column.append(switch)
        title = toga.Label("What to clean", style=Pack(font_weight="bold", margin_bottom=8))
        choices = toga.Box(
            children=[title, *column], style=Pack(direction="column", margin_right=16)
        )
        self.preview_button = toga.Button("Preview", on_press=self.preview)
        self.clean_button = toga.Button("Clean", on_press=self.clean, style=Pack(margin_left=4))
        self.clean_bar = _bar()
        self.preview_table = self._table(
            ["Category", "Items", "Size", "Location"], ["category", "items", "size", "location"]
        )
        body = toga.Box(
            children=[
                choices,
                self._titled("Preview (nothing is deleted yet)", self.preview_table),
            ],
            style=Pack(direction="row", flex=1),
        )
        self.clean_status = toga.Label("Preview counts what Clean would remove.")
        buttons = [self.preview_button, self.clean_button, self.clean_bar]
        return self._page(buttons, body, self.clean_status)

    def _dup_page(self):
        self.find_button = toga.Button("Find", on_press=self.find)
        self.dup_bar = _bar()
        self.groups = self._table(
            ["Size", "Copies", "Reclaimable", "First copy"],
            ["size", "copies", "reclaimable", "first"],
            on_select=self._show_copies,
        )
        self.copies = self._table(["Copies of the selected group"], ["path"])
        body = toga.Box(
            children=[
                self._titled("Duplicate groups", self.groups),
                self._titled("Copies", self.copies),
            ],
            style=Pack(direction="row", flex=1),
        )
        self.dup_status = toga.Label("Find lists files with the same content. Nothing is deleted.")
        return self._page([self.find_button, self.dup_bar], body, self.dup_status)

    @staticmethod
    def _titled(title, widget):
        label = toga.Label(title, style=Pack(font_weight="bold", margin_bottom=4))
        style = Pack(direction="column", flex=1, margin_right=8)
        return toga.Box(children=[label, widget], style=style)

    # ------------------------------------------------------------------ helpers
    def target_path(self):
        return next((path for label, path in self.targets if label == self.target.value), None)

    async def choose_folder(self, widget):
        folder = await self.main_window.dialog(toga.SelectFolderDialog("Choose folder"))
        if folder:
            label = Path(folder).name or str(folder)
            self.targets.append((label, str(folder)))
            self.target.items = [label for label, _ in self.targets]
            self.target.value = label

    @staticmethod
    def say(label, text, tone=""):
        label.text = text
        if TONES[tone]:
            label.style.color = TONES[tone]
        else:
            del label.style.color

    def ticked(self):
        return {key for key, switch in self.switches.items() if switch.value}

    def _update_buttons(self):
        idle = self.busy is None
        for button in (self.analyze_button, self.preview_button, self.find_button):
            button.enabled = idle
        self.stop_button.enabled = self.busy == "analysis"
        self.clean_button.enabled = (
            idle
            and self.previewed is not None
            and self.previewed[0] == self.ticked()
            and self.previewed[1].total_items > 0
        )

    def _blocking(self, call):
        """Runs call() on a daemon thread; the returned future resolves on the app's loop."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def work():
            try:
                result = call()
            except Exception as err:  # shown as one line, never raised into the GUI
                loop.call_soon_threadsafe(future.set_exception, err)
            else:
                loop.call_soon_threadsafe(future.set_result, result)

        threading.Thread(target=work, daemon=True).start()
        return future

    async def _job(self, kind, call, label, bar, pending):
        """Shows the pending line now, runs the call, and returns its result or None on error."""
        self.busy = kind
        self._update_buttons()
        self.say(label, pending)
        bar.style.visibility = "visible"
        bar.start()
        try:
            future = self._blocking(call)
            while not future.done():
                if kind == "analysis":
                    self.say(label, f"Scanning: {plural(self.scanned, 'file')}")
                await asyncio.wait({future}, timeout=0.2)
            return future.result()
        except Exception as err:
            self.say(label, (str(err) or type(err).__name__).splitlines()[0][:160], "bad")
            return None
        finally:
            bar.stop()
            bar.style.visibility = "hidden"
            self.busy = None
            self._update_buttons()

    # ------------------------------------------------------------------ analyze
    async def analyze(self, widget):
        if self.busy:
            return
        self.cancel.clear()
        self.scanned = 0
        target = self.target_path()

        def progress(count):
            self.scanned = count

        result = await self._job(
            "analysis",
            lambda: self.service.analyze(target, cancel=self.cancel, progress=progress),
            self.analyze_status,
            self.analyze_bar,
            f"Scanning {target}",
        )
        if result is None:
            return
        size = self.service.format_size
        rows = lambda entries: [  # noqa: E731
            {"name": e.name, "size": size(e.size), "path": e.path} for e in entries
        ]
        self.folders.data = rows(result.folders)
        self.files.data = rows(result.files)
        count = plural(result.files_scanned, "file")
        if result.stop_reason:
            self.say(self.analyze_status, f"Stopped: {result.stop_reason}; {count}")
        else:
            self.say(self.analyze_status, f"{count} in {result.seconds} s")

    def stop(self, widget):
        self.cancel.set()

    def on_exit(self):
        self.cancel.set()  # the scan stops within 1000 files; other jobs are daemon threads
        return True

    # ------------------------------------------------------------------ clean
    async def preview(self, widget):
        if self.busy:
            return
        chosen = self.ticked()
        self.previewed = None
        report = await self._job(
            "preview",
            lambda: self.service.clean(sorted(chosen), dry_run=True),
            self.clean_status,
            self.clean_bar,
            "Counting what Clean would remove; this can take minutes",
        )
        if report is None:
            return
        self.previewed = (chosen, report)
        self._update_buttons()
        size, names = self.service.format_size, self.service.CATEGORIES
        self.preview_table.data = [
            {
                "category": names[r.category],
                "items": f"{r.items:,}",
                "size": size(r.size),
                "location": r.path,
            }
            for r in report.rows
        ]
        self.say(
            self.clean_status,
            f"Clean would remove {plural(report.total_items, 'item')} ({size(report.total_size)})",
        )

    async def clean(self, widget):
        if not self.clean_button.enabled:
            return
        chosen, report = self.previewed
        size = self.service.format_size
        text = (
            f"Delete {plural(report.total_items, 'item')} ({size(report.total_size)}) "
            f"from {plural(len(report.rows), 'location')}? This cannot be undone."
        )
        if not await self.main_window.dialog(toga.ConfirmDialog("Delete files", text)):
            return
        self.previewed = None
        report = await self._job(
            "clean",
            lambda: self.service.clean(sorted(chosen), dry_run=False),
            self.clean_status,
            self.clean_bar,
            "Cleaning",
        )
        if report is None:
            return
        errors = report.error_count
        self.say(
            self.clean_status,
            f"Freed {size(report.total_size)} from {plural(report.total_items, 'item')}; "
            f"{plural(errors, 'error')}",
            "bad" if errors else "ok",
        )

    # ------------------------------------------------------------------ duplicates
    async def find(self, widget):
        if self.busy:
            return
        target = self.target_path()
        groups = await self._job(
            "dups",
            lambda: self.service.duplicates(target),
            self.dup_status,
            self.dup_bar,
            f"Looking for duplicates in {target}",
        )
        if groups is None:
            return
        size = self.service.format_size
        self.found = groups
        self.groups.data = [
            {"size": size(g.size), "copies": len(g.paths), "reclaimable": size(g.reclaimable),
             "first": g.paths[0], "paths": g.paths}
            for g in groups
        ]
        self.copies.data = []
        total = sum(g.reclaimable for g in groups)
        text = "No duplicates"
        if groups:
            text = f"{plural(len(groups), 'group')}; {size(total)} reclaimable"
        self.say(self.dup_status, text)

    def _show_copies(self, widget):
        row = widget.selection
        self.copies.data = [{"path": path} for path in row.paths] if row is not None else []
