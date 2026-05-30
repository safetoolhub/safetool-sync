# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""E2E tests — snapshot comparison flow: save two snapshots → compare → diff types."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.comparator import compare
from services.hasher import hash_file
from services.models import CompareMode, DiffType, FileEntry, SyncAction
from services.scanner import scan_directory
from services.snapshot_manager import SnapshotManager
from tests.fixtures.scenario_builder import ScenarioName, ScenarioResult


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as d:
        yield SnapshotManager(snapshots_dir=Path(d))


def _entry(rel_path: str, size: int = 100, mtime: float = 1000.0,
           hash_sha256: str = "", is_dir: bool = False) -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=mtime,
                     is_dir=is_dir, hash_sha256=hash_sha256)


def _save_dir_snapshot(manager: SnapshotManager, disk_id: str, label: str, root: Path,
                       with_hashes: bool = False):
    scan = scan_directory(root)
    if with_hashes:
        for entry in scan.entries:
            if not entry.is_dir:
                entry.hash_sha256 = hash_file(root / entry.rel_path)
    manager.save_snapshot(disk_id, label, scan.entries)


def _compare_snapshots(manager: SnapshotManager, disk_a: str, disk_b: str,
                       mode: CompareMode = CompareMode.SMART):
    files_a = [e for e in manager.load_all_entries(disk_a) if not e.is_dir]
    files_b = [e for e in manager.load_all_entries(disk_b) if not e.is_dir]
    results = compare(files_a, files_b, mode=mode)
    return {r.rel_path: r for r in results}


# ── Tests: basic diff types between two snapshots ────────────────────────────


class TestSnapshotCompareBasic:
    def test_identical_entry(self, manager):
        entries = [_entry("same.txt", size=10, mtime=100.0, hash_sha256="h1")]
        manager.save_snapshot("A", "Disk A", entries)
        manager.save_snapshot("B", "Disk B", entries)

        index = _compare_snapshots(manager, "A", "B")
        assert index["same.txt"].diff_type == DiffType.IDENTICAL
        assert index["same.txt"].action == SyncAction.SKIP

    def test_only_in_a_is_source_only(self, manager):
        manager.save_snapshot("A", "Disk A", [_entry("onlyA.txt", hash_sha256="h1")])
        manager.save_snapshot("B", "Disk B", [_entry("other.txt", hash_sha256="h2")])

        index = _compare_snapshots(manager, "A", "B")
        assert index["onlyA.txt"].diff_type == DiffType.SOURCE_ONLY

    def test_only_in_b_is_dest_only(self, manager):
        manager.save_snapshot("A", "Disk A", [_entry("other.txt", hash_sha256="h2")])
        manager.save_snapshot("B", "Disk B", [_entry("onlyB.txt", hash_sha256="h1")])

        index = _compare_snapshots(manager, "A", "B")
        assert index["onlyB.txt"].diff_type == DiffType.DEST_ONLY

    def test_modified_by_hash(self, manager):
        manager.save_snapshot("A", "Disk A", [_entry("mod.txt", size=10, mtime=100.0, hash_sha256="hA")])
        manager.save_snapshot("B", "Disk B", [_entry("mod.txt", size=10, mtime=100.0, hash_sha256="hB")])

        index = _compare_snapshots(manager, "A", "B", mode=CompareMode.SMART)
        assert index["mod.txt"].diff_type == DiffType.MODIFIED

    def test_modified_by_size_fast_mode(self, manager):
        manager.save_snapshot("A", "Disk A", [_entry("mod.txt", size=10, mtime=100.0)])
        manager.save_snapshot("B", "Disk B", [_entry("mod.txt", size=99, mtime=100.0)])

        index = _compare_snapshots(manager, "A", "B", mode=CompareMode.FAST)
        assert index["mod.txt"].diff_type == DiffType.MODIFIED


class TestSnapshotCompareMixed:
    def test_all_diff_types_present(self, manager):
        a = [
            _entry("same.txt", size=10, mtime=1.0, hash_sha256="h1"),
            _entry("mod.txt", size=10, mtime=1.0, hash_sha256="hA"),
            _entry("onlyA.txt", size=5, mtime=1.0, hash_sha256="h3"),
        ]
        b = [
            _entry("same.txt", size=10, mtime=1.0, hash_sha256="h1"),
            _entry("mod.txt", size=10, mtime=1.0, hash_sha256="hB"),
            _entry("onlyB.txt", size=7, mtime=1.0, hash_sha256="h4"),
        ]
        manager.save_snapshot("A", "Disk A", a)
        manager.save_snapshot("B", "Disk B", b)

        index = _compare_snapshots(manager, "A", "B")
        found = {r.diff_type for r in index.values()}
        assert DiffType.IDENTICAL in found
        assert DiffType.MODIFIED in found
        assert DiffType.SOURCE_ONLY in found
        assert DiffType.DEST_ONLY in found

    def test_directories_excluded_from_compare(self, manager):
        a = [
            _entry("folder", size=0, mtime=1.0, is_dir=True),
            _entry("folder/file.txt", size=10, mtime=1.0, hash_sha256="h1"),
        ]
        manager.save_snapshot("A", "Disk A", a)
        manager.save_snapshot("B", "Disk B", a)

        files_a = [e for e in manager.load_all_entries("A") if not e.is_dir]
        files_b = [e for e in manager.load_all_entries("B") if not e.is_dir]
        results = compare(files_a, files_b, mode=CompareMode.SMART)
        paths = {r.rel_path for r in results}
        assert "folder" not in paths
        assert "folder/file.txt" in paths

    def test_only_differences_filter(self, manager):
        a = [
            _entry("same.txt", size=10, mtime=1.0, hash_sha256="h1"),
            _entry("mod.txt", size=10, mtime=1.0, hash_sha256="hA"),
        ]
        b = [
            _entry("same.txt", size=10, mtime=1.0, hash_sha256="h1"),
            _entry("mod.txt", size=10, mtime=1.0, hash_sha256="hB"),
        ]
        manager.save_snapshot("A", "Disk A", a)
        manager.save_snapshot("B", "Disk B", b)

        index = _compare_snapshots(manager, "A", "B")
        diffs_only = [r for r in index.values() if r.diff_type != DiffType.IDENTICAL]
        assert len(diffs_only) == 1
        assert diffs_only[0].rel_path == "mod.txt"


# ── Tests: real directory scenarios → snapshots → compare ────────────────────


class TestSnapshotCompareFromScenarios:
    def test_compare_real_dirs_via_snapshots(self, mixed_scenario: ScenarioResult, manager):
        _save_dir_snapshot(manager, "src", "Source", mixed_scenario.source_root)
        _save_dir_snapshot(manager, "dst", "Dest", mixed_scenario.dest_root)

        index = _compare_snapshots(manager, "src", "dst", mode=CompareMode.FAST)
        found = {r.diff_type for r in index.values()}
        assert DiffType.IDENTICAL in found
        assert DiffType.SOURCE_ONLY in found
        assert DiffType.DEST_ONLY in found
        assert DiffType.MODIFIED in found

    def test_stealth_conflict_detected_with_hashes(self, conflict_stealth_scenario: ScenarioResult, manager):
        _save_dir_snapshot(manager, "src", "Source", conflict_stealth_scenario.source_root, with_hashes=True)
        _save_dir_snapshot(manager, "dst", "Dest", conflict_stealth_scenario.dest_root, with_hashes=True)

        index = _compare_snapshots(manager, "src", "dst", mode=CompareMode.SMART)
        assert index["stealth_conflict.dat"].diff_type == DiffType.MODIFIED

    def test_identical_dirs_all_skip(self, identical_scenario: ScenarioResult, manager):
        _save_dir_snapshot(manager, "src", "Source", identical_scenario.source_root)
        _save_dir_snapshot(manager, "dst", "Dest", identical_scenario.dest_root)

        index = _compare_snapshots(manager, "src", "dst", mode=CompareMode.FAST)
        assert index["shared.txt"].diff_type == DiffType.IDENTICAL


# ── Tests: get_drive_for_path (setup screen drive label) ─────────────────────


class TestGetDriveForPath:
    def test_returns_drive_for_existing_path(self, tmp_path: Path):
        from services.disk_detector import get_drive_for_path, get_all_drives
        if not get_all_drives():
            pytest.skip("No drives detected in environment")
        drive = get_drive_for_path(str(tmp_path))
        assert drive is not None
        assert drive.mount_point

    def test_empty_path_returns_none(self):
        from services.disk_detector import get_drive_for_path
        assert get_drive_for_path("") is None

    def test_longest_mount_match_is_chosen(self, tmp_path: Path):
        from services.disk_detector import get_drive_for_path, get_all_drives
        drives = get_all_drives()
        if not drives:
            pytest.skip("No drives detected in environment")
        drive = get_drive_for_path(str(tmp_path))
        assert drive is not None
        import os
        common = os.path.commonpath([os.path.abspath(str(tmp_path)), os.path.abspath(drive.mount_point)])
        assert common == os.path.abspath(drive.mount_point)
