# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Executor — executes sync plans with per-file verification and progress tracking."""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from config import Config
from services.models import DiffType, SyncAction, SyncPlan, SyncReport

logger = logging.getLogger(__name__)


def execute_plan(
    plan: SyncPlan,
    source_root: Path,
    dest_root: Path,
    verify_mode: str = "FULL",
    use_trash: bool = True,
    cleanup_empty_dirs: bool = False,
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
        cleanup_empty_dirs: If True, remove empty directories after deletions.
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
                if entry.diff_type == DiffType.CASE_MISMATCH:
                    success = _overwrite_case_mismatch(src_path, dst_path, dest_root)
                else:
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
                if entry.diff_type == DiffType.CASE_MISMATCH:
                    success = _overwrite_case_mismatch(src_path, dst_path, dest_root)
                else:
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

    if cleanup_empty_dirs and not dry_run:
        _do_cleanup(dest_root, progress_cb, cancel_check)

    return report


def _clear_readonly(path: Path) -> None:
    """Remove read-only attribute from a file, logging when successful."""
    try:
        if os.access(str(path), os.W_OK):
            return
        path.chmod(0o666)
        logger.info("Removed read-only attribute: %s", path)
    except OSError:
        pass


def _copy_file(src: Path, dst: Path) -> bool:
    """Copy a file, creating parent directories as needed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        _clear_readonly(dst)
    shutil.copy2(str(src), str(dst))
    return True


def _delete_file(path: Path) -> bool:
    """Permanently delete a file."""
    if path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        _clear_readonly(path)
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
    _clear_readonly(path)
    return _delete_file(path)


def _rename_file(old_path: Path, new_path: Path) -> bool:
    """Rename/move a file from old_path to new_path."""
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if new_path.exists():
        _clear_readonly(new_path)
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


def _overwrite_case_mismatch(src_path: Path | None, dst_path: Path, dest_root: Path) -> bool:
    """Handle CASE_MISMATCH overwrite by removing old case and creating correct case.

    On case-insensitive filesystems (Windows), copying to a path with different
    case won't change the existing directory/file case. This function:
    1. Finds and removes the existing entry at the case-insensitive location
    2. Fixes parent directory case if needed
    3. Copies the source with the correct case
    """
    if src_path is None:
        return False

    _fix_parent_case(dst_path, dest_root)

    if dst_path.exists():
        if dst_path.is_dir():
            shutil.rmtree(str(dst_path))
        else:
            _clear_readonly(dst_path)
            dst_path.unlink()

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src_path), str(dst_path))
    return True


def _fix_parent_case(target_path: Path, root: Path) -> bool:
    """Walk up from target_path to root, fixing directory case mismatches.

    For each directory component, if the actual on-disk name differs in case
    from the target name, rename it to match the target case.
    """
    parts = target_path.relative_to(root).parts[:-1]
    if not parts:
        return True

    current = root
    for part in parts:
        target_dir = current / part
        if not target_dir.exists():
            try:
                parent_entries = [e.name for e in current.iterdir() if e.is_dir()]
                actual_name = None
                for entry_name in parent_entries:
                    if entry_name.lower() == part.lower():
                        actual_name = entry_name
                        break

                if actual_name:
                    actual_dir = current / actual_name
                    if actual_name != part:
                        temp_dir = current / (part + "_tmp_case_fix")
                        if temp_dir.exists():
                            shutil.rmtree(str(temp_dir))
                        os.rename(str(actual_dir), str(temp_dir))
                        os.rename(str(temp_dir), str(target_dir))
                        current = target_dir
                    else:
                        current = target_dir
                else:
                    current = target_dir
            except OSError:
                current = target_dir
            continue

        try:
            parent_entries = [e.name for e in current.iterdir() if e.is_dir()]
            actual_name = None
            for entry_name in parent_entries:
                if entry_name.lower() == part.lower():
                    actual_name = entry_name
                    break

            if actual_name and actual_name != part:
                temp_dir = current / (part + "_tmp_case_fix")
                if temp_dir.exists():
                    shutil.rmtree(str(temp_dir))
                actual_dir = current / actual_name
                os.rename(str(actual_dir), str(temp_dir))
                os.rename(str(temp_dir), str(target_dir))
                current = target_dir
            else:
                current = target_dir
        except OSError:
            current = target_dir

    return True


def _do_cleanup(
    root: Path,
    progress_cb: Callable[[int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """Remove empty directories under root after sync operations."""
    from services.cleanup import cleanup_empty_dirs

    removed = cleanup_empty_dirs(root, progress_cb, cancel_check)
    if removed:
        logger.info("Cleaned up %d empty directories under %s", len(removed), root)