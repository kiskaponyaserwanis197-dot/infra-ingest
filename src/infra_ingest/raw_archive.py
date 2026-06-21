"""Archive immutable input copies for the local research library."""

import shutil
from pathlib import Path


def raw_root_for_library(db_path):
    """Return the raw archive directory next to the library database."""
    return Path(db_path).expanduser().parent / "raw"


def archive_source(input_path, file_hash, db_path):
    """Copy the processed input file into the immutable raw archive."""
    source_path = Path(input_path).expanduser().resolve()
    if not source_path.exists():
        return None

    raw_root = raw_root_for_library(db_path)
    raw_root.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix
    safe_name = sanitize_archive_name(source_path.stem)
    archive_path = raw_root / f"{file_hash[:16]}-{safe_name}{suffix}"
    if not archive_path.exists():
        shutil.copy2(source_path, archive_path)
    return str(archive_path)


def sanitize_archive_name(name):
    """Return a filesystem-safe archive stem."""
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name)
    return safe.strip("-")[:80] or "source"
