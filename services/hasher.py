# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""SHA-256 file hasher with thread-pool support for SafeTool Sync."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from config import Config
from utils.platform_utils import win_long_path


def hash_file(path: Path, block_size: int = Config.HASH_BLOCK_SIZE) -> str:
    """Compute SHA-256 hash of a single file.

    Args:
        path: File path to hash.
        block_size: Read block size in bytes (default 64 KB).

    Returns:
        Hex digest string of SHA-256 hash.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read.
        OSError: On I/O errors.
    """
    sha = hashlib.sha256()
    with open(win_long_path(path), "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            sha.update(block)
    return sha.hexdigest()


def hash_files(
    paths: list[Path],
    progress_cb: Callable[[int, str], None] | None = None,
    max_workers: int | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Compute SHA-256 hashes for multiple files using a thread pool.

    Args:
        paths: List of file paths to hash.
        progress_cb: Optional callback(completed_count, file_path) for progress.
        max_workers: Maximum number of parallel workers. Defaults to Config optimal.
        cancel_check: Optional callable returning True to cancel.

    Returns:
        Dict mapping str(path) -> sha256_hex_digest.
        Files that failed to hash are omitted.
    """
    if max_workers is None:
        max_workers = Config.get_optimal_worker_threads()

    results: dict[str, str] = {}
    completed = 0
    total = len(paths)

    def _hash_one(path: Path) -> tuple[str, str | None]:
        try:
            digest = hash_file(path)
            return (str(path), digest)
        except (PermissionError, OSError, FileNotFoundError):
            return (str(path), None)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_hash_one, p): p for p in paths}

        for future in as_completed(futures):
            if cancel_check and cancel_check():
                executor.shutdown(wait=False, cancel_futures=True)
                break

            path_str, digest = future.result()
            completed += 1

            if digest is not None:
                results[path_str] = digest

            if progress_cb:
                progress_cb(completed, path_str)

    return results