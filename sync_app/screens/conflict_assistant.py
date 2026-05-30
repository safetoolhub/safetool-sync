# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
# noqa: E501
"""Conflict assistant — interactive dialog for resolving conflicts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QCheckBox,
    QGroupBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl

from PyQt6.QtGui import QColor, QBrush, QDesktopServices

from services.models import ComparisonEntry, ConflictResolution, DiffType, SyncAction, SyncDirection
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from sync_app.workers.hash_worker import HashWorker
from utils.i18n import tr
from utils.format_utils import format_size


class ConflictAssistant(QWidget):
    """Interactive conflict resolution assistant."""

    all_resolved = pyqtSignal()
    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conflicts: list[ComparisonEntry] = []
        self._current_index = 0
        self._direction: SyncDirection = SyncDirection.UNIDIRECTIONAL
        self._source_root: Path | None = None
        self._dest_root: Path | None = None
        self._hash_worker: HashWorker | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)

        header = QHBoxLayout()
        back_btn = QPushButton(tr("common.back"))
        back_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(back_btn, "arrow-left")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        title = QLabel(tr("conflict.title"))
        title.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold;")
        header.addWidget(title, stretch=1)

        self._finish_btn = QPushButton(tr("conflict.finish"))
        self._finish_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        icon_manager.set_button_icon(self._finish_btn, "check")
        self._finish_btn.clicked.connect(self.all_resolved.emit)
        self._finish_btn.setVisible(False)
        header.addWidget(self._finish_btn)

        layout.addLayout(header)

        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet(DesignSystem.get_progressbar_style())
        layout.addWidget(self._progress_bar)

        nav_container = QWidget()
        nav_container.setStyleSheet(
            f"QWidget {{ background-color: {DesignSystem.COLOR_SURFACE}; border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT}; border-radius: {DesignSystem.RADIUS_MD}px; }}"
        )
        nav_row = QHBoxLayout(nav_container)
        nav_row.setSpacing(0)
        nav_row.setContentsMargins(DesignSystem.SPACE_4, DesignSystem.SPACE_4, DesignSystem.SPACE_4, DesignSystem.SPACE_4)

        self._prev_btn = QPushButton(tr("conflict.previous"))
        self._prev_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._prev_btn, "chevron-left")
        self._prev_btn.clicked.connect(self._go_prev)
        nav_row.addWidget(self._prev_btn)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_LG}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};"
            f"padding: 0 {DesignSystem.SPACE_16}px; background: transparent; border: none;"
        )
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(self._progress_label, stretch=1)

        self._next_btn = QPushButton(tr("conflict.next"))
        self._next_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._next_btn, "chevron-right")
        self._next_btn.clicked.connect(self._go_next)
        nav_row.addWidget(self._next_btn)

        outer_nav = QHBoxLayout()
        outer_nav.addStretch()
        outer_nav.addWidget(nav_container)
        outer_nav.addStretch()
        layout.addLayout(outer_nav)

        self._file_label = QLabel("")
        self._file_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_BASE}px; color: {DesignSystem.COLOR_TEXT}; padding: {DesignSystem.SPACE_4}px 0;")
        self._file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._file_label.setWordWrap(True)

        file_row = QHBoxLayout()
        file_row.setSpacing(DesignSystem.SPACE_8)
        file_row.addStretch()

        self._open_src_btn = QPushButton(tr("review.open_file") + " (src)")
        self._open_src_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._open_src_btn, "open-in-new")
        self._open_src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_src_btn.setVisible(False)
        self._open_src_btn.clicked.connect(self._open_current_source_file)
        file_row.addWidget(self._open_src_btn)

        file_row.addWidget(self._file_label, stretch=1)

        self._open_dst_btn = QPushButton(tr("review.open_file") + " (dest)")
        self._open_dst_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._open_dst_btn, "open-in-new")
        self._open_dst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_dst_btn.setVisible(False)
        self._open_dst_btn.clicked.connect(self._open_current_dest_file)
        file_row.addWidget(self._open_dst_btn)

        file_row.addStretch()
        layout.addLayout(file_row)

        layout.addWidget(self._create_info_panel())

        self._action_row = QWidget()
        self._action_layout = QHBoxLayout(self._action_row)
        self._action_layout.setSpacing(DesignSystem.SPACE_8)
        self._action_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._action_row)

        bottom_controls = QHBoxLayout()

        self._apply_all_checkbox = QCheckBox(tr("conflict.apply_to_all"))
        self._apply_all_checkbox.setStyleSheet(DesignSystem.get_checkbox_style())
        bottom_controls.addWidget(self._apply_all_checkbox)
        bottom_controls.addStretch()

        layout.addLayout(bottom_controls)

        layout.addStretch()

    def _create_info_panel(self) -> QGroupBox:
        group = QGroupBox("")
        group.setStyleSheet(DesignSystem.get_conflict_dialog_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(DesignSystem.SPACE_12)

        self._comparison_table = QTableWidget()
        self._comparison_table.setColumnCount(3)
        self._comparison_table.setHorizontalHeaderLabels([
            tr("conflict.attribute"),
            tr("conflict.source_info"),
            tr("conflict.dest_info"),
        ])
        self._comparison_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._comparison_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._comparison_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._comparison_table.verticalHeader().setVisible(False)
        self._comparison_table.setShowGrid(False)
        self._comparison_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._comparison_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._comparison_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._comparison_table.setAlternatingRowColors(False)

        table_style = f"""
            QTableWidget {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
                gridline-color: transparent;
            }}
            QHeaderView::section {{
                background-color: {DesignSystem.COLOR_SURFACE};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_12}px;
                border: none;
                border-bottom: 2px solid {DesignSystem.COLOR_BORDER_LIGHT};
                font-weight: bold;
                font-size: {DesignSystem.SIZE_SM}px;
            }}
            QTableWidget::item {{
                padding: {DesignSystem.SPACE_12}px {DesignSystem.SPACE_12}px;
                text-align: center;
            }}
        """
        self._comparison_table.setStyleSheet(table_style)
        self._comparison_table.verticalHeader().setDefaultSectionSize(56)
        self._comparison_table.setMaximumHeight(290)
        layout.addWidget(self._comparison_table)

        return group

    def _build_action_buttons(self) -> None:
        while self._action_layout.count():
            child = self._action_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._action_buttons: list[tuple[QPushButton, SyncAction | str]] = []

        buttons = [
            (tr("conflict.choose_source"), SyncAction.OVERWRITE_DEST),
            (tr("conflict.choose_dest"), SyncAction.OVERWRITE_SOURCE),
            (tr("conflict.choose_newest"), "newest"),
            (tr("conflict.choose_largest"), "largest"),
            (tr("common.skip"), SyncAction.SKIP),
            (tr("actions.mark_review"), SyncAction.MARK_REVIEW),
        ]

        for label, action in buttons:
            btn = QPushButton(label)
            btn.setMinimumHeight(40)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, a=action: self._resolve(a))
            self._action_layout.addWidget(btn, stretch=1)
            self._action_buttons.append((btn, action))

        self._update_button_styles()

    def _action_to_button_key(self, action: SyncAction) -> SyncAction | str | None:
        if action in (SyncAction.OVERWRITE_DEST, SyncAction.OVERWRITE_SOURCE, SyncAction.SKIP, SyncAction.MARK_REVIEW):
            return action
        return None

    def _update_button_styles(self, current_action: SyncAction | None = None) -> None:
        if not hasattr(self, '_action_buttons'):
            return
        active_key = self._action_to_button_key(current_action) if current_action else None
        for btn, action in self._action_buttons:
            is_active = (action == active_key)
            if is_active:
                btn.setChecked(True)
                btn.setStyleSheet(DesignSystem.get_primary_button_style())
            else:
                btn.setChecked(False)
                btn.setStyleSheet(DesignSystem.get_secondary_button_style())

    def set_conflicts(
        self,
        conflicts: list[ComparisonEntry],
        direction: SyncDirection = SyncDirection.UNIDIRECTIONAL,
        source_root: Path | None = None,
        dest_root: Path | None = None,
    ) -> None:
        self._conflicts = conflicts
        self._direction = direction
        self._source_root = source_root
        self._dest_root = dest_root
        self._current_index = 0
        self._build_action_buttons()
        self._show_current()

    def _go_prev(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
        else:
            self._current_index = len(self._conflicts) - 1
        self._show_current()

    def _go_next(self) -> None:
        if self._current_index < len(self._conflicts) - 1:
            self._current_index += 1
        else:
            self._current_index = 0
        self._show_current()

    def _show_current(self) -> None:
        total = len(self._conflicts)
        if total == 0:
            return

        resolved_count = sum(1 for e in self._conflicts if e.action != SyncAction.MARK_REVIEW)
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(resolved_count)
        self._progress_bar.setFormat(tr("conflict.resolved_n_of_m", resolved=resolved_count, total=total))
        self._progress_label.setText(tr("conflict.conflict_n_of_m", current=self._current_index + 1, total=total))

        if self._current_index >= total:
            self._current_index = total - 1

        entry = self._conflicts[self._current_index]
        self._file_label.setText(entry.rel_path)

        self._open_src_btn.setVisible(
            bool(entry.source and self._source_root and not entry.source.is_dir)
        )
        self._open_dst_btn.setVisible(
            bool(entry.dest and self._dest_root and not entry.dest.is_dir)
        )

        self._populate_comparison_table(entry)

        self._prev_btn.setEnabled(len(self._conflicts) > 1)
        self._next_btn.setEnabled(len(self._conflicts) > 1)
        self._finish_btn.setVisible(resolved_count == total)

        self._update_button_styles(entry.action)

    def _populate_comparison_table(self, entry: ComparisonEntry) -> None:
        self._comparison_table.setRowCount(0)
        src = entry.source
        dst = entry.dest

        COLOR_MATCH_BG = "#e8f5e9"
        COLOR_MISMATCH_BG = "#ffebee"
        COLOR_NEUTRAL_BG = DesignSystem.COLOR_SURFACE

        rows: list[tuple[str, str, str, bool | None, str]] = []

        if src and dst:
            path_match = src.rel_path == dst.rel_path
            rows.append((
                tr("conflict.path"),
                src.rel_path,
                dst.rel_path,
                path_match,
                "",
            ))

            size_match = src.size == dst.size
            size_detail = ""
            if not size_match:
                size_diff = dst.size - src.size
                size_label = "+" if size_diff > 0 else ""
                size_detail = f" ({size_label}{format_size(abs(size_diff))})"
            rows.append((
                tr("conflict.size"),
                f"{format_size(src.size)} ({src.size:,} bytes)",
                f"{format_size(dst.size)} ({dst.size:,} bytes){size_detail}",
                size_match,
                "",
            ))

            mtime_match = int(src.mtime) == int(dst.mtime)
            src_date = datetime.fromtimestamp(src.mtime).strftime('%Y-%m-%d %H:%M:%S')
            dst_date = datetime.fromtimestamp(dst.mtime).strftime('%Y-%m-%d %H:%M:%S')
            extra = ""
            if not mtime_match:
                extra = f" ({tr('conflict.source_newer')})" if src.mtime > dst.mtime else f" ({tr('conflict.dest_newer')})"
            rows.append((
                tr("conflict.modified_date"),
                src_date,
                dst_date + extra,
                mtime_match,
                "",
            ))

            if src.hash_sha256 and dst.hash_sha256:
                hash_match = src.hash_sha256 == dst.hash_sha256
                rows.append((
                    tr("conflict.hash"),
                    src.hash_sha256[:16] + "...",
                    dst.hash_sha256[:16] + "...",
                    hash_match,
                    "",
                ))
            else:
                rows.append((
                    tr("conflict.hash"),
                    src.hash_sha256[:16] + "..." if src.hash_sha256 else "—",
                    dst.hash_sha256[:16] + "..." if dst.hash_sha256 else "—",
                    None,
                    "calc",
                ))
        elif src:
            rows.append((tr("conflict.path"), src.rel_path, "—", None, ""))
            rows.append((tr("conflict.size"), f"{format_size(src.size)} ({src.size:,} bytes)", "—", None, ""))
            rows.append((tr("conflict.modified_date"), datetime.fromtimestamp(src.mtime).strftime('%Y-%m-%d %H:%M:%S'), "—", None, ""))
            rows.append((tr("conflict.hash"), src.hash_sha256[:16] + "..." if src.hash_sha256 else "—", "—", None, ""))
        elif dst:
            rows.append((tr("conflict.path"), "—", dst.rel_path, None, ""))
            rows.append((tr("conflict.size"), "—", f"{format_size(dst.size)} ({dst.size:,} bytes)", None, ""))
            rows.append((tr("conflict.modified_date"), "—", datetime.fromtimestamp(dst.mtime).strftime('%Y-%m-%d %H:%M:%S'), None, ""))
            rows.append((tr("conflict.hash"), "—", dst.hash_sha256[:16] + "..." if dst.hash_sha256 else "—", None, ""))

        self._hash_row_index = -1
        self._comparison_table.setRowCount(len(rows))
        for row_idx, (attr, src_val, dst_val, match_state, special) in enumerate(rows):
            if match_state is True:
                bg_color = QColor(COLOR_MATCH_BG)
            elif match_state is False:
                bg_color = QColor(COLOR_MISMATCH_BG)
            else:
                bg_color = QColor(COLOR_NEUTRAL_BG)

            bg_brush = QBrush(bg_color)

            center = Qt.AlignmentFlag.AlignCenter

            attr_item = QTableWidgetItem(attr)
            font = attr_item.font()
            font.setBold(True)
            attr_item.setFont(font)
            attr_item.setBackground(bg_brush)
            attr_item.setTextAlignment(center)
            self._comparison_table.setItem(row_idx, 0, attr_item)

            src_item = QTableWidgetItem(src_val)
            src_item.setBackground(bg_brush)
            src_item.setTextAlignment(center)
            if match_state is False and src and dst:
                src_item.setForeground(QBrush(QColor(DesignSystem.COLOR_DANGER)))
            self._comparison_table.setItem(row_idx, 1, src_item)

            dst_item = QTableWidgetItem(dst_val)
            dst_item.setBackground(bg_brush)
            dst_item.setTextAlignment(center)
            if match_state is False and src and dst:
                dst_item.setForeground(QBrush(QColor(DesignSystem.COLOR_DANGER)))
            self._comparison_table.setItem(row_idx, 2, dst_item)

            if special == "calc":
                self._hash_row_index = row_idx
                can_calc = (
                    self._source_root is not None
                    and self._dest_root is not None
                    and entry.source is not None
                    and entry.dest is not None
                )
                calc_btn = QPushButton()
                calc_btn.setFixedSize(28, 28)
                calc_btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; border: none; border-radius: 4px; }}"
                    f"QPushButton:hover {{ background: {DesignSystem.COLOR_PRIMARY_LIGHT}; }}"
                    f"QPushButton:disabled {{ opacity: 0.4; }}"
                )
                icon_manager.set_button_icon(calc_btn, "file-compare")
                calc_btn.setEnabled(can_calc)
                calc_btn.clicked.connect(self._compute_hashes_for_current)
                self._comparison_table.setCellWidget(row_idx, 2, calc_btn)

    def _compute_hashes_for_current(self) -> None:
        if self._hash_worker and self._hash_worker.isRunning():
            return
        if not self._conflicts or self._current_index >= len(self._conflicts):
            return
        entry = self._conflicts[self._current_index]
        if not entry.source or not entry.dest:
            return
        if not self._source_root or not self._dest_root:
            return

        src_path = self._source_root / entry.source.rel_path
        dst_path = self._dest_root / entry.dest.rel_path

        if self._hash_row_index >= 0:
            calc_btn = self._comparison_table.cellWidget(self._hash_row_index, 2)
            if calc_btn:
                calc_btn.setEnabled(False)

        self._hash_worker = HashWorker([src_path, dst_path], parent=self)
        self._hash_worker.finished.connect(lambda result: self._on_hashes_finished(result, entry))
        self._hash_worker.start()

    def _on_hashes_finished(self, result: dict[str, str], entry: ComparisonEntry) -> None:
        if entry.source:
            src_path = str(self._source_root / entry.source.rel_path) if self._source_root else ""
            if src_path in result:
                entry.source.hash_sha256 = result[src_path]
        if entry.dest:
            dst_path = str(self._dest_root / entry.dest.rel_path) if self._dest_root else ""
            if dst_path in result:
                entry.dest.hash_sha256 = result[dst_path]

        if self._conflicts and self._current_index < len(self._conflicts) and self._conflicts[self._current_index] is entry:
            self._populate_comparison_table(entry)

    def _open_current_source_file(self) -> None:
        if not self._conflicts or self._current_index >= len(self._conflicts):
            return
        entry = self._conflicts[self._current_index]
        if entry.source and self._source_root:
            full_path = self._source_root / entry.source.rel_path
            if full_path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))

    def _open_current_dest_file(self) -> None:
        if not self._conflicts or self._current_index >= len(self._conflicts):
            return
        entry = self._conflicts[self._current_index]
        if entry.dest and self._dest_root:
            full_path = self._dest_root / entry.dest.rel_path
            if full_path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))

    def _resolve(self, action: SyncAction | str) -> None:
        entry = self._conflicts[self._current_index]

        def get_act(e: ComparisonEntry, a: SyncAction | str) -> SyncAction:
            if a == "newest":
                if e.source and e.dest:
                    return SyncAction.OVERWRITE_DEST if e.source.mtime > e.dest.mtime else SyncAction.OVERWRITE_SOURCE
                return SyncAction.OVERWRITE_DEST
            elif a == "largest":
                if e.source and e.dest:
                    return SyncAction.OVERWRITE_DEST if e.source.size > e.dest.size else SyncAction.OVERWRITE_SOURCE
                return SyncAction.OVERWRITE_DEST
            return a

        if self._apply_all_checkbox.isChecked():
            for i in range(len(self._conflicts)):
                self._conflicts[i].action = get_act(self._conflicts[i], action)
        else:
            entry.action = get_act(entry, action)

        self._apply_all_checkbox.setChecked(False)
        self._show_current()

    def get_conflict_entries(self) -> list[ComparisonEntry]:
        return self._conflicts
