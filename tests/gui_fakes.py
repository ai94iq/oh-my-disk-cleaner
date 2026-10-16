"""A stand-in for diskcleaner_gui.service, shared by the Qt and Toga app tests."""

from diskcleaner_gui import service as real


class FakeService:
    """The service's names with canned results; records every call."""

    CATEGORIES = real.CATEGORIES
    DEFAULT_CATEGORIES = real.DEFAULT_CATEGORIES

    def __init__(self, items=3, error=None):
        self.calls, self.items, self.error = [], items, error

    @staticmethod
    def format_size(size):
        return f"{size} B"

    def drives(self):
        return [real.Drive("C:\\", 1000, 600, 400), real.Drive("D:\\", 2000, 500, 1500)]

    def analyze(self, path, cancel=None, progress=None):
        self.calls.append(("analyze", path))
        if self.error:
            raise self.error
        return real.Analysis(
            [real.Entry("big", "C:\\big", 900), real.Entry("small", "C:\\small", 10)],
            [real.Entry("f.bin", "C:\\big\\f.bin", 800)],
            1234,
            1.5,
            "",
        )

    def clean(self, categories, dry_run):
        self.calls.append(("clean", tuple(categories), dry_run))
        rows = [real.CleanRow("temp", "C:\\Temp", self.items, 100 * self.items, [])]
        return real.CleanReport(dry_run, rows if self.items else [])

    def duplicates(self, path):
        self.calls.append(("duplicates", path))
        return [real.DupGroup(50, ["C:\\a\\x.txt", "C:\\b\\x.txt", "C:\\c\\x.txt"])]
