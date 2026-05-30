# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Scan worker — scans directories in a background QThread."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.models import ExclusionPreset, ScanResult
from services.scanner import scan_directory


class ScanWorker(QThread):
    """Background worker that scans a directory tree."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        root: Path,
        exclusions: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._root = Path(root)
        self._exclusions = exclusions or []
        self._cancelled = False

    def run(self) -> None:
        try:
            result = scan_directory(
                self._root,
                exclusions=self._exclusions,
                progress_cb=self._on_progress,
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
        if percent < 0:
            percent = 0
        self.progress.emit(percent, message)

    def request_cancel(self) -> None:
        self._cancelled = True