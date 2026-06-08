# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
# noqa: E501
"""Setup screen — source/dest selection, unified presets, exclusion configuration."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QFrame,
    QFileDialog,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
    QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from config import Config
from services.models import (
    CompareMode,
    ConflictPolicy,
    ExclusionPreset,
    SyncAction,
    SyncDirection,
    SyncPreset,
    VerifyMode,
    SYNC_PRESET_CONFIGS,
)
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.format_utils import format_size
from services.disk_detector import detect_external_drives, get_all_drives, get_drive_for_path
from utils.settings_manager import settings_manager


class SetupScreen(QScrollArea):
    """Setup screen for configuring and starting a sync operation."""

    analyze_requested = pyqtSignal()
    source_changed = pyqtSignal(str)
    dest_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._selected_preset = SyncPreset.MIRROR_SAFE
        self._current_direction = SyncDirection.UNIDIRECTIONAL
        self._source_path = ""
        self._dest_path = ""
        self._active_exclusion_presets: list[ExclusionPreset] = [
            ExclusionPreset.SYSTEM_FILES,
            ExclusionPreset.TRASH_FOLDERS,
        ]
        self._custom_exclusions: list[str] = []

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(DesignSystem.SPACE_16)
        main_layout.setContentsMargins(
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
        )

        # Columns row
        content_row = QHBoxLayout()
        content_row.setSpacing(DesignSystem.SPACE_20)

        # Left Column (Paths & Presets)
        left_col = QVBoxLayout()
        left_col.setSpacing(DesignSystem.SPACE_12)

        self._paths_card = self._create_paths_card()
        left_col.addWidget(self._paths_card)

        self._presets_card = self._create_presets_card()
        left_col.addWidget(self._presets_card)
        left_col.addStretch()

        left_col_widget = QWidget()
        left_col_widget.setLayout(left_col)
        left_col_widget.setMinimumWidth(440)
        left_col_widget.setMaximumWidth(460)

        # Right Column (Tab widget for advanced & exclusions)
        right_col = QVBoxLayout()
        right_col.setSpacing(DesignSystem.SPACE_12)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(DesignSystem.get_tab_widget_style())

        # Tab 1: Advanced settings
        self._adv_tab_widget = self._create_advanced_config()
        self._tabs.addTab(self._adv_tab_widget, tr("setup.advanced_settings"))

        # Tab 2: Exclusions
        self._exc_tab_widget = self._create_exclusions_panel()
        self._tabs.addTab(self._exc_tab_widget, tr("setup.exclusions"))

        right_col.addWidget(self._tabs)
        right_col.addStretch()

        right_col_widget = QWidget()
        right_col_widget.setLayout(right_col)

        content_row.addWidget(left_col_widget, stretch=1)
        content_row.addWidget(right_col_widget, stretch=1)
        main_layout.addLayout(content_row)

        # Bottom Bar (Analyze button only)
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self._analyze_btn = self._create_analyze_button()
        self._analyze_btn.setMinimumWidth(200)
        bottom_bar.addWidget(self._analyze_btn)
        main_layout.addLayout(bottom_bar)

        self.setWidgetResizable(True)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
                border: none;
            }}
        """)
        self.setWidget(container)

        self._select_preset(SyncPreset.MIRROR_SAFE)
        self._load_last_paths()
        self._update_analyze_button_state()

    # ── Paths Card ─────────────────────────────────────────────────────

    def _create_paths_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(DesignSystem.SPACE_16, DesignSystem.SPACE_12, DesignSystem.SPACE_16, DesignSystem.SPACE_12)
        layout.setSpacing(DesignSystem.SPACE_6)

        # Source Section (with colored left accent)
        src_frame = QFrame()
        src_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border: none;
                border-left: 3px solid {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: 0px;
            }}
        """)
        src_frame_layout = QVBoxLayout(src_frame)
        src_frame_layout.setContentsMargins(DesignSystem.SPACE_10, DesignSystem.SPACE_8, DesignSystem.SPACE_10, DesignSystem.SPACE_8)
        src_frame_layout.setSpacing(DesignSystem.SPACE_6)

        src_header = QHBoxLayout()
        src_header.setSpacing(DesignSystem.SPACE_6)
        src_icon = QLabel()
        icon_s = icon_manager.get_icon("mdi6.folder-upload", color=DesignSystem.COLOR_PRIMARY)
        if icon_s:
            src_icon.setPixmap(icon_s.pixmap(16, 16))
        src_header.addWidget(src_icon)
        src_title = QLabel(tr("setup.source"))
        src_title.setStyleSheet(f"font-weight: bold; color: {DesignSystem.COLOR_PRIMARY}; font-size: {DesignSystem.SIZE_SM}px; background: transparent; border: none;")
        src_header.addWidget(src_title)
        self._source_drive_label = QLabel("")
        self._source_drive_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_PRIMARY}; background: transparent; border: none;"
        )
        self._source_drive_label.setVisible(False)
        src_header.addWidget(self._source_drive_label)
        src_header.addStretch()
        src_frame_layout.addLayout(src_header)

        src_row = QHBoxLayout()
        src_row.setSpacing(DesignSystem.SPACE_6)
        self._source_edit = QComboBox()
        self._source_edit.setEditable(True)
        self._source_edit.setPlaceholderText(tr("setup.select_source"))
        history = settings_manager.get_path_history()
        if history:
            self._source_edit.addItems(history)
        self._source_edit.setCurrentText("")
        self._source_edit.setStyleSheet(DesignSystem.get_combobox_style())
        self._source_edit.currentTextChanged.connect(self._update_analyze_button_state)
        src_row.addWidget(self._source_edit, stretch=1)

        source_browse = QPushButton()
        source_browse.setIcon(icon_manager.get_icon("mdi6.folder-open"))
        source_browse.setToolTip(tr("setup.select_source"))
        source_browse.setStyleSheet(DesignSystem.get_secondary_button_style())
        source_browse.setFixedSize(30, 30)
        source_browse.clicked.connect(self._browse_source)
        src_row.addWidget(source_browse)

        source_disk = QPushButton()
        source_disk.setIcon(icon_manager.get_icon("mdi6.harddisk"))
        source_disk.setToolTip(tr("setup.detected_disks"))
        source_disk.setStyleSheet(DesignSystem.get_secondary_button_style())
        source_disk.setFixedSize(30, 30)
        source_disk.clicked.connect(lambda: self._select_disk("source"))
        src_row.addWidget(source_disk)
        src_frame_layout.addLayout(src_row)

        layout.addWidget(src_frame)

        # Swap button (centered between source and dest)
        swap_layout = QHBoxLayout()
        swap_layout.setContentsMargins(0, 0, 0, 0)
        swap_layout.addStretch()

        self._invert_btn = QPushButton()
        self._invert_btn.setFixedSize(32, 32)
        self._invert_btn.setToolTip(tr("setup.swap_paths"))
        self._invert_btn.setIcon(icon_manager.get_icon("mdi6.swap-vertical", color=DesignSystem.COLOR_PRIMARY))
        self._invert_btn.setIconSize(QSize(16, 16))
        self._invert_btn.clicked.connect(self._invert_paths)

        swap_layout.addWidget(self._invert_btn)
        swap_layout.addStretch()
        layout.addLayout(swap_layout)

        # Destination Section (with colored left accent)
        dst_frame = QFrame()
        dst_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #EBF7EE;
                border: none;
                border-left: 3px solid {DesignSystem.COLOR_SUCCESS};
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: 0px;
            }}
        """)
        dst_frame_layout = QVBoxLayout(dst_frame)
        dst_frame_layout.setContentsMargins(DesignSystem.SPACE_10, DesignSystem.SPACE_8, DesignSystem.SPACE_10, DesignSystem.SPACE_8)
        dst_frame_layout.setSpacing(DesignSystem.SPACE_6)

        dst_header = QHBoxLayout()
        dst_header.setSpacing(DesignSystem.SPACE_6)
        dst_icon = QLabel()
        icon_d = icon_manager.get_icon("mdi6.folder-download", color=DesignSystem.COLOR_SUCCESS)
        if icon_d:
            dst_icon.setPixmap(icon_d.pixmap(16, 16))
        dst_header.addWidget(dst_icon)
        dst_title = QLabel(tr("setup.destination"))
        dst_title.setStyleSheet(f"font-weight: bold; color: {DesignSystem.COLOR_SUCCESS}; font-size: {DesignSystem.SIZE_SM}px; background: transparent; border: none;")
        dst_header.addWidget(dst_title)
        self._dest_drive_label = QLabel("")
        self._dest_drive_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_SUCCESS}; background: transparent; border: none;"
        )
        self._dest_drive_label.setVisible(False)
        dst_header.addWidget(self._dest_drive_label)
        dst_header.addStretch()
        dst_frame_layout.addLayout(dst_header)

        dst_row = QHBoxLayout()
        dst_row.setSpacing(DesignSystem.SPACE_6)
        self._dest_edit = QComboBox()
        self._dest_edit.setEditable(True)
        self._dest_edit.setPlaceholderText(tr("setup.select_dest"))
        if history:
            self._dest_edit.addItems(history)
        self._dest_edit.setCurrentText("")
        self._dest_edit.setStyleSheet(DesignSystem.get_combobox_style())
        self._dest_edit.currentTextChanged.connect(self._update_analyze_button_state)
        dst_row.addWidget(self._dest_edit, stretch=1)

        dest_browse = QPushButton()
        dest_browse.setIcon(icon_manager.get_icon("mdi6.folder-open"))
        dest_browse.setToolTip(tr("setup.select_dest"))
        dest_browse.setStyleSheet(DesignSystem.get_secondary_button_style())
        dest_browse.setFixedSize(30, 30)
        dest_browse.clicked.connect(self._browse_dest)
        dst_row.addWidget(dest_browse)

        dest_disk = QPushButton()
        dest_disk.setIcon(icon_manager.get_icon("mdi6.harddisk"))
        dest_disk.setToolTip(tr("setup.detected_disks"))
        dest_disk.setStyleSheet(DesignSystem.get_secondary_button_style())
        dest_disk.setFixedSize(30, 30)
        dest_disk.clicked.connect(lambda: self._select_disk("dest"))
        dst_row.addWidget(dest_disk)
        dst_frame_layout.addLayout(dst_row)

        layout.addWidget(dst_frame)

        return card

    def _invert_paths(self) -> None:
        src = self.get_source_path()
        dst = self.get_dest_path()
        self._source_edit.setCurrentText(dst)
        self._dest_edit.setCurrentText(src)
        self._source_path = dst
        self._dest_path = src
        self.source_changed.emit(dst)
        self.dest_changed.emit(src)
        self._update_analyze_button_state()

    def _select_disk(self, purpose: str) -> None:
        from sync_app.dialogs.disk_selector_dialog import DiskSelectorDialog
        dialog = DiskSelectorDialog(purpose=purpose, parent=self)
        def on_selected(mount_point: str, label: str):
            if purpose == "source":
                self._source_edit.setCurrentText(mount_point)
                self._source_path = mount_point
                self.source_changed.emit(mount_point)
            elif purpose == "dest":
                self._dest_edit.setCurrentText(mount_point)
                self._dest_path = mount_point
                self.dest_changed.emit(mount_point)
            self._update_analyze_button_state()
        dialog.disk_selected.connect(on_selected)
        dialog.exec()

    # ── Presets Card ────────────────────────────────────────────────────

    def _create_presets_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(DesignSystem.get_card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(DesignSystem.SPACE_16, DesignSystem.SPACE_12, DesignSystem.SPACE_16, DesignSystem.SPACE_12)
        layout.setSpacing(DesignSystem.SPACE_8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(DesignSystem.SPACE_8)
        preset_icon = QLabel()
        icon = icon_manager.get_icon("mdi6.sync", color=DesignSystem.COLOR_PRIMARY)
        if icon:
            preset_icon.setPixmap(icon.pixmap(20, 20))
        header.addWidget(preset_icon)
        
        title = QLabel(tr("setup.sync_type"))
        title.setStyleSheet(f"font-size: {DesignSystem.SIZE_MD}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self._preset_buttons: dict[SyncPreset, QPushButton] = {}
        preset_btn_spacing = DesignSystem.SPACE_6

        # Subtitle Unidirectional
        uni_label = QLabel(tr("directions.unidirectional").split(" (")[0] + " (→)")
        uni_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; font-weight: bold; color: {DesignSystem.COLOR_PRIMARY}; margin-top: 4px;")
        layout.addWidget(uni_label)

        # Unidirectional Grid (2x2)
        uni_grid = QGridLayout()
        uni_grid.setSpacing(preset_btn_spacing)
        
        unidirectional_presets_data = [
            (SyncPreset.MIRROR_SAFE, "presets.mirror_safe", "mdi6.shield-check"),
            (SyncPreset.MIRROR_EXACT, "presets.mirror_exact", "mdi6.mirror"),
            (SyncPreset.COPY_ONLY, "presets.copy_only", "mdi6.content-copy"),
            (SyncPreset.MIRROR_HASH, "presets.mirror_hash", "mdi6.shield-lock"),
        ]
        
        for idx, (preset, desc_key, icon_name) in enumerate(unidirectional_presets_data):
            row, col = divmod(idx, 2)
            btn = QPushButton(tr(desc_key))
            btn.setIcon(icon_manager.get_icon(icon_name))
            btn.setToolTip(tr(f"{desc_key}_desc"))
            btn.setCheckable(True)
            btn.setMinimumHeight(38)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(self._get_subtle_preset_style())
            btn.clicked.connect(lambda checked, p=preset: self._select_preset(p))
            self._preset_buttons[preset] = btn
            uni_grid.addWidget(btn, row, col)
            
        layout.addLayout(uni_grid)

        # Subtitle Bidirectional
        bi_label = QLabel(tr("directions.bidirectional").split(" (")[0] + " (⇄)")
        bi_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; font-weight: bold; color: {DesignSystem.COLOR_SUCCESS}; margin-top: 4px;")
        layout.addWidget(bi_label)

        # Bidirectional Grid (2x2 with colSpan 2 on the third button to avoid clipping)
        bi_grid = QGridLayout()
        bi_grid.setSpacing(preset_btn_spacing)

        bidirectional_presets_data = [
            (SyncPreset.TWO_WAY_SAFE, "presets.two_way_safe", "mdi6.swap-horizontal"),
            (SyncPreset.TWO_WAY_EXACT, "presets.two_way_exact", "mdi6.swap-horizontal-bold"),
            (SyncPreset.TWO_WAY_HASH, "presets.two_way_hash", "mdi6.swap-horizontal-circle"),
        ]

        # First two buttons in Row 0
        for idx in range(2):
            preset, desc_key, icon_name = bidirectional_presets_data[idx]
            btn = QPushButton(tr(desc_key))
            btn.setIcon(icon_manager.get_icon(icon_name))
            btn.setToolTip(tr(f"{desc_key}_desc"))
            btn.setCheckable(True)
            btn.setMinimumHeight(38)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(self._get_subtle_preset_style())
            btn.clicked.connect(lambda checked, p=preset: self._select_preset(p))
            self._preset_buttons[preset] = btn
            bi_grid.addWidget(btn, 0, idx)

        # Third button in Row 1, spanning both columns (0 and 1)
        preset, desc_key, icon_name = bidirectional_presets_data[2]
        btn = QPushButton(tr(desc_key))
        btn.setIcon(icon_manager.get_icon(icon_name))
        btn.setToolTip(tr(f"{desc_key}_desc"))
        btn.setCheckable(True)
        btn.setMinimumHeight(38)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(self._get_subtle_preset_style())
        btn.clicked.connect(lambda checked, p=preset: self._select_preset(p))
        self._preset_buttons[preset] = btn
        bi_grid.addWidget(btn, 1, 0, 1, 2)

        layout.addLayout(bi_grid)

        # Custom Separator
        line_p = QFrame()
        line_p.setFrameShape(QFrame.Shape.HLine)
        line_p.setFrameShadow(QFrame.Shadow.Plain)
        line_p.setFixedHeight(1)
        line_p.setStyleSheet(f"border: none; background-color: {DesignSystem.COLOR_BORDER_LIGHT};")
        layout.addWidget(line_p)

        # Custom standalone button
        custom_btn = QPushButton(tr("presets.custom"))
        custom_btn.setIcon(icon_manager.get_icon("mdi6.tune-variant"))
        custom_btn.setToolTip(tr("presets.custom_desc"))
        custom_btn.setCheckable(True)
        custom_btn.setMinimumHeight(40)
        custom_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        custom_btn.setStyleSheet(self._get_custom_preset_style())
        custom_btn.clicked.connect(lambda checked: self._select_preset(SyncPreset.CUSTOM))
        self._preset_buttons[SyncPreset.CUSTOM] = custom_btn
        layout.addWidget(custom_btn)

        # Preset description (inline, no border)
        self._preset_desc_label = QLabel()
        self._preset_desc_label.setWordWrap(True)
        self._preset_desc_label.setStyleSheet(f"""
            QLabel {{
                font-size: {DesignSystem.SIZE_SM}px;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                padding: {DesignSystem.SPACE_4}px 0px;
                background-color: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._preset_desc_label)

        return card

    def _get_subtle_preset_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_6}px {DesignSystem.SPACE_8}px;
                font-size: 12px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
                color: {DesignSystem.COLOR_TEXT};
                border-color: {DesignSystem.COLOR_BORDER};
            }}
            QPushButton:checked {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                color: {DesignSystem.COLOR_PRIMARY};
                border-color: {DesignSystem.COLOR_PRIMARY};
                font-weight: bold;
            }}
        """

    def _get_custom_preset_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {DesignSystem.COLOR_PRIMARY};
                border: 1.5px dashed {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_12}px;
                font-size: {DesignSystem.SIZE_SM}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border-style: solid;
            }}
            QPushButton:checked {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: white;
                border-style: solid;
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
        """

    # ── Advanced Config (Tab 1 Content) ──────────────────────────────────

    def _create_advanced_config(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
        )
        grid.setSpacing(DesignSystem.SPACE_12)

        # Column Stretch
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)

        # Row 0: Direction
        direction_label = QLabel(tr("setup.custom_direction"))
        direction_label.setStyleSheet("font-weight: bold;")
        self._dir_uni_radio = QRadioButton(tr("setup.custom_direction_uni"))
        self._dir_bi_radio = QRadioButton(tr("setup.custom_direction_bi"))
        self._dir_uni_radio.setChecked(True)
        self._direction_group = QButtonGroup(self)
        self._direction_group.addButton(self._dir_uni_radio, 0)
        self._direction_group.addButton(self._dir_bi_radio, 1)
        self._direction_group.idToggled.connect(self._on_direction_radio_changed)

        dir_layout = QHBoxLayout()
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(DesignSystem.SPACE_12)
        dir_layout.addWidget(self._dir_uni_radio)
        dir_layout.addWidget(self._dir_bi_radio)
        dir_layout.addStretch()

        grid.addWidget(direction_label, 0, 0)
        grid.addWidget(self._create_info_btn("info.direction_title", "info.direction_text"), 0, 1)
        grid.addLayout(dir_layout, 0, 2)

        # Row 1: Compare Mode
        compare_label = QLabel(tr("setup.compare_mode"))
        compare_label.setStyleSheet("font-weight: bold;")
        self._compare_combo = QComboBox()
        self._compare_combo.addItems([
            tr("compare_modes.fast"),
            tr("compare_modes.smart"),
            tr("compare_modes.full_hash"),
        ])
        self._compare_combo.setItemData(0, tr("compare_modes.fast_desc"), Qt.ItemDataRole.ToolTipRole)
        self._compare_combo.setItemData(1, tr("compare_modes.smart_desc"), Qt.ItemDataRole.ToolTipRole)
        self._compare_combo.setItemData(2, tr("compare_modes.full_hash_desc"), Qt.ItemDataRole.ToolTipRole)
        self._compare_combo.setCurrentIndex(1)
        self._compare_combo.setToolTip(tr("compare_modes.smart_desc"))
        self._compare_combo.currentIndexChanged.connect(
            lambda idx: self._compare_combo.setToolTip(
                self._compare_combo.itemData(idx, Qt.ItemDataRole.ToolTipRole)
            )
        )
        self._compare_combo.currentIndexChanged.connect(self._on_compare_mode_changed)
        self._compare_combo.setStyleSheet(DesignSystem.get_combobox_style())

        grid.addWidget(compare_label, 1, 0)
        grid.addWidget(self._create_info_btn("info.compare_mode_title", "info.compare_mode_text"), 1, 1)
        grid.addWidget(self._compare_combo, 1, 2)

        # Row 2: Precompute Hashes
        precompute_label = QLabel(tr("setup.precompute_hashes"))
        precompute_label.setStyleSheet("font-weight: bold;")
        self._precompute_hashes_checkbox = QCheckBox(tr("setup.precompute_hashes"))
        self._precompute_hashes_checkbox.setToolTip(tr("setup.precompute_hashes_desc"))
        self._precompute_hashes_checkbox.setStyleSheet(DesignSystem.get_checkbox_style())

        grid.addWidget(precompute_label, 2, 0)
        grid.addWidget(self._create_info_btn("info.precompute_hashes_title", "info.precompute_hashes_text"), 2, 1)
        grid.addWidget(self._precompute_hashes_checkbox, 2, 2)

        # Row 3: Conflict Policy
        conflict_label = QLabel(tr("setup.conflict_policy"))
        conflict_label.setStyleSheet("font-weight: bold;")
        self._conflict_combo = QComboBox()
        self._conflict_combo.setStyleSheet(DesignSystem.get_combobox_style())

        grid.addWidget(conflict_label, 3, 0)
        grid.addWidget(self._create_info_btn("info.conflict_policy_title", "info.conflict_policy_text"), 3, 1)
        grid.addWidget(self._conflict_combo, 3, 2)

        # Row 4: Dest-only Action
        dest_only_label = QLabel(tr("setup.dest_only_action"))
        dest_only_label.setStyleSheet("font-weight: bold;")
        self._dest_only_combo = QComboBox()
        self._dest_only_combo.setStyleSheet(DesignSystem.get_combobox_style())

        grid.addWidget(dest_only_label, 4, 0)
        grid.addWidget(self._create_info_btn("info.dest_only_action_title", "info.dest_only_action_text"), 4, 1)
        grid.addWidget(self._dest_only_combo, 4, 2)

        # Row 5: Verify Mode
        verify_label = QLabel(tr("setup.verify_mode"))
        verify_label.setStyleSheet("font-weight: bold;")
        self._verify_combo = QComboBox()
        self._verify_combo.addItems([
            tr("verify_modes.off"),
            tr("verify_modes.spot_check"),
            tr("verify_modes.full"),
        ])
        self._verify_combo.setCurrentIndex(2)
        self._verify_combo.setStyleSheet(DesignSystem.get_combobox_style())

        grid.addWidget(verify_label, 5, 0)
        grid.addWidget(self._create_info_btn("info.verify_mode_title", "info.verify_mode_text"), 5, 1)
        grid.addWidget(self._verify_combo, 5, 2)

        # Row 6: Use Trash
        trash_label = QLabel(tr("setup.use_trash"))
        trash_label.setStyleSheet("font-weight: bold;")
        self._trash_checkbox = QCheckBox(tr("setup.use_trash"))
        self._trash_checkbox.setChecked(True)
        self._trash_checkbox.setStyleSheet(DesignSystem.get_checkbox_style())

        grid.addWidget(trash_label, 6, 0)
        grid.addWidget(self._create_info_btn("info.use_trash_title", "info.use_trash_text"), 6, 1)
        grid.addWidget(self._trash_checkbox, 6, 2)

        self._populate_conflict_combo(SyncDirection.UNIDIRECTIONAL)
        self._populate_dest_only_combo(SyncDirection.UNIDIRECTIONAL)

        return container

    def _populate_conflict_combo(self, direction: SyncDirection) -> None:
        options = CONFLICT_OPTIONS_BI if direction == SyncDirection.BIDIRECTIONAL else CONFLICT_OPTIONS_UNI
        self._conflict_combo.blockSignals(True)
        self._conflict_combo.clear()
        for label_key, policy, action in options:
            self._conflict_combo.addItem(tr(label_key), (policy, action))
        self._conflict_combo.blockSignals(False)

    def _populate_dest_only_combo(self, direction: SyncDirection) -> None:
        self._dest_only_combo.blockSignals(True)
        self._dest_only_combo.clear()
        if direction == SyncDirection.BIDIRECTIONAL:
            self._dest_only_combo.addItem(tr("dest_only_actions.copy_to_source"), SyncAction.COPY_TO_SOURCE)
        self._dest_only_combo.addItem(tr("dest_only_actions.skip"), SyncAction.SKIP)
        self._dest_only_combo.addItem(tr("dest_only_actions.move_to_trash"), SyncAction.MOVE_TO_TRASH)
        self._dest_only_combo.addItem(tr("dest_only_actions.delete"), SyncAction.DELETE_FROM_DEST)
        self._dest_only_combo.blockSignals(False)

    def _on_compare_mode_changed(self, idx: int) -> None:
        if idx == 2:
            self._precompute_hashes_checkbox.setChecked(True)

    def _on_direction_radio_changed(self, button_id: int, checked: bool) -> None:
        if not checked:
            return
        direction = SyncDirection.BIDIRECTIONAL if button_id == 1 else SyncDirection.UNIDIRECTIONAL
        self._current_direction = direction
        self._populate_conflict_combo(direction)
        self._populate_dest_only_combo(direction)

    # ── Exclusions Config (Tab 2 Content) ────────────────────────────────

    def _create_exclusions_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
        )
        layout.setSpacing(DesignSystem.SPACE_16)

        self._exclusion_checkboxes: dict[ExclusionPreset, QCheckBox] = {}
        presets = [
            (ExclusionPreset.SYSTEM_FILES, "exclusion_presets.system_files"),
            (ExclusionPreset.TRASH_FOLDERS, "exclusion_presets.trash_folders"),
            (ExclusionPreset.DEV_FOLDERS, "exclusion_presets.dev_folders"),
            (ExclusionPreset.TEMP_FILES, "exclusion_presets.temp_files"),
        ]

        grid = QGridLayout()
        grid.setSpacing(DesignSystem.SPACE_12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for idx, (preset, key) in enumerate(presets):
            row, col = divmod(idx, 2)
            cell = QHBoxLayout()
            cell.setSpacing(DesignSystem.SPACE_6)
            cb = QCheckBox(tr(key))
            cb.setChecked(preset in self._active_exclusion_presets)
            cb.setStyleSheet(DesignSystem.get_checkbox_style())
            self._exclusion_checkboxes[preset] = cb
            cell.addWidget(cb)
            cell.addWidget(self._create_info_btn(key, f"info.exc_{preset.name.lower()}"))
            cell.addStretch()
            cell_widget = QWidget()
            cell_widget.setLayout(cell)
            grid.addWidget(cell_widget, row, col)

        layout.addLayout(grid)

        # Custom Exclusions divider line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedHeight(1)
        line.setStyleSheet(f"border: none; background-color: {DesignSystem.COLOR_BORDER_LIGHT};")
        layout.addWidget(line)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(DesignSystem.SPACE_8)
        custom_label = QLabel(tr("settings.custom_exclusions"))
        custom_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_SM}px; font-weight: bold; color: {DesignSystem.COLOR_TEXT};"
        )
        custom_row.addWidget(custom_label)
        custom_row.addWidget(self._create_info_btn("info.custom_exclusions_title", "info.custom_exclusions_text"))
        custom_row.addStretch()
        layout.addLayout(custom_row)

        self._custom_exclusion_edit = QLineEdit()
        self._custom_exclusion_edit.setPlaceholderText("*.log, *.bak, temp/")
        self._custom_exclusion_edit.setStyleSheet(DesignSystem.get_combobox_style())
        layout.addWidget(self._custom_exclusion_edit)

        return container

    def _create_analyze_button(self) -> QPushButton:
        btn = QPushButton(tr("setup.analyze"))
        btn.setIcon(icon_manager.get_icon("mdi6.magnify", color="white"))
        btn.setToolTip(tr("setup.analyze"))
        btn.setStyleSheet(DesignSystem.get_primary_button_style())
        btn.setMinimumHeight(48)
        btn.setEnabled(False)
        btn.clicked.connect(self._validate_and_analyze)
        return btn

    def _show_info(self, title_key: str, text_key: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle(tr(title_key))
        msg.setText(tr(text_key))
        icon = icon_manager.get_icon("mdi6.information-outline", color=DesignSystem.COLOR_PRIMARY)
        if icon:
            msg.setWindowIcon(icon)
            msg.setIconPixmap(icon.pixmap(48, 48))
        msg.setStyleSheet(DesignSystem.get_stylesheet())
        msg.exec()

    def _create_info_btn(self, title_key: str, text_key: str) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(icon_manager.get_icon("mdi6.information-outline", color=DesignSystem.COLOR_TEXT_SECONDARY))
        btn.setToolTip(tr("common.details"))
        btn.setFixedSize(24, 24)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
            }}
        """)
        btn.clicked.connect(lambda _, t=title_key, txt=text_key: self._show_info(t, txt))
        return btn

    # ── Logic & Lifecycle ───────────────────────────────────────────────

    def _load_last_paths(self) -> None:
        if not settings_manager.get_remember_last_paths():
            return
        last_source = settings_manager.get_last_source()
        last_dest = settings_manager.get_last_dest()
        if last_source:
            self._source_edit.setCurrentText(last_source)
            self._source_path = last_source
        if last_dest:
            self._dest_edit.setCurrentText(last_dest)
            self._dest_path = last_dest

    def _validate_and_analyze(self) -> None:
        source = self.get_source_path()
        dest = self.get_dest_path()
        if not source or not dest:
            return
        source_path = Path(source)
        dest_path = Path(dest)
        if not source_path.exists():
            QMessageBox.warning(self, tr("common.warning"), tr("setup.source_not_found"))
            return
        if not dest_path.exists():
            reply = QMessageBox.question(
                self,
                tr("setup.create_dest_title"),
                tr("setup.create_dest_message", path=dest),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    dest_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(
                        self, tr("common.error"),
                        tr("setup.create_dest_error", error=str(e)),
                    )
                    return
            else:
                return
        self._source_path = source
        self._dest_path = dest
        settings_manager.add_path_history(source)
        settings_manager.add_path_history(dest)
        if settings_manager.get_remember_last_paths():
            settings_manager.set_last_source(source)
            settings_manager.set_last_dest(dest)
            settings_manager.sync()
        self.analyze_requested.emit()

    def _update_analyze_button_state(self) -> None:
        source = self.get_source_path()
        dest = self.get_dest_path()
        ready = bool(source.strip()) and bool(dest.strip())
        self._analyze_btn.setEnabled(ready)
        if ready:
            self._analyze_btn.setToolTip(tr("setup.analyze"))
        else:
            self._analyze_btn.setToolTip(tr("setup.analyze_disabled_tooltip"))
        self._update_drive_labels()


    def _update_drive_labels(self) -> None:
        self._update_one_drive_label(
            getattr(self, "_source_drive_label", None), self.get_source_path()
        )
        self._update_one_drive_label(
            getattr(self, "_dest_drive_label", None), self.get_dest_path()
        )

    def _update_one_drive_label(self, label: QLabel | None, path: str) -> None:
        if label is None:
            return
        path = path.strip()
        if not path:
            label.setVisible(False)
            label.clear()
            return
        drive = get_drive_for_path(path)
        if drive is None:
            label.setVisible(False)
            label.clear()
            return
        size_str = format_size(drive.total_bytes)
        label.setText(tr("setup.disk_label", label=drive.label, size=size_str))
        label.setVisible(True)

    def _select_preset(self, preset: SyncPreset) -> None:
        self._selected_preset = preset
        for p, btn in self._preset_buttons.items():
            btn.setChecked(p == preset)

        # Update dynamic description
        preset_name = preset.name.lower()
        detail_key = f"presets.{preset_name}_detail"
        self._preset_desc_label.setText(tr(detail_key))

        from services.planner import apply_preset
        config = apply_preset(preset)

        direction = config["direction"]
        self._current_direction = direction

        if direction == SyncDirection.BIDIRECTIONAL:
            self._dir_bi_radio.setChecked(True)
        else:
            self._dir_uni_radio.setChecked(True)

        # Update dynamic borders of swap button
        arrow_color = DesignSystem.COLOR_SUCCESS if direction == SyncDirection.BIDIRECTIONAL else DesignSystem.COLOR_PRIMARY
        badge_bg_color = "#EBF7EE" if direction == SyncDirection.BIDIRECTIONAL else DesignSystem.COLOR_PRIMARY_LIGHT

        self._invert_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1.5px solid {arrow_color};
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {badge_bg_color};
            }}
        """)
        arrow_icon = icon_manager.get_icon("mdi6.swap-vertical", color=arrow_color)
        if arrow_icon:
            self._invert_btn.setIcon(arrow_icon)
            self._invert_btn.setIconSize(QSize(16, 16))

        mode_index = {
            CompareMode.FAST: 0,
            CompareMode.SMART: 1,
            CompareMode.FULL_HASH: 2,
        }.get(config["compare_mode"], 1)
        self._compare_combo.setCurrentIndex(mode_index)

        self._populate_conflict_combo(direction)
        self._populate_dest_only_combo(direction)

        policy = config["conflict_policy"]
        if policy == ConflictPolicy.SOURCE_WINS:
            self._conflict_combo.setCurrentIndex(0)
        elif policy == ConflictPolicy.KEEP_DEST:
            self._conflict_combo.setCurrentIndex(1)
        elif policy == ConflictPolicy.MARK_PENDING:
            last_idx = self._conflict_combo.count() - 1
            self._conflict_combo.setCurrentIndex(last_idx)

        dest_only_action = config["dest_only_action"]
        for i in range(self._dest_only_combo.count()):
            if self._dest_only_combo.itemData(i) == dest_only_action:
                self._dest_only_combo.setCurrentIndex(i)
                break

        if config["verify_mode"] == VerifyMode.FULL:
            self._verify_combo.setCurrentIndex(2)
        elif config["verify_mode"] == VerifyMode.SPOT_CHECK:
            self._verify_combo.setCurrentIndex(1)
        else:
            self._verify_combo.setCurrentIndex(0)

        self._trash_checkbox.setChecked(config["use_trash"])

        is_custom = preset == SyncPreset.CUSTOM
        self._compare_combo.setEnabled(is_custom)
        self._conflict_combo.setEnabled(is_custom)
        self._dest_only_combo.setEnabled(is_custom)
        self._verify_combo.setEnabled(is_custom)
        self._trash_checkbox.setEnabled(is_custom)
        self._dir_uni_radio.setEnabled(is_custom)
        self._dir_bi_radio.setEnabled(is_custom)
        self._precompute_hashes_checkbox.setEnabled(is_custom)
        if not is_custom:
            self._precompute_hashes_checkbox.setChecked(
                config["compare_mode"] == CompareMode.FULL_HASH
            )

        self._flash_settings(is_custom)

    def _flash_settings(self, is_custom: bool) -> None:
        combo_style = self._get_highlighted_combobox_style(is_custom)
        self._compare_combo.setStyleSheet(combo_style)
        self._conflict_combo.setStyleSheet(combo_style)
        self._dest_only_combo.setStyleSheet(combo_style)
        self._verify_combo.setStyleSheet(combo_style)
        self._trash_checkbox.setStyleSheet(self._get_highlighted_checkbox_style(is_custom))

    def _get_highlighted_combobox_style(self, is_custom: bool) -> str:
        if is_custom:
            return f"""
                QComboBox {{
                    background-color: {DesignSystem.COLOR_SURFACE};
                    color: {DesignSystem.COLOR_PRIMARY};
                    border: 1px solid {DesignSystem.COLOR_PRIMARY};
                    border-radius: {DesignSystem.RADIUS_BASE}px;
                    padding: 6px 10px;
                    min-height: 24px;
                    font-weight: bold;
                }}
                QComboBox:hover {{
                    background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 24px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    width: 0;
                    height: 0;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid {DesignSystem.COLOR_PRIMARY};
                    margin-top: 2px;
                }}
            """
        else:
            return f"""
                QComboBox {{
                    background-color: {DesignSystem.COLOR_BACKGROUND};
                    color: {DesignSystem.COLOR_TEXT_SECONDARY};
                    border: 1px solid transparent;
                    border-radius: {DesignSystem.RADIUS_BASE}px;
                    padding: 6px 10px;
                    min-height: 24px;
                    font-weight: bold;
                }}
                QComboBox::drop-down {{
                    width: 0px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    width: 0;
                    height: 0;
                }}
            """

    def _get_highlighted_checkbox_style(self, is_custom: bool) -> str:
        if is_custom:
            return f"""
                QCheckBox {{
                    spacing: 8px;
                    color: {DesignSystem.COLOR_PRIMARY};
                    font-weight: bold;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid {DesignSystem.COLOR_PRIMARY};
                    border-radius: {DesignSystem.RADIUS_SM}px;
                    background-color: {DesignSystem.COLOR_SURFACE};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {DesignSystem.COLOR_PRIMARY};
                }}
            """
        else:
            return f"""
                QCheckBox {{
                    spacing: 8px;
                    color: {DesignSystem.COLOR_TEXT_SECONDARY};
                    font-weight: bold;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid transparent;
                    border-radius: {DesignSystem.RADIUS_SM}px;
                    background-color: {DesignSystem.COLOR_BORDER};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {DesignSystem.COLOR_TEXT_SECONDARY};
                }}
            """

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("setup.select_source"))
        if path:
            self._source_edit.setCurrentText(path)
            self._source_path = path
            self.source_changed.emit(path)
            self._update_analyze_button_state()

    def _browse_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("setup.select_dest"))
        if path:
            self._dest_edit.setCurrentText(path)
            self._dest_path = path
            self.dest_changed.emit(path)
            self._update_analyze_button_state()

    # ── Getters ────────────────────────────────────────────────────────

    def get_source_path(self) -> str:
        return self._source_edit.currentText().strip()

    def get_dest_path(self) -> str:
        return self._dest_edit.currentText().strip()

    def refresh_history(self) -> None:
        history = settings_manager.get_path_history()

        current_source = self._source_edit.currentText()
        self._source_edit.clear()
        if history:
            self._source_edit.addItems(history)
        self._source_edit.setCurrentText(current_source)

        current_dest = self._dest_edit.currentText()
        self._dest_edit.clear()
        if history:
            self._dest_edit.addItems(history)
        self._dest_edit.setCurrentText(current_dest)

    def get_compare_mode(self) -> CompareMode:
        return [CompareMode.FAST, CompareMode.SMART, CompareMode.FULL_HASH][self._compare_combo.currentIndex()]

    def get_conflict_policy(self) -> ConflictPolicy:
        data = self._conflict_combo.currentData()
        if data:
            return data[0]
        return ConflictPolicy.SOURCE_WINS

    def get_conflict_action(self) -> SyncAction | None:
        data = self._conflict_combo.currentData()
        if data:
            return data[1]
        return None

    def get_direction(self) -> SyncDirection:
        return self._current_direction

    def get_verify_mode(self) -> VerifyMode:
        return [VerifyMode.OFF, VerifyMode.SPOT_CHECK, VerifyMode.FULL][self._verify_combo.currentIndex()]

    def get_use_trash(self) -> bool:
        return self._trash_checkbox.isChecked()

    def get_selected_preset(self) -> SyncPreset:
        return self._selected_preset

    def get_dest_only_action(self) -> SyncAction:
        if self._selected_preset == SyncPreset.CUSTOM:
            data = self._dest_only_combo.currentData()
            if data:
                return data
            if self._current_direction == SyncDirection.BIDIRECTIONAL:
                return SyncAction.COPY_TO_SOURCE
            if self._trash_checkbox.isChecked():
                return SyncAction.MOVE_TO_TRASH
            return SyncAction.DELETE_FROM_DEST
        return SYNC_PRESET_CONFIGS[self._selected_preset]["dest_only_action"]

    def get_precompute_hashes(self) -> bool:
        return self._precompute_hashes_checkbox.isChecked()

    def get_active_exclusion_presets(self) -> list[ExclusionPreset]:
        return [p for p, cb in self._exclusion_checkboxes.items() if cb.isChecked()]

    def get_custom_exclusions(self) -> list[str]:
        text = self._custom_exclusion_edit.text().strip()
        if not text:
            return []
        return [p.strip() for p in text.split(",") if p.strip()]


# Option definitions for combo boxes
CONFLICT_OPTIONS_UNI = [
    ("conflict_policies.overwrite_dest", ConflictPolicy.SOURCE_WINS, SyncAction.OVERWRITE_DEST),
    ("conflict_policies.keep_dest", ConflictPolicy.KEEP_DEST, SyncAction.KEEP_DEST),
    ("conflict_policies.skip", ConflictPolicy.SOURCE_WINS, SyncAction.SKIP),
    ("conflict_policies.mark_pending", ConflictPolicy.MARK_PENDING, None),
]

CONFLICT_OPTIONS_BI = [
    ("conflict_policies.overwrite_dest", ConflictPolicy.SOURCE_WINS, SyncAction.OVERWRITE_DEST),
    ("conflict_policies.keep_dest", ConflictPolicy.KEEP_DEST, SyncAction.KEEP_DEST),
    ("conflict_policies.overwrite_source", ConflictPolicy.SOURCE_WINS, SyncAction.OVERWRITE_SOURCE),
    ("conflict_policies.keep_source", ConflictPolicy.KEEP_DEST, SyncAction.KEEP_SOURCE),
    ("conflict_policies.skip", ConflictPolicy.SOURCE_WINS, SyncAction.SKIP),
    ("conflict_policies.mark_pending", ConflictPolicy.MARK_PENDING, None),
]
