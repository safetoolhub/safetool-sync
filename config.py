# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Centralised application metadata."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


class Config:
    """Single source of truth for app metadata and constants."""

    # ── Identity ──────────────────────────────────────────────────
    APP_NAME: str = "SafeTool Sync"
    APP_VERSION: str = "1.0.5"
    APP_VERSION_SUFFIX: str = "beta"
    APP_AUTHOR: str = "SafeToolHub"
    APP_CONTACT: str = "safetoolhub@protonmail.com"
    APP_WEBSITE: str = "https://safetoolhub.org"
    APP_REPO: str = "https://github.com/safetoolhub/safetool-sync"
    APP_DESCRIPTION: str = "Mirror synchronization between disks and folders"
    APP_LICENSE: str = "GPLv3"

    # ── Paths ─────────────────────────────────────────────────────
    APP_DIR_NAME: str = ".safetool_sync"
    BASE_DIR: Path = Path.home() / APP_DIR_NAME
    LOGS_DIR: Path = BASE_DIR / "logs"
    SNAPSHOTS_DIR: Path = BASE_DIR / "snapshots"
    PROFILES_DIR: Path = BASE_DIR / "profiles"
    SYNC_STATE_DB: Path = BASE_DIR / "sync_state.db"
    SETTINGS_FILE: Path = BASE_DIR / "settings.json"

    # ── Sync defaults ─────────────────────────────────────────────
    DEFAULT_COMPARE_MODE: str = "SMART"
    DEFAULT_CONFLICT_POLICY: str = "SOURCE_WINS"
    DEFAULT_VERIFY_MODE: str = "FULL"
    DEFAULT_USE_TRASH: bool = True
    DEFAULT_SPOT_CHECK_PERCENT: int = 10
    DEFAULT_SYNC_PRESET: str = "MIRROR_SAFE"

    # ── Performance ───────────────────────────────────────────────
    HASH_BLOCK_SIZE: int = 65536  # 64 KB
    SCAN_BATCH_SIZE: int = 1000
    UI_UPDATE_INTERVAL_MS: int = 100
    RESOURCE_MONITOR_INTERVAL_S: int = 2
    MAX_WORKER_THREADS: int = 8
    MIN_WORKER_THREADS: int = 2

    # ── Sync state ────────────────────────────────────────────────
    SYNC_STATE_DB_NAME: str = "sync_state.db"
    SNAPSHOT_DB_SUFFIX: str = ".db"

    # ── Exclusion presets ─────────────────────────────────────────
    DEFAULT_EXCLUSION_PRESETS: list[str] = ["SYSTEM_FILES", "TRASH_FOLDERS"]

    @classmethod
    def get_full_version(cls) -> str:
        if cls.APP_VERSION_SUFFIX:
            return f"{cls.APP_VERSION}-{cls.APP_VERSION_SUFFIX}"
        return cls.APP_VERSION

    @classmethod
    def get_optimal_worker_threads(cls) -> int:
        cpu_count = os.cpu_count() or 4
        return max(cls.MIN_WORKER_THREADS, min(cpu_count, cls.MAX_WORKER_THREADS))

    @classmethod
    def default_logs_dir(cls) -> Path:
        return Path.home() / cls.APP_DIR_NAME / "logs"

    @classmethod
    def default_snapshots_dir(cls) -> Path:
        return Path.home() / cls.APP_DIR_NAME / "snapshots"

    @classmethod
    def ensure_dirs(cls) -> None:
        for d in (cls.BASE_DIR, cls.LOGS_DIR, cls.SNAPSHOTS_DIR, cls.PROFILES_DIR):
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_system_info(cls) -> str:
        return (
            f"{platform.system()} {platform.release()} | "
            f"Python {sys.version.split()[0]} | "
            f"CPU {os.cpu_count() or 'unknown'}"
        )