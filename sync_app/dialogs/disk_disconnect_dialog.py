# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Disk disconnect dialog — shown when a disk is disconnected during sync."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt

from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr


class DiskDisconnectDialog(BaseDialog):
    """Dialog shown when a disk is disconnected during scan or sync."""

    def __init__(self, disk_path: str = "", parent=None) -> None:
        super().__init__(parent, title=tr("execution.disk_disconnected"), minimum_width=440, minimum_height=240)
        self._retry_clicked = False

        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, "alert-circle", color=DesignSystem.COLOR_WARNING, size=40)
        self._layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        message = QLabel(tr("execution.disk_disconnected_msg"))
        message.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(message)

        if disk_path:
            path_label = QLabel(f"📁 {disk_path}")
            path_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY}; font-family: monospace;")
            path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            path_label.setWordWrap(True)
            self._layout.addWidget(path_label)

        self._layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        retry_btn = QPushButton(tr("common.retry"))
        retry_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        retry_btn.setMinimumWidth(120)
        retry_btn.setMinimumHeight(36)
        retry_btn.clicked.connect(self._on_retry)
        btn_row.addWidget(retry_btn)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        cancel_btn.setMinimumWidth(120)
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._layout.addLayout(btn_row)

    def _on_retry(self) -> None:
        self._retry_clicked = True
        self.accept()

    @property
    def should_retry(self) -> bool:
        return self._retry_clicked