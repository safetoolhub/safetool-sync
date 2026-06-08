# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Space calculator — checks destination has enough free space for sync plan."""
from __future__ import annotations

from pathlib import Path

from services.models import SpaceCheckResult, SyncPlan

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


def calculate_required_space(plan: SyncPlan) -> int:
    """Calculate the total bytes required on the destination.

    Sums up sizes of COPY_TO_DEST and OVERWRITE_DEST entries.

    Args:
        plan: The SyncPlan to calculate space requirements for.

    Returns:
        Total bytes required on destination.
    """
    total = 0
    for entry in plan.entries:
        if entry.action.value in ("copy_to_dest", "overwrite_dest"):
            if entry.source:
                total += entry.source.size
    return total


def calculate_required_space_per_side(plan: SyncPlan) -> tuple[int, int]:
    """Calculate bytes required on each side for a bidirectional plan.

    Args:
        plan: The SyncPlan to calculate space requirements for.

    Returns:
        Tuple ``(dest_required, source_required)``:
            - ``dest_required``: bytes that will be written to the destination
              (``COPY_TO_DEST`` + ``OVERWRITE_DEST``, sized by ``entry.source``).
            - ``source_required``: bytes that will be written to the source
              (``COPY_TO_SOURCE`` + ``OVERWRITE_SOURCE``, sized by ``entry.dest``).
    """
    dest_required = 0
    source_required = 0
    for entry in plan.entries:
        action_value = entry.action.value
        if action_value in ("copy_to_dest", "overwrite_dest"):
            if entry.source:
                dest_required += entry.source.size
        elif action_value in ("copy_to_source", "overwrite_source"):
            if entry.dest:
                source_required += entry.dest.size
    return dest_required, source_required


def calculate_freed_space_per_side(plan: SyncPlan) -> tuple[int, int]:
    """Calculate bytes that will be freed on each side by delete/trash actions.

    Args:
        plan: The SyncPlan to calculate freed space for.

    Returns:
        Tuple ``(dest_freed, source_freed)``:
            - ``dest_freed``: bytes freed on destination
              (``DELETE_FROM_DEST`` + ``MOVE_TO_TRASH``, sized by ``entry.dest``).
            - ``source_freed``: bytes freed on source
              (``DELETE_FROM_SOURCE`` + ``MOVE_TO_TRASH_FROM_SOURCE``, sized by ``entry.source``).
    """
    dest_freed = 0
    source_freed = 0
    for entry in plan.entries:
        action_value = entry.action.value
        if action_value in ("delete_from_dest", "move_to_trash"):
            if entry.dest:
                dest_freed += entry.dest.size
    return dest_freed, source_freed


def check_destination_space(
    dest_path: Path,
    required_bytes: int,
    freed_bytes: int = 0,
) -> SpaceCheckResult:
    """Check if destination has enough free space.

    Args:
        dest_path: Path to the destination directory.
        required_bytes: Total bytes needed for write operations.
        freed_bytes: Bytes that will be freed by delete/trash operations.

    Returns:
        SpaceCheckResult with free/required/freed/sufficient info.
    """
    free_bytes = _get_free_space(dest_path)

    net_required = max(0, required_bytes - freed_bytes)
    sufficient = free_bytes >= net_required
    shortfall = max(0, net_required - free_bytes)

    return SpaceCheckResult(
        free_bytes=free_bytes,
        required_bytes=required_bytes,
        sufficient=sufficient,
        shortfall_bytes=shortfall,
        freed_bytes=freed_bytes,
    )


def reorder_plan_for_space(plan: SyncPlan, dest_path: Path, source_path: Path | None = None) -> SyncPlan:
    """Reorder plan entries so deletions run first when space is tight.

    If current free space is insufficient for write operations but would be
    sufficient after deletions are performed, returns a new SyncPlan with
    entries reordered: DELETE_FROM_DEST and MOVE_TO_TRASH first, then the rest.

    If space is already sufficient, returns the original plan unchanged.

    Args:
        plan: The SyncPlan to potentially reorder.
        dest_path: Path to the destination directory.
        source_path: Optional path to source (for bidirectional checks).

    Returns:
        A SyncPlan with entries optimally ordered for space constraints,
        or the original plan if no reordering is needed.
    """
    free_bytes = _get_free_space(dest_path)
    required_bytes, src_required = calculate_required_space_per_side(plan)
    freed_bytes, src_freed = calculate_freed_space_per_side(plan)

    dest_needs_reorder = free_bytes < required_bytes and (free_bytes + freed_bytes) >= required_bytes

    if source_path and src_required > 0:
        src_free = _get_free_space(source_path)
        src_needs_reorder = src_free < src_required and (src_free + src_freed) >= src_required
    else:
        src_needs_reorder = False

    if not dest_needs_reorder and not src_needs_reorder:
        return plan

    delete_entries = []
    write_entries = []
    other_entries = []

    for entry in plan.entries:
        action_value = entry.action.value
        if action_value in ("delete_from_dest", "move_to_trash"):
            delete_entries.append(entry)
        elif action_value in ("copy_to_dest", "overwrite_dest", "copy_to_source", "overwrite_source"):
            write_entries.append(entry)
        else:
            other_entries.append(entry)

    delete_entries.sort(key=lambda e: e.dest.size if e.dest else 0, reverse=True)

    reordered = delete_entries + write_entries + other_entries

    import copy
    new_plan = copy.copy(plan)
    new_plan.entries = reordered
    return new_plan


def _get_free_space(path: Path) -> int:
    """Get free disk space in bytes for the given path."""
    if psutil is not None:
        try:
            usage = psutil.disk_usage(str(path))
            return usage.free
        except FileNotFoundError:
            target = path
            while target != target.parent:
                if target.exists():
                    return psutil.disk_usage(str(target)).free
                target = target.parent
            return psutil.disk_usage(str(target)).free
        except Exception:
            pass

    import os
    check = path if path.exists() else path.parent
    try:
        return os.statvfs(str(check)).f_bavail * os.statvfs(str(check)).f_frsize
    except (AttributeError, OSError):
        return 0