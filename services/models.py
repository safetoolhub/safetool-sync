# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""All data models, enums and dataclasses for SafeTool Sync."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────────


class DiffType(Enum):
    IDENTICAL = "identical"
    SOURCE_ONLY = "source_only"
    DEST_ONLY = "dest_only"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    RENAMED = "renamed"
    ERROR_SOURCE = "error_source"
    ERROR_DEST = "error_dest"


class SyncAction(Enum):
    COPY_TO_DEST = "copy_to_dest"
    COPY_TO_SOURCE = "copy_to_source"
    OVERWRITE_DEST = "overwrite_dest"
    OVERWRITE_SOURCE = "overwrite_source"
    DELETE_FROM_DEST = "delete_from_dest"
    MOVE_TO_TRASH = "move_to_trash"
    RENAME_IN_DEST = "rename_in_dest"
    KEEP_DEST = "keep_dest"
    KEEP_SOURCE = "keep_source"
    SKIP = "skip"
    MARK_REVIEW = "mark_review"


class CompareMode(Enum):
    FAST = "fast"
    SMART = "smart"
    FULL_HASH = "full_hash"


class ConflictPolicy(Enum):
    SOURCE_WINS = "source_wins"
    KEEP_DEST = "keep_dest"
    MARK_PENDING = "mark_pending"


class SyncDirection(Enum):
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"


class VerifyMode(Enum):
    OFF = "off"
    SPOT_CHECK = "spot_check"
    FULL = "full"


class ViewMode(Enum):
    LIST = "list"
    TREE = "tree"


class SyncPreset(Enum):
    MIRROR_EXACT = "mirror_exact"
    MIRROR_SAFE = "mirror_safe"
    COPY_ONLY = "copy_only"
    MIRROR_HASH = "mirror_hash"
    TWO_WAY_SAFE = "two_way_safe"
    TWO_WAY_EXACT = "two_way_exact"
    TWO_WAY_HASH = "two_way_hash"
    CUSTOM = "custom"


class ExclusionPreset(Enum):
    SYSTEM_FILES = "system_files"
    TRASH_FOLDERS = "trash_folders"
    DEV_FOLDERS = "dev_folders"
    TEMP_FILES = "temp_files"


# ── Exclusion preset patterns ─────────────────────────────────────────────

EXCLUSION_PATTERNS: dict[ExclusionPreset, list[str]] = {
    ExclusionPreset.SYSTEM_FILES: [
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
    ],
    ExclusionPreset.TRASH_FOLDERS: [
        ".Trash*",
        ".Trashes",
        "$RECYCLE.BIN",
    ],
    ExclusionPreset.DEV_FOLDERS: [
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        ".tox",
    ],
    ExclusionPreset.TEMP_FILES: [
        "*.tmp",
        "*.bak",
        "~*",
        "*.swp",
    ],
}

# ── Sync preset configurations ────────────────────────────────────────────

SYNC_PRESET_CONFIGS: dict[SyncPreset, dict] = {
    SyncPreset.MIRROR_EXACT: {
        "direction": SyncDirection.UNIDIRECTIONAL,
        "compare_mode": CompareMode.SMART,
        "conflict_policy": ConflictPolicy.SOURCE_WINS,
        "dest_only_action": SyncAction.DELETE_FROM_DEST,
        "verify_mode": VerifyMode.FULL,
        "use_trash": False,
    },
    SyncPreset.MIRROR_SAFE: {
        "direction": SyncDirection.UNIDIRECTIONAL,
        "compare_mode": CompareMode.SMART,
        "conflict_policy": ConflictPolicy.SOURCE_WINS,
        "dest_only_action": SyncAction.MOVE_TO_TRASH,
        "verify_mode": VerifyMode.FULL,
        "use_trash": True,
    },
    SyncPreset.COPY_ONLY: {
        "direction": SyncDirection.UNIDIRECTIONAL,
        "compare_mode": CompareMode.FAST,
        "conflict_policy": ConflictPolicy.SOURCE_WINS,
        "dest_only_action": SyncAction.SKIP,
        "verify_mode": VerifyMode.SPOT_CHECK,
        "use_trash": False,
    },
    SyncPreset.MIRROR_HASH: {
        "direction": SyncDirection.UNIDIRECTIONAL,
        "compare_mode": CompareMode.FULL_HASH,
        "conflict_policy": ConflictPolicy.SOURCE_WINS,
        "dest_only_action": SyncAction.MOVE_TO_TRASH,
        "verify_mode": VerifyMode.FULL,
        "use_trash": True,
    },
    SyncPreset.TWO_WAY_SAFE: {
        "direction": SyncDirection.BIDIRECTIONAL,
        "compare_mode": CompareMode.SMART,
        "conflict_policy": ConflictPolicy.MARK_PENDING,
        "dest_only_action": SyncAction.COPY_TO_SOURCE,
        "verify_mode": VerifyMode.FULL,
        "use_trash": True,
    },
    SyncPreset.TWO_WAY_EXACT: {
        "direction": SyncDirection.BIDIRECTIONAL,
        "compare_mode": CompareMode.SMART,
        "conflict_policy": ConflictPolicy.SOURCE_WINS,
        "dest_only_action": SyncAction.COPY_TO_SOURCE,
        "verify_mode": VerifyMode.FULL,
        "use_trash": True,
    },
    SyncPreset.TWO_WAY_HASH: {
        "direction": SyncDirection.BIDIRECTIONAL,
        "compare_mode": CompareMode.FULL_HASH,
        "conflict_policy": ConflictPolicy.MARK_PENDING,
        "dest_only_action": SyncAction.COPY_TO_SOURCE,
        "verify_mode": VerifyMode.FULL,
        "use_trash": True,
    },
    SyncPreset.CUSTOM: {
        "direction": SyncDirection.UNIDIRECTIONAL,
        "compare_mode": CompareMode.SMART,
        "conflict_policy": ConflictPolicy.MARK_PENDING,
        "dest_only_action": SyncAction.MOVE_TO_TRASH,
        "verify_mode": VerifyMode.FULL,
        "use_trash": True,
    },
}

# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class FileEntry:
    rel_path: str
    size: int
    mtime: float
    is_dir: bool
    hash_sha256: str = ""


@dataclass
class ScanResult:
    entries: list[FileEntry]
    total_files: int
    total_dirs: int
    total_size: int
    scan_time: float
    errors: list[str] = field(default_factory=list)


@dataclass
class ComparisonEntry:
    rel_path: str
    diff_type: DiffType
    source: FileEntry | None
    dest: FileEntry | None
    action: SyncAction
    error_msg: str = ""


@dataclass
class DiskSnapshot:
    disk_id: str
    label: str
    timestamp: float


@dataclass
class SyncProfile:
    name: str
    source: str
    dest: str
    compare_mode: CompareMode
    conflict_policy: ConflictPolicy
    verify_mode: VerifyMode
    use_trash: bool
    exclusion_presets: list[ExclusionPreset]
    custom_exclusions: list[str]
    preset: SyncPreset = SyncPreset.MIRROR_SAFE


@dataclass
class SyncPlan:
    entries: list[ComparisonEntry]
    total_copy_bytes: int
    total_delete_count: int
    total_overwrite_count: int
    total_rename_count: int
    estimated_duration: float | None = None


@dataclass
class SyncReport:
    copied: int = 0
    overwritten: int = 0
    deleted: int = 0
    trashed: int = 0
    renamed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    verified: int = 0
    verification_failures: int = 0
    duration: float = 0.0
    total_bytes: int = 0


@dataclass
class ConflictResolution:
    action: SyncAction
    apply_to_all_similar: bool = False
    similar_pattern: str = ""


@dataclass
class DiskInfo:
    mount_point: str
    label: str
    total_bytes: int
    free_bytes: int
    fstype: str
    device: str
    uuid_or_serial: str


@dataclass
class SpaceCheckResult:
    free_bytes: int
    required_bytes: int
    sufficient: bool
    shortfall_bytes: int