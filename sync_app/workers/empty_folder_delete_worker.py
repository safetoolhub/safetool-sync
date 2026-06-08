# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Empty folder delete worker — removes empty directories in a background QThread."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.empty_folder_finder import EmptyFolderDeleteResult, delete_empty_folders


class EmptyFolderDeleteWorker(QThread):

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, paths: list[str], cascade: bool = True, stop_at: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._paths = paths
        self._cascade = cascade
        self._stop_at = Path(stop_at) if stop_at else None
        self._cancelled = False

    def run(self) -> None:
        try:
            result = delete_empty_folders(
                self._paths,
                cascade=self._cascade,
                stop_at=self._stop_at,
                progress_cb=self._on_progress,
                cancel_check=lambda: self._cancelled,
            )
            if self._cancelled:
                return
            self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _on_progress(self, count: int, path: str) -> None:
        if self._cancelled:
            return
        self.progress.emit(count, path)

    def request_cancel(self) -> None:
        self._cancelled = True
