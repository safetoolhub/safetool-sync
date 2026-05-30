# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Integration test — end-to-end sync flow: scan → compare → plan → execute → verify."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from services.comparator import compare
from services.exclusion_engine import filter_entries, get_preset_patterns
from services.models import (
    CompareMode,
    ConflictPolicy,
    ExclusionPreset,
    SyncAction,
    VerifyMode,
)
from services.planner import build_plan
from services.scanner import scan_directory
from services.executor import execute_plan


@pytest.fixture
def sync_dirs():
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        src_root = Path(src)
        dst_root = Path(dst)

        (src_root / "docs").mkdir()
        (src_root / "docs" / "readme.txt").write_text("Hello World")
        (src_root / "docs" / "guide.md").write_text("# Guide")
        (src_root / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        (src_root / "config.ini").write_text("[settings]\nkey=value")

        (dst_root / "docs").mkdir()
        (dst_root / "docs" / "readme.txt").write_text("Hello World")
        (dst_root / "old_data.csv").write_text("a,b,c")

        yield src_root, dst_root


class TestFullSyncFlow:
    def test_scan_source(self, sync_dirs):
        src_root, dst_root = sync_dirs
        result = scan_directory(src_root)
        assert result.total_files >= 4
        assert result.total_size > 0
        assert len(result.errors) == 0

    def test_scan_dest(self, sync_dirs):
        src_root, dst_root = sync_dirs
        result = scan_directory(dst_root)
        assert result.total_files >= 2

    def test_scan_with_exclusions(self, sync_dirs):
        src_root, dst_root = sync_dirs
        result = scan_directory(src_root, exclusions=["*.ini"])
        names = {e.rel_path for e in result.entries}
        ini_files = [n for n in names if n.endswith(".ini")]
        assert len(ini_files) == 0

    def test_compare_source_dest(self, sync_dirs):
        src_root, dst_root = sync_dirs
        src_result = scan_directory(src_root)
        dst_result = scan_directory(dst_root)

        entries = compare(src_result.entries, dst_result.entries, mode=CompareMode.FAST)
        by_path = {e.rel_path: e for e in entries}

        assert "docs/readme.txt" in by_path
        assert by_path["docs/readme.txt"].diff_type.value in ("identical", "modified")

    def test_build_plan(self, sync_dirs):
        src_root, dst_root = sync_dirs
        src_result = scan_directory(src_root)
        dst_result = scan_directory(dst_root)

        entries = compare(src_result.entries, dst_result.entries, mode=CompareMode.FAST)
        plan = build_plan(entries, use_trash=True)

        assert plan.total_copy_bytes >= 0
        assert len(plan.entries) > 0

    def test_execute_plan_copies_files(self, sync_dirs):
        src_root, dst_root = sync_dirs

        (dst_root / "docs" / "readme.txt").write_text("Hello World")

        src_result = scan_directory(src_root)
        dst_result = scan_directory(dst_root)

        entries = compare(src_result.entries, dst_result.entries, mode=CompareMode.FAST)
        plan = build_plan(entries, use_trash=False)

        copy_actions = [e for e in plan.entries if e.action == SyncAction.COPY_TO_DEST]
        if copy_actions:
            report = execute_plan(plan, src_root, dst_root, verify_mode="OFF")
            assert report.copied >= 1 or report.skipped >= 1
            assert len(report.errors) == 0

    def test_exclude_then_sync(self, sync_dirs):
        src_root, dst_root = sync_dirs

        src_result = scan_directory(src_root, exclusions=["*.ini", "*.jpg"])
        dst_result = scan_directory(dst_root)

        entries = compare(src_result.entries, dst_result.entries, mode=CompareMode.FAST)

        ini_entries = [e for e in entries if e.rel_path.endswith(".ini")]
        jpg_entries = [e for e in entries if e.rel_path.endswith(".jpg")]
        assert len(ini_entries) == 0
        assert len(jpg_entries) == 0

    def test_preset_exclusion_then_sync(self, sync_dirs):
        src_root, dst_root = sync_dirs

        src_result = scan_directory(src_root)
        patterns = get_preset_patterns([ExclusionPreset.SYSTEM_FILES])
        filtered = filter_entries(src_result.entries, active_presets=[ExclusionPreset.SYSTEM_FILES])

        system_files = [e for e in filtered if e.rel_path in (".DS_Store", "Thumbs.db", "desktop.ini")]
        assert len(system_files) == 0

    def test_delete_dest_only_files(self, sync_dirs):
        src_root, dst_root = sync_dirs

        src_result = scan_directory(src_root)
        dst_result = scan_directory(dst_root)

        entries = compare(src_result.entries, dst_result.entries, mode=CompareMode.FAST)
        dest_only = [e for e in entries if e.diff_type.value == "dest_only"]

        assert len(dest_only) > 0
        for entry in dest_only:
            assert entry.action in (SyncAction.MOVE_TO_TRASH, SyncAction.DELETE_FROM_DEST, SyncAction.SKIP)