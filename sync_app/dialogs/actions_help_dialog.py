# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Actions help dialog — explains all synchronization actions in detail in a premium table format."""
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

from services.models import SyncAction
from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr

_ACTION_STYLES: dict[SyncAction, tuple[str, str]] = {
    SyncAction.COPY_TO_DEST:     (DesignSystem.COLOR_DIFF_SOURCE_ONLY, "content-copy"),
    SyncAction.COPY_TO_SOURCE:   (DesignSystem.COLOR_PRIMARY,          "content-copy"),
    SyncAction.OVERWRITE_DEST:   (DesignSystem.COLOR_DIFF_MODIFIED,    "sync"),
    SyncAction.OVERWRITE_SOURCE: ("#E65100",                           "sync-alert"),
    SyncAction.DELETE_FROM_DEST: (DesignSystem.COLOR_DANGER,           "trash-can-outline"),
    SyncAction.MOVE_TO_TRASH:    (DesignSystem.COLOR_WARNING,          "trash-can-outline"),
    SyncAction.RENAME_IN_DEST:   (DesignSystem.COLOR_DIFF_RENAMED,     "rename-box"),
    SyncAction.KEEP_DEST:        (DesignSystem.COLOR_DIFF_IDENTICAL,   "check-circle-outline"),
    SyncAction.KEEP_SOURCE:      ("#2E7D32",                           "check-circle-outline"),
    SyncAction.SKIP:             (DesignSystem.COLOR_TEXT_SECONDARY,   "skip-forward"),
    SyncAction.MARK_REVIEW:      (DesignSystem.COLOR_DIFF_CONFLICT,    "alert-circle-outline"),
}

_ACTION_GROUPS: list[tuple[str, str, list[SyncAction]]] = [
    (
        "Copiar / Transferir",
        "arrow-right-bold-box-outline",
        [SyncAction.COPY_TO_DEST, SyncAction.COPY_TO_SOURCE],
    ),
    (
        "Sobrescribir",
        "sync",
        [SyncAction.OVERWRITE_DEST, SyncAction.OVERWRITE_SOURCE],
    ),
    (
        "Eliminar",
        "trash-can-outline",
        [SyncAction.DELETE_FROM_DEST, SyncAction.MOVE_TO_TRASH],
    ),
    (
        "Renombrar / Conservar",
        "pencil-box-outline",
        [SyncAction.RENAME_IN_DEST, SyncAction.KEEP_DEST, SyncAction.KEEP_SOURCE],
    ),
    (
        "Sin cambios",
        "minus-circle-outline",
        [SyncAction.SKIP, SyncAction.MARK_REVIEW],
    ),
]

_V_PAD = 20
_DESC_H_PAD = 28


class ActionsHelpDialog(BaseDialog):
    """Dialog showing a detailed, premium explanation of all sync actions in a table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            title=tr("actions_help.title"),
            minimum_width=780,
            minimum_height=620,
        )

        self._desc_rows: list[tuple[int, str]] = []
        self._header_rows: list[int] = []

        intro = QLabel(tr("actions_help.intro"))
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
            tr("review.action"),
            tr("common.details"),
        ])

        self._col0_width = 260
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().resizeSection(0, self._col0_width)
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

        total_rows = sum(1 + len(actions) for _, _, actions in _ACTION_GROUPS)
        self._table.setRowCount(total_rows)

        row = 0
        for group_label, group_icon, actions in _ACTION_GROUPS:
            self._table.setSpan(row, 0, 1, 2)
            self._header_rows.append(row)

            header_widget = QWidget()
            header_widget.setStyleSheet(
                f"background-color: {DesignSystem.COLOR_SURFACE}; "
                f"border-bottom: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};"
            )
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(
                DesignSystem.SPACE_12, DesignSystem.SPACE_6,
                DesignSystem.SPACE_12, DesignSystem.SPACE_6,
            )
            header_layout.setSpacing(8)

            grp_icon_label = QLabel()
            grp_icon = icon_manager.get_icon(group_icon, color=DesignSystem.COLOR_TEXT_SECONDARY)
            if grp_icon:
                grp_icon_label.setPixmap(grp_icon.pixmap(16, 16))
            grp_icon_label.setFixedSize(16, 16)
            header_layout.addWidget(grp_icon_label)

            lbl = QLabel(group_label)
            lbl.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_SM}px; font-weight: bold; "
                f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; "
                f"letter-spacing: 0.5px; background: transparent; border: none;"
            )
            header_layout.addWidget(lbl)
            header_layout.addStretch()
            self._table.setCellWidget(row, 0, header_widget)
            row += 1

            for action in actions:
                color, icon_name = _ACTION_STYLES.get(
                    action, (DesignSystem.COLOR_TEXT_SECONDARY, "help-circle-outline")
                )

                action_widget = QWidget()
                action_widget.setStyleSheet("background-color: transparent;")
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(16, 10, 12, 10)
                action_layout.setSpacing(10)
                action_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

                icon_label = QLabel()
                icon_label.setFixedSize(20, 20)
                icon = icon_manager.get_icon(icon_name, color=color)
                if icon:
                    icon_label.setPixmap(icon.pixmap(20, 20))
                action_layout.addWidget(icon_label)

                name_label = QLabel(tr(f"actions_help.{action.value}_name"))
                name_label.setStyleSheet(
                    f"font-weight: bold; color: {color}; "
                    f"font-size: {DesignSystem.SIZE_SM}px; "
                    f"background: transparent; border: none;"
                )
                name_label.setWordWrap(False)
                action_layout.addWidget(name_label, stretch=1)

                self._table.setCellWidget(row, 0, action_widget)

                desc_text = tr(f"actions_help.{action.value}_desc")
                self._desc_rows.append((row, desc_text))

                desc_widget = QWidget()
                desc_widget.setStyleSheet("background-color: transparent;")
                desc_layout = QVBoxLayout(desc_widget)
                desc_layout.setContentsMargins(14, 10, 14, 10)
                desc_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

                desc_label = QLabel(desc_text)
                desc_label.setWordWrap(True)
                desc_label.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
                )
                desc_label.setStyleSheet(
                    f"color: {DesignSystem.COLOR_TEXT}; "
                    f"font-size: {DesignSystem.SIZE_SM}px; "
                    f"background: transparent; border: none;"
                )
                desc_layout.addWidget(desc_label)

                self._table.setCellWidget(row, 1, desc_widget)
                row += 1

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
        line_h = fm.lineSpacing()

        viewport_w = self._table.viewport().width()
        col1_w = max(viewport_w - self._col0_width - 4, 200)
        usable_w = col1_w - _DESC_H_PAD

        for table_row, text in self._desc_rows:
            rect = fm.boundingRect(
                0, 0, usable_w, 0,
                Qt.TextFlag.TextWordWrap,
                text,
            )
            text_h = rect.height()
            row_h = max(text_h + _V_PAD, line_h * 2 + _V_PAD)
            self._table.setRowHeight(table_row, row_h)

        header_font = QFont()
        header_font.setPointSize(DesignSystem.SIZE_SM)
        header_font.setBold(True)
        hfm = QFontMetrics(header_font)
        header_h = max(hfm.lineSpacing() + 12, 32)
        for table_row in self._header_rows:
            self._table.setRowHeight(table_row, header_h)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._recalc_row_heights()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._recalc_row_heights()
