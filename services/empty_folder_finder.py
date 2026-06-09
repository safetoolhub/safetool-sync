# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Empty folder finder — scans large directory trees for empty directories."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class EmptyFolderInfo:
    path: str
    rel_path: str
    depth: int
    parent: str


@dataclass
class EmptyFolderScanResult:
    empty_folders: list[EmptyFolderInfo] = field(default_factory=list)
    total_dirs_scanned: int = 0
    total_files_scanned: int = 0
    scan_time: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class EmptyFolderDeleteResult:
    removed: list[str] = field(default_factory=list)
    cascade_removed: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped_not_found: list[str] = field(default_factory=list)
    skipped_not_empty: list[str] = field(default_factory=list)
    total_freed_dirs: int = 0


def find_empty_folders(
    root: Path,
    progress_cb: Callable[[int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> EmptyFolderScanResult:
    root = Path(root).resolve()
    result = EmptyFolderScanResult()
    start_time = time.time()
    dirs_seen = 0
    files_seen = 0
    empty_set: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(str(root), topdown=False, onerror=_walk_error):
        if cancel_check and cancel_check():
            break

        dirpath_obj = Path(dirpath)
        if dirpath_obj == root:
            continue

        dirs_seen += 1

        filtered_dirs = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        real_files = [f for f in filenames if not os.path.islink(os.path.join(dirpath, f))]
        files_seen += len(real_files)

        if not real_files:
            all_subdirs_empty = all(
                os.path.join(dirpath, d) in empty_set for d in filtered_dirs
            )
            if all_subdirs_empty:
                abs_path = str(dirpath_obj)
                empty_set.add(abs_path)
                try:
                    rel = str(dirpath_obj.relative_to(root)).replace(os.sep, "/")
                except ValueError:
                    rel = abs_path
                depth = rel.count("/") + 1
                parent_rel = str(dirpath_obj.parent.relative_to(root)).replace(os.sep, "/") if dirpath_obj.parent != root else ""
                result.empty_folders.append(EmptyFolderInfo(
                    path=abs_path,
                    rel_path=rel,
                    depth=depth,
                    parent=parent_rel,
                ))

        if progress_cb and dirs_seen % 2000 == 0:
            progress_cb(-1, f"Scanned {dirs_seen} directories, {len(result.empty_folders)} empty...")

    result.empty_folders.sort(key=lambda e: e.rel_path.lower())
    result.total_dirs_scanned = dirs_seen
    result.total_files_scanned = files_seen
    result.scan_time = time.time() - start_time
    return result


def delete_empty_folders(
    paths: list[str],
    cascade: bool = True,
    stop_at: Path | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> EmptyFolderDeleteResult:
    result = EmptyFolderDeleteResult()
    sorted_paths = sorted(paths, key=lambda p: p.count(os.sep) + p.count("/"), reverse=True)
    removed_set: set[str] = set()
    stop_at_resolved = Path(stop_at).resolve() if stop_at else None

    for i, dir_path in enumerate(sorted_paths):
        if cancel_check and cancel_check():
            break

        try:
            p = Path(dir_path)
            if not p.exists():
                result.skipped_not_found.append(dir_path)
                logger.warning("Directory no longer exists, skipping: %s", dir_path)
                continue
            entries = list(p.iterdir())
            if entries:
                result.skipped_not_empty.append(dir_path)
                logger.warning("Directory is no longer empty, skipping: %s", dir_path)
                continue
            p.rmdir()
            result.removed.append(dir_path)
            removed_set.add(dir_path)
            logger.info("Removed empty directory: %s", dir_path)

            if cascade:
                parent = p.parent
                while parent.exists() and parent != p.anchor:
                    if stop_at_resolved and parent.resolve() == stop_at_resolved:
                        break
                    parent_entries = list(parent.iterdir())
                    if parent_entries:
                        break
                    parent.rmdir()
                    parent_str = str(parent)
                    result.cascade_removed.append(parent_str)
                    removed_set.add(parent_str)
                    logger.info("Cascade removed empty directory: %s", parent_str)
                    parent = parent.parent

        except OSError as e:
            result.failed.append((dir_path, str(e)))
            logger.debug("Cannot remove directory %s: %s", dir_path, e)

        if progress_cb and (i + 1) % 100 == 0:
            progress_cb(i + 1, dir_path)

    result.total_freed_dirs = len(result.removed) + len(result.cascade_removed)
    return result


def generate_delete_log(
    result: EmptyFolderDeleteResult,
    root: str,
) -> str:
    from datetime import datetime
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("SafeTool Sync - Empty Folder Cleanup Report")
    lines.append("=" * 70)
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Root: {root}")
    lines.append(f"Direct removals: {len(result.removed)}")
    lines.append(f"Cascade removals: {len(result.cascade_removed)}")
    lines.append(f"Failed: {len(result.failed)}")
    lines.append(f"Skipped (not found): {len(result.skipped_not_found)}")
    lines.append(f"Skipped (not empty): {len(result.skipped_not_empty)}")
    lines.append(f"Total directories removed: {result.total_freed_dirs}")
    lines.append("")

    if result.removed:
        lines.append("-" * 70)
        lines.append("DIRECTLY REMOVED DIRECTORIES:")
        lines.append("-" * 70)
        for p in sorted(result.removed):
            lines.append(f"  [REMOVED] {p}")
        lines.append("")

    if result.cascade_removed:
        lines.append("-" * 70)
        lines.append("CASCADE REMOVED (parent became empty):")
        lines.append("-" * 70)
        for p in sorted(result.cascade_removed):
            lines.append(f"  [CASCADE] {p}")
        lines.append("")

    if result.skipped_not_found:
        lines.append("-" * 70)
        lines.append("SKIPPED (no longer exists):")
        lines.append("-" * 70)
        for p in sorted(result.skipped_not_found):
            lines.append(f"  [NOT FOUND] {p}")
        lines.append("")

    if result.skipped_not_empty:
        lines.append("-" * 70)
        lines.append("SKIPPED (no longer empty):")
        lines.append("-" * 70)
        for p in sorted(result.skipped_not_empty):
            lines.append(f"  [NOT EMPTY] {p}")
        lines.append("")

    if result.failed:
        lines.append("-" * 70)
        lines.append("FAILED REMOVALS:")
        lines.append("-" * 70)
        for p, err in result.failed:
            lines.append(f"  [FAILED] {p} — {err}")
        lines.append("")

    lines.append("=" * 70)
    lines.append("End of report")
    lines.append("=" * 70)
    return "\n".join(lines)


def _walk_error(error: OSError) -> None:
    pass
