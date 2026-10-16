"""Human-readable sizes, shared by every report."""


def format_size(size_bytes: float) -> str:
    """Format a byte count: "512 B", "2.00 KB", "3.00 GB"."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            if unit == "B":
                return f"{int(size_bytes):,} {unit}"
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
