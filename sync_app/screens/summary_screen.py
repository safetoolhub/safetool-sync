# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Summary screen — final results with retry, export, and snapshot options."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QPlainTextEdit,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from services.models import SyncReport
from sync_app.styles.design_system import DesignSystem
from utils.i18n import tr
from utils.format_utils import format_size, format_duration


class SummaryScreen(QWidget):
    """Final summary screen with retry errors, export, and snapshot options."""

    retry_requested = pyqtSignal()
    export_analysis_requested = pyqtSignal()
    export_log_requested = pyqtSignal()
    new_sync_requested = pyqtSignal()
    save_snapshot_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report: SyncReport | None = None
        self._dry_run_mode: bool = False

        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_16)
        layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)

        self._title = QLabel(tr("summary.title"))
        self._title.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold;")
        layout.addWidget(self._title)

        layout.addWidget(self._create_metrics())

        layout.addWidget(self._create_error_section())

        layout.addStretch()

        layout.addWidget(self._create_buttons())

    def _create_metrics(self) -> QWidget:
        metrics = QWidget()
        layout = QHBoxLayout(metrics)
        layout.setSpacing(DesignSystem.SPACE_8)

        self._metric_labels: dict[str, QLabel] = {}
        items = [
            ("copied", DesignSystem.COLOR_PRIMARY),
            ("overwritten", DesignSystem.COLOR_DIFF_MODIFIED),
            ("deleted", DesignSystem.COLOR_DANGER),
            ("trashed", DesignSystem.COLOR_WARNING),
            ("renamed", DesignSystem.COLOR_DIFF_RENAMED),
            ("skipped", DesignSystem.COLOR_TEXT_SECONDARY),
            ("verified", DesignSystem.COLOR_SUCCESS),
            ("verification_failures", DesignSystem.COLOR_DANGER),
        ]

        for key, color in items:
            card = QWidget()
            card.setStyleSheet(DesignSystem.get_metric_card_style())
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(DesignSystem.SPACE_8, DesignSystem.SPACE_8, DesignSystem.SPACE_8, DesignSystem.SPACE_8)

            value = QLabel("0")
            value.setStyleSheet(f"font-size: {DesignSystem.SIZE_LG}px; font-weight: bold; color: {color};")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(value)
            self._metric_labels[key] = value

            text = QLabel(tr(f"summary.{key}"))
            text.setStyleSheet(f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setWordWrap(True)
            card_layout.addWidget(text)

            layout.addWidget(card, stretch=1)

        return metrics

    def _create_error_section(self) -> QGroupBox:
        self._error_group = QGroupBox(tr("summary.errors_detail"))
        self._error_group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(self._error_group)

        self._error_count_label = QLabel(tr("summary.no_errors"))
        self._error_count_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px;")
        layout.addWidget(self._error_count_label)

        self._error_list = QPlainTextEdit()
        self._error_list.setReadOnly(True)
        self._error_list.setMaximumHeight(100)
        self._error_list.setVisible(False)
        self._error_list.setStyleSheet(
            f"background-color: {DesignSystem.COLOR_BACKGROUND}; "
            f"color: {DesignSystem.COLOR_DANGER}; "
            f"font-family: monospace; font-size: {DesignSystem.SIZE_XS}px; "
            f"border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT}; "
            f"border-radius: {DesignSystem.RADIUS_SM}px;"
        )
        layout.addWidget(self._error_list)

        return self._error_group

    def _create_buttons(self) -> QWidget:
        btn_row = QWidget()
        layout = QHBoxLayout(btn_row)
        layout.setSpacing(DesignSystem.SPACE_12)

        self._retry_btn = QPushButton(tr("summary.retry_errors"))
        self._retry_btn.setStyleSheet(DesignSystem.get_danger_button_style())
        self._retry_btn.setMinimumWidth(140)
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        self._retry_btn.setVisible(False)
        layout.addWidget(self._retry_btn)

        self._export_btn = QPushButton(tr("summary.save_analysis"))
        self._export_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._export_btn.setMinimumWidth(140)
        self._export_btn.clicked.connect(self.export_analysis_requested.emit)
        layout.addWidget(self._export_btn)

        self._export_log_btn = QPushButton(tr("summary.export_log"))
        self._export_log_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._export_log_btn.setMinimumWidth(140)
        self._export_log_btn.clicked.connect(self.export_log_requested.emit)
        layout.addWidget(self._export_log_btn)

        self._snapshot_btn = QPushButton(tr("summary.save_snapshot"))
        self._snapshot_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._snapshot_btn.setMinimumWidth(140)
        self._snapshot_btn.clicked.connect(self.save_snapshot_requested.emit)
        layout.addWidget(self._snapshot_btn)

        layout.addStretch()

        self._new_sync_btn = QPushButton(tr("summary.new_sync"))
        self._new_sync_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        self._new_sync_btn.setMinimumWidth(160)
        self._new_sync_btn.setMinimumHeight(44)
        self._new_sync_btn.clicked.connect(self.new_sync_requested.emit)
        layout.addWidget(self._new_sync_btn)

        return btn_row

    def set_report(self, report: SyncReport) -> None:
        self._report = report
        if self._dry_run_mode:
            self._title.setText(tr("summary.title_dry_run"))
        else:
            self._title.setText(tr("summary.title"))
        self._metric_labels["copied"].setText(str(report.copied))
        self._metric_labels["overwritten"].setText(str(report.overwritten))
        self._metric_labels["deleted"].setText(str(report.deleted))
        self._metric_labels["trashed"].setText(str(report.trashed))
        self._metric_labels["renamed"].setText(str(report.renamed))
        self._metric_labels["skipped"].setText(str(report.skipped))
        self._metric_labels["verified"].setText(str(report.verified))
        self._metric_labels["verification_failures"].setText(str(report.verification_failures))

        if report.errors:
            self._error_count_label.setText(f"{len(report.errors)} {tr('summary.errors').lower()}")
            self._error_list.setPlainText("\n".join(report.errors))
            self._error_list.setVisible(True)
            self._retry_btn.setVisible(True)
        else:
            self._error_count_label.setText(tr("summary.no_errors"))
            self._error_list.setVisible(False)
            self._retry_btn.setVisible(False)

    def set_dry_run_mode(self, enabled: bool) -> None:
        self._dry_run_mode = enabled