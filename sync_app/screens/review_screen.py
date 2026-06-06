# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Review screen — diff summary, file list, filters, and action assignment.

Performance-optimized for 100k+ entries using QTableView + QAbstractTableModel
with custom delegates. Only visible rows are rendered (virtual scrolling).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTableView,
    QHeaderView,
    QGroupBox,
    QSizePolicy,
    QFrame,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QStackedWidget,
    QMessageBox,
    QCheckBox,
    QScrollArea,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QApplication,
    QAbstractItemView,
    QProgressBar,
)
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QUrl,
    QAbstractTableModel,
    QModelIndex,
    QTimer,
    QSortFilterProxyModel,
    QRect,
)
from PyQt6.QtGui import QColor, QDesktopServices, QPainter, QFont, QPen, QBrush
from PyQt6.QtWidgets import QStyle
import os
from datetime import datetime
from typing import Optional

from services.models import (
    ComparisonEntry,
    DiffType,
    FileEntry,
    SpaceCheckResult,
    SyncAction,
    SyncDirection,
    SyncPlan,
    ViewMode,
)
from services.session_manager import ReviewSession, SessionLoadResult
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.format_utils import format_size

DIFF_TYPE_COLORS = {
    DiffType.IDENTICAL: DesignSystem.COLOR_DIFF_IDENTICAL,
    DiffType.SOURCE_ONLY: DesignSystem.COLOR_DIFF_SOURCE_ONLY,
    DiffType.DEST_ONLY: DesignSystem.COLOR_DIFF_DEST_ONLY,
    DiffType.MODIFIED: DesignSystem.COLOR_DIFF_MODIFIED,
    DiffType.CONFLICT: DesignSystem.COLOR_DIFF_CONFLICT,
    DiffType.RENAMED: DesignSystem.COLOR_DIFF_RENAMED,
    DiffType.CASE_MISMATCH: DesignSystem.COLOR_DIFF_CASE_MISMATCH,
    DiffType.ERROR_SOURCE: DesignSystem.COLOR_DIFF_ERROR,
    DiffType.ERROR_DEST: DesignSystem.COLOR_DIFF_ERROR,
}

DIFF_TYPE_LABELS = {
    DiffType.IDENTICAL: "diff_types.identical",
    DiffType.SOURCE_ONLY: "diff_types.source_only",
    DiffType.DEST_ONLY: "diff_types.dest_only",
    DiffType.MODIFIED: "diff_types.modified",
    DiffType.CONFLICT: "diff_types.conflict",
    DiffType.RENAMED: "diff_types.renamed",
    DiffType.CASE_MISMATCH: "diff_types.case_mismatch",
    DiffType.ERROR_SOURCE: "diff_types.error_source",
    DiffType.ERROR_DEST: "diff_types.error_dest",
}

ACTION_CONFLICT_LABELS = {
    SyncAction.OVERWRITE_DEST: "conflict.choose_source",
    SyncAction.OVERWRITE_SOURCE: "conflict.choose_dest",
    SyncAction.KEEP_DEST: "conflict.choose_dest",
    SyncAction.KEEP_SOURCE: "conflict.choose_source",
    SyncAction.SKIP: "common.skip",
    SyncAction.MARK_REVIEW: "actions.mark_review",
}

ALLOWED_ACTIONS: dict[DiffType, list[SyncAction]] = {
    DiffType.IDENTICAL: [SyncAction.SKIP],
    DiffType.SOURCE_ONLY: [SyncAction.COPY_TO_DEST, SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.DEST_ONLY: [SyncAction.DELETE_FROM_DEST, SyncAction.MOVE_TO_TRASH, SyncAction.COPY_TO_SOURCE, SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.MODIFIED: [SyncAction.OVERWRITE_DEST, SyncAction.OVERWRITE_SOURCE, SyncAction.KEEP_DEST, SyncAction.KEEP_SOURCE, SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.CASE_MISMATCH: [SyncAction.OVERWRITE_DEST, SyncAction.OVERWRITE_SOURCE, SyncAction.KEEP_DEST, SyncAction.KEEP_SOURCE, SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.CONFLICT: [SyncAction.OVERWRITE_DEST, SyncAction.OVERWRITE_SOURCE, SyncAction.KEEP_DEST, SyncAction.KEEP_SOURCE, SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.RENAMED: [SyncAction.RENAME_IN_DEST, SyncAction.COPY_TO_DEST, SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.ERROR_SOURCE: [SyncAction.SKIP, SyncAction.MARK_REVIEW],
    DiffType.ERROR_DEST: [SyncAction.SKIP, SyncAction.MARK_REVIEW],
}

SUMMARY_KEY_TO_FILTER: dict[str, DiffType | str | None] = {
    "total": None,
    "identical": DiffType.IDENTICAL,
    "new_in_source": DiffType.SOURCE_ONLY,
    "modified": DiffType.MODIFIED,
    "dest_only": DiffType.DEST_ONLY,
    "case_mismatch": DiffType.CASE_MISMATCH,
    "conflict_pending": "conflict_pending",
    "conflict_managed": "conflict_managed",
    "renamed": DiffType.RENAMED,
    "error_source": DiffType.ERROR_SOURCE,
    "error_dest": DiffType.ERROR_DEST,
}


def _allowed_actions_for_diff(diff_type: DiffType) -> list[SyncAction]:
    return ALLOWED_ACTIONS.get(diff_type, [SyncAction.SKIP, SyncAction.MARK_REVIEW])


def _get_filter_chip_style(color: str, active: bool) -> str:
    if active:
        return (
            f"QPushButton {{ background-color: {color}; color: white; "
            f"border: 2px solid {color}; border-radius: {DesignSystem.RADIUS_FULL}px; "
            f"padding: 4px 14px; font-weight: bold; font-size: {DesignSystem.SIZE_SM}px; }}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
        )
    return (
        f"QPushButton {{ background-color: transparent; color: {color}; "
        f"border: 2px solid {color}; border-radius: {DesignSystem.RADIUS_FULL}px; "
        f"padding: 4px 14px; font-weight: bold; font-size: {DesignSystem.SIZE_SM}px; }}"
        f"QPushButton:hover {{ background-color: {color}; color: white; }}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Virtual table model — O(1) per visible row, no widget creation
# ═══════════════════════════════════════════════════════════════════════════════

COL_SOURCE = 0
COL_OPEN_SRC = 1
COL_STATUS = 2
COL_ACTION = 3
COL_DEST = 4
COL_OPEN_DEST = 5
COL_COMPARE = 6
NUM_COLUMNS = 7


class _ReviewTableModel(QAbstractTableModel):
    """Virtual model for ComparisonEntry list. Zero widget overhead."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[ComparisonEntry] = []
        self._base_source: str = ""
        self._base_dest: str = ""

    def set_data(self, entries: list[ComparisonEntry], base_source: str, base_dest: str) -> None:
        self.beginResetModel()
        self._entries = entries
        self._base_source = base_source
        self._base_dest = base_dest
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return NUM_COLUMNS

    def entry_at(self, row: int) -> ComparisonEntry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._entries):
            return None
        entry = self._entries[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_SOURCE:
                return entry.source.rel_path if entry.source else ""
            if col == COL_OPEN_SRC:
                return ""
            if col == COL_STATUS:
                if entry.diff_type == DiffType.CONFLICT:
                    if entry.action == SyncAction.MARK_REVIEW:
                        return tr("diff_types.conflict_pending")
                    return tr("diff_types.conflict_auto")
                return tr(DIFF_TYPE_LABELS.get(entry.diff_type, ""))
            if col == COL_ACTION:
                return tr(f"actions.{entry.action.value}")
            if col == COL_DEST:
                return entry.dest.rel_path if entry.dest else ""
            if col == COL_OPEN_DEST:
                return ""
            if col == COL_COMPARE:
                return ""
        elif role == Qt.ItemDataRole.UserRole:
            return entry
        elif role == Qt.ItemDataRole.UserRole + 1:
            if col == COL_SOURCE and entry.source:
                return format_size(entry.source.size)
            if col == COL_DEST and entry.dest:
                return format_size(entry.dest.size)
            return ""
        elif role == Qt.ItemDataRole.UserRole + 2:
            if col == COL_SOURCE and entry.source:
                return datetime.fromtimestamp(entry.source.mtime).strftime("%Y-%m-%d %H:%M")
            if col == COL_DEST and entry.dest:
                return datetime.fromtimestamp(entry.dest.mtime).strftime("%Y-%m-%d %H:%M")
            return ""
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == COL_SOURCE:
                return tr("review.source_file")
            if section == COL_OPEN_SRC:
                return ""
            if section == COL_STATUS:
                return tr("review.status")
            if section == COL_ACTION:
                return tr("review.action")
            if section == COL_DEST:
                return tr("review.dest_file")
            if section == COL_OPEN_DEST:
                return ""
            if section == COL_COMPARE:
                return ""
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == COL_ACTION:
            entry = self.entry_at(index.row())
            if entry and len(_allowed_actions_for_diff(entry.diff_type)) > 1:
                base |= Qt.ItemFlag.ItemIsEditable
        return base

    def notify_action_changed(self, row: int) -> None:
        idx_status = self.index(row, COL_STATUS)
        idx_action = self.index(row, COL_ACTION)
        self.dataChanged.emit(idx_status, idx_status, [Qt.ItemDataRole.DisplayRole])
        self.dataChanged.emit(idx_action, idx_action, [Qt.ItemDataRole.DisplayRole])


class _ReviewFilterProxy(QSortFilterProxyModel):
    """Filters entries by DiffType and search text without recreating widgets."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._diff_filter: DiffType | str | None = None
        self._search_text: str = ""
        self._hide_identical: bool = False

    def set_diff_filter(self, f: DiffType | str | None) -> None:
        self._diff_filter = f
        self.invalidateFilter()

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self.invalidateFilter()

    def set_hide_identical(self, hide: bool) -> None:
        self._hide_identical = hide
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        entry = model.entry_at(source_row)
        if entry is None:
            return False

        if self._hide_identical and entry.diff_type == DiffType.IDENTICAL:
            return False

        if self._diff_filter is not None:
            if self._diff_filter == "conflict_pending":
                if not (entry.diff_type == DiffType.CONFLICT and entry.action == SyncAction.MARK_REVIEW):
                    return False
            elif self._diff_filter == "conflict_managed":
                if not (entry.diff_type == DiffType.CONFLICT and entry.action != SyncAction.MARK_REVIEW):
                    return False
            else:
                if entry.diff_type != self._diff_filter:
                    return False

        if self._search_text:
            if self._search_text not in entry.rel_path.lower():
                return False

        return True


class _FileDelegate(QStyledItemDelegate):
    """Paints file info (path + name + size + date) directly — no widget creation."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        rect = option.rect.adjusted(8, 4, -8, -4)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(DesignSystem.COLOR_PRIMARY_LIGHT))

        rel_path = index.data(Qt.ItemDataRole.DisplayRole) or ""
        size_str = index.data(Qt.ItemDataRole.UserRole + 1) or ""
        date_str = index.data(Qt.ItemDataRole.UserRole + 2) or ""

        if not rel_path:
            painter.restore()
            return

        parts = rel_path.replace("\\", "/").rsplit("/", 1)
        folder = parts[0] if len(parts) > 1 else "/"
        name = parts[-1]

        top_rect = QRect(rect.x(), rect.y(), rect.width(), rect.height() // 2)
        bot_rect = QRect(rect.x(), rect.y() + rect.height() // 2, rect.width(), rect.height() // 2)

        painter.setPen(QColor(DesignSystem.COLOR_TEXT_SECONDARY))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, folder)

        painter.setPen(QColor(DesignSystem.COLOR_TEXT))
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        name_width = painter.fontMetrics().horizontalAdvance(name)
        painter.drawText(bot_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(DesignSystem.COLOR_TEXT_SECONDARY))
        meta = f"  {size_str}  {date_str}" if size_str else ""
        meta_rect = QRect(rect.x() + name_width + 8, bot_rect.y(), rect.width() - name_width - 8, bot_rect.height())
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        return option.rect.size() if option.rect.isValid() else super().sizeHint(option, index)


class _StatusDelegate(QStyledItemDelegate):
    """Paints status badge directly — colored pill with text."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        entry = index.data(Qt.ItemDataRole.UserRole)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(DesignSystem.COLOR_PRIMARY_LIGHT))

        if not text or entry is None:
            painter.restore()
            return

        if entry.diff_type == DiffType.CONFLICT and entry.action != SyncAction.MARK_REVIEW:
            color = QColor(DesignSystem.COLOR_SUCCESS)
        else:
            color = QColor(DIFF_TYPE_COLORS.get(entry.diff_type, DesignSystem.COLOR_TEXT))

        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text) + 20
        text_height = fm.height() + 8
        pill_rect = QRect(
            option.rect.center().x() - text_width // 2,
            option.rect.center().y() - text_height // 2,
            text_width,
            text_height,
        )

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(pill_rect, DesignSystem.RADIUS_SM, DesignSystem.RADIUS_SM)

        painter.setPen(QColor("white"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()


class _ActionDelegate(QStyledItemDelegate):
    """Paints action text; creates QComboBox editor on double-click/enter."""

    action_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        entry = index.data(Qt.ItemDataRole.UserRole)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(DesignSystem.COLOR_PRIMARY_LIGHT))

        painter.setPen(QColor(DesignSystem.COLOR_TEXT))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(option.rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, text)

        if entry and len(_allowed_actions_for_diff(entry.diff_type)) > 1:
            painter.setPen(QColor(DesignSystem.COLOR_TEXT_SECONDARY))
            font.setPointSize(7)
            painter.setFont(font)
            indicator_rect = QRect(option.rect.right() - 20, option.rect.top(), 16, option.rect.height())
            painter.drawText(indicator_rect, Qt.AlignmentFlag.AlignCenter, "\u25BC")

        painter.restore()

    def createEditor(self, parent, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return None
        allowed = _allowed_actions_for_diff(entry.diff_type)
        if len(allowed) <= 1:
            return None

        combo = QComboBox(parent)
        for action in allowed:
            combo.addItem(tr(f"actions.{action.value}"), action)
        combo.setStyleSheet(DesignSystem.get_combobox_style() + " min-height: 26px;")
        return combo

    def setEditorData(self, editor, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        allowed = _allowed_actions_for_diff(entry.diff_type)
        for i, action in enumerate(allowed):
            if action == entry.action:
                editor.setCurrentIndex(i)
                break

    def setModelData(self, editor, model, index):
        combo = editor
        action = combo.currentData()
        if action is None:
            return
        source_model = model
        if hasattr(model, 'sourceModel'):
            source_index = model.mapToSource(index)
            source_model = model.sourceModel()
            row = source_index.row()
        else:
            row = index.row()
        entry = source_model.entry_at(row)
        if entry and entry.action != action:
            entry.action = action
            source_model.notify_action_changed(row)
            widget = self.parent()
            while widget is not None:
                if hasattr(widget, '_on_action_changed'):
                    widget._on_action_changed()
                    break
                widget = widget.parent()


class _CompareDelegate(QStyledItemDelegate):
    """Paints a compare icon in the last column."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(DesignSystem.COLOR_PRIMARY_LIGHT))
        painter.setPen(QColor(DesignSystem.COLOR_PRIMARY))
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, "\U0001f50d")
        painter.restore()


class _OpenFileDelegate(QStyledItemDelegate):
    """Paints an open-file icon. Only shows when entry has a file on that side."""

    def __init__(self, side: str, parent=None) -> None:
        super().__init__(parent)
        self._side = side

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(DesignSystem.COLOR_PRIMARY_LIGHT))

        entry = index.data(Qt.ItemDataRole.UserRole)
        has_file = False
        if entry:
            if self._side == "source" and entry.source and not entry.source.is_dir:
                has_file = True
            elif self._side == "dest" and entry.dest and not entry.dest.is_dir:
                has_file = True

        if has_file:
            painter.setPen(QColor(DesignSystem.COLOR_TEXT_SECONDARY))
            font = painter.font()
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, "\u2197")
        painter.restore()


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewScreen — main widget
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewScreen(QWidget):
    """Screen showing scan results with diff summary, filters, and actions.

    Optimized for 100k+ entries: uses QTableView with virtual model and
    custom delegates. Only visible rows (~20-30) are rendered at any time.
    """

    sync_requested = pyqtSignal()
    resolve_conflicts_requested = pyqtSignal()
    back_requested = pyqtSignal()
    execute_requested = pyqtSignal()
    dry_run_requested = pyqtSignal()
    save_session_requested = pyqtSignal()
    load_session_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[ComparisonEntry] = []
        self._base_source = ""
        self._base_dest = ""
        self._view_mode = ViewMode.LIST
        self._current_filter: DiffType | str | None = None
        self._direction: SyncDirection = SyncDirection.UNIDIRECTIONAL
        self._plan: Optional[SyncPlan] = None
        self._dest_space: Optional[SpaceCheckResult] = None
        self._source_space: Optional[SpaceCheckResult] = None
        self._pending_conflicts: int = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(
            DesignSystem.SPACE_24, DesignSystem.SPACE_20,
            DesignSystem.SPACE_24, DesignSystem.SPACE_20,
        )

        layout.addLayout(self._create_title())
        layout.addWidget(self._create_summary_chips())

        self._loading_widget = self._create_loading_widget()
        layout.addWidget(self._loading_widget)
        self._loading_widget.setVisible(False)

        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setSpacing(DesignSystem.SPACE_8)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._create_filters())

        self._view_stack = QStackedWidget()
        self._view_stack.addWidget(self._create_table())
        self._view_stack.addWidget(self._create_tree())
        content_layout.addWidget(self._view_stack, stretch=1)

        self._view_toggle_btn = QToolButton(self._content_widget)
        icon_manager.set_button_icon(self._view_toggle_btn, "file-tree", color=DesignSystem.COLOR_TEXT_SECONDARY)
        self._view_toggle_btn.setStyleSheet(DesignSystem.get_icon_button_style())
        self._view_toggle_btn.setToolTip(tr("review.view_tree"))
        self._view_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_toggle_btn.setFixedSize(28, 28)
        self._view_toggle_btn.raise_()
        self._view_toggle_btn.clicked.connect(self._toggle_view_mode)

        layout.addWidget(self._content_widget, stretch=1)

        self._plan_scroll = QScrollArea()
        self._plan_scroll.setWidgetResizable(True)
        self._plan_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._plan_scroll.setWidget(self._create_plan_panel())
        self._plan_scroll.setVisible(False)
        layout.addWidget(self._plan_scroll, stretch=1)

        layout.addWidget(self._create_action_bar())

    def _create_loading_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(DesignSystem.SPACE_12)

        self._loading_label = QLabel(tr("review.loading_entries"))
        self._loading_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_LG}px; color: {DesignSystem.COLOR_TEXT}; font-weight: bold;"
        )
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._loading_label)

        self._loading_progress = QProgressBar()
        self._loading_progress.setStyleSheet(DesignSystem.get_progressbar_style())
        self._loading_progress.setRange(0, 0)
        self._loading_progress.setFixedWidth(400)
        layout.addWidget(self._loading_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self._loading_detail = QLabel("")
        self._loading_detail.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
        )
        self._loading_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._loading_detail)

        return w

    def _create_action_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        self._sync_btn = QPushButton(tr("review.sync"))
        self._sync_btn.setToolTip(tr("Proceder a la vista previa de ejecución con estos cambios"))
        self._sync_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        icon_manager.set_button_icon(self._sync_btn, "play")
        self._sync_btn.setMinimumWidth(200)
        self._sync_btn.setMinimumHeight(44)
        self._sync_btn.clicked.connect(self.sync_requested.emit)
        layout.addWidget(self._sync_btn)

        self._review_again_btn = QPushButton(tr("review.review_again"))
        self._review_again_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._review_again_btn, "eye-check")
        self._review_again_btn.setMinimumWidth(200)
        self._review_again_btn.setMinimumHeight(44)
        self._review_again_btn.clicked.connect(self._on_review_again)
        self._review_again_btn.setVisible(False)
        layout.addWidget(self._review_again_btn)

        self._dry_run_btn = QPushButton(tr("review.dry_run"))
        self._dry_run_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._dry_run_btn, "play-box-outline")
        self._dry_run_btn.clicked.connect(self.dry_run_requested.emit)
        self._dry_run_btn.setVisible(False)
        layout.addWidget(self._dry_run_btn)

        self._execute_btn = QPushButton(tr("review.execute"))
        self._execute_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        icon_manager.set_button_icon(self._execute_btn, "play")
        self._execute_btn.setMinimumHeight(44)
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        self._execute_btn.setVisible(False)
        layout.addWidget(self._execute_btn)

        return bar

    def _create_plan_panel(self) -> QWidget:
        self._plan_panel = QWidget()
        panel_layout = QVBoxLayout(self._plan_panel)
        panel_layout.setSpacing(DesignSystem.SPACE_16)
        panel_layout.setContentsMargins(
            DesignSystem.SPACE_8, DesignSystem.SPACE_8,
            DesignSystem.SPACE_8, DesignSystem.SPACE_8,
        )

        panel_layout.addWidget(self._create_summary_cards_panel())
        panel_layout.addWidget(self._create_empty_folders_banner())
        panel_layout.addWidget(self._create_pending_conflicts_banner())
        panel_layout.addWidget(self._create_space_check_panel())
        panel_layout.addWidget(self._create_destructive_warning_panel())
        panel_layout.addStretch()
        return self._plan_panel

    def _create_summary_cards_panel(self) -> QWidget:
        cards = QWidget()
        layout = QHBoxLayout(cards)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)

        self._plan_summary_labels: dict[str, QLabel] = {}
        categories = [
            ("copy_to_dest", DesignSystem.COLOR_PRIMARY, "actions.copy_to_dest"),
            ("copy_to_source", DesignSystem.COLOR_PRIMARY, "actions.copy_to_source"),
            ("overwrite_dest", DesignSystem.COLOR_DIFF_MODIFIED, "actions.overwrite_dest"),
            ("overwrite_source", DesignSystem.COLOR_DIFF_MODIFIED, "actions.overwrite_source"),
            ("delete_from_dest", DesignSystem.COLOR_DANGER, "actions.delete_from_dest"),
            ("move_to_trash", DesignSystem.COLOR_WARNING, "actions.move_to_trash"),
            ("rename_in_dest", DesignSystem.COLOR_DIFF_RENAMED, "actions.rename_in_dest"),
            ("keep_dest", DesignSystem.COLOR_DIFF_IDENTICAL, "actions.keep_dest"),
            ("keep_source", DesignSystem.COLOR_DIFF_IDENTICAL, "actions.keep_source"),
            ("skip", DesignSystem.COLOR_TEXT_SECONDARY, "actions.skip"),
            ("mark_review", DesignSystem.COLOR_DIFF_CONFLICT, "actions.mark_review"),
        ]

        for key, color, label_key in categories:
            card = QFrame()
            card.setStyleSheet(DesignSystem.get_metric_card_style())
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(
                DesignSystem.SPACE_4, DesignSystem.SPACE_4,
                DesignSystem.SPACE_4, DesignSystem.SPACE_4,
            )

            value_label = QLabel("0")
            value_label.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_LG}px; font-weight: bold; color: {color};"
            )
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(value_label)
            self._plan_summary_labels[key] = value_label

            text_label = QLabel(tr(label_key))
            text_label.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
            )
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_label.setWordWrap(True)
            card_layout.addWidget(text_label)

            layout.addWidget(card, stretch=1)

        return cards

    def _create_pending_conflicts_banner(self) -> QWidget:
        self._pending_banner = QFrame()
        self._pending_banner.setVisible(False)
        self._pending_banner.setStyleSheet(f"""
            QFrame {{
                background-color: #FFF3E0;
                border: 1px solid {DesignSystem.COLOR_WARNING};
                border-radius: {DesignSystem.RADIUS_MD}px;
            }}
        """)

        banner_layout = QVBoxLayout(self._pending_banner)
        banner_layout.setContentsMargins(
            DesignSystem.SPACE_16, DesignSystem.SPACE_12,
            DesignSystem.SPACE_16, DesignSystem.SPACE_12,
        )
        banner_layout.setSpacing(DesignSystem.SPACE_4)

        self._pending_label = QLabel("")
        self._pending_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; "
            f"color: {DesignSystem.COLOR_WARNING}; border: none; background: transparent;"
        )
        banner_layout.addWidget(self._pending_label)

        self._pending_hint = QLabel("")
        self._pending_hint.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_SM}px; "
            f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; background: transparent;"
        )
        self._pending_hint.setWordWrap(True)
        banner_layout.addWidget(self._pending_hint)

        return self._pending_banner

    def _create_empty_folders_banner(self) -> QWidget:
        self._empty_folders_banner = QFrame()
        self._empty_folders_banner.setVisible(False)
        self._empty_folders_banner.setStyleSheet(f"""
            QFrame {{
                background-color: #FFF3E0;
                border: 1px solid {DesignSystem.COLOR_WARNING};
                border-radius: {DesignSystem.RADIUS_MD}px;
            }}
        """)

        banner_layout = QVBoxLayout(self._empty_folders_banner)
        banner_layout.setContentsMargins(
            DesignSystem.SPACE_16, DesignSystem.SPACE_12,
            DesignSystem.SPACE_16, DesignSystem.SPACE_12,
        )
        banner_layout.setSpacing(DesignSystem.SPACE_8)

        self._empty_folders_label = QLabel("")
        self._empty_folders_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; "
            f"color: {DesignSystem.COLOR_WARNING}; border: none; background: transparent;"
        )
        self._empty_folders_label.setWordWrap(True)
        banner_layout.addWidget(self._empty_folders_label)

        self._empty_folders_scroll = QScrollArea()
        self._empty_folders_scroll.setWidgetResizable(True)
        self._empty_folders_scroll.setMaximumHeight(160)
        self._empty_folders_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._empty_folders_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._empty_folders_list = QWidget()
        self._empty_folders_list_layout = QVBoxLayout(self._empty_folders_list)
        self._empty_folders_list_layout.setContentsMargins(0, 0, 0, 0)
        self._empty_folders_list_layout.setSpacing(DesignSystem.SPACE_4)
        self._empty_folders_scroll.setWidget(self._empty_folders_list)
        banner_layout.addWidget(self._empty_folders_scroll)

        self._empty_folders_hint = QLabel("")
        self._empty_folders_hint.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_SM}px; "
            f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; background: transparent;"
        )
        self._empty_folders_hint.setWordWrap(True)
        banner_layout.addWidget(self._empty_folders_hint)

        return self._empty_folders_banner

    def _create_space_check_panel(self) -> QWidget:
        self._space_group = QGroupBox(tr("review.space_check"))
        self._space_group.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(self._space_group)
        layout.setSpacing(DesignSystem.SPACE_4)

        self._dest_space_label = QLabel("")
        self._dest_space_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
        self._dest_space_label.setVisible(False)
        layout.addWidget(self._dest_space_label)

        self._dest_space_warning_label = QLabel("")
        self._dest_space_warning_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; "
            f"color: {DesignSystem.COLOR_DANGER};"
        )
        self._dest_space_warning_label.setWordWrap(True)
        self._dest_space_warning_label.setVisible(False)
        layout.addWidget(self._dest_space_warning_label)

        self._source_space_label = QLabel("")
        self._source_space_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px;")
        self._source_space_label.setVisible(False)
        layout.addWidget(self._source_space_label)

        self._source_space_warning_label = QLabel("")
        self._source_space_warning_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; "
            f"color: {DesignSystem.COLOR_DANGER};"
        )
        self._source_space_warning_label.setWordWrap(True)
        self._source_space_warning_label.setVisible(False)
        layout.addWidget(self._source_space_warning_label)

        self._no_writes_label = QLabel(tr("review.space_no_writes"))
        self._no_writes_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"
        )
        self._no_writes_label.setVisible(False)
        layout.addWidget(self._no_writes_label)

        return self._space_group

    def _create_destructive_warning_panel(self) -> QWidget:
        self._destructive_widget = QFrame()
        self._destructive_widget.setVisible(False)
        layout = QVBoxLayout(self._destructive_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)

        self._destructive_label = QLabel("")
        self._destructive_label.setStyleSheet(DesignSystem.get_destructive_warning_style())
        self._destructive_label.setWordWrap(True)
        layout.addWidget(self._destructive_label)

        self._confirm_checkbox = QCheckBox("")
        self._confirm_checkbox.setStyleSheet(DesignSystem.get_checkbox_style())
        self._confirm_checkbox.stateChanged.connect(self._refresh_action_buttons)
        layout.addWidget(self._confirm_checkbox)

        return self._destructive_widget

    def show_plan_panel(
        self,
        plan: SyncPlan,
        dest_space: SpaceCheckResult,
        source_space: SpaceCheckResult,
        pending_conflicts: int,
        direction: SyncDirection,
    ) -> None:
        self._plan = plan
        self._dest_space = dest_space
        self._source_space = source_space
        self._pending_conflicts = pending_conflicts
        self._direction = direction
        self._content_widget.setVisible(False)
        self._plan_scroll.setVisible(True)
        self._sync_btn.setVisible(False)
        self._review_again_btn.setVisible(True)
        self._dry_run_btn.setVisible(True)
        self._execute_btn.setVisible(True)
        self._update_plan_panel()

    def _hide_plan_panel(self) -> None:
        self._plan = None
        self._dest_space = None
        self._source_space = None
        self._content_widget.setVisible(True)
        self._plan_scroll.setVisible(False)
        self._sync_btn.setVisible(True)
        self._review_again_btn.setVisible(False)
        self._dry_run_btn.setVisible(False)
        self._execute_btn.setVisible(False)

    def _on_review_again(self) -> None:
        self._hide_plan_panel()

    def apply_loaded_session_actions(self, session: ReviewSession) -> SessionLoadResult:
        from services.session_manager import apply_session_to_entries

        result = apply_session_to_entries(session, self._entries, ALLOWED_ACTIONS)
        self._update_summary()
        self._refresh_view()
        self._hide_plan_panel()
        return result

    def _update_plan_panel(self) -> None:
        if self._plan is None:
            return

        action_counts: dict[str, int] = {
            "copy_to_dest": 0, "copy_to_source": 0,
            "overwrite_dest": 0, "overwrite_source": 0,
            "delete_from_dest": 0, "move_to_trash": 0,
            "rename_in_dest": 0, "keep_dest": 0,
            "keep_source": 0, "skip": 0, "mark_review": 0,
        }

        for e in self._plan.entries:
            key = e.action.value
            if key in action_counts:
                action_counts[key] += 1

        for key, count in action_counts.items():
            if key in self._plan_summary_labels:
                self._plan_summary_labels[key].setText(str(count))

        delete_count = action_counts["delete_from_dest"]
        trash_count = action_counts["move_to_trash"]

        if self._pending_conflicts > 0:
            self._pending_label.setText(
                tr("review.pending_conflicts", count=self._pending_conflicts)
            )
            self._pending_hint.setText(tr("review.pending_conflicts_hint"))
            self._pending_banner.setVisible(True)
        else:
            self._pending_banner.setVisible(False)

        empty_source_count = len(getattr(self, '_source_empty_dirs', []))
        empty_dest_count = len(getattr(self, '_dest_empty_dirs', []))
        if empty_source_count > 0 or empty_dest_count > 0:
            parts = []
            if empty_source_count > 0:
                parts.append(tr("review.empty_folders_source", count=empty_source_count))
            if empty_dest_count > 0:
                parts.append(tr("review.empty_folders_dest", count=empty_dest_count))
            self._empty_folders_label.setText(" ".join(parts))
            self._empty_folders_hint.setText(tr("review.empty_folders_hint"))
            self._populate_empty_folders_list()
            self._empty_folders_banner.setVisible(True)
        else:
            self._empty_folders_banner.setVisible(False)

        dest = self._dest_space
        src = self._source_space
        dest_required = dest.required_bytes if dest else 0
        src_required = src.required_bytes if src else 0

        if dest is not None and dest_required > 0:
            self._dest_space_label.setText(
                tr("review.space_check_dest", free=format_size(dest.free_bytes), required=format_size(dest.required_bytes))
            )
            self._dest_space_label.setVisible(True)
            if not dest.sufficient:
                self._dest_space_warning_label.setText(
                    tr("review.space_insufficient_short", shortfall=format_size(dest.shortfall_bytes))
                )
                self._dest_space_warning_label.setVisible(True)
            else:
                self._dest_space_warning_label.setVisible(False)
        else:
            self._dest_space_label.setVisible(False)
            self._dest_space_warning_label.setVisible(False)

        if src is not None and src_required > 0:
            self._source_space_label.setText(
                tr("review.space_check_source", free=format_size(src.free_bytes), required=format_size(src.required_bytes))
            )
            self._source_space_label.setVisible(True)
            if not src.sufficient:
                self._source_space_warning_label.setText(
                    tr("review.space_insufficient_short", shortfall=format_size(src.shortfall_bytes))
                )
                self._source_space_warning_label.setVisible(True)
            else:
                self._source_space_warning_label.setVisible(False)
        else:
            self._source_space_label.setVisible(False)
            self._source_space_warning_label.setVisible(False)

        self._no_writes_label.setVisible(dest_required == 0 and src_required == 0)

        has_destructive = delete_count > 0 or trash_count > 0
        if has_destructive:
            if delete_count > 0 and trash_count > 0:
                destructive_text = tr(
                    "review.confirm_destructive_both",
                    delete_count=delete_count, trash_count=trash_count,
                )
                checkbox_text = tr(
                    "review.confirm_destructive_both_checkbox",
                    delete_count=delete_count, trash_count=trash_count,
                )
            elif trash_count > 0:
                destructive_text = tr(
                    "review.confirm_destructive_trash", count=trash_count,
                )
                checkbox_text = tr(
                    "review.confirm_destructive_trash_checkbox", count=trash_count,
                )
            else:
                destructive_text = tr(
                    "review.confirm_destructive_delete", count=delete_count,
                )
                checkbox_text = tr(
                    "review.confirm_destructive_delete_checkbox", count=delete_count,
                )
            self._destructive_label.setText(destructive_text)
            self._destructive_label.setVisible(True)
            self._confirm_checkbox.blockSignals(True)
            self._confirm_checkbox.setText(checkbox_text)
            self._confirm_checkbox.setChecked(False)
            self._confirm_checkbox.blockSignals(False)
            self._destructive_widget.setVisible(True)
        else:
            self._destructive_widget.setVisible(False)

        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        if self._plan is None:
            self._dry_run_btn.setEnabled(False)
            self._execute_btn.setEnabled(False)
            return

        dest_ok = (
            self._dest_space is None
            or self._dest_space.required_bytes == 0
            or self._dest_space.sufficient
        )
        src_ok = (
            self._source_space is None
            or self._source_space.required_bytes == 0
            or self._source_space.sufficient
        )
        space_ok = dest_ok and src_ok

        has_destructive = self._plan.total_delete_count > 0 or any(
            e.action == SyncAction.MOVE_TO_TRASH for e in self._plan.entries
        )
        confirmed = (
            self._confirm_checkbox.isChecked()
            if self._destructive_widget.isVisible()
            else True
        )

        self._dry_run_btn.setEnabled(space_ok)
        self._execute_btn.setEnabled(space_ok and (not has_destructive or confirmed))

    def _create_title(self) -> QHBoxLayout:
        header_row = QHBoxLayout()
        header_row.setSpacing(DesignSystem.SPACE_12)

        back_btn = QPushButton(tr("common.back"))
        back_btn.setToolTip(tr("Regresar a la configuración de sincronización"))
        back_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(back_btn, "arrow-left")
        back_btn.setMinimumHeight(36)
        back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(back_btn)

        title = QLabel(tr("review.title"))
        title.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_2XL}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        return header_row

    def _create_summary_chips(self) -> QWidget:
        chips_container = QWidget()
        layout = QHBoxLayout(chips_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)

        self._chip_buttons: dict[str, QPushButton] = {}
        self._chip_colors: dict[str, str] = {}
        categories = [
            ("total", DesignSystem.COLOR_TEXT, "review.total"),
            ("identical", DesignSystem.COLOR_DIFF_IDENTICAL, "review.identical"),
            ("new_in_source", DesignSystem.COLOR_DIFF_SOURCE_ONLY, "review.new_in_source"),
            ("modified", DesignSystem.COLOR_DIFF_MODIFIED, "review.modified"),
            ("dest_only", DesignSystem.COLOR_DIFF_DEST_ONLY, "review.dest_only"),
            ("case_mismatch", DesignSystem.COLOR_DIFF_CASE_MISMATCH, "review.case_mismatch"),
            ("conflict_pending", DesignSystem.COLOR_DIFF_CONFLICT, "review.conflict_pending"),
            ("conflict_managed", DesignSystem.COLOR_SUCCESS, "review.conflict_managed"),
            ("renamed", DesignSystem.COLOR_DIFF_RENAMED, "review.renamed"),
            ("error_source", DesignSystem.COLOR_DIFF_ERROR, "review.error_source"),
            ("error_dest", DesignSystem.COLOR_DIFF_ERROR, "review.error_dest"),
        ]

        for key, color, label_key in categories:
            btn = QPushButton(f"{tr(label_key)}: 0")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_get_filter_chip_style(color, False))
            btn.clicked.connect(lambda checked, k=key: self._on_chip_clicked(k))
            layout.addWidget(btn)
            self._chip_buttons[key] = btn
            self._chip_colors[key] = color

        info_btn = QToolButton()
        icon_manager.set_button_icon(info_btn, "information-outline", color=DesignSystem.COLOR_PRIMARY)
        info_btn.setStyleSheet(DesignSystem.get_icon_button_style())
        info_btn.setToolTip(tr("review.statuses_help_tooltip"))
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.clicked.connect(self._show_statuses_explanation)
        layout.addWidget(info_btn)

        layout.addStretch(1)

        return chips_container

    def _on_chip_clicked(self, key: str) -> None:
        target_filter = SUMMARY_KEY_TO_FILTER.get(key)
        if self._current_filter == target_filter:
            self._current_filter = None
        else:
            self._current_filter = target_filter

        for k, btn in self._chip_buttons.items():
            is_active = (SUMMARY_KEY_TO_FILTER.get(k) == self._current_filter and self._current_filter is not None)
            btn.setStyleSheet(_get_filter_chip_style(self._chip_colors[k], is_active))

        self._proxy_model.set_diff_filter(self._current_filter)

    def _create_filters(self) -> QWidget:
        filter_widget = QFrame()
        filter_widget.setStyleSheet(
            f"background-color: {DesignSystem.COLOR_SURFACE}; "
            f"border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT}; "
            f"border-radius: {DesignSystem.RADIUS_MD}px;"
        )
        layout = QHBoxLayout(filter_widget)
        layout.setContentsMargins(
            DesignSystem.SPACE_12, DesignSystem.SPACE_8,
            DesignSystem.SPACE_12, DesignSystem.SPACE_8,
        )
        layout.setSpacing(DesignSystem.SPACE_12)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("review.search_placeholder"))
        self._search_edit.setStyleSheet(
            DesignSystem.get_combobox_style() + f" min-width: 250px; font-size: {DesignSystem.SIZE_MD}px;"
        )
        self._search_edit.textChanged.connect(self._apply_search)
        layout.addWidget(self._search_edit)

        self._hide_identical_cb = QCheckBox(tr("review.hide_identical"))
        self._hide_identical_cb.setStyleSheet(DesignSystem.get_checkbox_style())
        self._hide_identical_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hide_identical_cb.stateChanged.connect(self._on_hide_identical_changed)
        layout.addWidget(self._hide_identical_cb)

        layout.addStretch(1)

        self._save_session_btn = QPushButton(tr("review.save_session"))
        self._save_session_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._save_session_btn, "content-save")
        self._save_session_btn.setToolTip(tr("review.save_session_tooltip"))
        self._save_session_btn.clicked.connect(self.save_session_requested.emit)
        self._save_session_btn.setEnabled(False)
        layout.addWidget(self._save_session_btn)

        self._load_session_btn = QPushButton(tr("review.load_session"))
        self._load_session_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        icon_manager.set_button_icon(self._load_session_btn, "folder-open-outline")
        self._load_session_btn.setToolTip(tr("review.load_session_tooltip"))
        self._load_session_btn.clicked.connect(self.load_session_requested.emit)
        layout.addWidget(self._load_session_btn)

        self._smart_match_btn = QPushButton(tr("smart_match.button"))
        self._smart_match_btn.setToolTip(tr("smart_match.button_tooltip"))
        self._smart_match_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: white;
                border: none;
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: {DesignSystem.SIZE_BASE}px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.COLOR_BORDER_LIGHT};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """)
        self._smart_match_btn.clicked.connect(self._open_smart_match)
        layout.addWidget(self._smart_match_btn)

        conflict_btn = QPushButton(tr("review.manual_review"))
        conflict_btn.setToolTip(tr("Abrir asistente paso a paso para resolver conflictos manualmente"))
        conflict_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_DIFF_MODIFIED};
                color: white;
                border: none;
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: {DesignSystem.SIZE_BASE}px;
            }}
            QPushButton:hover {{
                background-color: #E8700A;
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.COLOR_BORDER_LIGHT};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """)
        conflict_btn.clicked.connect(self.resolve_conflicts_requested.emit)
        self._conflict_btn = conflict_btn
        layout.addWidget(conflict_btn)

        return filter_widget

    def _create_table(self) -> QWidget:
        self._table_model = _ReviewTableModel(self)
        self._proxy_model = _ReviewFilterProxy(self)
        self._proxy_model.setSourceModel(self._table_model)

        self._table = QTableView()
        self._table.setModel(self._proxy_model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(52)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setStyleSheet(DesignSystem.get_table_style())
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_SOURCE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_OPEN_SRC, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_OPEN_SRC, 36)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_STATUS, 170)
        header.setSectionResizeMode(COL_ACTION, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_ACTION, 190)
        header.setSectionResizeMode(COL_DEST, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_OPEN_DEST, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_OPEN_DEST, 36)
        header.setSectionResizeMode(COL_COMPARE, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_COMPARE, 40)

        self._file_delegate = _FileDelegate(self._table)
        self._status_delegate = _StatusDelegate(self._table)
        self._action_delegate = _ActionDelegate(self._table)
        self._compare_delegate = _CompareDelegate(self._table)
        self._open_src_delegate = _OpenFileDelegate("source", self._table)
        self._open_dest_delegate = _OpenFileDelegate("dest", self._table)

        self._table.setItemDelegateForColumn(COL_SOURCE, self._file_delegate)
        self._table.setItemDelegateForColumn(COL_OPEN_SRC, self._open_src_delegate)
        self._table.setItemDelegateForColumn(COL_STATUS, self._status_delegate)
        self._table.setItemDelegateForColumn(COL_ACTION, self._action_delegate)
        self._table.setItemDelegateForColumn(COL_DEST, self._file_delegate)
        self._table.setItemDelegateForColumn(COL_OPEN_DEST, self._open_dest_delegate)
        self._table.setItemDelegateForColumn(COL_COMPARE, self._compare_delegate)

        self._table.clicked.connect(self._on_table_clicked)

        return self._table

    def _create_tree(self) -> QWidget:
        self._tree = QTreeWidget()
        self._tree.setColumnCount(10)
        self._tree.setHeaderLabels([
            tr("review.path"),
            tr("review.status"),
            tr("review.action"),
            tr("review.size_source"),
            tr("review.size_dest"),
            tr("review.date_source"),
            tr("review.date_dest"),
            "",
            "",
            "",
        ])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self._tree.header().resizeSection(7, 36)
        self._tree.header().setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self._tree.header().resizeSection(8, 36)
        self._tree.header().setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self._tree.header().resizeSection(9, 36)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tree.setStyleSheet(DesignSystem.get_table_style())

        return self._tree

    def set_base_paths(self, source: str, dest: str) -> None:
        self._base_source = source
        self._base_dest = dest

    def set_entries(self, entries: list[ComparisonEntry], source_empty_dirs: list[str] | None = None, dest_empty_dirs: list[str] | None = None) -> None:
        self._entries = entries
        self._source_empty_dirs = source_empty_dirs or []
        self._dest_empty_dirs = dest_empty_dirs or []
        count = len(entries)

        if count > 10000:
            self._content_widget.setVisible(False)
            self._loading_widget.setVisible(True)
            self._loading_label.setText(tr("review.loading_entries"))
            self._loading_detail.setText(
                f"{count:,} {tr('review.entries_to_load')}"
            )
            self._loading_progress.setRange(0, 0)
            QApplication.processEvents()

        self._update_summary()
        self._table_model.set_data(entries, self._base_source, self._base_dest)
        self._proxy_model.set_diff_filter(self._current_filter)

        if count > 10000:
            self._loading_widget.setVisible(False)
            self._content_widget.setVisible(True)

        self._save_session_btn.setEnabled(bool(entries))
        self._hide_plan_panel()

    def _on_action_changed(self) -> None:
        self._update_summary()
        self._hide_plan_panel()

    def _on_table_clicked(self, index: QModelIndex) -> None:
        col = index.column()
        if col == COL_COMPARE:
            source_index = self._proxy_model.mapToSource(index)
            entry = self._table_model.entry_at(source_index.row())
            if entry:
                self._show_unified_details(entry)
        elif col == COL_OPEN_SRC:
            source_index = self._proxy_model.mapToSource(index)
            entry = self._table_model.entry_at(source_index.row())
            if entry and entry.source and not entry.source.is_dir:
                self._open_file_with_default_app(self._base_source, entry.source.rel_path)
        elif col == COL_OPEN_DEST:
            source_index = self._proxy_model.mapToSource(index)
            entry = self._table_model.entry_at(source_index.row())
            if entry and entry.dest and not entry.dest.is_dir:
                self._open_file_with_default_app(self._base_dest, entry.dest.rel_path)

    def _open_folder(self, path: str) -> None:
        folder = os.path.dirname(path)
        if os.path.exists(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _open_file_with_default_app(self, base: str, rel_path: str) -> None:
        full_path = os.path.join(base, rel_path)
        if os.path.isfile(full_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))

    def _populate_empty_folders_list(self) -> None:
        while self._empty_folders_list_layout.count():
            item = self._empty_folders_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        source_dirs = getattr(self, '_source_empty_dirs', [])
        dest_dirs = getattr(self, '_dest_empty_dirs', [])

        for rel_path in source_dirs:
            row = QHBoxLayout()
            row.setSpacing(DesignSystem.SPACE_8)
            full_path = os.path.join(self._base_source, rel_path)
            label = QLabel(f"[{tr('common.source')}] {full_path}")
            label.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT}; border: none; background: transparent;"
            )
            label.setWordWrap(True)
            row.addWidget(label, stretch=1)
            open_btn = QPushButton("")
            open_btn.setFixedSize(24, 24)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            icon_manager.set_button_icon(open_btn, "folder-open", color=DesignSystem.COLOR_PRIMARY)
            open_btn.setStyleSheet(DesignSystem.get_icon_button_style())
            open_btn.setToolTip(tr("review.open_folder"))
            open_btn.clicked.connect(lambda _, p=full_path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            row.addWidget(open_btn)
            self._empty_folders_list_layout.addLayout(row)

        for rel_path in dest_dirs:
            row = QHBoxLayout()
            row.setSpacing(DesignSystem.SPACE_8)
            full_path = os.path.join(self._base_dest, rel_path)
            label = QLabel(f"[{tr('setup.destination')}] {full_path}")
            label.setStyleSheet(
                f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT}; border: none; background: transparent;"
            )
            label.setWordWrap(True)
            row.addWidget(label, stretch=1)
            open_btn = QPushButton("")
            open_btn.setFixedSize(24, 24)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            icon_manager.set_button_icon(open_btn, "folder-open", color=DesignSystem.COLOR_PRIMARY)
            open_btn.setStyleSheet(DesignSystem.get_icon_button_style())
            open_btn.setToolTip(tr("review.open_folder"))
            open_btn.clicked.connect(lambda _, p=full_path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            row.addWidget(open_btn)
            self._empty_folders_list_layout.addLayout(row)

        self._empty_folders_list_layout.addStretch()

    def _update_summary(self) -> None:
        counts: dict[str, int] = {
            "total": 0, "identical": 0, "new_in_source": 0,
            "modified": 0, "dest_only": 0, "case_mismatch": 0,
            "conflict_pending": 0, "conflict_managed": 0, "renamed": 0,
            "error_source": 0, "error_dest": 0,
        }
        counts["total"] = len(self._entries)
        for entry in self._entries:
            if entry.diff_type == DiffType.IDENTICAL:
                counts["identical"] += 1
            elif entry.diff_type == DiffType.SOURCE_ONLY:
                counts["new_in_source"] += 1
            elif entry.diff_type == DiffType.DEST_ONLY:
                counts["dest_only"] += 1
            elif entry.diff_type == DiffType.MODIFIED:
                counts["modified"] += 1
            elif entry.diff_type == DiffType.CASE_MISMATCH:
                counts["case_mismatch"] += 1
            elif entry.diff_type == DiffType.CONFLICT:
                if entry.action == SyncAction.MARK_REVIEW:
                    counts["conflict_pending"] += 1
                else:
                    counts["conflict_managed"] += 1
            elif entry.diff_type == DiffType.RENAMED:
                counts["renamed"] += 1
            elif entry.diff_type == DiffType.ERROR_SOURCE:
                counts["error_source"] += 1
            elif entry.diff_type == DiffType.ERROR_DEST:
                counts["error_dest"] += 1

        label_keys = {
            "total": "review.total", "identical": "review.identical",
            "new_in_source": "review.new_in_source", "modified": "review.modified",
            "dest_only": "review.dest_only", "case_mismatch": "review.case_mismatch",
            "conflict_pending": "review.conflict_pending",
            "conflict_managed": "review.conflict_managed", "renamed": "review.renamed",
            "error_source": "review.error_source", "error_dest": "review.error_dest",
        }
        for key, btn in self._chip_buttons.items():
            count = counts.get(key, 0)
            btn.setText(f"{tr(label_keys[key])}: {count}")

        has_conflicts = counts["conflict_pending"] > 0
        has_mark_review = any(e.action == SyncAction.MARK_REVIEW for e in self._entries)
        mark_review_count = sum(1 for e in self._entries if e.action == SyncAction.MARK_REVIEW)
        self._conflict_btn.setVisible(True)
        self._conflict_btn.setEnabled(has_mark_review)
        if mark_review_count > 0:
            self._conflict_btn.setText(f"{tr('review.manual_review')} ({mark_review_count})")
        else:
            self._conflict_btn.setText(tr("review.manual_review"))

        has_orphans = counts["new_in_source"] > 0 and counts["dest_only"] > 0
        self._smart_match_btn.setVisible(has_orphans)

    def _apply_search(self) -> None:
        text = self._search_edit.text()
        if self._view_mode == ViewMode.LIST:
            self._proxy_model.set_search_text(text)
        else:
            self._populate_tree()

    def _on_hide_identical_changed(self, state: int) -> None:
        hide = state == Qt.CheckState.Checked.value
        if self._view_mode == ViewMode.LIST:
            self._proxy_model.set_hide_identical(hide)
        else:
            self._populate_tree()

    def _refresh_view(self) -> None:
        self._table_model.set_data(self._entries, self._base_source, self._base_dest)
        self._proxy_model.set_diff_filter(self._current_filter)
        if self._view_mode == ViewMode.TREE:
            self._populate_tree()

    def _populate_tree(self) -> None:
        self._tree.clear()
        filtered = self._get_filtered_entries()

        if len(filtered) > 50000:
            self._tree.addTopLevelItem(
                QTreeWidgetItem([tr("review.tree_too_large"), "", "", "", "", "", "", ""])
            )
            return

        root = self._tree.invisibleRootItem()
        dirs: dict[str, QTreeWidgetItem] = {}

        for entry in filtered:
            parts = entry.rel_path.replace("\\", "/").split("/")
            parent_path = ""
            parent_item = root
            for i, part in enumerate(parts[:-1]):
                current_path = f"{parent_path}/{part}" if parent_path else part
                if current_path not in dirs:
                    dir_item = QTreeWidgetItem(parent_item, [part, "", "", "", "", "", "", ""])
                    dir_item.setExpanded(True)
                    icon = icon_manager.get_icon("folder", color=DesignSystem.COLOR_TEXT_SECONDARY)
                    if icon:
                        dir_item.setIcon(0, icon)
                    dirs[current_path] = dir_item
                parent_item = dirs[current_path]
                parent_path = current_path

            name = parts[-1]
            diff_label = tr(DIFF_TYPE_LABELS.get(entry.diff_type, ""))
            if entry.diff_type == DiffType.CONFLICT and entry.action != SyncAction.MARK_REVIEW:
                diff_label = tr("diff_types.conflict_resolved")

            src_size = format_size(entry.source.size) if entry.source else "\u2014"
            dst_size = format_size(entry.dest.size) if entry.dest else "\u2014"

            src_date = ""
            if entry.source:
                src_date = datetime.fromtimestamp(entry.source.mtime).strftime("%Y-%m-%d %H:%M")
            dst_date = ""
            if entry.dest:
                dst_date = datetime.fromtimestamp(entry.dest.mtime).strftime("%Y-%m-%d %H:%M")

            file_item = QTreeWidgetItem(parent_item, [name, diff_label, "", src_size, dst_size, src_date, dst_date, ""])

            color = DIFF_TYPE_COLORS.get(entry.diff_type, DesignSystem.COLOR_TEXT)
            if entry.diff_type == DiffType.CONFLICT and entry.action != SyncAction.MARK_REVIEW:
                color = DesignSystem.COLOR_SUCCESS
            file_item.setForeground(1, QColor(color))
            font = file_item.font(1)
            font.setBold(True)
            file_item.setFont(1, font)

            icon = icon_manager.get_icon("file-document-outline", color=DesignSystem.COLOR_TEXT_SECONDARY)
            if icon:
                file_item.setIcon(0, icon)

            action_combo = QComboBox()
            allowed = _allowed_actions_for_diff(entry.diff_type)
            for action in allowed:
                action_combo.addItem(tr(f"actions.{action.value}"), action)
            action_combo.setStyleSheet(DesignSystem.get_combobox_style() + " min-height: 26px;")
            current_idx = 0
            for i, action in enumerate(allowed):
                if action == entry.action:
                    current_idx = i
                    break
            action_combo.setCurrentIndex(current_idx)
            action_combo.currentIndexChanged.connect(
                lambda idx, e=entry, c=action_combo: self._update_entry_action_filtered(e, c, idx)
            )
            self._tree.setItemWidget(file_item, 2, action_combo)

            full_path = ""
            if entry.source and self._base_source:
                full_path = os.path.join(self._base_source, entry.rel_path)
            elif entry.dest and self._base_dest:
                full_path = os.path.join(self._base_dest, entry.rel_path)
            else:
                full_path = entry.rel_path
            file_item.setToolTip(0, full_path)

            compare_btn = QToolButton()
            icon_manager.set_button_icon(compare_btn, "file-compare", color=DesignSystem.COLOR_PRIMARY)
            compare_btn.setStyleSheet(DesignSystem.get_icon_button_style())
            compare_btn.setToolTip(tr("review.file_compare"))
            compare_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            compare_btn.setFixedSize(24, 24)
            compare_btn.clicked.connect(lambda _, e=entry: self._show_unified_details(e))
            self._tree.setItemWidget(file_item, 7, compare_btn)

            if entry.source and not entry.source.is_dir:
                open_src_btn = QToolButton()
                icon_manager.set_button_icon(open_src_btn, "open-in-new", color=DesignSystem.COLOR_TEXT_SECONDARY)
                open_src_btn.setStyleSheet(DesignSystem.get_icon_button_style())
                open_src_btn.setToolTip(tr("review.open_file") + " (src)")
                open_src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_src_btn.setFixedSize(24, 24)
                open_src_btn.clicked.connect(
                    lambda _, e=entry: self._open_file_with_default_app(self._base_source, e.source.rel_path)
                )
                self._tree.setItemWidget(file_item, 8, open_src_btn)

            if entry.dest and not entry.dest.is_dir:
                open_dst_btn = QToolButton()
                icon_manager.set_button_icon(open_dst_btn, "open-in-new", color=DesignSystem.COLOR_TEXT_SECONDARY)
                open_dst_btn.setStyleSheet(DesignSystem.get_icon_button_style())
                open_dst_btn.setToolTip(tr("review.open_file") + " (dest)")
                open_dst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_dst_btn.setFixedSize(24, 24)
                open_dst_btn.clicked.connect(
                    lambda _, e=entry: self._open_file_with_default_app(self._base_dest, e.dest.rel_path)
                )
                self._tree.setItemWidget(file_item, 9, open_dst_btn)

        self._tree.expandToDepth(0)

    def _get_filtered_entries(self) -> list[ComparisonEntry]:
        filtered = self._entries

        if self._hide_identical_cb.isChecked():
            filtered = [e for e in filtered if e.diff_type != DiffType.IDENTICAL]

        if self._current_filter is not None:
            if self._current_filter == "conflict_pending":
                filtered = [
                    e for e in filtered
                    if e.diff_type == DiffType.CONFLICT and e.action == SyncAction.MARK_REVIEW
                ]
            elif self._current_filter == "conflict_managed":
                filtered = [
                    e for e in filtered
                    if e.diff_type == DiffType.CONFLICT and e.action != SyncAction.MARK_REVIEW
                ]
            else:
                filtered = [e for e in filtered if e.diff_type == self._current_filter]

        search_text = self._search_edit.text().strip().lower()
        if search_text:
            filtered = [e for e in filtered if search_text in e.rel_path.lower()]
        return filtered

    def _update_entry_action_filtered(self, entry: ComparisonEntry, combo: QComboBox, index: int) -> None:
        action = combo.itemData(index)
        if action:
            entry.action = action
            self._hide_plan_panel()
            self._update_summary()

    def _toggle_view_mode(self) -> None:
        if self._view_mode == ViewMode.LIST:
            self._view_mode = ViewMode.TREE
            icon_manager.set_button_icon(self._view_toggle_btn, "list", color=DesignSystem.COLOR_TEXT_SECONDARY)
            self._view_toggle_btn.setToolTip(tr("review.view_list"))
            self._populate_tree()
            self._view_stack.setCurrentWidget(self._tree)
        else:
            self._view_mode = ViewMode.LIST
            icon_manager.set_button_icon(self._view_toggle_btn, "file-tree", color=DesignSystem.COLOR_TEXT_SECONDARY)
            self._view_toggle_btn.setToolTip(tr("review.view_tree"))
            self._view_stack.setCurrentWidget(self._table)

    def get_entries(self) -> list[ComparisonEntry]:
        return self._entries

    def _show_unified_details(self, entry: ComparisonEntry) -> None:
        from PyQt6.QtCore import Qt as QtCore_Qt
        from pathlib import Path
        from services.hasher import hash_file

        src = entry.source
        dst = entry.dest

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if src and not src.hash_sha256 and not src.is_dir:
                p = os.path.join(self._base_source, src.rel_path)
                if os.path.exists(p):
                    src.hash_sha256 = hash_file(Path(p))

            if dst and not dst.hash_sha256 and not dst.is_dir:
                p = os.path.join(self._base_dest, dst.rel_path)
                if os.path.exists(p):
                    dst.hash_sha256 = hash_file(Path(p))
        except Exception:
            pass
        finally:
            QApplication.restoreOverrideCursor()

        def format_hash(h: str) -> str:
            if not h or h == "N/A":
                return "N/A"
            return "<br>".join(h[i:i + 16] for i in range(0, len(h), 16))

        html = f"<h3>{tr('review.file_compare')}</h3>"
        html += "<table width='100%' border='1' cellspacing='0' cellpadding='8' style='border-collapse: collapse; border: 1px solid #ddd;'>"

        if src and dst:
            html += "<tr style='background-color: #f8f9fa;'><th>Atributo</th><th>Origen</th><th>Destino</th><th>Estado</th></tr>"

            path_match = src.rel_path == dst.rel_path
            path_icon = "\u2714\uFE0F" if path_match else "\u274C"
            html += f"<tr><td><b>Nombre/Ruta</b></td><td>{src.rel_path}</td><td>{dst.rel_path}</td><td align='center'>{path_icon}</td></tr>"

            size_match = src.size == dst.size
            size_icon = "\u2714\uFE0F" if size_match else "\u274C"
            html += f"<tr><td><b>{tr('conflict.size')}</b></td><td>{format_size(src.size)}</td><td>{format_size(dst.size)}</td><td align='center'>{size_icon}</td></tr>"

            mtime_match = int(src.mtime) == int(dst.mtime)
            date_icon = "\u2714\uFE0F" if mtime_match else "\u274C"
            src_date = datetime.fromtimestamp(src.mtime).strftime('%Y-%m-%d %H:%M:%S')
            dst_date = datetime.fromtimestamp(dst.mtime).strftime('%Y-%m-%d %H:%M:%S')
            html += f"<tr><td><b>{tr('conflict.modified_date')}</b></td><td>{src_date}</td><td>{dst_date}</td><td align='center'>{date_icon}</td></tr>"

            if src.hash_sha256 and dst.hash_sha256:
                hash_match = src.hash_sha256 == dst.hash_sha256
                hash_icon = "\u2714\uFE0F" if hash_match else "\u274C"
                html += f"<tr><td><b>{tr('conflict.hash')}</b></td><td>{format_hash(src.hash_sha256)}</td><td>{format_hash(dst.hash_sha256)}</td><td align='center'>{hash_icon}</td></tr>"
            else:
                html += f"<tr><td><b>{tr('conflict.hash')}</b></td><td>{format_hash(src.hash_sha256)}</td><td>{format_hash(dst.hash_sha256)}</td><td align='center'>-</td></tr>"
        else:
            fe = src if src else dst
            side_name = "Origen" if src else "Destino"
            html += f"<tr style='background-color: #f8f9fa;'><th>Atributo</th><th>{side_name}</th></tr>"
            html += f"<tr><td><b>Nombre/Ruta</b></td><td>{fe.rel_path}</td></tr>"
            html += f"<tr><td><b>{tr('conflict.size')}</b></td><td>{format_size(fe.size)}</td></tr>"
            date_str = datetime.fromtimestamp(fe.mtime).strftime('%Y-%m-%d %H:%M:%S')
            html += f"<tr><td><b>{tr('conflict.modified_date')}</b></td><td>{date_str}</td></tr>"
            html += f"<tr><td><b>{tr('conflict.hash')}</b></td><td>{format_hash(fe.hash_sha256)}</td></tr>"

        html += "</table><br>"

        msg = QMessageBox(self)
        msg.setWindowTitle(tr("review.file_compare"))
        msg.setText(html)
        msg.exec()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_view_toggle()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reposition_view_toggle()

    def _reposition_view_toggle(self) -> None:
        if hasattr(self, "_view_toggle_btn") and hasattr(self, "_view_stack"):
            stack_geom = self._view_stack.geometry()
            x = stack_geom.right() - self._view_toggle_btn.width() - 6
            y = stack_geom.top() + 6
            self._view_toggle_btn.move(x, y)
            self._view_toggle_btn.raise_()

    def _show_actions_explanation(self) -> None:
        from sync_app.dialogs.actions_help_dialog import ActionsHelpDialog
        dialog = ActionsHelpDialog(self)
        dialog.exec()

    def _show_statuses_explanation(self) -> None:
        from sync_app.dialogs.statuses_help_dialog import StatusesHelpDialog
        dialog = StatusesHelpDialog(self)
        dialog.exec()

    def _open_smart_match(self) -> None:
        from sync_app.dialogs.smart_match_dialog import SmartMatchDialog
        dialog = SmartMatchDialog(self._entries, parent=self, base_source=self._base_source, base_dest=self._base_dest)
        dialog.exec()
        if dialog.was_applied:
            self._update_summary()
            self._refresh_view()
            self._hide_plan_panel()
