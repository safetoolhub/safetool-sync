# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Sync worker — executes a sync plan in a background QThread."""
from __future__ import annotations

import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.executor import execute_plan
from services.models import SyncPlan, SyncReport
from services.sync_state_manager import SyncStateManager


class SyncWorker(QThread):
    """Background worker that executes a sync plan with per-file verification."""

    progress = pyqtSignal(int, str)
    file_completed = pyqtSignal(str, bool)
    file_verified = pyqtSignal(str, bool)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        plan: SyncPlan,
        source_root: Path,
        dest_root: Path,
        verify_mode: str = "FULL",
        use_trash: bool = True,
        cleanup_empty_dirs: bool = False,
        state_manager: SyncStateManager | None = None,
        dry_run: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._plan = plan
        self._source_root = Path(source_root)
        self._dest_root = Path(dest_root)
        self._verify_mode = verify_mode
        self._use_trash = use_trash
        self._cleanup_empty_dirs = cleanup_empty_dirs
        self._state_manager = state_manager
        self._dry_run = dry_run
        self._cancelled = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def run(self) -> None:
        try:
            if self._state_manager:
                self._state_manager.save_state(
                    str(self._source_root),
                    str(self._dest_root),
                    len(self._plan.entries),
                )

            report = execute_plan(
                plan=self._plan,
                source_root=self._source_root,
                dest_root=self._dest_root,
                verify_mode=self._verify_mode,
                use_trash=self._use_trash,
                cleanup_empty_dirs=self._cleanup_empty_dirs,
                progress_cb=self._on_progress,
                file_completed_cb=self._on_file_completed,
                file_verified_cb=self._on_file_verified,
                error_cb=self._on_error,
                cancel_check=self._is_cancelled,
                state_manager=self._state_manager,
                dry_run=self._dry_run,
            )

            if self._cancelled:
                return

            if self._state_manager:
                self._state_manager.mark_completed_state()

            self.finished.emit(report)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _on_progress(self, percent: int, message: str) -> None:
        if not self._cancelled:
            self.progress.emit(percent, message)

    def _on_file_completed(self, rel_path: str, success: bool) -> None:
        if not self._cancelled:
            self.file_completed.emit(rel_path, success)

    def _on_file_verified(self, rel_path: str, verified: bool) -> None:
        if not self._cancelled:
            self.file_verified.emit(rel_path, verified)

    def _on_error(self, error_msg: str) -> None:
        pass

    def _is_cancelled(self) -> bool:
        self._pause_event.wait()
        return self._cancelled

    def request_cancel(self) -> None:
        self._cancelled = True
        self._pause_event.set()

    def request_pause(self) -> None:
        self._pause_event.clear()

    def request_resume(self) -> None:
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()
