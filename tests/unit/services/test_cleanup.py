# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Tests for services/cleanup.py — empty directory cleanup."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.cleanup import cleanup_empty_dirs


@pytest.fixture()
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestCleanupEmptyDirs:

    def test_removes_single_empty_dir(self, temp_dir: Path) -> None:
        empty = temp_dir / "empty_folder"
        empty.mkdir()
        assert empty.exists()

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 1
        assert not empty.exists()

    def test_removes_nested_empty_dirs(self, temp_dir: Path) -> None:
        nested = temp_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)
        assert nested.exists()

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 3
        assert not (temp_dir / "a").exists()

    def test_does_not_remove_root(self, temp_dir: Path) -> None:
        removed = cleanup_empty_dirs(temp_dir)
        assert len(removed) == 0
        assert temp_dir.exists()

    def test_keeps_dirs_with_files(self, temp_dir: Path) -> None:
        folder = temp_dir / "keep_me"
        folder.mkdir()
        (folder / "file.txt").write_text("content")

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 0
        assert folder.exists()

    def test_removes_empty_parent_keeps_sibling_with_files(self, temp_dir: Path) -> None:
        empty = temp_dir / "empty"
        with_files = temp_dir / "with_files"
        empty.mkdir()
        with_files.mkdir()
        (with_files / "file.txt").write_text("content")

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 1
        assert not empty.exists()
        assert with_files.exists()

    def test_cleanup_after_file_deletion(self, temp_dir: Path) -> None:
        folder = temp_dir / "orphan_folder"
        folder.mkdir()
        (folder / "orphan.txt").write_text("data")

        (folder / "orphan.txt").unlink()

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 1
        assert not folder.exists()

    def test_deeply_nested_cleanup(self, temp_dir: Path) -> None:
        deep = temp_dir
        for i in range(10):
            deep = deep / f"level_{i}"
        deep.mkdir(parents=True)

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 10
        assert not (temp_dir / "level_0").exists()

    def test_mixed_empty_and_nonempty(self, temp_dir: Path) -> None:
        empty1 = temp_dir / "empty1"
        empty2 = temp_dir / "empty2"
        nonempty = temp_dir / "nonempty"
        empty1.mkdir()
        empty2.mkdir()
        nonempty.mkdir()
        (nonempty / "file.txt").write_text("data")
        nested_empty = nonempty / "nested_empty"
        nested_empty.mkdir()

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 3
        assert not empty1.exists()
        assert not empty2.exists()
        assert nonempty.exists()
        assert not nested_empty.exists()

    def test_cancel_check_stops_cleanup(self, temp_dir: Path) -> None:
        for i in range(5):
            (temp_dir / f"empty_{i}").mkdir()

        cancel_called = [False]

        def cancel_check() -> bool:
            if len(cancel_called) == 1:
                cancel_called[0] = True
                return True
            return False

        removed = cleanup_empty_dirs(temp_dir, cancel_check=cancel_check)

        assert cancel_called[0]
        assert len(removed) < 5

    def test_progress_callback(self, temp_dir: Path) -> None:
        for i in range(3):
            (temp_dir / f"empty_{i}").mkdir()

        calls: list[tuple[int, str]] = []
        cleanup_empty_dirs(temp_dir, progress_cb=lambda c, p: calls.append((c, p)))

        assert len(calls) == 3

    def test_special_chars_in_dir_name(self, temp_dir: Path) -> None:
        folder = temp_dir / "folder with spaces (especial)"
        folder.mkdir()

        removed = cleanup_empty_dirs(temp_dir)

        assert len(removed) == 1
        assert not folder.exists()
