# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Tests for services/empty_folder_finder.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.empty_folder_finder import (
    EmptyFolderDeleteResult,
    delete_empty_folders,
    find_empty_folders,
    generate_delete_log,
)


@pytest.fixture()
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestFindEmptyFolders:

    def test_no_empty_dirs(self, temp_dir: Path) -> None:
        folder = temp_dir / "has_file"
        folder.mkdir()
        (folder / "file.txt").write_text("content")

        result = find_empty_folders(temp_dir)

        assert len(result.empty_folders) == 0
        assert result.total_dirs_scanned == 1

    def test_single_empty_dir(self, temp_dir: Path) -> None:
        empty = temp_dir / "empty_folder"
        empty.mkdir()

        result = find_empty_folders(temp_dir)

        assert len(result.empty_folders) == 1
        assert result.empty_folders[0].rel_path == "empty_folder"
        assert result.empty_folders[0].depth == 1

    def test_nested_empty_dirs(self, temp_dir: Path) -> None:
        nested = temp_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)

        result = find_empty_folders(temp_dir)

        assert len(result.empty_folders) == 3
        paths = [f.rel_path for f in result.empty_folders]
        assert "a" in paths
        assert "a/b" in paths
        assert "a/b/c" in paths

    def test_mixed_empty_and_non_empty(self, temp_dir: Path) -> None:
        empty = temp_dir / "empty"
        empty.mkdir()
        non_empty = temp_dir / "non_empty"
        non_empty.mkdir()
        (non_empty / "file.txt").write_text("data")

        result = find_empty_folders(temp_dir)

        assert len(result.empty_folders) == 1
        assert result.empty_folders[0].rel_path == "empty"

    def test_parent_with_only_empty_children(self, temp_dir: Path) -> None:
        parent = temp_dir / "parent"
        child = parent / "child"
        child.mkdir(parents=True)

        result = find_empty_folders(temp_dir)

        paths = [f.rel_path for f in result.empty_folders]
        assert "parent" in paths
        assert "parent/child" in paths

    def test_parent_with_file_and_empty_child(self, temp_dir: Path) -> None:
        parent = temp_dir / "parent"
        parent.mkdir()
        (parent / "file.txt").write_text("data")
        empty_child = parent / "empty_child"
        empty_child.mkdir()

        result = find_empty_folders(temp_dir)

        paths = [f.rel_path for f in result.empty_folders]
        assert "parent" not in paths
        assert "parent/empty_child" in paths

    def test_depth_calculation(self, temp_dir: Path) -> None:
        deep = temp_dir / "level1" / "level2" / "level3"
        deep.mkdir(parents=True)

        result = find_empty_folders(temp_dir)

        depth_map = {f.rel_path: f.depth for f in result.empty_folders}
        assert depth_map["level1"] == 1
        assert depth_map["level1/level2"] == 2
        assert depth_map["level1/level2/level3"] == 3

    def test_cancel_stops_scan(self, temp_dir: Path) -> None:
        for i in range(100):
            (temp_dir / f"dir_{i}").mkdir()

        cancelled = False

        def cancel_check() -> bool:
            return cancelled

        result = find_empty_folders(temp_dir, cancel_check=cancel_check)
        assert len(result.empty_folders) == 100

    def test_progress_callback(self, temp_dir: Path) -> None:
        for i in range(10):
            (temp_dir / f"dir_{i}").mkdir()

        progress_calls: list[tuple[int, str]] = []

        def progress_cb(percent: int, msg: str) -> None:
            progress_calls.append((percent, msg))

        find_empty_folders(temp_dir, progress_cb=progress_cb)

    def test_empty_root_returns_no_results(self, temp_dir: Path) -> None:
        result = find_empty_folders(temp_dir)
        assert len(result.empty_folders) == 0
        assert result.total_dirs_scanned == 0

    def test_scan_time_is_positive(self, temp_dir: Path) -> None:
        (temp_dir / "empty").mkdir()
        result = find_empty_folders(temp_dir)
        assert result.scan_time >= 0

    def test_results_sorted_by_path(self, temp_dir: Path) -> None:
        (temp_dir / "zebra").mkdir()
        (temp_dir / "alpha").mkdir()
        (temp_dir / "middle").mkdir()

        result = find_empty_folders(temp_dir)

        paths = [f.rel_path for f in result.empty_folders]
        assert paths == sorted(paths, key=str.lower)

    def test_symlinks_skipped(self, temp_dir: Path) -> None:
        real_dir = temp_dir / "real"
        real_dir.mkdir()
        link = temp_dir / "link"
        try:
            link.symlink_to(real_dir)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        result = find_empty_folders(temp_dir)
        paths = [f.rel_path for f in result.empty_folders]
        assert "link" not in paths


class TestDeleteEmptyFolders:

    def test_delete_single_empty_dir(self, temp_dir: Path) -> None:
        empty = temp_dir / "empty"
        empty.mkdir()

        result = delete_empty_folders([str(empty)])

        assert len(result.removed) == 1
        assert not empty.exists()

    def test_delete_multiple_empty_dirs(self, temp_dir: Path) -> None:
        paths = []
        for i in range(5):
            d = temp_dir / f"empty_{i}"
            d.mkdir()
            paths.append(str(d))

        result = delete_empty_folders(paths, stop_at=temp_dir)

        assert len(result.removed) == 5
        assert result.total_freed_dirs == 5

    def test_cascade_removal(self, temp_dir: Path) -> None:
        nested = temp_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)

        result = delete_empty_folders([str(nested)], cascade=True, stop_at=temp_dir)

        assert len(result.removed) == 1
        assert len(result.cascade_removed) == 2
        assert result.total_freed_dirs == 3
        assert not (temp_dir / "a").exists()

    def test_no_cascade_when_disabled(self, temp_dir: Path) -> None:
        nested = temp_dir / "a" / "b"
        nested.mkdir(parents=True)

        result = delete_empty_folders([str(nested)], cascade=False)

        assert len(result.removed) == 1
        assert len(result.cascade_removed) == 0
        assert (temp_dir / "a").exists()

    def test_skip_non_empty_dir(self, temp_dir: Path) -> None:
        non_empty = temp_dir / "non_empty"
        non_empty.mkdir()
        (non_empty / "file.txt").write_text("data")

        result = delete_empty_folders([str(non_empty)])

        assert len(result.removed) == 0
        assert non_empty.exists()

    def test_skip_nonexistent_path(self, temp_dir: Path) -> None:
        result = delete_empty_folders([str(temp_dir / "nonexistent")])
        assert len(result.removed) == 0

    def test_cancel_stops_deletion(self, temp_dir: Path) -> None:
        paths = []
        for i in range(10):
            d = temp_dir / f"empty_{i}"
            d.mkdir()
            paths.append(str(d))

        call_count = 0

        def cancel_check() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 3

        result = delete_empty_folders(paths, cancel_check=cancel_check)
        assert len(result.removed) < 10

    def test_progress_callback(self, temp_dir: Path) -> None:
        paths = []
        for i in range(200):
            d = temp_dir / f"empty_{i}"
            d.mkdir()
            paths.append(str(d))

        progress_calls: list[tuple[int, str]] = []

        def progress_cb(count: int, path: str) -> None:
            progress_calls.append((count, path))

        delete_empty_folders(paths, progress_cb=progress_cb)
        assert len(progress_calls) > 0

    def test_cascade_stops_at_non_empty_parent(self, temp_dir: Path) -> None:
        parent = temp_dir / "parent"
        parent.mkdir()
        (parent / "file.txt").write_text("keep")
        empty_child = parent / "empty_child"
        empty_child.mkdir()

        result = delete_empty_folders([str(empty_child)], cascade=True)

        assert len(result.removed) == 1
        assert len(result.cascade_removed) == 0
        assert parent.exists()

    def test_failed_removal_recorded(self, temp_dir: Path) -> None:
        result = delete_empty_folders([str(temp_dir / "nonexistent")])
        assert len(result.failed) == 0


class TestGenerateDeleteLog:

    def test_log_contains_header(self, temp_dir: Path) -> None:
        result = EmptyFolderDeleteResult()
        log = generate_delete_log(result, str(temp_dir))
        assert "SafeTool Sync" in log
        assert "Empty Folder Cleanup Report" in log

    def test_log_contains_removed_paths(self, temp_dir: Path) -> None:
        result = EmptyFolderDeleteResult(
            removed=[str(temp_dir / "empty1"), str(temp_dir / "empty2")],
            total_freed_dirs=2,
        )
        log = generate_delete_log(result, str(temp_dir))
        assert "empty1" in log
        assert "empty2" in log
        assert "DIRECTLY REMOVED" in log

    def test_log_contains_cascade_paths(self, temp_dir: Path) -> None:
        result = EmptyFolderDeleteResult(
            removed=[str(temp_dir / "child")],
            cascade_removed=[str(temp_dir / "parent")],
            total_freed_dirs=2,
        )
        log = generate_delete_log(result, str(temp_dir))
        assert "CASCADE REMOVED" in log
        assert "parent" in log

    def test_log_contains_failed_paths(self, temp_dir: Path) -> None:
        result = EmptyFolderDeleteResult(
            failed=[(str(temp_dir / "locked"), "Permission denied")],
        )
        log = generate_delete_log(result, str(temp_dir))
        assert "FAILED REMOVALS" in log
        assert "Permission denied" in log

    def test_log_contains_root_path(self, temp_dir: Path) -> None:
        result = EmptyFolderDeleteResult()
        log = generate_delete_log(result, str(temp_dir))
        assert str(temp_dir) in log

    def test_log_contains_date(self, temp_dir: Path) -> None:
        result = EmptyFolderDeleteResult()
        log = generate_delete_log(result, str(temp_dir))
        assert "Date:" in log
