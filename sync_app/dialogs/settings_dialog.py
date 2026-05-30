# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Settings dialog — user preferences."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QSize

from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.platform_utils import open_folder_in_explorer
from utils.settings_manager import SettingsManager
from config import Config


class SettingsDialog(BaseDialog):
    """Settings dialog with General and Advanced sections."""

    def __init__(self, settings: SettingsManager, parent=None) -> None:
        self._settings = settings
        super().__init__(parent, title=tr("settings.title"), minimum_width=720, minimum_height=680)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(DesignSystem.SPACE_16)

        container_layout.addWidget(self._create_general_section())
        container_layout.addWidget(self._create_locations_section())
        container_layout.addWidget(self._create_advanced_section())
        container_layout.addStretch()

        scroll.setWidget(container)
        self._layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton(tr("common.save"))
        save_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        cancel_btn.setMinimumWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._layout.addLayout(btn_row)

    def _create_general_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.general"))
        group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(DesignSystem.SPACE_12)

        lang_row = QHBoxLayout()
        lang_label = QLabel(tr("settings.language"))
        lang_label.setMinimumWidth(160)
        lang_row.addWidget(lang_label)
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Español", "English"])
        current_lang = self._settings.get_language()
        self._lang_combo.setCurrentIndex(0 if current_lang == "es" else 1)
        self._lang_combo.setStyleSheet(DesignSystem.get_combobox_style())
        lang_row.addWidget(self._lang_combo, stretch=1)
        layout.addLayout(lang_row)

        lang_note = QLabel(tr("settings.language_restart"))
        lang_note.setStyleSheet(f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        lang_note.setWordWrap(True)
        layout.addWidget(lang_note)

        self._remember_paths_checkbox = QCheckBox(tr("settings.remember_last_paths"))
        self._remember_paths_checkbox.setChecked(self._settings.get_remember_last_paths())
        self._remember_paths_checkbox.setStyleSheet(DesignSystem.get_checkbox_style())
        layout.addWidget(self._remember_paths_checkbox)

        hist_row = QHBoxLayout()
        hist_label = QLabel(tr("settings.path_history"))
        hist_label.setMinimumWidth(160)
        hist_row.addWidget(hist_label)

        self._clear_hist_btn = QPushButton(tr("settings.clear_history"))
        self._clear_hist_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {DesignSystem.COLOR_PRIMARY};
                border: none;
                font-size: {DesignSystem.SIZE_SM}px;
                text-decoration: underline;
                padding: 0;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {DesignSystem.COLOR_PRIMARY_HOVER};
            }}
        """)
        self._clear_hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_hist_btn.clicked.connect(self._clear_path_history)

        hist_row.addWidget(self._clear_hist_btn)
        hist_row.addStretch()
        layout.addLayout(hist_row)

        return group

    def _clear_path_history(self) -> None:
        self._settings.clear_path_history()
        self._clear_hist_btn.setEnabled(False)
        QMessageBox.information(
            self,
            tr("common.info", default="Info"),
            tr("settings.history_cleared")
        )

    def _create_locations_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.locations"))
        group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(DesignSystem.SPACE_12)

        self._logs_edit = self._add_location_row(
            layout,
            tr("settings.logs_dir"),
            self._settings.get_logs_dir(),
            self._change_logs_dir,
        )

        logs_note = QLabel(tr("settings.logs_dir_restart"))
        logs_note.setStyleSheet(f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        logs_note.setWordWrap(True)
        layout.addWidget(logs_note)

        self._snapshots_edit = self._add_location_row(
            layout,
            tr("settings.snapshots_dir"),
            self._settings.get_snapshots_dir(),
            self._change_snapshots_dir,
        )

        snapshots_note = QLabel(tr("settings.snapshots_dir_restart"))
        snapshots_note.setStyleSheet(f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        snapshots_note.setWordWrap(True)
        layout.addWidget(snapshots_note)

        return group

    def _add_location_row(self, layout, label_text, current_path, on_change) -> QLineEdit:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(160)
        row.addWidget(label)

        path_edit = QLineEdit(str(current_path))
        path_edit.setReadOnly(True)
        path_edit.setCursorPosition(0)
        row.addWidget(path_edit, stretch=1)

        open_btn = QToolButton()
        open_btn.setStyleSheet(DesignSystem.get_icon_button_style())
        icon_manager.set_button_icon(open_btn, "folder-open", color=DesignSystem.COLOR_PRIMARY)
        open_btn.setIconSize(QSize(18, 18))
        open_btn.setToolTip(tr("settings.open_folder"))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: open_folder_in_explorer(path_edit.text()))
        row.addWidget(open_btn)

        change_btn = QToolButton()
        change_btn.setStyleSheet(DesignSystem.get_icon_button_style())
        icon_manager.set_button_icon(change_btn, "pencil-box-outline", color=DesignSystem.COLOR_PRIMARY)
        change_btn.setIconSize(QSize(18, 18))
        change_btn.setToolTip(tr("settings.change_folder"))
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.clicked.connect(on_change)
        row.addWidget(change_btn)

        layout.addLayout(row)
        return path_edit

    def _change_logs_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("settings.select_logs_dir"), self._logs_edit.text()
        )
        if path:
            self._logs_edit.setText(path)
            self._logs_edit.setCursorPosition(0)

    def _change_snapshots_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("settings.select_snapshots_dir"), self._snapshots_edit.text()
        )
        if path:
            self._snapshots_edit.setText(path)
            self._snapshots_edit.setCursorPosition(0)

    def _create_advanced_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.advanced"))
        group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(group)

        log_row = QHBoxLayout()
        log_label = QLabel(tr("settings.log_level"))
        log_label.setMinimumWidth(160)
        log_row.addWidget(log_label)
        self._log_combo = QComboBox()
        self._log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_level = self._settings.get_log_level()
        self._log_combo.setCurrentIndex({"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}.get(log_level, 0))
        self._log_combo.setStyleSheet(DesignSystem.get_combobox_style())
        log_row.addWidget(self._log_combo, stretch=1)
        layout.addLayout(log_row)

        return group

    def _save_and_close(self) -> None:
        self._settings.set_language("es" if self._lang_combo.currentIndex() == 0 else "en")
        self._settings.set_remember_last_paths(self._remember_paths_checkbox.isChecked())
        self._settings.set_log_level(self._log_combo.currentText())

        old_logs_dir = str(self._settings.get_logs_dir())
        old_snapshots_dir = str(self._settings.get_snapshots_dir())
        new_logs_dir = self._logs_edit.text().strip()
        new_snapshots_dir = self._snapshots_edit.text().strip()

        logs_changed = bool(new_logs_dir) and new_logs_dir != old_logs_dir
        snapshots_changed = bool(new_snapshots_dir) and new_snapshots_dir != old_snapshots_dir

        if new_logs_dir:
            self._settings.set_logs_dir(new_logs_dir)
        if new_snapshots_dir:
            self._settings.set_snapshots_dir(new_snapshots_dir)
            Config.SNAPSHOTS_DIR = Path(new_snapshots_dir)

        self._settings.sync()

        if logs_changed or snapshots_changed:
            QMessageBox.information(
                self,
                tr("common.info", default="Info"),
                tr("settings.dir_change_restart"),
            )

        self.accept()
