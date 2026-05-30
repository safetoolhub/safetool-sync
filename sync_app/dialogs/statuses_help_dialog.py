# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Statuses help dialog — explains all possible file diff statuses in a table format."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics, QFont

from services.models import DiffType
from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr

_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "identical":       (DesignSystem.COLOR_DIFF_IDENTICAL,   "check-circle-outline"),
    "source_only":     (DesignSystem.COLOR_DIFF_SOURCE_ONLY, "plus-circle-outline"),
    "dest_only":       (DesignSystem.COLOR_DIFF_DEST_ONLY,   "minus-circle-outline"),
    "modified":        (DesignSystem.COLOR_DIFF_MODIFIED,    "pencil-circle-outline"),
    "conflict_pending":(DesignSystem.COLOR_DIFF_CONFLICT,    "alert-circle-outline"),
    "conflict_auto":   (DesignSystem.COLOR_SUCCESS,          "check-decagram-outline"),
    "renamed":         (DesignSystem.COLOR_DIFF_RENAMED,     "rename-box"),
    "error_source":    (DesignSystem.COLOR_DIFF_ERROR,       "alert-octagon-outline"),
    "error_dest":      (DesignSystem.COLOR_DIFF_ERROR,       "alert-octagon-outline"),
}

_V_PAD = 20
_DESC_H_PAD = 28
_COL0_WIDTH = 260


class StatusesHelpDialog(BaseDialog):
    """Dialog showing a detailed explanation of all file diff statuses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            title=tr("diff_types_help.title"),
            minimum_width=780,
            minimum_height=560,
        )

        self._desc_rows: list[tuple[int, str]] = []

        intro = QLabel(tr("diff_types_help.intro"))
        intro.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; "
            f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; "
            f"margin-bottom: {DesignSystem.SPACE_8}px;"
        )
        intro.setWordWrap(True)
        self._layout.addWidget(intro)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels([
            tr("review.status"),
            tr("common.details"),
        ])

        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().resizeSection(0, _COL0_WIDTH)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(DesignSystem.get_table_style())
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        status_keys = list(_STATUS_STYLES.keys())
        self._table.setRowCount(len(status_keys))

        for row, key in enumerate(status_keys):
            color, icon_name = _STATUS_STYLES[key]

            name_widget = QWidget()
            name_widget.setStyleSheet("background-color: transparent;")
            name_layout = QHBoxLayout(name_widget)
            name_layout.setContentsMargins(16, 10, 12, 10)
            name_layout.setSpacing(10)
            name_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            icon_label = QLabel()
            icon_label.setFixedSize(20, 20)
            icon = icon_manager.get_icon(icon_name, color=color)
            if icon:
                icon_label.setPixmap(icon.pixmap(20, 20))
            name_layout.addWidget(icon_label)

            badge = QLabel(tr(f"diff_types_help.{key}_name"))
            badge.setStyleSheet(
                f"background-color: {color}; color: white; "
                f"border-radius: {DesignSystem.RADIUS_SM}px; "
                f"padding: 3px 10px; font-weight: bold; "
                f"font-size: {DesignSystem.SIZE_XS}px;"
            )
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_layout.addWidget(badge)
            name_layout.addStretch()

            self._table.setCellWidget(row, 0, name_widget)

            desc_text = tr(f"diff_types_help.{key}_desc")
            self._desc_rows.append((row, desc_text))

            desc_widget = QWidget()
            desc_widget.setStyleSheet("background-color: transparent;")
            desc_layout = QVBoxLayout(desc_widget)
            desc_layout.setContentsMargins(14, 10, 14, 10)
            desc_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            desc_label.setStyleSheet(
                f"color: {DesignSystem.COLOR_TEXT}; "
                f"font-size: {DesignSystem.SIZE_SM}px; "
                f"background: transparent; border: none;"
            )
            desc_layout.addWidget(desc_label)

            self._table.setCellWidget(row, 1, desc_widget)

        self._layout.addWidget(self._table, stretch=1)

        close_btn = QPushButton(tr("common.close"))
        close_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        close_btn.setMinimumWidth(120)
        close_btn.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        self._layout.addLayout(btn_layout)

    def _recalc_row_heights(self) -> None:
        desc_font = QFont()
        desc_font.setPointSize(DesignSystem.SIZE_SM)
        fm = QFontMetrics(desc_font)

        viewport_w = self._table.viewport().width()
        col1_w = max(viewport_w - _COL0_WIDTH - 4, 200)
        usable_w = col1_w - _DESC_H_PAD

        for table_row, text in self._desc_rows:
            rect = fm.boundingRect(
                0, 0, usable_w, 0,
                Qt.TextFlag.TextWordWrap,
                text,
            )
            text_h = rect.height()
            row_h = max(text_h + _V_PAD, fm.lineSpacing() * 2 + _V_PAD)
            self._table.setRowHeight(table_row, row_h)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._recalc_row_heights()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._recalc_row_heights()
