# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Empty folder scan worker — finds empty directories in a background QThread."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.empty_folder_finder import EmptyFolderScanResult, find_empty_folders


class EmptyFolderScanWorker(QThread):

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, root: Path, parent=None) -> None:
        super().__init__(parent)
        self._root = Path(root)
        self._cancelled = False

    def run(self) -> None:
        try:
            result = find_empty_folders(
                self._root,
                progress_cb=self._on_progress,
                cancel_check=lambda: self._cancelled,
            )
            if self._cancelled:
                return
            self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _on_progress(self, percent: int, message: str) -> None:
        if self._cancelled:
            return
        self.progress.emit(percent, message)

    def request_cancel(self) -> None:
        self._cancelled = True
