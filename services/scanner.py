# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Directory scanner — recursively scans a root path and returns FileEntry list."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from services.models import FileEntry, ScanResult


def scan_directory(
    root: Path,
    exclusions: list[str] | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> ScanResult:
    """Recursively scan a directory using os.scandir().

    Args:
        root: Root directory to scan.
        exclusions: Glob patterns to exclude (fnmatch style).
        progress_cb: Optional callback(percent, message) for progress updates.

    Returns:
        ScanResult with entries, counts, and any errors.
    """
    root = Path(root).resolve()
    entries: list[FileEntry] = []
    empty_dirs: list[str] = []
    total_files = 0
    total_dirs = 0
    total_size = 0
    errors: list[str] = []
    symlinks_found = 0

    exclusions = exclusions or []

    def _should_exclude(name: str, is_dir: bool) -> bool:
        from fnmatch import fnmatch
        for pattern in exclusions:
            if fnmatch(name, pattern):
                return True
            if is_dir and pattern in (".git", "node_modules", "__pycache__", ".venv", ".tox",
                                       ".Trash*", ".Trashes", "$RECYCLE.BIN"):
                if name == pattern.rstrip("*"):
                    return True
        return False

    try:
        scan_start = _now()
    except Exception:
        from time import time as _time_func
        scan_start = _time_func()

    for dirpath, dirnames, filenames in os.walk(str(root), onerror=_walk_error):
        dirpath_obj = Path(dirpath)
        rel_dir = dirpath_obj.relative_to(root)

        filtered_dirs = []
        for d in dirnames:
            if os.path.islink(os.path.join(dirpath, d)):
                symlinks_found += 1
                continue
            if _should_exclude(d, is_dir=True):
                continue
            filtered_dirs.append(d)
        dirnames[:] = filtered_dirs

        total_dirs += len(filtered_dirs)

        if not filtered_dirs and not filenames:
            raw = str(rel_dir) if str(rel_dir) != "." else ""
            if raw:
                rel_path = raw.replace(os.sep, "/")
                empty_dirs.append(rel_path)

        for fname in filenames:
            full_path = dirpath_obj / fname
            try:
                if os.path.islink(str(full_path)):
                    symlinks_found += 1
                    continue

                if _should_exclude(fname, is_dir=False):
                    continue

                stat = full_path.lstat()
                raw = str(rel_dir / fname) if str(rel_dir) != "." else fname
                rel_path = raw.replace(os.sep, "/")

                entry = FileEntry(
                    rel_path=rel_path,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    is_dir=False,
                    hash_sha256="",
                )
                entries.append(entry)
                total_files += 1
                total_size += stat.st_size

                if progress_cb and total_files % 500 == 0:
                    progress_cb(-1, f"Scanned {total_files} files...")

            except (PermissionError, OSError) as e:
                errors.append(f"Error reading {full_path}: {e}")
                continue

    try:
        from time import time as _t
        scan_time = _t() - scan_start
    except Exception:
        scan_time = 0.0

    if symlinks_found > 0:
        errors.append(f"Skipped {symlinks_found} symbolic links (not supported)")

    return ScanResult(
        entries=entries,
        total_files=total_files,
        total_dirs=total_dirs,
        total_size=total_size,
        scan_time=scan_time,
        errors=errors,
        empty_dirs=empty_dirs,
    )


def _walk_error(error: OSError) -> None:
    pass


def _now() -> float:
    from time import time
    return time()