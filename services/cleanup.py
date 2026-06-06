# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Cleanup — removes empty directories after sync operations."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def cleanup_empty_dirs(
    root: Path,
    progress_cb: Callable[[int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[str]:
    """Remove all empty directories under root, bottom-up.

    Walks the directory tree from deepest to shallowest, removing
    any directory that becomes empty after file deletions.

    Args:
        root: Root directory to clean up (not removed itself).
        progress_cb: Optional callback(count, path).
        cancel_check: Callable returning True to cancel.

    Returns:
        List of removed directory paths.
    """
    root = Path(root).resolve()
    removed: list[str] = []

    for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
        if cancel_check and cancel_check():
            break

        dirpath_obj = Path(dirpath)
        if dirpath_obj == root:
            continue

        try:
            entries = list(dirpath_obj.iterdir())
            if not entries:
                dirpath_obj.rmdir()
                removed.append(str(dirpath_obj))
                logger.info("Removed empty directory: %s", dirpath_obj)
                if progress_cb:
                    progress_cb(len(removed), str(dirpath_obj))
        except OSError as e:
            logger.debug("Cannot remove directory %s: %s", dirpath_obj, e)

    return removed
