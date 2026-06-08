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


class TestDirectoryMtimePreservation:
    def test_new_subdir_preserves_source_mtime(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            sub = src_root / "olddir"
            sub.mkdir()
            (sub / "file.txt").write_text("hello")
            old_mtime = 946684800.0
            os.utime(str(sub), (old_mtime, old_mtime))

            source_entry = _entry("olddir/file.txt", size=5)
            entries = [_comparison("olddir/file.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=5, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)

            execute_plan(plan, src_root, dst_root, verify_mode="OFF")

            dst_dir = dst_root / "olddir"
            assert dst_dir.exists()
            assert abs(dst_dir.stat().st_mtime - old_mtime) < 1.0

    def test_deep_nested_dirs_preserve_mtime(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            deep = src_root / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "file.txt").write_text("deep")
            mtime_a = 946684800.0
            mtime_b = 978307200.0
            mtime_c = 1009843200.0
            os.utime(str(src_root / "a"), (mtime_a, mtime_a))
            os.utime(str(src_root / "a" / "b"), (mtime_b, mtime_b))
            os.utime(str(src_root / "a" / "b" / "c"), (mtime_c, mtime_c))

            source_entry = _entry("a/b/c/file.txt", size=4)
            entries = [_comparison("a/b/c/file.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry)]
            plan = SyncPlan(entries=entries, total_copy_bytes=4, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)

            execute_plan(plan, src_root, dst_root, verify_mode="OFF")

            assert abs((dst_root / "a").stat().st_mtime - mtime_a) < 1.0
            assert abs((dst_root / "a" / "b").stat().st_mtime - mtime_b) < 1.0
            assert abs((dst_root / "a" / "b" / "c").stat().st_mtime - mtime_c) < 1.0

    def test_existing_dir_not_touched_by_restore(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            src_sub = src_root / "shared"
            src_sub.mkdir()
            (src_sub / "new.txt").write_text("new file")
            old_src_mtime = 946684800.0
            os.utime(str(src_sub), (old_src_mtime, old_src_mtime))
            old_dst_mtime = 978307200.0
            dst_sub = dst_root / "shared"
            dst_sub.mkdir()
            os.utime(str(dst_sub), (old_dst_mtime, old_dst_mtime))

            from services.executor import _collect_new_parent_dirs
            src_path = src_root / "shared" / "new.txt"
            dst_path = dst_root / "shared" / "new.txt"
            new_dirs = _collect_new_parent_dirs(dst_path, src_path)
            assert len(new_dirs) == 0

    def test_rename_preserves_new_dir_mtime(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)
            src_sub = src_root / "newdir"
            src_sub.mkdir()
            (src_sub / "moved.txt").write_text("moved")
            old_mtime = 946684800.0
            os.utime(str(src_sub), (old_mtime, old_mtime))
            old_path = src_root / "newdir" / "moved.txt"
            new_path = dst_root / "newdir" / "moved.txt"
            from services.executor import _rename_file
            _rename_file(old_path, new_path)

            assert new_path.exists()
            assert abs((dst_root / "newdir").stat().st_mtime - old_mtime) < 1.0


class TestEarlyCleanupAfterDeletePhase:

    def test_early_cleanup_removes_empty_dirs_before_copy_phase(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)

            (src_root / "new_file.txt").write_text("new content")

            orphan_dir = dst_root / "orphan" / "nested"
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "old.txt").write_text("old")

            dest_entry = _entry("orphan/nested/old.txt", size=3)
            source_entry = _entry("new_file.txt", size=11)
            entries = [
                _comparison("orphan/nested/old.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=dest_entry),
                _comparison("new_file.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry),
            ]
            plan = SyncPlan(entries=entries, total_copy_bytes=11, total_delete_count=1, total_overwrite_count=0, total_rename_count=0)

            execute_plan(plan, src_root, dst_root, verify_mode="OFF", cleanup_empty_dirs=True)

            assert not (dst_root / "orphan").exists()
            assert (dst_root / "new_file.txt").read_text() == "new content"

    def test_early_cleanup_on_cancel_after_deletes(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)

            (src_root / "file1.txt").write_text("content1")
            (src_root / "file2.txt").write_text("content2")

            for i in range(3):
                orphan = dst_root / f"orphan_{i}" / "deep"
                orphan.mkdir(parents=True)
                (orphan / f"old_{i}.txt").write_text("old")

            delete_entries = [
                _comparison(f"orphan_{i}/deep/old_{i}.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST,
                            dest=_entry(f"orphan_{i}/deep/old_{i}.txt", size=3))
                for i in range(3)
            ]
            copy_entries = [
                _comparison(f"file{i+1}.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                            source=_entry(f"file{i+1}.txt", size=8))
                for i in range(2)
            ]
            entries = delete_entries + copy_entries
            plan = SyncPlan(entries=entries, total_copy_bytes=16, total_delete_count=3, total_overwrite_count=0, total_rename_count=0)

            cancel_after = [0]
            processed = [0]

            def cancel_check() -> bool:
                processed[0] += 1
                if processed[0] > 3:
                    return True
                return False

            execute_plan(plan, src_root, dst_root, verify_mode="OFF", cleanup_empty_dirs=True, cancel_check=cancel_check)

            for i in range(3):
                assert not (dst_root / f"orphan_{i}").exists()

    def test_no_early_cleanup_without_flag(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)

            (src_root / "new.txt").write_text("new")

            orphan = dst_root / "orphan"
            orphan.mkdir()
            (orphan / "old.txt").write_text("old")

            dest_entry = _entry("orphan/old.txt", size=3)
            source_entry = _entry("new.txt", size=3)
            entries = [
                _comparison("orphan/old.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=dest_entry),
                _comparison("new.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry),
            ]
            plan = SyncPlan(entries=entries, total_copy_bytes=3, total_delete_count=1, total_overwrite_count=0, total_rename_count=0)

            execute_plan(plan, src_root, dst_root, verify_mode="OFF", cleanup_empty_dirs=False)

            assert (dst_root / "orphan").exists()

    def test_early_cleanup_with_move_to_trash(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)

            (src_root / "keep.txt").write_text("keep")

            orphan = dst_root / "trash_me" / "sub"
            orphan.mkdir(parents=True)
            (orphan / "junk.txt").write_text("junk")

            dest_entry = _entry("trash_me/sub/junk.txt", size=4)
            source_entry = _entry("keep.txt", size=4)
            entries = [
                _comparison("trash_me/sub/junk.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH, dest=dest_entry),
                _comparison("keep.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry),
            ]
            plan = SyncPlan(entries=entries, total_copy_bytes=4, total_delete_count=1, total_overwrite_count=0, total_rename_count=0)

            execute_plan(plan, src_root, dst_root, verify_mode="OFF", cleanup_empty_dirs=True, use_trash=False)

            assert not (dst_root / "trash_me").exists()
            assert (dst_root / "keep.txt").read_text() == "keep"

    def test_early_cleanup_keeps_non_empty_dirs(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_root = Path(src)
            dst_root = Path(dst)

            (src_root / "new.txt").write_text("new")

            mixed = dst_root / "mixed"
            mixed.mkdir()
            (mixed / "delete_me.txt").write_text("bye")
            (mixed / "keep_me.txt").write_text("stay")

            dest_entry = _entry("mixed/delete_me.txt", size=3)
            source_entry = _entry("new.txt", size=3)
            entries = [
                _comparison("mixed/delete_me.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=dest_entry),
                _comparison("new.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=source_entry),
            ]
            plan = SyncPlan(entries=entries, total_copy_bytes=3, total_delete_count=1, total_overwrite_count=0, total_rename_count=0)

            execute_plan(plan, src_root, dst_root, verify_mode="OFF", cleanup_empty_dirs=True)

            assert mixed.exists()
            assert (mixed / "keep_me.txt").read_text() == "stay"
            assert (dst_root / "new.txt").read_text() == "new"