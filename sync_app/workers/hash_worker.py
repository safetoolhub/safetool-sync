# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Hash worker — computes SHA-256 hashes for files in a background QThread."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.hasher import hash_files


class HashWorker(QThread):
    """Background worker that computes SHA-256 hashes for a list of files."""

    progress = pyqtSignal(int, str)
    file_hashed = pyqtSignal(str, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        paths: list[Path],
        max_workers: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._max_workers = max_workers
        self._cancelled = False

    def run(self) -> None:
        try:
            self.progress.emit(0, "Starting hash computation...")

            result = hash_files(
                self._paths,
                progress_cb=self._on_progress,
                max_workers=self._max_workers,
                cancel_check=self._is_cancelled,
            )

            if self._cancelled:
                return

            self.progress.emit(100, "Hash computation complete")
            self.finished.emit(result)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _on_progress(self, completed: int, path_str: str) -> None:
        if self._cancelled:
            return
        total = len(self._paths)
        percent = int((completed / total) * 100) if total > 0 else 0
        self.progress.emit(percent, f"Hashing {completed}/{total}")
        self.file_hashed.emit(path_str, "")

    def _is_cancelled(self) -> bool:
        return self._cancelled

    def request_cancel(self) -> None:
        self._cancelled = True