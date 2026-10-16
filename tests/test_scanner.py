"""DirectoryScanner walks a tree once per entry, however deep the tree is."""

import os
import sys

from diskcleaner.core.scanner import DirectoryScanner


def deep_tree(root, depth):
    folder = root
    for level in range(depth):
        folder = folder / f"d{level}"
        folder.mkdir()
        (folder / "f.txt").write_text("x", encoding="utf-8")
    return root


def scan(root):
    return list(DirectoryScanner(str(root), cache_enabled=False).scan_generator())


def test_every_entry_is_found_and_folders_come_before_their_contents(tmp_path):
    deep_tree(tmp_path, 3)
    found = scan(tmp_path)
    paths = [info.path for info in found]
    assert len(paths) == 6  # 3 folders, 3 files
    for info in found:
        if info.is_dir:
            inside = [p for p in paths if p.startswith(info.path + os.sep)]
            assert inside and all(paths.index(info.path) < paths.index(p) for p in inside)
    assert [info.depth for info in found if info.is_dir] == [0, 1, 2]


def test_deep_trees_cost_one_resume_per_entry(tmp_path):
    # A recursive generator re-yields each entry through every folder above it: the
    # 30 s profile of C:\ showed 19.1M resumes for 1.7M entries, half the scan time.
    depth = 40
    deep_tree(tmp_path, depth)
    resumes = 0

    def count(frame, event, arg):
        nonlocal resumes
        if event == "call" and frame.f_code.co_name == "_scan_directory_scandir":
            resumes += 1

    sys.setprofile(count)
    try:
        found = scan(tmp_path)
    finally:
        sys.setprofile(None)
    assert len(found) == 2 * depth
    assert resumes <= len(found) + 2
