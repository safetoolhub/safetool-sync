# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Design system — all visual tokens and QSS methods for SafeTool Sync."""
from __future__ import annotations


class DesignSystem:
    # ── Colors ──────────────────────────────────────────────────────────
    COLOR_BACKGROUND = "#F8F9FA"
    COLOR_SURFACE = "#FFFFFF"
    COLOR_TEXT = "#212529"
    COLOR_TEXT_SECONDARY = "#6C757D"
    COLOR_PRIMARY = "#0D6EFD"
    COLOR_PRIMARY_HOVER = "#0B5ED7"
    COLOR_PRIMARY_ACTIVE = "#0A58CA"
    COLOR_PRIMARY_LIGHT = "#E7F1FF"
    COLOR_SUCCESS = "#198754"
    COLOR_WARNING = "#FFC107"
    COLOR_DANGER = "#DC3545"
    COLOR_INFO = "#0DCAF0"
    COLOR_BORDER = "#DEE2E6"
    COLOR_BORDER_LIGHT = "#E9ECEF"

    # ── Typography ──────────────────────────────────────────────────────
    FONT_FAMILY_BASE = "'Segoe UI','Roboto','Helvetica Neue',sans-serif"
    SIZE_XS = 11
    SIZE_SM = 13
    SIZE_BASE = 14
    SIZE_MD = 16
    SIZE_LG = 18
    SIZE_XL = 24
    SIZE_2XL = 32

    # ── Spacing ─────────────────────────────────────────────────────────
    SPACE_2 = 2
    SPACE_4 = 4
    SPACE_6 = 6
    SPACE_8 = 8
    SPACE_10 = 10
    SPACE_12 = 12
    SPACE_16 = 16
    SPACE_20 = 20
    SPACE_24 = 24
    SPACE_32 = 32
    SPACE_40 = 40
    SPACE_48 = 48

    # ── Radius ──────────────────────────────────────────────────────────
    RADIUS_SM = 4
    RADIUS_BASE = 6
    RADIUS_MD = 8
    RADIUS_LG = 12
    RADIUS_XL = 16
    RADIUS_FULL = 9999

    # ── Diff type colors ─────────────────────────────────────────────────
    COLOR_DIFF_IDENTICAL = "#198754"
    COLOR_DIFF_SOURCE_ONLY = "#0D6EFD"
    COLOR_DIFF_MODIFIED = "#FD7E14"
    COLOR_DIFF_DEST_ONLY = "#DC3545"
    COLOR_DIFF_CONFLICT = "#FFC107"
    COLOR_DIFF_RENAMED = "#6F42C1"
    COLOR_DIFF_CASE_MISMATCH = "#17A2B8"
    COLOR_DIFF_ERROR = "#6C757D"

    # ── Stylesheet methods ───────────────────────────────────────────────

    @staticmethod
    def get_stylesheet() -> str:
        return f"""
            * {{
                font-family: {DesignSystem.FONT_FAMILY_BASE};
                font-size: {DesignSystem.SIZE_BASE}px;
                color: {DesignSystem.COLOR_TEXT};
            }}
            QMainWindow {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
            }}
            QWidget {{
                color: {DesignSystem.COLOR_TEXT};
            }}
            QScrollArea {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_MD}px;
                margin-top: 8px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }}
            QLabel {{
                color: {DesignSystem.COLOR_TEXT};
            }}
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                background-color: {DesignSystem.COLOR_SURFACE};
            }}
            QLineEdit:focus {{
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
            QSpinBox, QDoubleSpinBox {{
                padding: 4px 8px;
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                background-color: {DesignSystem.COLOR_SURFACE};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: {DesignSystem.COLOR_PRIMARY};
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                width: 10px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {DesignSystem.COLOR_BORDER};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """

    @staticmethod
    def get_header_style() -> str:
        return f"""
            QFrame#headerCard {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border-bottom: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                padding: 0;
            }}
        """

    @staticmethod
    def get_header_title_style() -> str:
        return f"""
            QLabel {{
                font-size: {DesignSystem.SIZE_LG}px;
                font-weight: bold;
                color: {DesignSystem.COLOR_TEXT};
            }}
        """

    @staticmethod
    def get_header_icon_container_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
            }}
        """

    @staticmethod
    def get_header_brand_label_style() -> str:
        return f"""
            QLabel {{
                font-size: {DesignSystem.SIZE_XS}px;
                font-weight: bold;
                color: {DesignSystem.COLOR_PRIMARY};
                letter-spacing: 2px;
            }}
        """

    @staticmethod
    def get_primary_button_style() -> str:
        return f"""
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
                background-color: {DesignSystem.COLOR_PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.COLOR_PRIMARY_ACTIVE};
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.COLOR_BORDER_LIGHT};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """

    @staticmethod
    def get_secondary_button_style() -> str:
        return f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_SURFACE};
                color: {DesignSystem.COLOR_TEXT};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: {DesignSystem.SIZE_BASE}px;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
            }}
        """

    @staticmethod
    def get_danger_button_style() -> str:
        return f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_DANGER};
                color: white;
                border: none;
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: {DesignSystem.SIZE_BASE}px;
            }}
            QPushButton:hover {{
                background-color: #BB2D3B;
            }}
        """

    @staticmethod
    def get_icon_button_style() -> str:
        return f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: 4px;
            }}
            QToolButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
            }}
        """

    @staticmethod
    def get_card_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_16}px;
            }}
        """

    @staticmethod
    def get_checkbox_style() -> str:
        return f"""
            QCheckBox {{
                spacing: 6px;
                color: {DesignSystem.COLOR_TEXT};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_SM}px;
                background-color: {DesignSystem.COLOR_SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
        """

    @staticmethod
    def get_combobox_style() -> str:
        return f"""
            QComboBox {{
                padding: 6px 10px;
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                background-color: {DesignSystem.COLOR_SURFACE};
                min-height: 24px;
            }}
            QComboBox:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
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
                border-top: 5px solid {DesignSystem.COLOR_TEXT_SECONDARY};
                margin-top: 2px;
            }}
        """

    @staticmethod
    def get_progressbar_style() -> str:
        return f"""
            QProgressBar {{
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                background-color: {DesignSystem.COLOR_BORDER_LIGHT};
                text-align: center;
                height: 20px;
                font-size: {DesignSystem.SIZE_SM}px;
            }}
            QProgressBar::chunk {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_BASE - 1}px;
            }}
        """

    @staticmethod
    def get_tab_widget_style() -> str:
        return f"""
            QTabWidget::pane {{
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_SM}px;
                background-color: {DesignSystem.COLOR_SURFACE};
            }}
            QTabBar::tab {{
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-bottom: none;
                border-top-left-radius: {DesignSystem.RADIUS_SM}px;
                border-top-right-radius: {DesignSystem.RADIUS_SM}px;
                background-color: {DesignSystem.COLOR_BACKGROUND};
            }}
            QTabBar::tab:selected {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border-bottom: 2px solid {DesignSystem.COLOR_PRIMARY};
            }}
        """

    @staticmethod
    def get_context_menu_style() -> str:
        return f"""
            QMenu {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px;
                border-radius: {DesignSystem.RADIUS_SM}px;
            }}
            QMenu::item:selected {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                color: {DesignSystem.COLOR_PRIMARY};
            }}
        """

    @staticmethod
    def get_table_style() -> str:
        return f"""
            QTableWidget {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
                gridline-color: {DesignSystem.COLOR_BORDER_LIGHT};
                selection-background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                selection-color: {DesignSystem.COLOR_TEXT};
                font-size: {DesignSystem.SIZE_BASE}px;
            }}
            QHeaderView::section {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_12}px;
                border: none;
                border-bottom: 1px solid {DesignSystem.COLOR_BORDER};
                font-weight: bold;
                font-size: {DesignSystem.SIZE_SM}px;
                text-transform: uppercase;
            }}
            QTableWidget::item {{
                padding: {DesignSystem.SPACE_4}px {DesignSystem.SPACE_8}px;
                border-bottom: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                color: {DesignSystem.COLOR_TEXT};
            }}
        """

    @staticmethod
    def get_summary_card_style(border_color: str) -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-top: 4px solid {border_color};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
            .QFrame:hover {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
                border-color: {DesignSystem.COLOR_BORDER};
                border-top: 4px solid {border_color};
            }}
        """

    # ── App-specific styles ────────────────────────────────────────────

    @staticmethod
    def get_source_panel_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 2px solid {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """

    @staticmethod
    def get_dest_panel_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 2px solid {DesignSystem.COLOR_SUCCESS};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """

    @staticmethod
    def get_diff_row_style(diff_type: str) -> str:
        colors = {
            "identical": DesignSystem.COLOR_DIFF_IDENTICAL,
            "source_only": DesignSystem.COLOR_DIFF_SOURCE_ONLY,
            "modified": DesignSystem.COLOR_DIFF_MODIFIED,
            "dest_only": DesignSystem.COLOR_DIFF_DEST_ONLY,
            "conflict": DesignSystem.COLOR_DIFF_CONFLICT,
            "renamed": DesignSystem.COLOR_DIFF_RENAMED,
            "error": DesignSystem.COLOR_DIFF_ERROR,
        }
        color = colors.get(diff_type, DesignSystem.COLOR_TEXT)
        return f"""
            QWidget {{
                border-left: 3px solid {color};
                padding-left: 8px;
            }}
        """

    @staticmethod
    def get_metric_card_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """

    @staticmethod
    def get_destructive_warning_style() -> str:
        return f"""
            .QFrame {{
                background-color: #FFF5F5;
                border: 2px solid {DesignSystem.COLOR_DANGER};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_16}px;
            }}
            QLabel {{
                color: {DesignSystem.COLOR_DANGER};
                font-weight: bold;
            }}
        """

    @staticmethod
    def get_conflict_dialog_style() -> str:
        return f"""
            QDialog {{
                background-color: {DesignSystem.COLOR_SURFACE};
            }}
        """

    @staticmethod
    def get_preset_card_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 2px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_16}px;
            }}
            .QFrame:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
        """

    @staticmethod
    def get_preset_card_selected_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border: 2px solid {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_16}px;
            }}
        """

    @staticmethod
    def get_disk_card_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
            .QFrame:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
            }}
        """

    @staticmethod
    def get_disk_action_button_style(color: str = "") -> str:
        bg = color or DesignSystem.COLOR_PRIMARY_LIGHT
        text = DesignSystem.COLOR_PRIMARY
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: 4px 10px;
                font-size: {DesignSystem.SIZE_SM}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: white;
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
        """

    @staticmethod
    def get_preset_detail_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """

    @staticmethod
    def get_resource_monitor_style() -> str:
        return f"""
            .QFrame {{
                background-color: {DesignSystem.COLOR_BACKGROUND};
                border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT};
                border-radius: {DesignSystem.RADIUS_SM}px;
                padding: {DesignSystem.SPACE_8}px;
            }}
            QLabel {{
                font-size: {DesignSystem.SIZE_SM}px;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """