# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Resume dialog — offers to resume an incomplete synchronization."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt

from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from utils.i18n import tr


class ResumeDialog(BaseDialog):
    """Dialog shown on startup when an incomplete sync state is detected."""

    def __init__(self, completed_ops: int, pending_ops: int, destination: str = "", parent=None) -> None:
        super().__init__(parent, title=tr("resume.title"), minimum_width=480, minimum_height=280)
        self._resume_clicked = False

        message = QLabel(tr("resume.message"))
        message.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
        message.setWordWrap(True)
        self._layout.addWidget(message)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(DesignSystem.SPACE_8)

        if completed_ops > 0:
            completed_label = QLabel(tr("resume.completed_ops", count=completed_ops))
            completed_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_BASE}px; color: {DesignSystem.COLOR_SUCCESS};")
            info_layout.addWidget(completed_label)

        pending_label = QLabel(tr("resume.pending_ops", count=pending_ops))
        pending_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_BASE}px; color: {DesignSystem.COLOR_WARNING};")
        info_layout.addWidget(pending_label)

        if destination:
            dest_label = QLabel(tr("resume.destination", dest=destination))
            dest_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
            dest_label.setWordWrap(True)
            info_layout.addWidget(dest_label)

        self._layout.addWidget(info_widget)
        self._layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        resume_btn = QPushButton(tr("resume.resume"))
        resume_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        resume_btn.setMinimumWidth(140)
        resume_btn.setMinimumHeight(40)
        resume_btn.clicked.connect(self._on_resume)
        btn_row.addWidget(resume_btn)

        discard_btn = QPushButton(tr("resume.discard"))
        discard_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        discard_btn.setMinimumWidth(140)
        discard_btn.setMinimumHeight(40)
        discard_btn.clicked.connect(self._on_discard)
        btn_row.addWidget(discard_btn)

        self._layout.addLayout(btn_row)

    def _on_resume(self) -> None:
        self._resume_clicked = True
        self.accept()

    def _on_discard(self) -> None:
        self._resume_clicked = False
        self.reject()

    @property
    def should_resume(self) -> bool:
        return self._resume_clicked