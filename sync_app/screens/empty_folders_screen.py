# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Empty folders screen — find and remove empty directories."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import tr
from services.empty_folder_finder import (
    EmptyFolderDeleteResult,
    EmptyFolderInfo,
    EmptyFolderScanResult,
    generate_delete_log,
)
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager

COL_CHECK = 0
COL_PATH = 1
COL_DEPTH = 2
NUM_COLUMNS = 3


class _EmptyFolderTableModel(QAbstractTableModel):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._folders: list[EmptyFolderInfo] = []
        self._checked: list[bool] = []
        self._checked_count: int = 0

    def set_data(self, folders: list[EmptyFolderInfo]) -> None:
        self.beginResetModel()
        self._folders = folders
        self._checked = [True] * len(folders)
        self._checked_count = len(folders)
        self.endResetModel()

    def clear_data(self) -> None:
        self.beginResetModel()
        self._folders = []
        self._checked = []
        self._checked_count = 0
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._folders)

    def columnCount(self, parent=QModelIndex()) -> int:
        return NUM_COLUMNS

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._folders):
            return None
        folder = self._folders[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_PATH:
                return folder.rel_path
            if col == COL_DEPTH:
                return str(folder.depth)
        elif role == Qt.ItemDataRole.CheckStateRole:
            if col == COL_CHECK:
                return Qt.CheckState.Checked if self._checked[index.row()] else Qt.CheckState.Unchecked
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == COL_PATH:
                return folder.path
        elif role == Qt.ItemDataRole.UserRole:
            return folder
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == COL_CHECK:
            row = index.row()
            was_checked = self._checked[row]
            new_checked = value == Qt.CheckState.Checked.value
            if was_checked != new_checked:
                self._checked[row] = new_checked
                self._checked_count += 1 if new_checked else -1
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsEnabled

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == COL_CHECK:
                return ""
            if section == COL_PATH:
                return tr("empty_folders.col_path")
            if section == COL_DEPTH:
                return tr("empty_folders.col_depth")
        return None

    def set_all_checked(self, checked: bool) -> None:
        if not self._folders:
            return
        self._checked = [checked] * len(self._folders)
        self._checked_count = len(self._folders) if checked else 0
        self.beginResetModel()
        self.endResetModel()

    def get_checked_paths(self) -> list[str]:
        return [
            self._folders[i].path
            for i in range(len(self._folders))
            if self._checked[i]
        ]

    def checked_count(self) -> int:
        return self._checked_count


class EmptyFoldersScreen(QWidget):

    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scan_worker = None
        self._delete_worker = None
        self._scan_result: EmptyFolderScanResult | None = None
        self._delete_result: EmptyFolderDeleteResult | None = None
        self._current_root: str = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(
            DesignSystem.SPACE_24, DesignSystem.SPACE_24,
            DesignSystem.SPACE_24, DesignSystem.SPACE_24,
        )

        header_row = QHBoxLayout()
        back_btn = QPushButton(tr("common.back"))
        back_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(back_btn, "arrow-left")
        back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(back_btn)

        title = QLabel(tr("empty_folders.title"))
        title.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};"
        )
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        layout.addWidget(self._create_path_card())
        layout.addWidget(self._create_progress_card())
        layout.addWidget(self._create_results_card(), stretch=1)
        layout.addWidget(self._create_actions_card())

    def _create_path_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_card_style())
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(DesignSystem.SPACE_12)

        path_row = QHBoxLayout()
        path_label = QLabel(tr("empty_folders.directory"))
        path_label.setStyleSheet(
            f"font-weight: bold; font-size: {DesignSystem.SIZE_BASE}px;"
        )
        path_row.addWidget(path_label)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText(tr("empty_folders.path_placeholder"))
        path_row.addWidget(self._path_input, stretch=1)

        browse_btn = QPushButton(tr("common.browse"))
        browse_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(browse_btn, "folder-open")
        browse_btn.clicked.connect(self._browse_directory)
        path_row.addWidget(browse_btn)

        disk_btn = QPushButton(tr("empty_folders.select_drive"))
        disk_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(disk_btn, "harddisk")
        disk_btn.clicked.connect(self._select_drive)
        path_row.addWidget(disk_btn)

        card_layout.addLayout(path_row)

        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton(tr("empty_folders.scan_button"))
        self._scan_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        icon_manager.set_button_icon(self._scan_btn, "folder-search", color="#FFFFFF")
        self._scan_btn.setMinimumWidth(240)
        self._scan_btn.clicked.connect(self._start_scan)
        scan_row.addWidget(self._scan_btn)
        scan_row.addStretch()
        card_layout.addLayout(scan_row)

        return card

    def _create_progress_card(self) -> QFrame:
        self._progress_card = QFrame()
        self._progress_card.setStyleSheet(DesignSystem.get_card_style())
        card_layout = QVBoxLayout(self._progress_card)
        card_layout.setSpacing(DesignSystem.SPACE_8)

        from PyQt6.QtWidgets import QProgressBar
        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet(DesignSystem.get_progressbar_style())
        self._progress_bar.setRange(0, 0)
        card_layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(
            f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; font-size: {DesignSystem.SIZE_SM}px;"
        )
        card_layout.addWidget(self._progress_label)

        self._progress_card.setVisible(False)
        return self._progress_card

    def _create_results_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_card_style())
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(DesignSystem.SPACE_8)

        toolbar = QHBoxLayout()

        self._select_all_btn = QPushButton(tr("empty_folders.select_all"))
        self._select_all_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._select_all_btn, "check-all")
        self._select_all_btn.clicked.connect(self._on_select_all)
        self._select_all_btn.setEnabled(False)
        toolbar.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton(tr("empty_folders.deselect_all"))
        self._deselect_all_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._deselect_all_btn, "close-circle")
        self._deselect_all_btn.clicked.connect(self._on_deselect_all)
        self._deselect_all_btn.setEnabled(False)
        toolbar.addWidget(self._deselect_all_btn)

        toolbar.addStretch()

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
        )
        toolbar.addWidget(self._count_label)

        card_layout.addLayout(toolbar)

        self._table_model = _EmptyFolderTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._table_model)
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(32)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setStyleSheet(DesignSystem.get_table_style())
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_CHECK, 36)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DEPTH, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_DEPTH, 130)

        self._table.clicked.connect(self._on_table_clicked)

        card_layout.addWidget(self._table)

        self._results_card = card
        return card

    def _create_actions_card(self) -> QFrame:
        self._actions_card = QFrame()
        self._actions_card.setStyleSheet(DesignSystem.get_card_style())
        actions_layout = QHBoxLayout(self._actions_card)

        self._delete_btn = QPushButton(tr("empty_folders.delete_selected"))
        self._delete_btn.setStyleSheet(DesignSystem.get_danger_button_style())
        icon_manager.set_button_icon(self._delete_btn, "delete-sweep", color="#FFFFFF")
        self._delete_btn.setMinimumWidth(200)
        self._delete_btn.clicked.connect(self._on_delete_selected)
        self._delete_btn.setEnabled(False)
        actions_layout.addWidget(self._delete_btn)

        self._save_log_btn = QPushButton(tr("empty_folders.save_log"))
        self._save_log_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._save_log_btn, "content-save")
        self._save_log_btn.clicked.connect(self._on_save_log)
        self._save_log_btn.setEnabled(False)
        actions_layout.addWidget(self._save_log_btn)

        self._cancel_btn = QPushButton(tr("common.cancel"))
        self._cancel_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._cancel_btn, "close-circle")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setVisible(False)
        actions_layout.addWidget(self._cancel_btn)

        actions_layout.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
        )
        actions_layout.addWidget(self._status_label)

        return self._actions_card

    def _browse_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, tr("empty_folders.select_directory"), self._path_input.text()
        )
        if directory:
            self._path_input.setText(directory)

    def _select_drive(self) -> None:
        from sync_app.dialogs.disk_selector_dialog import DiskSelectorDialog
        dialog = DiskSelectorDialog(purpose="source", parent=self)
        def on_selected(mount_point: str, label: str):
            self._path_input.setText(mount_point)
        dialog.disk_selected.connect(on_selected)
        dialog.exec()

    def _start_scan(self) -> None:
        root = self._path_input.text().strip()
        if not root:
            QMessageBox.warning(self, tr("empty_folders.no_path_title"), tr("empty_folders.no_path_msg"))
            return

        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            QMessageBox.warning(self, tr("empty_folders.invalid_path_title"), tr("empty_folders.invalid_path_msg"))
            return

        self._current_root = root
        self._table_model.clear_data()
        self._scan_result = None
        self._delete_result = None
        self._set_scanning_ui(True)

        from sync_app.workers.empty_folder_scan_worker import EmptyFolderScanWorker
        self._scan_worker = EmptyFolderScanWorker(root_path, parent=self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _set_scanning_ui(self, scanning: bool) -> None:
        self._progress_card.setVisible(scanning)
        self._scan_btn.setEnabled(not scanning)
        self._cancel_btn.setVisible(scanning)
        self._delete_btn.setEnabled(not scanning and self._table_model.checked_count() > 0)
        self._save_log_btn.setEnabled(not scanning and self._delete_result is not None)
        self._select_all_btn.setEnabled(not scanning and self._table_model.rowCount() > 0)
        self._deselect_all_btn.setEnabled(not scanning and self._table_model.rowCount() > 0)
        if scanning:
            self._progress_label.setText(tr("empty_folders.scanning"))
            self._count_label.setText("")
            self._status_label.setText("")

    def _on_scan_progress(self, percent: int, message: str) -> None:
        self._progress_label.setText(message)

    def _on_scan_finished(self, result: EmptyFolderScanResult) -> None:
        self._scan_result = result
        self._scan_worker = None

        if not result.empty_folders:
            self._set_scanning_ui(False)
            self._count_label.setText(tr("empty_folders.no_empty_found"))
            self._status_label.setText(
                tr("empty_folders.scan_complete", dirs=result.total_dirs_scanned, time=f"{result.scan_time:.1f}")
            )
            return

        self._table_model.set_data(result.empty_folders)
        total = len(result.empty_folders)
        checked = self._table_model.checked_count()
        self._count_label.setText(tr("empty_folders.found_count", total=total))
        self._set_scanning_ui(False)
        self._update_delete_btn()
        self._status_label.setText(
            tr("empty_folders.scan_complete", dirs=result.total_dirs_scanned, time=f"{result.scan_time:.1f}")
        )

    def _on_scan_error(self, error: str) -> None:
        self._scan_worker = None
        self._set_scanning_ui(False)
        QMessageBox.critical(self, tr("common.error"), error)

    def _on_table_clicked(self, index) -> None:
        if index.column() == COL_CHECK:
            row = index.row()
            was_checked = self._table_model._checked[row]
            self._table_model._checked[row] = not was_checked
            self._table_model._checked_count += -1 if was_checked else 1
            self._table.viewport().update()
            self._update_delete_btn()

    def _update_count_label(self) -> None:
        total = self._table_model.rowCount()
        checked = self._table_model.checked_count()
        if total > 0:
            self._count_label.setText(tr("empty_folders.selected_of", checked=checked, total=total))

    def _update_delete_btn(self) -> None:
        self._delete_btn.setEnabled(self._table_model.checked_count() > 0)
        self._update_count_label()

    def _on_select_all(self) -> None:
        self._table_model.set_all_checked(True)
        self._update_delete_btn()

    def _on_deselect_all(self) -> None:
        self._table_model.set_all_checked(False)
        self._update_delete_btn()

    def _on_delete_selected(self) -> None:
        paths = self._table_model.get_checked_paths()
        if not paths:
            return

        confirm = QMessageBox.question(
            self,
            tr("empty_folders.confirm_title"),
            tr("empty_folders.confirm_msg", count=len(paths)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._set_scanning_ui(True)
        self._progress_label.setText(tr("empty_folders.deleting"))

        from sync_app.workers.empty_folder_delete_worker import EmptyFolderDeleteWorker
        self._delete_worker = EmptyFolderDeleteWorker(paths, cascade=True, stop_at=self._current_root, parent=self)
        self._delete_worker.progress.connect(self._on_delete_progress)
        self._delete_worker.finished.connect(self._on_delete_finished)
        self._delete_worker.error.connect(self._on_delete_error)
        self._delete_worker.start()

    def _on_delete_progress(self, count: int, path: str) -> None:
        self._progress_label.setText(tr("empty_folders.deleting_path", count=count, path=path))

    def _on_delete_finished(self, result: EmptyFolderDeleteResult) -> None:
        self._delete_result = result
        self._delete_worker = None
        self._set_scanning_ui(False)
        self._save_log_btn.setEnabled(True)

        total = result.total_freed_dirs
        failed = len(result.failed)
        cascade = len(result.cascade_removed)

        msg_parts = [tr("empty_folders.delete_complete", total=total)]
        if cascade > 0:
            msg_parts.append(tr("empty_folders.cascade_info", count=cascade))
        if failed > 0:
            msg_parts.append(tr("empty_folders.failed_info", count=failed))

        self._status_label.setText(" | ".join(msg_parts))

        self._table_model.clear_data()
        self._count_label.setText(tr("empty_folders.folders_removed", count=total))

        QMessageBox.information(
            self,
            tr("empty_folders.complete_title"),
            "\n".join(msg_parts),
        )

    def _on_delete_error(self, error: str) -> None:
        self._delete_worker = None
        self._set_scanning_ui(False)
        QMessageBox.critical(self, tr("common.error"), error)

    def _on_save_log(self) -> None:
        if not self._delete_result:
            return

        log_text = generate_delete_log(self._delete_result, self._current_root)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("empty_folders.save_log_title"),
            "empty_folders_cleanup.log",
            "Log files (*.log);;Text files (*.txt);;All files (*)",
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(log_text, encoding="utf-8")
            QMessageBox.information(
                self,
                tr("empty_folders.log_saved_title"),
                tr("empty_folders.log_saved_msg", path=file_path),
            )
        except OSError as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    def _on_cancel(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.request_cancel()
        if self._delete_worker and self._delete_worker.isRunning():
            self._delete_worker.request_cancel()
