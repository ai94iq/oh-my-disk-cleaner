"""What a bundle must prove without a display: the bundled scripts answer through the service."""

import os
import tempfile


def sample_tree(folder):
    """A small folder with large files and two copies, for checks and screenshots."""
    for name, size in (("videos", 24), ("photos", 12), ("notes", 1)):
        os.makedirs(os.path.join(folder, name), exist_ok=True)
        with open(os.path.join(folder, name, f"{name}.bin"), "wb") as out:
            out.write(b"x" * size * 1024 * 1024)
    for copy in ("a", "b"):
        with open(os.path.join(folder, "notes", f"copy-{copy}.txt"), "w", encoding="utf-8") as out:
            out.write("same text")
    return folder


def check_service():
    """A real scan, duplicate search and dry run on a sample folder; raises when one fails."""
    from . import service

    with tempfile.TemporaryDirectory() as folder:
        found = service.analyze(sample_tree(folder))
        groups = service.duplicates(folder)
    preview = service.clean([], dry_run=True)
    if not (found.folders and groups and preview.dry_run):
        raise RuntimeError("the service returned nothing for the sample folder")
    return "service: ok"
