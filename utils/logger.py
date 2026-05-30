# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Thread-safe rotating logger for SafeTool Sync."""
from __future__ import annotations

import logging
import os
import platform
import threading
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import Config

_LOG_LOCK = threading.RLock()
_logger: logging.Logger | None = None
_file_handler: RotatingFileHandler | None = None
_warn_error_handler: RotatingFileHandler | None = None
_file_logging_disabled: bool = False

APP_LOGGER_NAME = "SafeToolSync"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


def _sanitize_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


class ThreadSafeRotatingFileHandler(RotatingFileHandler):
    def __init__(self, filename: str, **kwargs: object) -> None:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename, **kwargs)
        if os.path.exists(filename):
            self.doRollover()

    def emit(self, record: logging.LogRecord) -> None:
        with _LOG_LOCK:
            super().emit(record)


class SimpleLogger:
    def __init__(self, name: str = APP_LOGGER_NAME) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)

    def debug(self, msg: str, *args: object, **kwargs: object) -> None:
        self._logger.debug(_sanitize_html(str(msg)), *args, **kwargs)

    def info(self, msg: str, *args: object, **kwargs: object) -> None:
        self._logger.info(_sanitize_html(str(msg)), *args, **kwargs)

    def warning(self, msg: str, *args: object, **kwargs: object) -> None:
        self._logger.warning(_sanitize_html(str(msg)), *args, **kwargs)

    def error(self, msg: str, *args: object, **kwargs: object) -> None:
        self._logger.error(_sanitize_html(str(msg)), *args, **kwargs)

    def critical(self, msg: str, *args: object, **kwargs: object) -> None:
        self._logger.critical(_sanitize_html(str(msg)), *args, **kwargs)

    def exception(self, msg: str, *args: object, **kwargs: object) -> None:
        self._logger.exception(_sanitize_html(str(msg)), *args, **kwargs)


def configure_logging(
    logs_dir: Path | None = None,
    level: int = logging.DEBUG,
    dual_log_enabled: bool = True,
    disable_file_logging: bool = False,
) -> SimpleLogger:
    global _logger, _file_handler, _warn_error_handler, _file_logging_disabled

    if logs_dir is None:
        logs_dir = Config.LOGS_DIR

    _file_logging_disabled = disable_file_logging

    if not disable_file_logging:
        logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    if not disable_file_logging:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        main_log = logs_dir / f"safetool_sync_{timestamp}.log"
        _file_handler = ThreadSafeRotatingFileHandler(
            str(main_log),
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        _file_handler.setLevel(level)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        _file_handler.setFormatter(file_fmt)
        logger.addHandler(_file_handler)

        if dual_log_enabled:
            warn_log = logs_dir / f"safetool_sync_{timestamp}_WARNERROR.log"
            _warn_error_handler = ThreadSafeRotatingFileHandler(
                str(warn_log),
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            _warn_error_handler.setLevel(logging.WARNING)
            _warn_error_handler.setFormatter(file_fmt)
            logger.addHandler(_warn_error_handler)

    simple = SimpleLogger(APP_LOGGER_NAME)
    _logger = simple
    return simple


def get_logger() -> SimpleLogger:
    global _logger
    if _logger is None:
        _logger = configure_logging()
    return _logger


def log_section_header(title: str, char: str = "=", width: int = 60) -> None:
    logger = get_logger()
    logger.info(char * width)
    logger.info(f"  {title}")
    logger.info(char * width)


def change_logs_directory(new_dir: Path) -> None:
    global _file_handler, _warn_error_handler, _file_logging_disabled
    if _file_logging_disabled:
        return
    new_dir.mkdir(parents=True, exist_ok=True)
    cur = get_logger()
    if _file_handler:
        cur._logger.removeHandler(_file_handler)
        _file_handler.close()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_main = new_dir / f"safetool_sync_{timestamp}.log"
        _file_handler = ThreadSafeRotatingFileHandler(
            str(new_main),
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        _file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        cur._logger.addHandler(_file_handler)


def set_file_logging_disabled(disabled: bool) -> None:
    global _file_logging_disabled
    _file_logging_disabled = disabled