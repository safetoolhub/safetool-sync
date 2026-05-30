# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Snapshots screen — offline disk explorer with global search."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QGroupBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from services.models import DiskSnapshot, DiffType, CompareMode
from services.comparator import compare as compare_entries
from services.snapshot_manager import SnapshotManager
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.format_utils import format_size


class SnapshotsScreen(QWidget):
    """Screen for browsing saved disk snapshots and searching files offline."""

    back_requested = pyqtSignal()
    snapshot_requested = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = SnapshotManager()
        self._current_snapshot: str | None = None
        self._current_entries: list = []
        self._show_all_drives = False
        self._compare_results: list = []
        self._in_compare_mode = False

        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)

        header_row = QHBoxLayout()
        header_row.setSpacing(DesignSystem.SPACE_12)

        back_btn = QPushButton(tr("common.back"))
        back_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(back_btn, "arrow-left")
        back_btn.setMinimumHeight(36)
        back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(back_btn)

        title = QLabel(tr("snapshots.title"))
        title.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};")
        header_row.addWidget(title)
        header_row.addStretch()

        layout.addLayout(header_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._create_disk_detection())
        splitter.addWidget(self._create_snapshot_list())
        splitter.addWidget(self._create_explorer())
        splitter.setSizes([350, 250, 500])
        layout.addWidget(splitter, stretch=1)

        self._refresh()

    def _create_snapshot_list(self) -> QWidget:
        group = QGroupBox(tr("snapshots.saved_snapshots"))
        group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(group)

        header_row = QHBoxLayout()
        header_row.setSpacing(DesignSystem.SPACE_8)
        header_row.addStretch()

        refresh_btn = QToolButton()
        refresh_btn.setStyleSheet(DesignSystem.get_icon_button_style())
        refresh_btn.setToolTip(tr("snapshots.refresh_list"))
        refresh_btn.setAutoRaise(True)
        icon_manager.set_button_icon(refresh_btn, "sync", size=18)
        refresh_btn.clicked.connect(self._refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        from PyQt6.QtWidgets import QScrollArea, QFrame
        self._snapshot_scroll_area = QScrollArea()
        self._snapshot_scroll_area.setWidgetResizable(True)
        self._snapshot_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._snapshot_scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

        self._snapshot_cards_container = QWidget()
        self._snapshot_cards_layout = QVBoxLayout(self._snapshot_cards_container)
        self._snapshot_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._snapshot_cards_layout.setSpacing(DesignSystem.SPACE_6)
        self._snapshot_cards_layout.addStretch()

        self._snapshot_scroll_area.setWidget(self._snapshot_cards_container)
        layout.addWidget(self._snapshot_scroll_area)

        return group

    def _create_explorer(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(DesignSystem.SPACE_8)

        compare_group = QGroupBox(tr("snapshots.compare_title"))
        compare_group.setStyleSheet(DesignSystem.get_card_style())
        compare_layout = QVBoxLayout(compare_group)
        compare_layout.setSpacing(DesignSystem.SPACE_6)

        selectors_row = QHBoxLayout()
        selectors_row.setSpacing(DesignSystem.SPACE_6)

        self._compare_a_combo = QComboBox()
        self._compare_a_combo.setStyleSheet(DesignSystem.get_combobox_style())
        self._compare_b_combo = QComboBox()
        self._compare_b_combo.setStyleSheet(DesignSystem.get_combobox_style())

        selectors_row.addWidget(self._compare_a_combo, stretch=1)
        vs_label = QLabel(tr("snapshots.compare_vs"))
        vs_label.setStyleSheet(f"font-weight: bold; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        selectors_row.addWidget(vs_label)
        selectors_row.addWidget(self._compare_b_combo, stretch=1)
        compare_layout.addLayout(selectors_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(DesignSystem.SPACE_6)

        self._compare_btn = QPushButton(tr("snapshots.compare_run"))
        self._compare_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        icon_manager.set_button_icon(self._compare_btn, "file-compare")
        self._compare_btn.clicked.connect(self._on_compare_snapshots)
        actions_row.addWidget(self._compare_btn)

        self._only_diff_check = QCheckBox(tr("snapshots.only_differences"))
        self._only_diff_check.setStyleSheet(DesignSystem.get_checkbox_style())
        self._only_diff_check.setChecked(True)
        self._only_diff_check.stateChanged.connect(self._on_search_changed)
        actions_row.addWidget(self._only_diff_check)

        actions_row.addStretch()

        self._clear_compare_btn = QPushButton(tr("snapshots.compare_clear"))
        self._clear_compare_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._clear_compare_btn.clicked.connect(self._on_clear_compare)
        self._clear_compare_btn.setVisible(False)
        actions_row.addWidget(self._clear_compare_btn)

        compare_layout.addLayout(actions_row)

        self._compare_summary_label = QLabel("")
        self._compare_summary_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        self._compare_summary_label.setVisible(False)
        compare_layout.addWidget(self._compare_summary_label)

        layout.addWidget(compare_group)

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("snapshots.search_placeholder"))
        self._search_edit.setStyleSheet(DesignSystem.get_combobox_style())
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_edit, stretch=1)
        layout.addLayout(search_row)

        self._tree = QTreeWidget()
        self._tree.setStyleSheet(DesignSystem.get_table_style())
        self._set_tree_headers(compare=False)
        layout.addWidget(self._tree, stretch=1)

        self._status_label = QLabel(tr("snapshots.no_snapshots"))
        self._status_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        return panel

    def _set_tree_headers(self, compare: bool) -> None:
        if compare:
            self._tree.setHeaderLabels([
                tr("review.path"),
                tr("review.status"),
                tr("conflict.size"),
                tr("review.date"),
            ])
            self._tree.setColumnWidth(0, 340)
            self._tree.setColumnWidth(1, 110)
            self._tree.setColumnWidth(2, 90)
            self._tree.setColumnWidth(3, 130)
        else:
            self._tree.setHeaderLabels([
                tr("review.path"),
                tr("conflict.size"),
                tr("review.date"),
            ])
            self._tree.setColumnWidth(0, 400)
            self._tree.setColumnWidth(1, 100)
            self._tree.setColumnWidth(2, 150)

    def _create_disk_detection(self) -> QWidget:
        group = QGroupBox(tr("setup.detected_disks"))
        group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(group)

        header_row = QHBoxLayout()
        self._drive_filter_btn = QPushButton(tr("setup.disk_external_only"))
        self._drive_filter_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._drive_filter_btn.clicked.connect(self._toggle_drive_filter)
        header_row.addWidget(self._drive_filter_btn)
        header_row.addStretch()

        refresh_btn = QPushButton(tr("common.refresh"))
        refresh_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        refresh_btn.clicked.connect(self._refresh_disks)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        from PyQt6.QtWidgets import QScrollArea, QFrame
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
        layout.addWidget(self._disk_scroll_area)

        self._refresh_disks()
        return group

    def _toggle_drive_filter(self) -> None:
        self._show_all_drives = not getattr(self, "_show_all_drives", False)
        label = tr("setup.disk_all_drives") if not self._show_all_drives else tr("setup.disk_external_only")
        self._drive_filter_btn.setText(label)
        self._refresh_disks()

    def _refresh_disks(self) -> None:
        while getattr(self, "_disk_cards_layout", None) and self._disk_cards_layout.count() > 1:
            child = self._disk_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        from services.disk_detector import detect_external_drives, get_all_drives
        drives = get_all_drives() if getattr(self, "_show_all_drives", False) else detect_external_drives()
        
        if not drives:
            no_disks = QLabel(tr("setup.no_disks"))
            no_disks.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; padding: {DesignSystem.SPACE_8}px;")
            self._disk_cards_layout.insertWidget(0, no_disks)
            self._disk_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return

        for idx, drive in enumerate(drives):
            card = self._create_disk_card(drive)
            self._disk_cards_layout.insertWidget(idx, card)

        if len(drives) <= 6:
            self._disk_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self._disk_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _create_disk_card(self, drive) -> QWidget:
        from PyQt6.QtWidgets import QFrame
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_disk_card_style())
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(DesignSystem.SPACE_10, DesignSystem.SPACE_8, DesignSystem.SPACE_10, DesignSystem.SPACE_8)
        card_layout.setSpacing(DesignSystem.SPACE_8)

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

        btn = QPushButton(tr("setup.save_disk_snapshot"))
        btn.setToolTip(tr("setup.snapshot_saving"))
        btn.setStyleSheet(DesignSystem.get_disk_action_button_style("#FFF3E0"))
        
        mount = drive.mount_point
        label = drive.label
        btn.clicked.connect(lambda _, m=mount, l=label: self.snapshot_requested.emit(m, l))
        card_layout.addWidget(btn)

        return card

    def _create_snapshot_card(self, snap: DiskSnapshot) -> QWidget:
        """Create a card widget for a snapshot."""
        from PyQt6.QtWidgets import QFrame
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_disk_card_style())
        card.setProperty("disk_id", snap.disk_id)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(DesignSystem.SPACE_8, DesignSystem.SPACE_6, DesignSystem.SPACE_8, DesignSystem.SPACE_6)
        card_layout.setSpacing(DesignSystem.SPACE_4)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        first_row = QHBoxLayout()
        first_row.setSpacing(DesignSystem.SPACE_8)
        name_label = QLabel(f"{snap.label}")
        name_label.setStyleSheet(f"font-weight: bold; font-size: {DesignSystem.SIZE_BASE}px; border: none; padding: 0;")
        first_row.addWidget(name_label, stretch=1)

        file_size = self._get_snapshot_file_size(snap.disk_id)
        size_label = QLabel(format_size(file_size))
        size_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; padding: 0;")
        first_row.addWidget(size_label)
        info_layout.addLayout(first_row)

        date_str = _format_timestamp(snap.timestamp)
        date_label = QLabel(date_str)
        date_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; padding: 0;")
        info_layout.addWidget(date_label)

        db_path = self._manager._db_path(snap.disk_id)
        path_label = QLabel(str(db_path))
        path_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; padding: 0;")
        path_label.setWordWrap(True)
        info_layout.addWidget(path_label)

        card_layout.addLayout(info_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(DesignSystem.SPACE_4)

        view_btn = QPushButton(tr("snapshots.view_snapshot"))
        view_btn.setStyleSheet(DesignSystem.get_disk_action_button_style("#E3F2FD"))
        view_btn.clicked.connect(lambda: self._on_view_snapshot(snap.disk_id))
        buttons_layout.addWidget(view_btn)

        delete_btn = QPushButton(tr("snapshots.delete_snapshot"))
        delete_btn.setStyleSheet(DesignSystem.get_disk_action_button_style("#FFEBEE"))
        delete_btn.clicked.connect(lambda: self._on_delete_snapshot_by_id(snap.disk_id))
        buttons_layout.addWidget(delete_btn)

        card_layout.addLayout(buttons_layout)

        return card

    def _get_snapshot_file_size(self, disk_id: str) -> int:
        """Get the size of the snapshot database file."""
        db_path = self._manager._db_path(disk_id)
        if db_path.exists():
            return db_path.stat().st_size
        return 0

    def _refresh(self) -> None:
        while getattr(self, "_snapshot_cards_layout", None) and self._snapshot_cards_layout.count() > 1:
            child = self._snapshot_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        snapshots = self._manager.list_snapshots()
        self._populate_compare_combos(snapshots)
        if not snapshots:
            no_snapshots = QLabel(tr("snapshots.no_snapshots"))
            no_snapshots.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; padding: {DesignSystem.SPACE_8}px;")
            self._snapshot_cards_layout.insertWidget(0, no_snapshots)
            self._snapshot_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._status_label.setText(tr("snapshots.no_snapshots"))
            return

        for idx, snap in enumerate(snapshots):
            card = self._create_snapshot_card(snap)
            self._snapshot_cards_layout.insertWidget(idx, card)

        if len(snapshots) <= 4:
            self._snapshot_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self._snapshot_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _on_view_snapshot(self, disk_id: str) -> None:
        """Load and display a snapshot in the explorer."""
        self._in_compare_mode = False
        self._compare_results = []
        self._clear_compare_btn.setVisible(False)
        self._compare_summary_label.setVisible(False)
        self._set_tree_headers(compare=False)
        self._current_snapshot = disk_id
        self._current_entries = self._manager.load_all_entries(disk_id)
        self._search_edit.clear()
        self._on_search_changed()

    def _on_delete_snapshot_by_id(self, disk_id: str) -> None:
        """Delete a snapshot by its disk_id."""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("common.delete") + "?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._manager.delete_snapshot(disk_id):
                if self._current_snapshot == disk_id:
                    self._current_snapshot = None
                    self._current_entries = []
                    self._tree.clear()
                    self._status_label.setText(tr("snapshots.no_snapshots"))
                self._refresh()

    def _on_search_changed(self) -> None:
        if self._in_compare_mode:
            self._apply_compare_filter()
            return

        if not hasattr(self, "_current_entries") or not self._current_entries:
            self._tree.clear()
            self._status_label.setText(tr("snapshots.no_snapshots"))
            return

        search_text = self._search_edit.text().strip().lower()
        if not search_text:
            self._populate_tree(self._current_entries)
            self._status_label.setText(f"{len(self._current_entries)} " + tr("review.total").lower())
        else:
            filtered = [e for e in self._current_entries if search_text in e.rel_path.lower()]
            self._populate_tree(filtered)
            self._status_label.setText(f"{len(filtered)} / {len(self._current_entries)} " + tr("review.total").lower())

    def _populate_tree(self, entries) -> None:
        self._tree.clear()
        root = self._tree.invisibleRootItem()
        dirs: dict[str, QTreeWidgetItem] = {}

        for entry in entries:
            parts = entry.rel_path.split("/")
            parent_path = ""
            parent_item = root
            for i, part in enumerate(parts[:-1]):
                current_path = f"{parent_path}/{part}" if parent_path else part
                if current_path not in dirs:
                    dir_item = QTreeWidgetItem(parent_item, [part, "", ""])
                    dir_item.setExpanded(False)
                    icon = icon_manager.get_icon("folder")
                    if icon:
                        dir_item.setIcon(0, icon)
                    dirs[current_path] = dir_item
                parent_item = dirs[current_path]
                parent_path = current_path

            name = parts[-1]
            size_str = format_size(entry.size) if not entry.is_dir else ""
            date_str = _format_timestamp(entry.mtime) if not entry.is_dir else ""
            file_item = QTreeWidgetItem(parent_item, [name, size_str, date_str])
            
            if entry.is_dir:
                icon = icon_manager.get_icon("folder")
            else:
                icon = icon_manager.get_icon("file-document-outline")
                
            if icon:
                file_item.setIcon(0, icon)

        self._tree.expandToDepth(0)

    # ── Snapshot comparison ─────────────────────────────────────────────

    def _populate_compare_combos(self, snapshots) -> None:
        if not hasattr(self, "_compare_a_combo"):
            return
        prev_a = self._compare_a_combo.currentData()
        prev_b = self._compare_b_combo.currentData()

        for combo in (self._compare_a_combo, self._compare_b_combo):
            combo.blockSignals(True)
            combo.clear()

        for snap in snapshots:
            label = f"{snap.label} — {_format_timestamp(snap.timestamp)}"
            self._compare_a_combo.addItem(label, snap.disk_id)
            self._compare_b_combo.addItem(label, snap.disk_id)

        has_two = len(snapshots) >= 2
        self._compare_a_combo.setEnabled(bool(snapshots))
        self._compare_b_combo.setEnabled(bool(snapshots))
        if hasattr(self, "_compare_btn"):
            self._compare_btn.setEnabled(has_two)

        if prev_a is not None:
            idx = self._compare_a_combo.findData(prev_a)
            if idx >= 0:
                self._compare_a_combo.setCurrentIndex(idx)
        if prev_b is not None:
            idx = self._compare_b_combo.findData(prev_b)
            if idx >= 0:
                self._compare_b_combo.setCurrentIndex(idx)
        elif len(snapshots) >= 2:
            self._compare_b_combo.setCurrentIndex(1)

        for combo in (self._compare_a_combo, self._compare_b_combo):
            combo.blockSignals(False)

    def _on_compare_snapshots(self) -> None:
        disk_a = self._compare_a_combo.currentData()
        disk_b = self._compare_b_combo.currentData()
        if not disk_a or not disk_b:
            return
        if disk_a == disk_b:
            self._status_label.setText(tr("snapshots.compare_same_warning"))
            return

        entries_a = self._manager.load_all_entries(disk_a)
        entries_b = self._manager.load_all_entries(disk_b)

        files_a = [e for e in entries_a if not e.is_dir]
        files_b = [e for e in entries_b if not e.is_dir]

        self._compare_results = compare_entries(files_a, files_b, mode=CompareMode.SMART)
        self._in_compare_mode = True
        self._current_entries = []
        self._current_snapshot = None

        self._set_tree_headers(compare=True)
        self._clear_compare_btn.setVisible(True)
        self._compare_summary_label.setVisible(True)
        self._search_edit.clear()
        self._apply_compare_filter()

    def _on_clear_compare(self) -> None:
        self._in_compare_mode = False
        self._compare_results = []
        self._clear_compare_btn.setVisible(False)
        self._compare_summary_label.setVisible(False)
        self._set_tree_headers(compare=False)
        self._tree.clear()
        self._search_edit.clear()
        self._status_label.setText(tr("snapshots.no_snapshots"))

    def _apply_compare_filter(self) -> None:
        results = self._compare_results
        only_diff = self._only_diff_check.isChecked()
        search_text = self._search_edit.text().strip().lower()

        if only_diff:
            results = [r for r in results if r.diff_type != DiffType.IDENTICAL]
        if search_text:
            results = [r for r in results if search_text in r.rel_path.lower()]

        self._populate_compare_tree(results)
        self._update_compare_summary()

        shown = len(results)
        total = len(self._compare_results)
        self._status_label.setText(f"{shown} / {total} " + tr("review.total").lower())

    def _update_compare_summary(self) -> None:
        counts = {
            DiffType.IDENTICAL: 0,
            DiffType.MODIFIED: 0,
            DiffType.SOURCE_ONLY: 0,
            DiffType.DEST_ONLY: 0,
        }
        for r in self._compare_results:
            if r.diff_type in counts:
                counts[r.diff_type] += 1
        parts = [
            f"{tr('snapshots.cmp_identical')}: {counts[DiffType.IDENTICAL]}",
            f"{tr('snapshots.cmp_modified')}: {counts[DiffType.MODIFIED]}",
            f"{tr('snapshots.cmp_only_a')}: {counts[DiffType.SOURCE_ONLY]}",
            f"{tr('snapshots.cmp_only_b')}: {counts[DiffType.DEST_ONLY]}",
        ]
        self._compare_summary_label.setText("   ".join(parts))

    def _populate_compare_tree(self, results) -> None:
        self._tree.clear()
        root = self._tree.invisibleRootItem()
        dirs: dict[str, QTreeWidgetItem] = {}

        for entry in results:
            parts = entry.rel_path.split("/")
            parent_path = ""
            parent_item = root
            for part in parts[:-1]:
                current_path = f"{parent_path}/{part}" if parent_path else part
                if current_path not in dirs:
                    dir_item = QTreeWidgetItem(parent_item, [part, "", "", ""])
                    dir_item.setExpanded(False)
                    icon = icon_manager.get_icon("folder")
                    if icon:
                        dir_item.setIcon(0, icon)
                    dirs[current_path] = dir_item
                parent_item = dirs[current_path]
                parent_path = current_path

            name = parts[-1]
            ref = entry.source or entry.dest
            size_str = format_size(ref.size) if ref else ""
            date_str = _format_timestamp(ref.mtime) if ref else ""
            status_str, color = _diff_label_and_color(entry.diff_type)

            file_item = QTreeWidgetItem(parent_item, [name, status_str, size_str, date_str])
            icon = icon_manager.get_icon("file-document-outline")
            if icon:
                file_item.setIcon(0, icon)
            brush = QBrush(QColor(color))
            file_item.setForeground(1, brush)

        self._tree.expandToDepth(0)


def _diff_label_and_color(diff_type: DiffType) -> tuple[str, str]:
    mapping = {
        DiffType.IDENTICAL: (tr("snapshots.cmp_identical"), DesignSystem.COLOR_DIFF_IDENTICAL),
        DiffType.MODIFIED: (tr("snapshots.cmp_modified"), DesignSystem.COLOR_DIFF_MODIFIED),
        DiffType.SOURCE_ONLY: (tr("snapshots.cmp_only_a"), DesignSystem.COLOR_DIFF_SOURCE_ONLY),
        DiffType.DEST_ONLY: (tr("snapshots.cmp_only_b"), DesignSystem.COLOR_DIFF_DEST_ONLY),
    }
    return mapping.get(diff_type, (diff_type.value, DesignSystem.COLOR_DIFF_ERROR))


def _format_timestamp(ts: float) -> str:
    from datetime import datetime
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)