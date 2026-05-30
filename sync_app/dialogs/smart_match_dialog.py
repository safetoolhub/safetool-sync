# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Smart Match Dialog — shows intelligent matches between orphan files."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QTabWidget,
    QAbstractItemView,
    QToolButton,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from services.models import ComparisonEntry, DiffType, SyncAction
from services.smart_matcher import SmartMatch, SmartMatchResult, find_smart_matches
from sync_app.dialogs.base_dialog import BaseDialog
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.format_utils import format_size

import os


MATCH_ACTIONS: list[SyncAction] = [
    SyncAction.SKIP,
    SyncAction.OVERWRITE_DEST,
    SyncAction.KEEP_DEST,
    SyncAction.MARK_REVIEW,
]


class SmartMatchDialog(BaseDialog):
    """Dialog showing smart matches between SOURCE_ONLY and DEST_ONLY files."""

    def __init__(self, entries: list[ComparisonEntry], parent=None, base_source: str = "", base_dest: str = "") -> None:
        super().__init__(
            parent=parent,
            title=tr("smart_match.title"),
            minimum_width=900,
            minimum_height=600,
        )
        self._entries = entries
        self._base_source = base_source
        self._base_dest = base_dest
        self._result: SmartMatchResult = find_smart_matches(entries)
        self._action_combos: list[QComboBox] = []
        self._applied = False

        self._build_ui()

    def _build_ui(self) -> None:
        header = QLabel(tr("smart_match.description"))
        header.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
        )
        header.setWordWrap(True)
        self._layout.addWidget(header)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(DesignSystem.SPACE_16)

        matches_label = QLabel(
            tr("smart_match.matches_found", count=len(self._result.matches))
        )
        matches_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_LG}px; font-weight: bold; color: {DesignSystem.COLOR_SUCCESS};"
        )
        summary_layout.addWidget(matches_label)

        unmatched_src_label = QLabel(
            tr("smart_match.unmatched_source", count=len(self._result.unmatched_source))
        )
        unmatched_src_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_DIFF_SOURCE_ONLY};"
        )
        summary_layout.addWidget(unmatched_src_label)

        unmatched_dst_label = QLabel(
            tr("smart_match.unmatched_dest", count=len(self._result.unmatched_dest))
        )
        unmatched_dst_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_DIFF_DEST_ONLY};"
        )
        summary_layout.addWidget(unmatched_dst_label)

        summary_layout.addStretch()
        self._layout.addLayout(summary_layout)

        tabs = QTabWidget()

        matches_tab = self._build_matches_tab()
        tabs.addTab(matches_tab, tr("smart_match.tab_matches"))

        unmatched_tab = self._build_unmatched_tab()
        tabs.addTab(unmatched_tab, tr("smart_match.tab_unmatched"))

        self._layout.addWidget(tabs, stretch=1)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(DesignSystem.SPACE_12)

        if self._result.matches:
            bulk_label = QLabel(tr("smart_match.bulk_action"))
            bulk_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
            action_bar.addWidget(bulk_label)

            self._bulk_combo = QComboBox()
            for action in MATCH_ACTIONS:
                self._bulk_combo.addItem(tr(f"actions.{action.value}"), action)
            self._bulk_combo.setStyleSheet(DesignSystem.get_combobox_style())
            action_bar.addWidget(self._bulk_combo)

            apply_all_btn = QPushButton(tr("smart_match.apply_all"))
            apply_all_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
            apply_all_btn.clicked.connect(self._apply_bulk_action)
            action_bar.addWidget(apply_all_btn)

        action_bar.addStretch()

        apply_btn = QPushButton(tr("smart_match.apply_close"))
        apply_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        apply_btn.setMinimumHeight(40)
        apply_btn.clicked.connect(self._apply_and_close)
        action_bar.addWidget(apply_btn)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        action_bar.addWidget(cancel_btn)

        self._layout.addLayout(action_bar)

    def _build_matches_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, DesignSystem.SPACE_8, 0, 0)

        if not self._result.matches:
            no_matches = QLabel(tr("smart_match.no_matches"))
            no_matches.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_LG}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
            )
            no_matches.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_matches)
            return w

        self._matches_table = QTableWidget()
        self._matches_table.setColumnCount(7)
        self._matches_table.setHorizontalHeaderLabels([
            tr("smart_match.col_source"),
            "",
            tr("smart_match.col_dest"),
            "",
            tr("smart_match.col_size"),
            tr("smart_match.col_confidence"),
            tr("smart_match.col_action"),
        ])
        self._matches_table.setRowCount(len(self._result.matches))
        self._matches_table.setAlternatingRowColors(True)
        self._matches_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._matches_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._matches_table.verticalHeader().setVisible(False)
        self._matches_table.setStyleSheet(DesignSystem.get_table_style())

        header = self._matches_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 36)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 36)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 180)

        self._action_combos = []
        for row, match in enumerate(self._result.matches):
            src_name = match.source_entry.rel_path
            dst_name = match.dest_entry.rel_path

            src_item = QTableWidgetItem(src_name)
            src_item.setToolTip(src_name)
            src_item.setForeground(QColor(DesignSystem.COLOR_DIFF_SOURCE_ONLY))
            self._matches_table.setItem(row, 0, src_item)

            if self._base_source:
                open_src_btn = QToolButton()
                icon_manager.set_button_icon(open_src_btn, "open-in-new", color=DesignSystem.COLOR_TEXT_SECONDARY)
                open_src_btn.setStyleSheet(DesignSystem.get_icon_button_style())
                open_src_btn.setToolTip(tr("review.open_file"))
                open_src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_src_btn.setFixedSize(24, 24)
                open_src_btn.clicked.connect(
                    lambda _, p=src_name: self._open_file(self._base_source, p)
                )
                self._matches_table.setCellWidget(row, 1, open_src_btn)

            dst_item = QTableWidgetItem(dst_name)
            dst_item.setToolTip(dst_name)
            dst_item.setForeground(QColor(DesignSystem.COLOR_DIFF_DEST_ONLY))
            self._matches_table.setItem(row, 2, dst_item)

            if self._base_dest:
                open_dst_btn = QToolButton()
                icon_manager.set_button_icon(open_dst_btn, "open-in-new", color=DesignSystem.COLOR_TEXT_SECONDARY)
                open_dst_btn.setStyleSheet(DesignSystem.get_icon_button_style())
                open_dst_btn.setToolTip(tr("review.open_file"))
                open_dst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_dst_btn.setFixedSize(24, 24)
                open_dst_btn.clicked.connect(
                    lambda _, p=dst_name: self._open_file(self._base_dest, p)
                )
                self._matches_table.setCellWidget(row, 3, open_dst_btn)

            size = match.source_entry.source.size if match.source_entry.source else 0
            size_item = QTableWidgetItem(format_size(size))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._matches_table.setItem(row, 4, size_item)

            conf_item = QTableWidgetItem(tr("smart_match.confidence_prefix"))
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._matches_table.setItem(row, 5, conf_item)

            combo = QComboBox()
            for action in MATCH_ACTIONS:
                combo.addItem(tr(f"actions.{action.value}"), action)
            combo.setStyleSheet(DesignSystem.get_combobox_style())
            self._matches_table.setCellWidget(row, 6, combo)
            self._action_combos.append(combo)

        layout.addWidget(self._matches_table)
        return w

    def _build_unmatched_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, DesignSystem.SPACE_8, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_12)

        if self._result.unmatched_source:
            src_title = QLabel(
                tr("smart_match.unmatched_source_title", count=len(self._result.unmatched_source))
            )
            src_title.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; "
                f"color: {DesignSystem.COLOR_DIFF_SOURCE_ONLY};"
            )
            layout.addWidget(src_title)

            src_table = QTableWidget()
            src_table.setColumnCount(3)
            src_table.setHorizontalHeaderLabels([
                tr("smart_match.col_file"), tr("smart_match.col_size"), ""
            ])
            src_table.setRowCount(len(self._result.unmatched_source))
            src_table.setAlternatingRowColors(True)
            src_table.verticalHeader().setVisible(False)
            src_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            src_table.setStyleSheet(DesignSystem.get_table_style())
            src_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            src_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            src_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            src_table.horizontalHeader().resizeSection(2, 36)

            for row, entry in enumerate(self._result.unmatched_source):
                item = QTableWidgetItem(entry.rel_path)
                item.setToolTip(entry.rel_path)
                src_table.setItem(row, 0, item)
                size = entry.source.size if entry.source else 0
                size_item = QTableWidgetItem(format_size(size))
                size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                src_table.setItem(row, 1, size_item)

                if self._base_source:
                    open_btn = QToolButton()
                    icon_manager.set_button_icon(open_btn, "open-in-new", color=DesignSystem.COLOR_TEXT_SECONDARY)
                    open_btn.setStyleSheet(DesignSystem.get_icon_button_style())
                    open_btn.setToolTip(tr("review.open_file"))
                    open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    open_btn.setFixedSize(24, 24)
                    open_btn.clicked.connect(
                        lambda _, p=entry.rel_path: self._open_file(self._base_source, p)
                    )
                    src_table.setCellWidget(row, 2, open_btn)

            layout.addWidget(src_table, stretch=1)

        if self._result.unmatched_dest:
            dst_title = QLabel(
                tr("smart_match.unmatched_dest_title", count=len(self._result.unmatched_dest))
            )
            dst_title.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; "
                f"color: {DesignSystem.COLOR_DIFF_DEST_ONLY};"
            )
            layout.addWidget(dst_title)

            dst_table = QTableWidget()
            dst_table.setColumnCount(3)
            dst_table.setHorizontalHeaderLabels([
                tr("smart_match.col_file"), tr("smart_match.col_size"), ""
            ])
            dst_table.setRowCount(len(self._result.unmatched_dest))
            dst_table.setAlternatingRowColors(True)
            dst_table.verticalHeader().setVisible(False)
            dst_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            dst_table.setStyleSheet(DesignSystem.get_table_style())
            dst_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            dst_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            dst_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            dst_table.horizontalHeader().resizeSection(2, 36)

            for row, entry in enumerate(self._result.unmatched_dest):
                item = QTableWidgetItem(entry.rel_path)
                item.setToolTip(entry.rel_path)
                dst_table.setItem(row, 0, item)
                size = entry.dest.size if entry.dest else 0
                size_item = QTableWidgetItem(format_size(size))
                size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                dst_table.setItem(row, 1, size_item)

                if self._base_dest:
                    open_btn = QToolButton()
                    icon_manager.set_button_icon(open_btn, "open-in-new", color=DesignSystem.COLOR_TEXT_SECONDARY)
                    open_btn.setStyleSheet(DesignSystem.get_icon_button_style())
                    open_btn.setToolTip(tr("review.open_file"))
                    open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    open_btn.setFixedSize(24, 24)
                    open_btn.clicked.connect(
                        lambda _, p=entry.rel_path: self._open_file(self._base_dest, p)
                    )
                    dst_table.setCellWidget(row, 2, open_btn)

            layout.addWidget(dst_table, stretch=1)

        if not self._result.unmatched_source and not self._result.unmatched_dest:
            all_matched = QLabel(tr("smart_match.all_matched"))
            all_matched.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_LG}px; color: {DesignSystem.COLOR_SUCCESS};"
            )
            all_matched.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(all_matched)

        layout.addStretch()
        return w

    def _open_file(self, base: str, rel_path: str) -> None:
        full_path = os.path.join(base, rel_path)
        if os.path.isfile(full_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))

    def _apply_bulk_action(self) -> None:
        action = self._bulk_combo.currentData()
        if action is None:
            return
        for combo in self._action_combos:
            for i in range(combo.count()):
                if combo.itemData(i) == action:
                    combo.setCurrentIndex(i)
                    break

    def _apply_and_close(self) -> None:
        for i, match in enumerate(self._result.matches):
            if i < len(self._action_combos):
                action = self._action_combos[i].currentData()
                if action and action != SyncAction.SKIP:
                    match.source_entry.action = action
                    match.dest_entry.action = action
        self._applied = True
        self.accept()

    @property
    def was_applied(self) -> bool:
        return self._applied
