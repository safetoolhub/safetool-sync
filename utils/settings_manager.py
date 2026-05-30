# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Centralized settings manager for SafeTool Sync."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import Config
from services.models import CompareMode, ConflictPolicy, VerifyMode, ExclusionPreset
from utils.storage import JsonStorageBackend, StorageBackend


class SettingsManager:
    KEY_LANGUAGE = "general/language"
    KEY_REMEMBER_LAST_PATHS = "general/remember_last_paths"
    KEY_LAST_SOURCE = "general/last_source"
    KEY_LAST_DEST = "general/last_dest"
    KEY_COMPARE_MODE = "sync/compare_mode"
    KEY_CONFLICT_POLICY = "sync/conflict_policy"
    KEY_VERIFY_MODE = "sync/verify_mode"
    KEY_USE_TRASH = "sync/use_trash"
    KEY_SPOT_CHECK_PERCENT = "sync/spot_check_percent"
    KEY_BUFFER_SIZE = "sync/buffer_size"
    KEY_LOG_LEVEL = "advanced/log_level"
    KEY_PATH_HISTORY = "advanced/path_history"
    KEY_LOGS_DIR = "advanced/logs_dir"
    KEY_SNAPSHOTS_DIR = "advanced/snapshots_dir"
    KEY_ACTIVE_EXCLUSION_PRESETS = "exclusions/active_presets"
    KEY_CUSTOM_EXCLUSIONS = "exclusions/custom_patterns"

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend: StorageBackend = backend or JsonStorageBackend()

    def get(self, key: str, default: Any = None) -> Any:
        return self._backend.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._backend.set(key, value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self._backend.get(key, default)
        return bool(val)

    def get_int(self, key: str, default: int = 0) -> int:
        val = self._backend.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        return str(self._backend.get(key, default))

    def get_path(self, key: str, default: str = "") -> Path:
        val = self._backend.get(key, default)
        return Path(val) if val else Path(default)

    # ── Convenience getters/setters ────────────────────────────────────

    def get_language(self) -> str:
        return self.get_str(self.KEY_LANGUAGE, "es")

    def set_language(self, lang: str) -> None:
        self.set(self.KEY_LANGUAGE, lang)

    def get_remember_last_paths(self) -> bool:
        return self.get_bool(self.KEY_REMEMBER_LAST_PATHS, True)

    def set_remember_last_paths(self, value: bool) -> None:
        self.set(self.KEY_REMEMBER_LAST_PATHS, value)

    def get_last_source(self) -> str:
        return self.get_str(self.KEY_LAST_SOURCE, "")

    def set_last_source(self, path: str) -> None:
        self.set(self.KEY_LAST_SOURCE, path)

    def get_last_dest(self) -> str:
        return self.get_str(self.KEY_LAST_DEST, "")

    def set_last_dest(self, path: str) -> None:
        self.set(self.KEY_LAST_DEST, path)

    def get_compare_mode(self) -> CompareMode:
        val = self.get_str(self.KEY_COMPARE_MODE, Config.DEFAULT_COMPARE_MODE)
        try:
            return CompareMode(val)
        except ValueError:
            return CompareMode.SMART

    def set_compare_mode(self, mode: CompareMode) -> None:
        self.set(self.KEY_COMPARE_MODE, mode.value)

    def get_conflict_policy(self) -> ConflictPolicy:
        val = self.get_str(self.KEY_CONFLICT_POLICY, Config.DEFAULT_CONFLICT_POLICY)
        if val == "ask_each":
            val = "mark_pending"
        try:
            return ConflictPolicy(val)
        except ValueError:
            return ConflictPolicy.SOURCE_WINS

    def set_conflict_policy(self, policy: ConflictPolicy) -> None:
        self.set(self.KEY_CONFLICT_POLICY, policy.value)

    def get_verify_mode(self) -> VerifyMode:
        val = self.get_str(self.KEY_VERIFY_MODE, Config.DEFAULT_VERIFY_MODE)
        try:
            return VerifyMode(val)
        except ValueError:
            return VerifyMode.FULL

    def set_verify_mode(self, mode: VerifyMode) -> None:
        self.set(self.KEY_VERIFY_MODE, mode.value)

    def get_use_trash(self) -> bool:
        return self.get_bool(self.KEY_USE_TRASH, Config.DEFAULT_USE_TRASH)

    def set_use_trash(self, use: bool) -> None:
        self.set(self.KEY_USE_TRASH, use)

    def get_spot_check_percent(self) -> int:
        return self.get_int(self.KEY_SPOT_CHECK_PERCENT, Config.DEFAULT_SPOT_CHECK_PERCENT)

    def set_spot_check_percent(self, percent: int) -> None:
        self.set(self.KEY_SPOT_CHECK_PERCENT, percent)

    def get_buffer_size(self) -> int:
        return self.get_int(self.KEY_BUFFER_SIZE, 65536)

    def set_buffer_size(self, size: int) -> None:
        self.set(self.KEY_BUFFER_SIZE, size)

    def get_log_level(self) -> str:
        return self.get_str(self.KEY_LOG_LEVEL, "DEBUG")

    def set_log_level(self, level: str) -> None:
        self.set(self.KEY_LOG_LEVEL, level)

    def get_logs_dir(self) -> Path:
        val = self.get_str(self.KEY_LOGS_DIR, "")
        return Path(val) if val else Config.default_logs_dir()

    def set_logs_dir(self, path: str) -> None:
        self.set(self.KEY_LOGS_DIR, path)

    def get_snapshots_dir(self) -> Path:
        val = self.get_str(self.KEY_SNAPSHOTS_DIR, "")
        return Path(val) if val else Config.default_snapshots_dir()

    def set_snapshots_dir(self, path: str) -> None:
        self.set(self.KEY_SNAPSHOTS_DIR, path)

    def get_path_history(self) -> list[str]:
        return self._backend.get(self.KEY_PATH_HISTORY, [])

    def add_path_history(self, path: str) -> None:
        history = self.get_path_history()
        if path in history:
            history.remove(path)
        history.insert(0, path)
        history = history[:5]
        self.set(self.KEY_PATH_HISTORY, history)
        self.sync()

    def clear_path_history(self) -> None:
        self.set(self.KEY_PATH_HISTORY, [])
        self.sync()

    def get_active_exclusion_presets(self) -> list[str]:
        return self._backend.get(self.KEY_ACTIVE_EXCLUSION_PRESETS, Config.DEFAULT_EXCLUSION_PRESETS)

    def set_active_exclusion_presets(self, presets: list[str]) -> None:
        self.set(self.KEY_ACTIVE_EXCLUSION_PRESETS, presets)

    def get_custom_exclusions(self) -> list[str]:
        return self._backend.get(self.KEY_CUSTOM_EXCLUSIONS, [])

    def set_custom_exclusions(self, patterns: list[str]) -> None:
        self.set(self.KEY_CUSTOM_EXCLUSIONS, patterns)

    def sync(self) -> None:
        self._backend.sync()


settings_manager = SettingsManager()