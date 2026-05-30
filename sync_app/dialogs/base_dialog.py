# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Base dialog — shared base for all SafeTool Sync dialogs."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from sync_app.styles.design_system import DesignSystem


class BaseDialog(QDialog):
    """Base dialog with stylesheet and tooltip palette fix (SKILL §8)."""

    def __init__(self, parent=None, title: str = "", minimum_width: int = 480, minimum_height: int = 300) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(minimum_width, minimum_height)
        self.setModal(True)

        self.setStyleSheet(DesignSystem.get_stylesheet())
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#000000"))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
        self.setPalette(pal)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(DesignSystem.SPACE_12)
        self._layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)