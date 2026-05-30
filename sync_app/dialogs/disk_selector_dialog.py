# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Disk selector dialog — allows selecting external/all drives."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from utils.i18n import tr
from utils.format_utils import format_size
from services.disk_detector import detect_external_drives, get_all_drives


class DiskSelectorDialog(BaseDialog):
    """Dialog for selecting a disk for source, dest, or snapshot."""

    # Emitted when a disk is selected. (mount_point, label)
    disk_selected = pyqtSignal(str, str)

    def __init__(self, purpose: str = "source", parent: QWidget | None = None) -> None:
        """
        :param purpose: "source", "dest", or "snapshot"
        """
        super().__init__(parent)
        self.setWindowTitle(tr("setup.detected_disks") if purpose != "snapshot" else tr("setup.save_disk_snapshot"))
        self.setMinimumSize(800, 600)

        self._purpose = purpose
        self._show_all_drives = False

        self._layout.setSpacing(DesignSystem.SPACE_16)
        self._layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)

        header_row = QHBoxLayout()
        self._drive_filter_btn = QPushButton(tr("setup.disk_external_only"))
        self._drive_filter_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._drive_filter_btn.setMaximumWidth(180)
        self._drive_filter_btn.clicked.connect(self._toggle_drive_filter)
        header_row.addWidget(self._drive_filter_btn)
        header_row.addStretch()

        refresh_btn = QPushButton(tr("common.refresh"))
        refresh_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        refresh_btn.setMaximumWidth(120)
        refresh_btn.clicked.connect(self._refresh_disks)
        header_row.addWidget(refresh_btn)
        self._layout.addLayout(header_row)

        self._disk_scroll_area = QScrollArea()
        self._disk_scroll_area.setWidgetResizable(True)
        self._disk_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._disk_scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

        self._disk_cards_container = QWidget()
        self._disk_cards_layout = QVBoxLayout(self._disk_cards_container)
        self._disk_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._disk_cards_layout.setSpacing(DesignSystem.SPACE_6)
        self._disk_cards_layout.addStretch()

        self._disk_scroll_area.setWidget(self._disk_cards_container)
        self._layout.addWidget(self._disk_scroll_area, stretch=1)

        self._refresh_disks()

    def _toggle_drive_filter(self) -> None:
        self._show_all_drives = not self._show_all_drives
        label = tr("setup.disk_all_drives") if not self._show_all_drives else tr("setup.disk_external_only")
        self._drive_filter_btn.setText(label)
        self._refresh_disks()

    def _refresh_disks(self) -> None:
        while self._disk_cards_layout.count() > 1:
            child = self._disk_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        drives = get_all_drives() if self._show_all_drives else detect_external_drives()
        
        if not drives:
            no_disks = QLabel(tr("setup.no_disks"))
            no_disks.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; padding: {DesignSystem.SPACE_8}px;")
            self._disk_cards_layout.insertWidget(0, no_disks)
            self._disk_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return

        for idx, drive in enumerate(drives):
            card = self._create_disk_card(drive)
            self._disk_cards_layout.insertWidget(idx, card)

        num_drives = len(drives)
        
        if num_drives <= 6:
            self._disk_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self._disk_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _create_disk_card(self, drive) -> QFrame:
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_disk_card_style())
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(DesignSystem.SPACE_10, DesignSystem.SPACE_8, DesignSystem.SPACE_10, DesignSystem.SPACE_8)
        card_layout.setSpacing(DesignSystem.SPACE_12)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        name_label = QLabel(f"{drive.label}")
        name_label.setStyleSheet(f"font-weight: bold; font-size: {DesignSystem.SIZE_BASE}px; border: none; padding: 0;")
        info_layout.addWidget(name_label)

        detail_text = f"{drive.mount_point}  —  {format_size(drive.free_bytes)} / {format_size(drive.total_bytes)}  ({drive.fstype})"
        detail_label = QLabel(detail_text)
        detail_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; padding: 0;")
        info_layout.addWidget(detail_label)
        card_layout.addLayout(info_layout, stretch=1)

        if self._purpose == "snapshot":
            btn = QPushButton(tr("setup.save_disk_snapshot"))
            btn.setToolTip(tr("setup.snapshot_saving"))
            btn.setStyleSheet(DesignSystem.get_disk_action_button_style("#FFF3E0"))
            btn.setFixedWidth(140)
        else:
            btn_text = tr("setup.use_as_dest") if self._purpose == "dest" else tr("setup.use_as_source")
            btn = QPushButton(btn_text)
            btn.setStyleSheet(DesignSystem.get_disk_action_button_style("#E8F5E9") if self._purpose == "dest" else DesignSystem.get_disk_action_button_style())
            btn.setFixedWidth(140)

        mount = drive.mount_point
        label = drive.label
        btn.clicked.connect(lambda _, m=mount, l=label: self._on_disk_selected(m, l))
        card_layout.addWidget(btn)

        return card

    def _on_disk_selected(self, mount_point: str, label: str) -> None:
        self.disk_selected.emit(mount_point, label)
        self.accept()
