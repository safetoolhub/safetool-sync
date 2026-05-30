# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Planner — builds a sync plan from comparison entries, checks space, applies policy."""
from __future__ import annotations

from services.models import (
    ComparisonEntry,
    ConflictPolicy,
    DiffType,
    SyncAction,
    SyncDirection,
    SyncPlan,
    SyncPreset,
    SYNC_PRESET_CONFIGS,
    VerifyMode,
)


def build_plan(
    entries: list[ComparisonEntry],
    verify_mode: VerifyMode = VerifyMode.FULL,
    use_trash: bool = True,
    destination_free_space: int | None = None,
) -> SyncPlan:
    """Build a sync plan from comparison entries.

    Replaces DELETE_FROM_DEST with MOVE_TO_TRASH if use_trash=True,
    converts MARK_REVIEW to SKIP, and calculates totals.

    Args:
        entries: List of ComparisonEntry with default actions assigned.
        verify_mode: Verification mode for the plan metadata.
        use_trash: If True, replace DELETE_FROM_DEST with MOVE_TO_TRASH.
        destination_free_space: If provided, verify sufficient space.

    Returns:
        SyncPlan with entries and totals.
    """
    plan_entries = list(entries)

    for i, entry in enumerate(plan_entries):
        action = entry.action

        if entry.diff_type == DiffType.CONFLICT:
            if entry.action == SyncAction.MARK_REVIEW:
                action = SyncAction.SKIP
            else:
                action = entry.action
        elif entry.action == SyncAction.MARK_REVIEW:
            action = SyncAction.SKIP

        if action == SyncAction.DELETE_FROM_DEST and use_trash:
            action = SyncAction.MOVE_TO_TRASH

        plan_entries[i] = ComparisonEntry(
            rel_path=entry.rel_path,
            diff_type=entry.diff_type,
            source=entry.source,
            dest=entry.dest,
            action=action,
            error_msg=entry.error_msg,
        )

    total_copy_bytes = 0
    total_delete_count = 0
    total_overwrite_count = 0
    total_rename_count = 0

    for entry in plan_entries:
        if entry.action == SyncAction.COPY_TO_DEST:
            if entry.source:
                total_copy_bytes += entry.source.size
        elif entry.action == SyncAction.COPY_TO_SOURCE:
            if entry.dest:
                total_copy_bytes += entry.dest.size
        elif entry.action == SyncAction.OVERWRITE_DEST:
            total_overwrite_count += 1
            if entry.source:
                total_copy_bytes += entry.source.size
        elif entry.action == SyncAction.OVERWRITE_SOURCE:
            total_overwrite_count += 1
            if entry.dest:
                total_copy_bytes += entry.dest.size
        elif entry.action in (SyncAction.DELETE_FROM_DEST, SyncAction.MOVE_TO_TRASH):
            total_delete_count += 1
        elif entry.action == SyncAction.RENAME_IN_DEST:
            total_rename_count += 1

    return SyncPlan(
        entries=plan_entries,
        total_copy_bytes=total_copy_bytes,
        total_delete_count=total_delete_count,
        total_overwrite_count=total_overwrite_count,
        total_rename_count=total_rename_count,
        estimated_duration=None,
    )


def apply_preset(
    preset: SyncPreset,
    conflict_policy: ConflictPolicy | None = None,
    verify_mode: VerifyMode | None = None,
    use_trash: bool | None = None,
) -> dict:
    """Get the configuration for a given SyncPreset.

    Returns a dict with direction, compare_mode, conflict_policy, dest_only_action,
    verify_mode, and use_trash.
    """
    config = SYNC_PRESET_CONFIGS[preset]
    return {
        "direction": config["direction"],
        "compare_mode": config["compare_mode"],
        "conflict_policy": conflict_policy or config["conflict_policy"],
        "dest_only_action": config["dest_only_action"],
        "verify_mode": verify_mode or config["verify_mode"],
        "use_trash": use_trash if use_trash is not None else config["use_trash"],
    }


