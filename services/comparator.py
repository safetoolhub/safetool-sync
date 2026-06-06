# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Comparator — compares source and destination file lists, detects renames."""
from __future__ import annotations

from typing import Callable

from services.models import (
    CompareMode,
    ComparisonEntry,
    ConflictPolicy,
    DiffType,
    FileEntry,
    SyncAction,
    SyncDirection,
    DiskSnapshot,
)


def compare(
    source: list[FileEntry],
    dest: list[FileEntry],
    mode: CompareMode = CompareMode.SMART,
    policy: ConflictPolicy = ConflictPolicy.SOURCE_WINS,
    dest_only_default: SyncAction = SyncAction.MOVE_TO_TRASH,
    direction: SyncDirection = SyncDirection.UNIDIRECTIONAL,
    conflict_action: SyncAction | None = None,
) -> list[ComparisonEntry]:
    """Compare two file lists and produce comparison entries.

    Args:
        source: List of FileEntry from source directory.
        dest: List of FileEntry from destination directory.
        mode: Comparison mode (FAST, SMART, FULL_HASH).
        policy: Conflict resolution policy.
        dest_only_default: Default action for DEST_ONLY entries.
        direction: Sync direction (UNIDIRECTIONAL or BIDIRECTIONAL).
        conflict_action: Direct action to assign to CONFLICT entries (overrides policy).

    Returns:
        List of ComparisonEntry with diff type and default action assigned.
    """
    source_index: dict[str, FileEntry] = {e.rel_path: e for e in source}
    dest_index: dict[str, FileEntry] = {e.rel_path: e for e in dest}
    dest_lower_index: dict[str, FileEntry] = {e.rel_path.lower(): e for e in dest}

    results: list[ComparisonEntry] = []
    matched_paths: set[str] = set()
    matched_lower_paths: set[str] = set()

    for path, src_entry in source_index.items():
        matched_paths.add(path)
        if path in dest_index:
            dest_entry = dest_index[path]
            diff_type = _compare_entries(src_entry, dest_entry, mode)

            if direction == SyncDirection.BIDIRECTIONAL and diff_type == DiffType.MODIFIED:
                diff_type = DiffType.CONFLICT

            action = _default_action_for_diff(diff_type, policy, dest_only_default, conflict_action)
            results.append(ComparisonEntry(
                rel_path=path,
                diff_type=diff_type,
                source=src_entry,
                dest=dest_entry,
                action=action,
            ))
        else:
            lower_path = path.lower()
            if lower_path in dest_lower_index and lower_path not in matched_lower_paths:
                dest_entry = dest_lower_index[lower_path]
                diff_type = DiffType.CASE_MISMATCH
                action = _default_action_for_diff(diff_type, policy, dest_only_default, conflict_action)
                results.append(ComparisonEntry(
                    rel_path=path,
                    diff_type=diff_type,
                    source=src_entry,
                    dest=dest_entry,
                    action=action,
                ))
                matched_lower_paths.add(lower_path)
                matched_paths.add(path)
            else:
                results.append(ComparisonEntry(
                    rel_path=path,
                    diff_type=DiffType.SOURCE_ONLY,
                    source=src_entry,
                    dest=None,
                    action=SyncAction.COPY_TO_DEST,
                ))

    for path, dest_entry in dest_index.items():
        if path not in matched_paths and path.lower() not in matched_lower_paths:
            if direction == SyncDirection.BIDIRECTIONAL:
                action = SyncAction.COPY_TO_SOURCE
            else:
                action = _default_action_for_dest_only(dest_only_default)
            results.append(ComparisonEntry(
                rel_path=path,
                diff_type=DiffType.DEST_ONLY,
                source=None,
                dest=dest_entry,
                action=action,
            ))

    return results


def detect_renames(
    entries: list[ComparisonEntry],
    snapshot_hash_index: dict[str, list[str]] | None = None,
) -> list[ComparisonEntry]:
    """Detect renamed files by matching hashes between SOURCE_ONLY and DEST_ONLY.

    After initial comparison, files that are SOURCE_ONLY may be renames of
    files that are DEST_ONLY (same hash, different path).

    Args:
        entries: List of ComparisonEntry from initial compare().
        snapshot_hash_index: Optional dict mapping hash -> [rel_paths] from
            a previous snapshot for more accurate rename detection.

    Returns:
        Updated list with renames detected and diff_type/action modified.
    """
    source_only: dict[str, ComparisonEntry] = {}
    dest_only: dict[str, ComparisonEntry] = {}

    for entry in entries:
        if entry.diff_type == DiffType.SOURCE_ONLY and entry.source and entry.source.hash_sha256:
            source_only[entry.rel_path] = entry
        elif entry.diff_type == DiffType.DEST_ONLY and entry.dest and entry.dest.hash_sha256:
            dest_only[entry.rel_path] = entry

    if not source_only or not dest_only:
        return entries

    hash_to_source: dict[str, str] = {}
    for path, entry in source_only.items():
        h = entry.source.hash_sha256
        if h:
            hash_to_source[h] = path

    used_dest_paths: set[str] = set()
    results = list(entries)

    for i, entry in enumerate(results):
        if entry.diff_type != DiffType.DEST_ONLY:
            continue
        if not entry.dest or not entry.dest.hash_sha256:
            continue
        if entry.rel_path in used_dest_paths:
            continue

        h = entry.dest.hash_sha256
        if h in hash_to_source:
            source_path = hash_to_source[h]
            source_idx = next(
                (j for j, e in enumerate(results) if e.rel_path == source_path),
                None,
            )
            if source_idx is not None:
                src_entry = results[source_idx]
                results[i] = ComparisonEntry(
                    rel_path=entry.rel_path,
                    diff_type=DiffType.RENAMED,
                    source=src_entry.source,
                    dest=entry.dest,
                    action=SyncAction.RENAME_IN_DEST,
                    error_msg="",
                )
                results[source_idx] = ComparisonEntry(
                    rel_path=source_path,
                    diff_type=DiffType.RENAMED,
                    source=src_entry.source,
                    dest=entry.dest,
                    action=SyncAction.RENAME_IN_DEST,
                    error_msg=f"Rename source: {entry.rel_path} → {source_path}",
                )
                used_dest_paths.add(entry.rel_path)

    return results


def _compare_entries(src: FileEntry, dest: FileEntry, mode: CompareMode) -> DiffType:
    """Determine DiffType between two matching files."""
    if mode == CompareMode.FAST:
        if src.size == dest.size and abs(src.mtime - dest.mtime) < 1.0:
            return DiffType.IDENTICAL
        return DiffType.MODIFIED

    if mode == CompareMode.SMART:
        if src.hash_sha256 and dest.hash_sha256:
            return DiffType.IDENTICAL if src.hash_sha256 == dest.hash_sha256 else DiffType.MODIFIED
        if src.size == dest.size and abs(src.mtime - dest.mtime) < 1.0:
            return DiffType.IDENTICAL
        return DiffType.MODIFIED

    if mode == CompareMode.FULL_HASH:
        if src.hash_sha256 and dest.hash_sha256:
            if src.hash_sha256 == dest.hash_sha256:
                return DiffType.IDENTICAL
        if src.size == dest.size and abs(src.mtime - dest.mtime) < 1.0 and not src.hash_sha256 and not dest.hash_sha256:
            return DiffType.IDENTICAL
        return DiffType.MODIFIED

    return DiffType.MODIFIED


def _default_action_for_diff(
    diff_type: DiffType,
    policy: ConflictPolicy,
    dest_only_default: SyncAction,
    conflict_action: SyncAction | None = None,
) -> SyncAction:
    """Assign default SyncAction for a given DiffType and ConflictPolicy."""
    if diff_type == DiffType.IDENTICAL:
        return SyncAction.SKIP
    if diff_type == DiffType.SOURCE_ONLY:
        return SyncAction.COPY_TO_DEST
    if diff_type == DiffType.MODIFIED:
        if policy == ConflictPolicy.MARK_PENDING:
            return SyncAction.MARK_REVIEW
        return SyncAction.OVERWRITE_DEST
    if diff_type == DiffType.CASE_MISMATCH:
        if policy == ConflictPolicy.MARK_PENDING:
            return SyncAction.MARK_REVIEW
        return SyncAction.OVERWRITE_DEST
    if diff_type == DiffType.DEST_ONLY:
        return dest_only_default
    if diff_type == DiffType.CONFLICT:
        if conflict_action is not None:
            return conflict_action
        if policy == ConflictPolicy.SOURCE_WINS:
            return SyncAction.OVERWRITE_DEST
        if policy == ConflictPolicy.KEEP_DEST:
            return SyncAction.KEEP_DEST
        if policy == ConflictPolicy.MARK_PENDING:
            return SyncAction.MARK_REVIEW
        return SyncAction.MARK_REVIEW
    if diff_type == DiffType.RENAMED:
        return SyncAction.RENAME_IN_DEST
    return SyncAction.MARK_REVIEW


def _default_action_for_dest_only(dest_only_default: SyncAction) -> SyncAction:
    """Return the configured default action for DEST_ONLY entries."""
    return dest_only_default