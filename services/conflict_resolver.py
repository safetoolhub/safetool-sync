# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Conflict resolver — groups conflicts and applies batch resolutions."""
from __future__ import annotations

from pathlib import PurePosixPath

from services.models import ComparisonEntry, ConflictPolicy, ConflictResolution, DiffType, SyncAction


def group_conflicts(
    entries: list[ComparisonEntry],
    group_by: str = "extension",
) -> dict[str, list[ComparisonEntry]]:
    """Group conflict entries by extension or parent folder.

    Args:
        entries: List of ComparisonEntry (should contain some with diff_type=CONFLICT).
        group_by: "extension" or "folder".

    Returns:
        Dict mapping group key → list of ConflictEntries in that group.
    """
    conflicts = [e for e in entries if e.diff_type == DiffType.CONFLICT]
    groups: dict[str, list[ComparisonEntry]] = {}

    for entry in conflicts:
        path = PurePosixPath(entry.rel_path)
        if group_by == "extension":
            key = path.suffix.lower() if path.suffix else "(no extension)"
        elif group_by == "folder":
            key = str(path.parent) if str(path.parent) != "." else "(root)"
        else:
            key = "all"

        groups.setdefault(key, []).append(entry)

    return groups


def apply_resolution(
    entries: list[ComparisonEntry],
    resolution: ConflictResolution,
    group_key: str | None = None,
    group_by: str = "extension",
) -> list[ComparisonEntry]:
    """Apply a conflict resolution to matching entries.

    Args:
        entries: Full list of ComparisonEntry.
        resolution: ConflictResolution specifying the action.
        group_key: If set, only apply to entries matching this group.
        group_by: How the group_key was computed ("extension" or "folder").

    Returns:
        Updated list of ComparisonEntry with conflicts resolved.
    """
    result = list(entries)

    for i, entry in enumerate(result):
        if entry.diff_type != DiffType.CONFLICT:
            continue

        if group_key is not None:
            path = PurePosixPath(entry.rel_path)
            if group_by == "extension":
                entry_key = path.suffix.lower() if path.suffix else "(no extension)"
            elif group_by == "folder":
                entry_key = str(path.parent) if str(path.parent) != "." else "(root)"
            else:
                entry_key = "all"

            if entry_key != group_key:
                continue

        result[i] = ComparisonEntry(
            rel_path=entry.rel_path,
            diff_type=entry.diff_type,
            source=entry.source,
            dest=entry.dest,
            action=resolution.action,
            error_msg=entry.error_msg,
        )

    return result


def apply_resolution_all(
    entries: list[ComparisonEntry],
    resolution: ConflictResolution,
) -> list[ComparisonEntry]:
    """Apply a conflict resolution to ALL conflict entries.

    Args:
        entries: Full list of ComparisonEntry.
        resolution: ConflictResolution specifying the action.

    Returns:
        Updated list with all conflicts resolved.
    """
    return apply_resolution(entries, resolution, group_key=None)


def count_conflicts(entries: list[ComparisonEntry]) -> int:
    """Count the number of unresolved conflict entries."""
    return sum(1 for e in entries if e.diff_type == DiffType.CONFLICT)


def get_quick_resolution(
    entry: ComparisonEntry,
    quick_action: str,
) -> SyncAction:
    """Get a SyncAction for a quick conflict resolution button.

    Args:
        entry: The conflict ComparisonEntry.
        quick_action: One of "source", "dest", "newest", "largest".

    Returns:
        The corresponding SyncAction.
    """
    if quick_action == "source":
        return SyncAction.OVERWRITE_DEST
    if quick_action == "dest":
        return SyncAction.KEEP_DEST
    if quick_action == "newest":
        if entry.source and entry.dest:
            if entry.source.mtime > entry.dest.mtime:
                return SyncAction.OVERWRITE_DEST
            return SyncAction.KEEP_DEST
        return SyncAction.OVERWRITE_DEST
    if quick_action == "largest":
        if entry.source and entry.dest:
            if entry.source.size > entry.dest.size:
                return SyncAction.OVERWRITE_DEST
            return SyncAction.KEEP_DEST
        return SyncAction.OVERWRITE_DEST
    return SyncAction.MARK_REVIEW