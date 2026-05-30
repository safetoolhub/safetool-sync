# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Compare worker — compares source and destination file lists in a background QThread."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.models import (
    CompareMode,
    ComparisonEntry,
    ConflictPolicy,
    DiskSnapshot,
    SyncAction,
    SyncDirection,
)
from services.comparator import compare, detect_renames


class CompareWorker(QThread):
    """Background worker that compares source and destination file lists."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        source: list,
        dest: list,
        mode: CompareMode = CompareMode.SMART,
        policy: ConflictPolicy = ConflictPolicy.SOURCE_WINS,
        dest_only_default: SyncAction = SyncAction.MOVE_TO_TRASH,
        detect_renames_enabled: bool = True,
        snapshot_hash_index: dict[str, list[str]] | None = None,
        direction: SyncDirection = SyncDirection.UNIDIRECTIONAL,
        conflict_action: SyncAction | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._dest = dest
        self._mode = mode
        self._policy = policy
        self._dest_only_default = dest_only_default
        self._detect_renames = detect_renames_enabled
        self._snapshot_hash_index = snapshot_hash_index
        self._direction = direction
        self._conflict_action = conflict_action
        self._cancelled = False

    def run(self) -> None:
        try:
            self.progress.emit(10, "Comparing files...")

            entries = compare(
                self._source,
                self._dest,
                mode=self._mode,
                policy=self._policy,
                dest_only_default=self._dest_only_default,
                direction=self._direction,
                conflict_action=self._conflict_action,
            )

            if self._cancelled:
                return

            self.progress.emit(60, "Comparison complete")

            if self._detect_renames:
                self.progress.emit(70, "Detecting renames...")
                entries = detect_renames(
                    entries,
                    snapshot_hash_index=self._snapshot_hash_index,
                )
                if self._cancelled:
                    return
                self.progress.emit(90, "Rename detection complete")

            self.progress.emit(100, "Done")
            self.finished.emit(entries)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def request_cancel(self) -> None:
        self._cancelled = True