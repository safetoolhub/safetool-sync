# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Analysis screen — shows scan progress and rename detection."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.format_utils import format_size, format_file_count


class AnalysisScreen(QWidget):
    """Screen showing scan progress, metrics, and rename detection."""

    cancel_requested = pyqtSignal()
    analysis_complete = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_16)
        layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)

        title = QLabel(tr("analysis.title"))
        title.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};")
        layout.addWidget(title)

        layout.addStretch()

        self._source_label = QLabel(tr("analysis.scanning_source"))
        self._source_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        layout.addWidget(self._source_label)

        self._source_progress = QProgressBar()
        self._source_progress.setStyleSheet(DesignSystem.get_progressbar_style())
        self._source_progress.setRange(0, 0)
        self._source_progress.setValue(0)
        layout.addWidget(self._source_progress)

        self._dest_label = QLabel(tr("analysis.scanning_dest"))
        self._dest_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        layout.addWidget(self._dest_label)

        self._dest_progress = QProgressBar()
        self._dest_progress.setStyleSheet(DesignSystem.get_progressbar_style())
        self._dest_progress.setRange(0, 0)
        self._dest_progress.setValue(0)
        layout.addWidget(self._dest_progress)

        self._rename_label = QLabel("")
        self._rename_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_PRIMARY}; font-weight: bold;")
        self._rename_label.setVisible(False)
        layout.addWidget(self._rename_label)

        layout.addStretch()

        metrics = QWidget()
        metrics_layout = QHBoxLayout(metrics)
        metrics_layout.setSpacing(DesignSystem.SPACE_24)

        self._files_label = QLabel(tr("analysis.files_scanned", count=0))
        self._files_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
        metrics_layout.addWidget(self._files_label)

        self._size_label = QLabel(tr("analysis.size_scanned", size="0 B"))
        self._size_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
        metrics_layout.addWidget(self._size_label)

        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        metrics_layout.addWidget(self._speed_label)

        layout.addWidget(metrics)

        self._cancel_btn = QPushButton(tr("analysis.cancel"))
        self._cancel_btn.setStyleSheet(DesignSystem.get_danger_button_style())
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self._cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def set_source_progress(self, percent: int, message: str = "") -> None:
        if percent >= 100:
            self._source_progress.setRange(0, 100)
            self._source_progress.setValue(100)
        else:
            self._source_progress.setRange(0, 0)
        if message:
            self._source_label.setText(message)

    def set_dest_progress(self, percent: int, message: str = "") -> None:
        if percent >= 100:
            self._dest_progress.setRange(0, 100)
            self._dest_progress.setValue(100)
        else:
            self._dest_progress.setRange(0, 0)
        if message:
            self._dest_label.setText(message)

    def set_renames_detected(self, count: int) -> None:
        self._rename_label.setText(tr("analysis.renames_detected", count=count))
        self._rename_label.setVisible(count > 0)

    def set_metrics(self, file_count: int, total_size: int) -> None:
        self._files_label.setText(tr("analysis.files_scanned", count=format_file_count(file_count)))
        self._size_label.setText(tr("analysis.size_scanned", size=format_size(total_size)))

    def reset(self) -> None:
        self._source_progress.setRange(0, 0)
        self._source_progress.setValue(0)
        self._dest_progress.setRange(0, 0)
        self._dest_progress.setValue(0)
        self._source_label.setText(tr("analysis.scanning_source"))
        self._dest_label.setText(tr("analysis.scanning_dest"))
        self._rename_label.setVisible(False)
        self._files_label.setText(tr("analysis.files_scanned", count=0))
        self._size_label.setText(tr("analysis.size_scanned", size="0 B"))