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


def check_destination_space(
    dest_path: Path,
    required_bytes: int,
) -> SpaceCheckResult:
    """Check if destination has enough free space.

    Args:
        dest_path: Path to the destination directory.
        required_bytes: Total bytes needed.

    Returns:
        SpaceCheckResult with free/required/sufficient info.
    """
    free_bytes = _get_free_space(dest_path)

    sufficient = free_bytes >= required_bytes
    shortfall = max(0, required_bytes - free_bytes)

    return SpaceCheckResult(
        free_bytes=free_bytes,
        required_bytes=required_bytes,
        sufficient=sufficient,
        shortfall_bytes=shortfall,
    )


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