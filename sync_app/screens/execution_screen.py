# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Execution screen — sync progress with per-file verification and resource monitoring."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QGroupBox,
    QSizePolicy,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from utils.i18n import tr
from utils.format_utils import format_size, format_duration, format_speed

ACTION_LABELS: dict[str, str] = {
    "copy_to_dest": "execution.action_copying",
    "copy_to_source": "execution.action_copying_to_source",
    "overwrite_dest": "execution.action_overwriting",
    "overwrite_source": "execution.action_overwriting_source",
    "delete_from_dest": "execution.action_deleting",
    "move_to_trash": "execution.action_trashing",
    "rename_in_dest": "execution.action_renaming",
    "keep_dest": "execution.action_keeping",
    "keep_source": "execution.action_keeping",
    "skip": "execution.action_skipping",
    "mark_review": "execution.action_skipping",
}


class ExecutionScreen(QWidget):
    """Screen showing sync execution progress, verification, and resource monitoring."""

    pause_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_paused = False

        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24, DesignSystem.SPACE_24)

        title = QLabel(tr("execution.title"))
        title.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold;")
        layout.addWidget(title)

        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet(DesignSystem.get_progressbar_style())
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        progress_row = QHBoxLayout()
        self._progress_label = QLabel("0%")
        self._progress_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_LG}px; font-weight: bold; color: {DesignSystem.COLOR_PRIMARY};")
        progress_row.addWidget(self._progress_label)

        self._eta_label = QLabel("")
        self._eta_label.setStyleSheet(f"font-size: {DesignSystem.SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        self._eta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self._eta_label)
        layout.addLayout(progress_row)

        layout.addWidget(self._create_current_file_section())

        layout.addWidget(self._create_counters())

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(180)
        self._log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._log.setStyleSheet(
            f"background-color: {DesignSystem.COLOR_BACKGROUND}; "
            f"color: {DesignSystem.COLOR_TEXT}; "
            f"font-family: monospace; font-size: {DesignSystem.SIZE_SM}px; "
            f"border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT}; "
            f"border-radius: {DesignSystem.RADIUS_SM}px;"
        )
        layout.addWidget(self._log, stretch=1)

        layout.addWidget(self._create_resource_monitor())
        layout.addWidget(self._create_buttons())

    def _create_current_file_section(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {DesignSystem.COLOR_SURFACE}; "
            f"border: 1px solid {DesignSystem.COLOR_BORDER_LIGHT}; "
            f"border-radius: {DesignSystem.RADIUS_MD}px; }}"
        )
        frame.setMinimumHeight(80)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(
            DesignSystem.SPACE_12, DesignSystem.SPACE_8,
            DesignSystem.SPACE_12, DesignSystem.SPACE_8,
        )
        frame_layout.setSpacing(DesignSystem.SPACE_4)

        self._action_label = QLabel("")
        self._action_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_SM}px; font-weight: bold; "
            f"color: {DesignSystem.COLOR_PRIMARY}; border: none; background: transparent;"
        )
        frame_layout.addWidget(self._action_label)

        self._current_file_label = QLabel(tr("execution.current_file") + ": —")
        self._current_file_label.setStyleSheet(
            f"font-size: {DesignSystem.SIZE_MD}px; color: {DesignSystem.COLOR_TEXT}; "
            f"border: none; background: transparent;"
        )
        self._current_file_label.setWordWrap(True)
        frame_layout.addWidget(self._current_file_label)

        return frame

    def _create_counters(self) -> QWidget:
        counters = QWidget()
        layout = QHBoxLayout(counters)
        layout.setSpacing(DesignSystem.SPACE_16)
        layout.setContentsMargins(0, DesignSystem.SPACE_4, 0, DesignSystem.SPACE_4)

        self._counter_labels: dict[str, QLabel] = {}
        counter_items = [
            ("completed", DesignSystem.COLOR_SUCCESS),
            ("verified", DesignSystem.COLOR_PRIMARY),
            ("errors", DesignSystem.COLOR_DANGER),
            ("skipped", DesignSystem.COLOR_TEXT_SECONDARY),
        ]

        for key, color in counter_items:
            pair = QWidget()
            pair_layout = QVBoxLayout(pair)
            pair_layout.setContentsMargins(DesignSystem.SPACE_4, DesignSystem.SPACE_4, DesignSystem.SPACE_4, DesignSystem.SPACE_4)

            value = QLabel("0")
            value.setStyleSheet(f"font-size: {DesignSystem.SIZE_XL}px; font-weight: bold; color: {color};")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pair_layout.addWidget(value)
            self._counter_labels[key] = value

            text = QLabel(tr(f"execution.{key}_count"))
            text.setStyleSheet(f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pair_layout.addWidget(text)

            layout.addWidget(pair, stretch=1)

        return counters

    def _create_resource_monitor(self) -> QWidget:
        monitor = QWidget()
        monitor.setFixedHeight(24)
        layout = QHBoxLayout(monitor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_12)

        style = f"font-size: {DesignSystem.SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};"

        self._cpu_label = QLabel(tr("execution.cpu", percent="0"))
        self._cpu_label.setStyleSheet(style)
        layout.addWidget(self._cpu_label)

        sep1 = QLabel("\u2022")
        sep1.setStyleSheet(style)
        layout.addWidget(sep1)

        self._ram_label = QLabel(tr("execution.ram_free", gb="0"))
        self._ram_label.setStyleSheet(style)
        layout.addWidget(self._ram_label)

        sep2 = QLabel("\u2022")
        sep2.setStyleSheet(style)
        layout.addWidget(sep2)

        self._src_free_label = QLabel(tr("execution.src_free", gb="0"))
        self._src_free_label.setStyleSheet(style)
        layout.addWidget(self._src_free_label)

        sep3 = QLabel("\u2022")
        sep3.setStyleSheet(style)
        layout.addWidget(sep3)

        self._dst_free_label = QLabel(tr("execution.dst_free", gb="0"))
        self._dst_free_label.setStyleSheet(style)
        layout.addWidget(self._dst_free_label)

        sep4 = QLabel("\u2022")
        sep4.setStyleSheet(style)
        layout.addWidget(sep4)

        self._speed_label = QLabel(tr("execution.write_speed", speed="0"))
        self._speed_label.setStyleSheet(style)
        layout.addWidget(self._speed_label)

        layout.addStretch()
        return monitor

    def _create_buttons(self) -> QWidget:
        btn_row = QWidget()
        layout = QHBoxLayout(btn_row)
        layout.addStretch()

        self._pause_btn = QPushButton(tr("execution.pause"))
        self._pause_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        self._pause_btn.setMinimumWidth(120)
        self._pause_btn.clicked.connect(self._toggle_pause)
        layout.addWidget(self._pause_btn)

        self._cancel_btn = QPushButton(tr("execution.cancel"))
        self._cancel_btn.setStyleSheet(DesignSystem.get_danger_button_style())
        self._cancel_btn.setMinimumWidth(120)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self._cancel_btn)

        return btn_row

    def set_progress(self, percent: int, message: str = "") -> None:
        self._progress_bar.setValue(min(percent, 100))
        self._progress_label.setText(f"{percent}%")
        if message:
            action_key, file_path = self._parse_progress_message(message)
            if action_key:
                action_text = tr(ACTION_LABELS.get(action_key, "execution.action_processing"))
                self._action_label.setText(action_text)
            self._current_file_label.setText(file_path if file_path else message)

    def _parse_progress_message(self, message: str) -> tuple[str, str]:
        if message.startswith("[") and "]" in message:
            bracket_end = message.index("]")
            action_key = message[1:bracket_end]
            file_path = message[bracket_end + 2:] if bracket_end + 2 < len(message) else ""
            return action_key, file_path
        return "", message

    def set_eta(self, eta_seconds: float | None = None, speed: float | None = None) -> None:
        parts = []
        if eta_seconds is not None:
            parts.append(tr("execution.eta", eta=format_duration(eta_seconds)))
        if speed is not None:
            parts.append(tr("execution.speed", speed=format_speed(speed)))
        self._eta_label.setText(" | ".join(parts))

    def set_counters(self, completed: int, verified: int, errors: int, skipped: int) -> None:
        self._counter_labels["completed"].setText(str(completed))
        self._counter_labels["verified"].setText(str(verified))
        self._counter_labels["errors"].setText(str(errors))
        self._counter_labels["skipped"].setText(str(skipped))

    def set_resources(self, cpu: float, ram_free: float, src_free: float, dst_free: float, write_speed: float) -> None:
        self._cpu_label.setText(tr("execution.cpu", percent=f"{cpu:.0f}"))
        self._ram_label.setText(tr("execution.ram_free", gb=f"{ram_free:.1f}"))
        self._src_free_label.setText(tr("execution.src_free", gb=f"{src_free:.1f}"))
        self._dst_free_label.setText(tr("execution.dst_free", gb=f"{dst_free:.1f}"))
        self._speed_label.setText(tr("execution.write_speed", speed=f"{write_speed:.1f}"))

    def append_log(self, message: str) -> None:
        self._log.appendPlainText(message)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _toggle_pause(self) -> None:
        self._is_paused = not self._is_paused
        self._pause_btn.setText(tr("execution.resume") if self._is_paused else tr("execution.pause"))
        self.pause_requested.emit()

    def reset(self) -> None:
        self._progress_bar.setValue(0)
        self._progress_label.setText("0%")
        self._eta_label.setText("")
        self._action_label.setText("")
        self._current_file_label.setText(tr("execution.current_file") + ": —")
        self.set_counters(0, 0, 0, 0)
        self._log.clear()
        self._is_paused = False
        self._pause_btn.setText(tr("execution.pause"))
        self._dry_run_mode = False

    def set_dry_run_mode(self, enabled: bool) -> None:
        self._dry_run_mode = enabled
        if enabled:
            self._log.appendPlainText(f"[DRY-RUN] {tr('execution.dry_run_notice')}")
