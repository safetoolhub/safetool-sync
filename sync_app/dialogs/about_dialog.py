# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""About dialog — app info, branding, privacy, and tutorial tabs."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from pathlib import Path

from config import Config
from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr


class AboutDialog(BaseDialog):
    """About dialog with app info, tutorial, and privacy tabs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, title=tr("about.title"), minimum_width=520, minimum_height=440)

        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(DesignSystem.get_tab_widget_style())

        tab_widget.addTab(self._create_about_tab(), tr("about.tab_about"))
        tab_widget.addTab(self._create_privacy_tab(), tr("about.tab_privacy"))

        self._layout.addWidget(tab_widget)

        close_btn = QPushButton(tr("common.close"))
        close_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        self._layout.addLayout(close_layout)

    def _create_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(DesignSystem.SPACE_16)

        icon_container = QWidget()
        icon_container.setFixedSize(64, 64)
        icon_container.setStyleSheet(DesignSystem.get_header_icon_container_style())
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon = QLabel()
        icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            app_icon.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_layout.addWidget(app_icon)
        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(Config.APP_NAME)
        name_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        version_label = QLabel(tr("about.version", version=Config.get_full_version()))
        version_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        brand_label = QLabel(tr("about.by"))
        brand_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_PRIMARY}; font-weight: bold; letter-spacing: 1px;")
        brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand_label)

        desc_label = QLabel(Config.APP_DESCRIPTION)
        desc_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_BASE}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        license_label = QLabel(tr("about.license"))
        license_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)

        website_btn = QPushButton(tr("about.website"))
        website_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        website_btn.clicked.connect(self._open_website)
        layout.addWidget(website_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return tab

    def _create_privacy_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(DesignSystem.SPACE_12)

        privacy_label = QLabel(tr("about.privacy"))
        privacy_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_LG}px; font-weight: bold; color: {DesignSystem.COLOR_SUCCESS};")
        privacy_label.setWordWrap(True)
        privacy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(privacy_label)

        details = QLabel(
            "SafeTool Sync processes all data locally on your device.\n\n"
            "- No data is sent to any server\n"
            "- No telemetry or analytics\n"
            "- No cloud synchronization\n"
            "- All file operations happen on your machine\n"
            "- Settings and logs are stored locally only"
        )
        details.setStyleSheet(f"font-size: {DesignSystem.SIZE_BASE}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        details.setWordWrap(True)
        layout.addWidget(details)

        layout.addStretch()
        return tab

    def _open_website(self) -> None:
        from utils.platform_utils import open_folder_in_explorer
        import webbrowser
        webbrowser.open(Config.APP_WEBSITE)