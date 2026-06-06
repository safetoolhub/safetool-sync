# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.executor."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from services.models import ComparisonEntry, DiffType, FileEntry, SyncAction, SyncPlan, SyncReport
from services.executor import execute_plan


def _entry(rel_path: str, size: int = 100, mtime: float = 1000.0, hash_sha256: str = "") -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=mtime, is_dir=False, hash_sha256=hash_sha256)


def _comparison(rel_path: str, diff_type: DiffType, action: SyncAction, source: FileEntry | None = None, dest: FileEntry | None = None) -> ComparisonEntry:
    return ComparisonEntry(rel_path=rel_path, diff_type=diff_type, source=source, dest=dest, action=action)


class TestExecutePlanCopy:
    def test_copy_file(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            (src_root / "hello.txt").write_text("hello world")

            source_entry = _entry("hello.txt", size=11)
            entries = [_comparison("hello.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=11, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.copied == 1
            assert (dst_root / "hello.txt").read_text() == "hello world"

    def test_copy_creates_subdirs(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            sub = src_root / "sub"
            sub.mkdir()
            (sub / "deep.txt").write_text("deep content")

            source_entry = _entry("sub/deep.txt", size=12)
            entries = [_comparison("sub/deep.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=12, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.copied == 1
            assert (dst_root / "sub" / "deep.txt").read_text() == "deep content"


class TestExecutePlanSkip:
    def test_skip_entry(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)

            entries = [_comparison("skip.txt", DiffType.IDENTICAL, SyncAction.SKIP)]
            plan = SyncPlan(entries=entries, total_copy_bytes=0, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.skipped == 1


class TestExecutePlanDelete:
    def test_delete_file(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            (dst_root / "to_delete.txt").write_text("bye")

            dest_entry = _entry("to_delete.txt")
            entries = [_comparison("to_delete.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=dest_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=0, total_delete_count=1, total_overwrite_count=0, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.deleted == 1
            assert not (dst_root / "to_delete.txt").exists()


class TestExecutePlanOverwrite:
    def test_overwrite_dest(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            (src_root / "file.txt").write_text("new content")
            (dst_root / "file.txt").write_text("old content")

            source_entry = _entry("file.txt", size=12, hash_sha256="new_hash")
            dest_entry = _entry("file.txt", size=12, hash_sha256="old_hash")
            entries = [_comparison("file.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=source_entry, dest=dest_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=12, total_delete_count=0, total_overwrite_count=1, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.overwritten == 1
            assert (dst_root / "file.txt").read_text() == "new content"


class TestExecutePlanCancel:
    def test_cancel_stops_execution(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            (src_root / "a.txt").write_text("a")
            (src_root / "b.txt").write_text("b")

            entries = [
                _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt")),
                _comparison("b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("b.txt")),
            ]
            plan = SyncPlan(entries=entries, total_copy_bytes=2, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)

            cancel_after_first = [True]

            def cancel_check():
                if cancel_after_first[0]:
                    cancel_after_first[0] = False
                    return False
                return True

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF", cancel_check=cancel_check)
            assert "Cancelled" in str(report.errors) or report.copied <= 2


class TestCaseMismatch:
    def test_case_mismatch_overwrite_fixes_case(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            (src_root / "COCHE" / "file.txt").parent.mkdir(parents=True, exist_ok=True)
            (src_root / "COCHE" / "file.txt").write_text("source content")

            (dst_root / "coche" / "file.txt").parent.mkdir(parents=True, exist_ok=True)
            (dst_root / "coche" / "file.txt").write_text("dest content")

            source_entry = _entry("COCHE/file.txt", size=14, hash_sha256="src")
            dest_entry = _entry("coche/file.txt", size=12, hash_sha256="dst")
            entries = [_comparison("COCHE/file.txt", DiffType.CASE_MISMATCH, SyncAction.OVERWRITE_DEST, source=source_entry, dest=dest_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=14, total_delete_count=0, total_overwrite_count=1, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.overwritten == 1

            actual_file = list(dst_root.rglob("file.txt"))[0]
            assert actual_file.parent.name == "COCHE"
            assert actual_file.read_text() == "source content"

    def test_case_mismatch_nested_directories(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            (src_root / "FOLDER" / "SUB" / "data.txt").parent.mkdir(parents=True, exist_ok=True)
            (src_root / "FOLDER" / "SUB" / "data.txt").write_text("new data")

            (dst_root / "folder" / "sub" / "data.txt").parent.mkdir(parents=True, exist_ok=True)
            (dst_root / "folder" / "sub" / "data.txt").write_text("old data")

            source_entry = _entry("FOLDER/SUB/data.txt", size=8, hash_sha256="src")
            dest_entry = _entry("folder/sub/data.txt", size=8, hash_sha256="dst")
            entries = [_comparison("FOLDER/SUB/data.txt", DiffType.CASE_MISMATCH, SyncAction.OVERWRITE_DEST, source=source_entry, dest=dest_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=8, total_delete_count=0, total_overwrite_count=1, total_rename_count=0)

            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.overwritten == 1

            actual_file = list(dst_root.rglob("data.txt"))[0]
            assert "FOLDER" in str(actual_file)
            assert "SUB" in str(actual_file)
            assert actual_file.read_text() == "new data"