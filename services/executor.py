# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Executor — executes sync plans with per-file verification and progress tracking."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from config import Config
from services.models import SyncAction, SyncPlan, SyncReport


def execute_plan(
    plan: SyncPlan,
    source_root: Path,
    dest_root: Path,
    verify_mode: str = "FULL",
    use_trash: bool = True,
    progress_cb: Callable[[int, str], None] | None = None,
    file_completed_cb: Callable[[str, bool], None] | None = None,
    file_verified_cb: Callable[[str, bool], None] | None = None,
    error_cb: Callable[[str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    state_manager: Optional[object] = None,
    dry_run: bool = False,
) -> SyncReport:
    """Execute a sync plan by performing file operations.

    Args:
        plan: SyncPlan with entries and action assignments.
        source_root: Root directory of the source.
        dest_root: Root directory of the destination.
        verify_mode: "OFF", "SPOT_CHECK", or "FULL".
        use_trash: If True, use send2trash for MOVE_TO_TRASH actions.
        progress_cb: Callback(percent, message).
        file_completed_cb: Callback(rel_path, success).
        file_verified_cb: Callback(rel_path, verified_ok).
        error_cb: Callback(error_message).
        cancel_check: Callable returning True to cancel.
        state_manager: Optional SyncStateManager for persistence.
        dry_run: If True, simulate all operations without touching files.

    Returns:
        SyncReport with operation counts and errors.
    """
    report = SyncReport()
    total_operations = len(plan.entries)
    completed = 0
    spot_check_counter = 0
    spot_check_interval = 10  # verify every Nth file for SPOT_CHECK

    for entry in plan.entries:
        if cancel_check and cancel_check():
            report.errors.append("Cancelled by user")
            break

        completed += 1
        if progress_cb:
            pct = int((completed / total_operations) * 100) if total_operations > 0 else 0
            progress_cb(pct, f"[{entry.action.value}] {entry.rel_path}")

        success = False
        try:
            src_path = source_root / entry.rel_path if entry.source else None
            dst_path = dest_root / entry.rel_path

            if dry_run:
                success = True
                if entry.action == SyncAction.COPY_TO_DEST:
                    report.copied += 1
                    report.verified += 1
                elif entry.action == SyncAction.COPY_TO_SOURCE:
                    report.copied += 1
                    report.verified += 1
                elif entry.action == SyncAction.OVERWRITE_DEST:
                    report.overwritten += 1
                    report.verified += 1
                elif entry.action == SyncAction.OVERWRITE_SOURCE:
                    report.overwritten += 1
                    report.verified += 1
                elif entry.action == SyncAction.DELETE_FROM_DEST:
                    report.deleted += 1
                elif entry.action == SyncAction.MOVE_TO_TRASH:
                    report.trashed += 1
                elif entry.action == SyncAction.RENAME_IN_DEST:
                    report.renamed += 1
                else:
                    report.skipped += 1

                if entry.source:
                    report.total_bytes += entry.source.size
                elif entry.dest and entry.action in (SyncAction.COPY_TO_SOURCE, SyncAction.OVERWRITE_SOURCE):
                    report.total_bytes += entry.dest.size

                if file_completed_cb:
                    file_completed_cb(entry.rel_path, True)

                if state_manager and hasattr(state_manager, 'mark_completed'):
                    state_manager.mark_completed(entry.rel_path, entry.action.value)
                continue

            if entry.action == SyncAction.COPY_TO_DEST:
                success = _copy_file(src_path, dst_path)
                report.copied += 1
                if success and verify_mode != "OFF":
                    should_verify = (
                        verify_mode == "FULL"
                        or (verify_mode == "SPOT_CHECK" and spot_check_counter % spot_check_interval == 0)
                    )
                    if should_verify:
                        verified = _verify_file(src_path, dst_path)
                        if file_verified_cb:
                            file_verified_cb(entry.rel_path, verified)
                        if verified:
                            report.verified += 1
                        else:
                            report.verification_failures += 1
                            report.errors.append(f"Verification failed: {entry.rel_path}")
                    spot_check_counter += 1
                else:
                    report.verified += 1

            elif entry.action == SyncAction.COPY_TO_SOURCE:
                if entry.dest:
                    src_from_dest = dest_root / entry.rel_path
                    dst_to_source = source_root / entry.rel_path
                    success = _copy_file(src_from_dest, dst_to_source)
                    report.copied += 1
                    if success and verify_mode != "OFF":
                        should_verify = (
                            verify_mode == "FULL"
                            or (verify_mode == "SPOT_CHECK" and spot_check_counter % spot_check_interval == 0)
                        )
                        if should_verify:
                            verified = _verify_file(src_from_dest, dst_to_source)
                            if file_verified_cb:
                                file_verified_cb(entry.rel_path, verified)
                            if verified:
                                report.verified += 1
                            else:
                                report.verification_failures += 1
                                report.errors.append(f"Verification failed: {entry.rel_path}")
                        spot_check_counter += 1
                    else:
                        report.verified += 1
                else:
                    success = True
                    report.skipped += 1

            elif entry.action == SyncAction.OVERWRITE_DEST:
                success = _copy_file(src_path, dst_path)
                report.overwritten += 1
                if success and verify_mode != "OFF":
                    should_verify = (
                        verify_mode == "FULL"
                        or (verify_mode == "SPOT_CHECK" and spot_check_counter % spot_check_interval == 0)
                    )
                    if should_verify:
                        verified = _verify_file(src_path, dst_path)
                        if file_verified_cb:
                            file_verified_cb(entry.rel_path, verified)
                        if verified:
                            report.verified += 1
                        else:
                            report.verification_failures += 1
                            report.errors.append(f"Verification failed: {entry.rel_path}")
                    spot_check_counter += 1
                else:
                    report.verified += 1

            elif entry.action == SyncAction.OVERWRITE_SOURCE:
                if entry.dest:
                    src_from_dest = dest_root / entry.rel_path
                    dst_to_source = source_root / entry.rel_path
                    success = _copy_file(src_from_dest, dst_to_source)
                    report.overwritten += 1
                    if success and verify_mode != "OFF":
                        should_verify = (
                            verify_mode == "FULL"
                            or (verify_mode == "SPOT_CHECK" and spot_check_counter % spot_check_interval == 0)
                        )
                        if should_verify:
                            verified = _verify_file(src_from_dest, dst_to_source)
                            if file_verified_cb:
                                file_verified_cb(entry.rel_path, verified)
                            if verified:
                                report.verified += 1
                            else:
                                report.verification_failures += 1
                                report.errors.append(f"Verification failed: {entry.rel_path}")
                        spot_check_counter += 1
                    else:
                        report.verified += 1
                else:
                    success = True
                    report.skipped += 1

            elif entry.action == SyncAction.DELETE_FROM_DEST:
                success = _delete_file(dst_path)
                report.deleted += 1

            elif entry.action == SyncAction.MOVE_TO_TRASH:
                success = _move_to_trash(dst_path, use_trash)
                report.trashed += 1

            elif entry.action == SyncAction.RENAME_IN_DEST:
                if entry.source and entry.dest:
                    new_path = dest_root / entry.source.rel_path
                    success = _rename_file(dst_path, new_path)
                    report.renamed += 1
                else:
                    success = True

            elif entry.action == SyncAction.KEEP_DEST:
                success = True
                report.skipped += 1

            elif entry.action == SyncAction.KEEP_SOURCE:
                success = True
                report.skipped += 1

            elif entry.action == SyncAction.SKIP:
                success = True
                report.skipped += 1

            elif entry.action == SyncAction.MARK_REVIEW:
                success = True
                report.skipped += 1

            if entry.source:
                report.total_bytes += entry.source.size
            elif entry.dest and entry.action in (SyncAction.COPY_TO_SOURCE, SyncAction.OVERWRITE_SOURCE):
                report.total_bytes += entry.dest.size

        except Exception as e:
            success = False
            error_msg = f"Error processing {entry.rel_path}: {e}"
            report.errors.append(error_msg)
            if error_cb:
                error_cb(error_msg)

        if file_completed_cb:
            file_completed_cb(entry.rel_path, success)

        if state_manager and hasattr(state_manager, 'mark_completed'):
            state_manager.mark_completed(entry.rel_path, entry.action.value)

    return report


def _copy_file(src: Path, dst: Path) -> bool:
    """Copy a file, creating parent directories as needed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    return True


def _delete_file(path: Path) -> bool:
    """Permanently delete a file."""
    if path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()
    return True


def _move_to_trash(path: Path, use_trash: bool = True) -> bool:
    """Move file to trash or permanently delete as fallback."""
    if use_trash:
        try:
            from send2trash import send2trash
            send2trash(str(path))
            return True
        except ImportError:
            pass
        except Exception:
            pass
    return _delete_file(path)


def _rename_file(old_path: Path, new_path: Path) -> bool:
    """Rename/move a file from old_path to new_path."""
    new_path.parent.mkdir(parents=True, exist_ok=True)
    os.rename(str(old_path), str(new_path))
    return True


def _verify_file(src: Path, dst: Path) -> bool:
    """Verify a copied file by comparing SHA-256 hashes."""
    try:
        src_hash = _hash_file(src)
        dst_hash = _hash_file(dst)
        return src_hash == dst_hash
    except Exception:
        return False


def _hash_file(path: Path, block_size: int = Config.HASH_BLOCK_SIZE) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            sha.update(block)
    return sha.hexdigest()