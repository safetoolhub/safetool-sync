# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Session manager — save and restore review sessions as JSON."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from services.models import ComparisonEntry, DiffType, SyncAction, SyncDirection

SESSION_VERSION = "1.0"


@dataclass
class ReviewSessionEntry:
    rel_path: str
    diff_type: str
    action: str


@dataclass
class ReviewSession:
    version: str
    saved_at: str
    source_path: str
    dest_path: str
    direction: str
    entry_count: int
    analysis_hash: str
    actions: list[ReviewSessionEntry] = field(default_factory=list)


@dataclass
class SessionLoadResult:
    applied: int = 0
    skipped_invalid: int = 0
    stale: int = 0
    analysis_drifted: bool = False


class SessionVersionError(ValueError):
    """Raised when a loaded session has an unsupported version."""


class SessionPathsMismatchError(ValueError):
    """Raised when session paths do not match the current analysis."""

    def __init__(
        self,
        saved_source: str,
        saved_dest: str,
        current_source: str,
        current_dest: str,
    ) -> None:
        super().__init__("Session paths mismatch")
        self.saved_source = saved_source
        self.saved_dest = saved_dest
        self.current_source = current_source
        self.current_dest = current_dest

def compute_analysis_hash(entries: list[ComparisonEntry]) -> str:
    """Deterministic 16-char SHA-256 prefix over sorted entries.

    Tuple per entry: (rel_path, diff_type, src_size, src_mtime, dst_size, dst_mtime).
    None sides serialize as (0, 0).
    """
    sorted_entries = sorted(entries, key=lambda e: e.rel_path)
    h = hashlib.sha256()
    for e in sorted_entries:
        src_size = e.source.size if e.source else 0
        src_mtime = int(e.source.mtime) if e.source else 0
        dst_size = e.dest.size if e.dest else 0
        dst_mtime = int(e.dest.mtime) if e.dest else 0
        line = f"{e.rel_path}|{e.diff_type.value}|{src_size}|{src_mtime}|{dst_size}|{dst_mtime}\n"
        h.update(line.encode("utf-8"))
    return h.hexdigest()[:16]


def save_session(
    path: Path,
    source: str,
    dest: str,
    direction: SyncDirection,
    entries: list[ComparisonEntry],
) -> None:
    """Persist a review session as JSON.

    Writes a UTF-8 JSON document containing the analysis hash, the sync
    direction and the list of per-entry actions. Creates parent directories
    if needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": SESSION_VERSION,
        "saved_at": datetime.now().isoformat(),
        "source_path": source,
        "dest_path": dest,
        "direction": direction.value,
        "entry_count": len(entries),
        "analysis_hash": compute_analysis_hash(entries),
        "actions": [
            {
                "rel_path": e.rel_path,
                "diff_type": e.diff_type.value,
                "action": e.action.value,
            }
            for e in entries
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_session(path: Path) -> ReviewSession:
    """Read a review session from JSON.

    Raises SessionVersionError when the document version does not match
    SESSION_VERSION. Tolerates missing analysis_hash for backwards
    compatibility with sessions saved before that field existed.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("version") != SESSION_VERSION:
        raise SessionVersionError(data.get("version", ""))
    return ReviewSession(
        version=data["version"],
        saved_at=data["saved_at"],
        source_path=data["source_path"],
        dest_path=data["dest_path"],
        direction=data["direction"],
        entry_count=data["entry_count"],
        analysis_hash=data.get("analysis_hash", ""),
        actions=[
            ReviewSessionEntry(
                rel_path=a["rel_path"],
                diff_type=a["diff_type"],
                action=a["action"],
            )
            for a in data.get("actions", [])
        ],
    )


def apply_session_to_entries(
    session: ReviewSession,
    entries: list[ComparisonEntry],
    allowed_actions: dict[DiffType, list[SyncAction]],
) -> SessionLoadResult:
    """Apply session decisions to current entries. Returns counters.

    The ``allowed_actions`` map is injected to keep this module Qt-free and
    avoid importing UI constants. The caller (MainWindow) passes the same map
    used by ReviewScreen (``ALLOWED_ACTIONS`` defined there).

    For each session action:
      - If no current entry matches ``rel_path`` -> ``stale``.
      - If the action string is not a valid ``SyncAction`` -> ``skipped_invalid``.
      - If the action is not allowed for the entry's ``diff_type`` -> ``skipped_invalid``.
      - Otherwise assign the action to the entry and increment ``applied``.

    Also sets ``analysis_drifted`` by comparing the freshly computed analysis
    hash against the one stored in the session.
    """
    result = SessionLoadResult()
    result.analysis_drifted = compute_analysis_hash(entries) != session.analysis_hash

    by_path = {e.rel_path: e for e in entries}
    for sa in session.actions:
        target = by_path.get(sa.rel_path)
        if target is None:
            result.stale += 1
            continue
        try:
            action = SyncAction(sa.action)
        except ValueError:
            result.skipped_invalid += 1
            continue
        if action not in allowed_actions.get(target.diff_type, []):
            result.skipped_invalid += 1
            continue
        target.action = action
        result.applied += 1

    return result
