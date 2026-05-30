# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""E2E tests — DiffType detection: scan → compare verifies every file state."""
from __future__ import annotations

import os
import time

import pytest

from services.comparator import compare, detect_renames
from services.hasher import hash_file
from services.models import CompareMode, ConflictPolicy, DiffType, SyncAction
from services.scanner import scan_directory
from tests.fixtures.scenario_builder import ScenarioName, ScenarioResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _scan_and_compare(
    result: ScenarioResult,
    mode: CompareMode = CompareMode.FAST,
    policy: ConflictPolicy = ConflictPolicy.SOURCE_WINS,
) -> dict[str, tuple]:
    src_scan = scan_directory(result.source_root)
    dst_scan = scan_directory(result.dest_root)

    entries = compare(
        src_scan.entries,
        dst_scan.entries,
        mode=mode,
        policy=policy,
    )
    return {e.rel_path: (e.diff_type, e.action) for e in entries}


def _scan_compare_with_hashes(
    result: ScenarioResult,
    mode: CompareMode = CompareMode.FULL_HASH,
    policy: ConflictPolicy = ConflictPolicy.SOURCE_WINS,
):
    src_scan = scan_directory(result.source_root)
    dst_scan = scan_directory(result.dest_root)

    for entry in src_scan.entries:
        if not entry.is_dir:
            entry.hash_sha256 = hash_file(result.source_root / entry.rel_path)
    for entry in dst_scan.entries:
        if not entry.is_dir:
            entry.hash_sha256 = hash_file(result.dest_root / entry.rel_path)

    entries = compare(
        src_scan.entries,
        dst_scan.entries,
        mode=mode,
        policy=policy,
    )
    return entries


# ── Tests: Identical ─────────────────────────────────────────────────────────


class TestDiffTypeIdentical:
    def test_identical_files_detected(self, identical_scenario: ScenarioResult):
        index = _scan_and_compare(identical_scenario)

        assert "shared.txt" in index
        diff_type, action = index["shared.txt"]
        assert diff_type == DiffType.IDENTICAL
        assert action == SyncAction.SKIP

    def test_identical_in_subdir(self, identical_scenario: ScenarioResult):
        index = _scan_and_compare(identical_scenario)
        assert "docs/manual.pdf" in index
        assert index["docs/manual.pdf"][0] == DiffType.IDENTICAL

    def test_identical_with_hash_mode(self, identical_scenario: ScenarioResult):
        entries = _scan_compare_with_hashes(identical_scenario, mode=CompareMode.FULL_HASH)
        by_path = {e.rel_path: e for e in entries}
        assert by_path["shared.txt"].diff_type == DiffType.IDENTICAL


# ── Tests: Source Only ───────────────────────────────────────────────────────


class TestDiffTypeSourceOnly:
    def test_source_only_root(self, source_only_scenario: ScenarioResult):
        index = _scan_and_compare(source_only_scenario)
        assert "new_report.docx" in index
        diff_type, action = index["new_report.docx"]
        assert diff_type == DiffType.SOURCE_ONLY
        assert action == SyncAction.COPY_TO_DEST

    def test_source_only_nested(self, source_only_scenario: ScenarioResult):
        index = _scan_and_compare(source_only_scenario)
        assert "images/photo.png" in index
        assert index["images/photo.png"][0] == DiffType.SOURCE_ONLY

    def test_source_only_deep(self, source_only_scenario: ScenarioResult):
        index = _scan_and_compare(source_only_scenario)
        assert "data/records/2024.csv" in index
        assert index["data/records/2024.csv"][0] == DiffType.SOURCE_ONLY


# ── Tests: Dest Only ─────────────────────────────────────────────────────────


class TestDiffTypeDestOnly:
    def test_dest_only_detected(self, dest_only_scenario: ScenarioResult):
        index = _scan_and_compare(dest_only_scenario)
        assert "obsolete.log" in index
        diff_type, action = index["obsolete.log"]
        assert diff_type == DiffType.DEST_ONLY
        assert action == SyncAction.MOVE_TO_TRASH

    def test_dest_only_in_subdir(self, dest_only_scenario: ScenarioResult):
        index = _scan_and_compare(dest_only_scenario)
        assert "backup/archive.tar" in index
        assert index["backup/archive.tar"][0] == DiffType.DEST_ONLY

    def test_dest_only_with_delete_policy(self, dest_only_scenario: ScenarioResult):
        src_scan = scan_directory(dest_only_scenario.source_root)
        dst_scan = scan_directory(dest_only_scenario.dest_root)

        entries = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.FAST,
            dest_only_default=SyncAction.DELETE_FROM_DEST,
        )
        by_path = {e.rel_path: e for e in entries}
        assert by_path["obsolete.log"].action == SyncAction.DELETE_FROM_DEST

    def test_dest_only_with_skip_policy(self, dest_only_scenario: ScenarioResult):
        src_scan = scan_directory(dest_only_scenario.source_root)
        dst_scan = scan_directory(dest_only_scenario.dest_root)

        entries = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.FAST,
            dest_only_default=SyncAction.SKIP,
        )
        by_path = {e.rel_path: e for e in entries}
        assert by_path["obsolete.log"].action == SyncAction.SKIP


# ── Tests: Modified ──────────────────────────────────────────────────────────


class TestDiffTypeModified:
    def test_modified_by_size(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_SIZE)
        index = _scan_and_compare(result)
        assert "growing.log" in index
        diff_type, action = index["growing.log"]
        assert diff_type == DiffType.MODIFIED
        assert action == SyncAction.OVERWRITE_DEST

    def test_modified_by_mtime(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_MTIME)
        index = _scan_and_compare(result)
        assert "touched.cfg" in index
        assert index["touched.cfg"][0] == DiffType.MODIFIED

    def test_modified_by_content(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_CONTENT)
        index = _scan_and_compare(result)
        assert "config.json" in index
        assert index["config.json"][0] == DiffType.MODIFIED

    def test_modified_by_content_smart_mode(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_CONTENT)
        index = _scan_and_compare(result, mode=CompareMode.SMART)
        assert index["config.json"][0] == DiffType.MODIFIED


# ── Tests: Conflicts ─────────────────────────────────────────────────────────


class TestDiffTypeConflict:
    def test_both_changed_detected_as_modified(self, conflict_scenario: ScenarioResult):
        index = _scan_and_compare(conflict_scenario)
        assert "notes.txt" in index
        assert index["notes.txt"][0] == DiffType.MODIFIED

    def test_both_changed_subdir(self, conflict_scenario: ScenarioResult):
        index = _scan_and_compare(conflict_scenario)
        assert "project/main.py" in index
        assert index["project/main.py"][0] == DiffType.MODIFIED

    def test_stealth_conflict_detected_fast_mode(self, conflict_stealth_scenario: ScenarioResult):
        index = _scan_and_compare(conflict_stealth_scenario, mode=CompareMode.FAST)
        assert "stealth_conflict.dat" in index
        assert index["stealth_conflict.dat"][0] == DiffType.IDENTICAL

    def test_stealth_conflict_detected_full_hash(self, conflict_stealth_scenario: ScenarioResult):
        entries = _scan_compare_with_hashes(conflict_stealth_scenario, mode=CompareMode.FULL_HASH)
        by_path = {e.rel_path: e for e in entries}
        assert by_path["stealth_conflict.dat"].diff_type == DiffType.MODIFIED

    def test_bidirectional_dest_newer(self, conflict_bidir_scenario: ScenarioResult):
        index = _scan_and_compare(conflict_bidir_scenario)
        assert "shared_doc.odt" in index
        assert index["shared_doc.odt"][0] == DiffType.MODIFIED

    def test_bidirectional_source_older(self, conflict_bidir_scenario: ScenarioResult):
        index = _scan_and_compare(conflict_bidir_scenario)
        assert "budget.xlsx" in index
        assert index["budget.xlsx"][0] == DiffType.MODIFIED

    def test_conflict_source_wins_policy(self, conflict_scenario: ScenarioResult):
        index = _scan_and_compare(
            conflict_scenario,
            policy=ConflictPolicy.SOURCE_WINS,
        )
        assert index["notes.txt"][1] == SyncAction.OVERWRITE_DEST

    def test_conflict_keep_dest_policy(self, conflict_bidir_scenario: ScenarioResult):
        src_scan = scan_directory(conflict_bidir_scenario.source_root)
        dst_scan = scan_directory(conflict_bidir_scenario.dest_root)

        entries = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.FAST,
            policy=ConflictPolicy.KEEP_DEST,
        )
        by_path = {e.rel_path: e for e in entries}
        assert by_path["shared_doc.odt"].action == SyncAction.OVERWRITE_DEST


# ── Tests: Renames ───────────────────────────────────────────────────────────


class TestDiffTypeRenamed:
    def test_rename_before_hash_is_source_dest_only(self, rename_scenario: ScenarioResult):
        index = _scan_and_compare(rename_scenario)
        assert "report_final.pdf" in index
        assert index["report_final.pdf"][0] == DiffType.SOURCE_ONLY
        assert "report_draft.pdf" in index
        assert index["report_draft.pdf"][0] == DiffType.DEST_ONLY

    def test_rename_detected_with_hashes(self, rename_scenario: ScenarioResult):
        entries = _scan_compare_with_hashes(rename_scenario)
        entries = detect_renames(entries)
        by_path = {e.rel_path: e for e in entries}

        renamed_entries = [e for e in entries if e.diff_type == DiffType.RENAMED]
        assert len(renamed_entries) > 0

    def test_cross_dir_rename_before_hash(self, rename_cross_dir_scenario: ScenarioResult):
        index = _scan_and_compare(rename_cross_dir_scenario)
        assert "2024/summary.csv" in index
        assert index["2024/summary.csv"][0] == DiffType.SOURCE_ONLY
        assert "archive/summary.csv" in index
        assert index["archive/summary.csv"][0] == DiffType.DEST_ONLY

    def test_cross_dir_rename_detected_with_hashes(self, rename_cross_dir_scenario: ScenarioResult):
        entries = _scan_compare_with_hashes(rename_cross_dir_scenario)
        entries = detect_renames(entries)

        renamed_entries = [e for e in entries if e.diff_type == DiffType.RENAMED]
        assert len(renamed_entries) > 0


# ── Tests: Edge Cases ────────────────────────────────────────────────────────


class TestDiffTypeEdgeCases:
    def test_empty_files(self, scenario_dir):
        result = scenario_dir(ScenarioName.EMPTY_FILES)
        index = _scan_and_compare(result)
        assert ".gitkeep" in index
        assert index[".gitkeep"][0] == DiffType.IDENTICAL
        assert "empty_new.txt" in index
        assert index["empty_new.txt"][0] == DiffType.SOURCE_ONLY

    def test_special_char_filenames(self, scenario_dir):
        result = scenario_dir(ScenarioName.SPECIAL_CHARS)
        index = _scan_and_compare(result)
        assert "file with spaces.txt" in index
        assert index["file with spaces.txt"][0] == DiffType.IDENTICAL

    def test_deep_nesting(self, scenario_dir):
        result = scenario_dir(ScenarioName.DEEP_NESTING)
        index = _scan_and_compare(result)
        deep_key = [k for k in index if k.endswith("bottom.txt")]
        assert len(deep_key) == 1
        assert index[deep_key[0]][0] == DiffType.MODIFIED

    def test_large_file(self, scenario_dir):
        result = scenario_dir(ScenarioName.LARGE_FILE)
        index = _scan_and_compare(result)
        assert "big_data.bin" in index
        assert index["big_data.bin"][0] == DiffType.MODIFIED

    def test_nested_dirs_mixed(self, scenario_dir):
        result = scenario_dir(ScenarioName.NESTED_DIRS)
        index = _scan_and_compare(result)
        assert "a/b/c/deep.txt" in index
        assert index["a/b/c/deep.txt"][0] == DiffType.IDENTICAL
        assert "a/b/new_in_branch.md" in index
        assert index["a/b/new_in_branch.md"][0] == DiffType.SOURCE_ONLY


# ── Tests: Mixed Scenario ────────────────────────────────────────────────────


class TestMixedScenario:
    def test_all_diff_types_present(self, mixed_scenario: ScenarioResult):
        src_scan = scan_directory(mixed_scenario.source_root)
        dst_scan = scan_directory(mixed_scenario.dest_root)

        entries = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.FAST,
        )

        found_types = {e.diff_type for e in entries}
        assert DiffType.IDENTICAL in found_types
        assert DiffType.SOURCE_ONLY in found_types
        assert DiffType.DEST_ONLY in found_types
        assert DiffType.MODIFIED in found_types

    def test_mixed_expectations_count(self, mixed_scenario: ScenarioResult):
        assert len(mixed_scenario.expectations) > 20

    def test_mixed_source_scan_no_errors(self, mixed_scenario: ScenarioResult):
        src_scan = scan_directory(mixed_scenario.source_root)
        assert len(src_scan.errors) == 0

    def test_mixed_dest_scan_no_errors(self, mixed_scenario: ScenarioResult):
        dst_scan = scan_directory(mixed_scenario.dest_root)
        assert len(dst_scan.errors) == 0


# ── Tests: Compare Modes ─────────────────────────────────────────────────────


class TestCompareModes:
    def test_fast_mode_uses_size_mtime(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_SIZE)
        index = _scan_and_compare(result, mode=CompareMode.FAST)
        assert index["growing.log"][0] == DiffType.MODIFIED

    def test_smart_mode_falls_back_to_hash(self, scenario_dir):
        result = scenario_dir(ScenarioName.CONFLICT_SAME_SIZE_DIFF_CONTENT)
        entries = _scan_compare_with_hashes(result, mode=CompareMode.SMART)
        by_path = {e.rel_path: e for e in entries}
        assert by_path["stealth_conflict.dat"].diff_type == DiffType.MODIFIED

    def test_full_hash_mode(self, scenario_dir):
        result = scenario_dir(ScenarioName.IDENTICAL)
        entries = _scan_compare_with_hashes(result, mode=CompareMode.FULL_HASH)
        by_path = {e.rel_path: e for e in entries}
        assert by_path["shared.txt"].diff_type == DiffType.IDENTICAL


# ── Tests: Same name/size/mtime but different hash ───────────────────────────


class TestSameSizeMtimeDifferentHash:
    """Files with identical name, size and mtime but different content (hash).

    This is the hardest case to detect: FAST mode cannot distinguish it
    (it sees size+mtime match and calls IDENTICAL), but SMART and FULL_HASH
    modes must detect MODIFIED when hashes are provided.
    """

    def _build_stealth_pair(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create source/dest with one file: same name, size, mtime, different bytes."""
        src_root = tmp_path / "source"
        dst_root = tmp_path / "dest"
        src_root.mkdir()
        dst_root.mkdir()

        mtime = time.time() - 3600
        size = 128
        src_content = b"A" * (size - 8) + b"_SOURCE_"
        dst_content = b"A" * (size - 8) + b"_DESTIN_"
        assert len(src_content) == len(dst_content) == size

        src_file = src_root / "stealth.dat"
        dst_file = dst_root / "stealth.dat"
        src_file.write_bytes(src_content)
        dst_file.write_bytes(dst_content)
        os.utime(str(src_file), (mtime, mtime))
        os.utime(str(dst_file), (mtime, mtime))

        return src_root, dst_root

    def test_fast_mode_cannot_detect_hash_difference(self, tmp_path: Path):
        src_root, dst_root = self._build_stealth_pair(tmp_path)
        src_scan = scan_directory(src_root)
        dst_scan = scan_directory(dst_root)

        entries = compare(src_scan.entries, dst_scan.entries, mode=CompareMode.FAST)
        by_path = {e.rel_path: e for e in entries}

        assert by_path["stealth.dat"].diff_type == DiffType.IDENTICAL

    def test_smart_mode_detects_hash_difference(self, tmp_path: Path):
        src_root, dst_root = self._build_stealth_pair(tmp_path)
        src_scan = scan_directory(src_root)
        dst_scan = scan_directory(dst_root)

        for entry in src_scan.entries:
            if not entry.is_dir:
                entry.hash_sha256 = hash_file(src_root / entry.rel_path)
        for entry in dst_scan.entries:
            if not entry.is_dir:
                entry.hash_sha256 = hash_file(dst_root / entry.rel_path)

        entries = compare(src_scan.entries, dst_scan.entries, mode=CompareMode.SMART)
        by_path = {e.rel_path: e for e in entries}

        assert by_path["stealth.dat"].diff_type == DiffType.MODIFIED
        assert by_path["stealth.dat"].action == SyncAction.OVERWRITE_DEST

    def test_full_hash_mode_detects_hash_difference(self, tmp_path: Path):
        src_root, dst_root = self._build_stealth_pair(tmp_path)
        src_scan = scan_directory(src_root)
        dst_scan = scan_directory(dst_root)

        for entry in src_scan.entries:
            if not entry.is_dir:
                entry.hash_sha256 = hash_file(src_root / entry.rel_path)
        for entry in dst_scan.entries:
            if not entry.is_dir:
                entry.hash_sha256 = hash_file(dst_root / entry.rel_path)

        entries = compare(src_scan.entries, dst_scan.entries, mode=CompareMode.FULL_HASH)
        by_path = {e.rel_path: e for e in entries}

        assert by_path["stealth.dat"].diff_type == DiffType.MODIFIED
        assert by_path["stealth.dat"].action == SyncAction.OVERWRITE_DEST

    def test_hashes_are_actually_different(self, tmp_path: Path):
        src_root, dst_root = self._build_stealth_pair(tmp_path)
        src_hash = hash_file(src_root / "stealth.dat")
        dst_hash = hash_file(dst_root / "stealth.dat")

        assert src_hash != dst_hash

    def test_size_and_mtime_are_identical(self, tmp_path: Path):
        src_root, dst_root = self._build_stealth_pair(tmp_path)
        src_stat = (src_root / "stealth.dat").stat()
        dst_stat = (dst_root / "stealth.dat").stat()

        assert src_stat.st_size == dst_stat.st_size
        assert abs(src_stat.st_mtime - dst_stat.st_mtime) < 1.0

    def test_scenario_builder_conflict_same_size_diff_content(self, scenario_dir):
        result = scenario_dir(ScenarioName.CONFLICT_SAME_SIZE_DIFF_CONTENT)
        src_root = result.source_root
        dst_root = result.dest_root

        src_stat = (src_root / "stealth_conflict.dat").stat()
        dst_stat = (dst_root / "stealth_conflict.dat").stat()
        assert src_stat.st_size == dst_stat.st_size

        src_hash = hash_file(src_root / "stealth_conflict.dat")
        dst_hash = hash_file(dst_root / "stealth_conflict.dat")
        assert src_hash != dst_hash
