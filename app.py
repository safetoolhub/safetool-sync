# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""SafeTool Sync — Entry point."""
from __future__ import annotations

import multiprocessing
import sys


def _install_exception_hook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def main() -> int:
    _install_exception_hook()

    from config import Config

    from utils.i18n import init_i18n
    from utils.settings_manager import settings_manager

    Config.LOGS_DIR = settings_manager.get_logs_dir()
    Config.SNAPSHOTS_DIR = settings_manager.get_snapshots_dir()
    Config.ensure_dirs()

    language = settings_manager.get_language()
    init_i18n(language)

    from utils.logger import configure_logging
    log_level_str = settings_manager.get_log_level()
    import logging
    log_level = getattr(logging, log_level_str.upper(), logging.DEBUG)
    configure_logging(level=log_level)

    from utils.logger import get_logger
    logger = get_logger()
    logger.info(f"Starting {Config.APP_NAME} {Config.get_full_version()}")
    logger.info(f"System: {Config.get_system_info()}")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.get_full_version())
    app.setOrganizationName("safetoolhub.org")
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(248, 249, 250))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(248, 249, 250))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(13, 110, 253))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(13, 110, 253))
    app.setPalette(palette)

    from sync_app.styles.design_system import DesignSystem
    app.setStyleSheet(DesignSystem.get_stylesheet())

    logger.info("UI initialized — Fusion theme applied")

    from sync_app.main_window import MainWindow
    window = MainWindow()
    window.showMaximized()

    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())