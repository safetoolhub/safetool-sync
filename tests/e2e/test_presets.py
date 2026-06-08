# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""E2E tests — sync presets: MIRROR_EXACT, MIRROR_SAFE, COPY_ONLY, CUSTOM."""
from __future__ import annotations

import pytest

from services.comparator import compare
from services.executor import execute_plan
from services.models import (
    CompareMode,
    ConflictPolicy,
    DiffType,
    SyncAction,
    SyncPreset,
    SYNC_PRESET_CONFIGS,
    VerifyMode,
)
from services.planner import apply_preset, build_plan
from services.scanner import scan_directory
from tests.fixtures.scenario_builder import ScenarioResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _run_with_preset(
    result: ScenarioResult,
    preset: SyncPreset,
):
    config = apply_preset(preset)
    src_scan = scan_directory(result.source_root)
    dst_scan = scan_directory(result.dest_root)

    comparison = compare(
        src_scan.entries,
        dst_scan.entries,
        mode=config["compare_mode"],
        policy=config["conflict_policy"],
        dest_only_default=config["dest_only_action"],
    )

    plan = build_plan(
        comparison,
        verify_mode=config["verify_mode"],
        use_trash=config["use_trash"],
    )

    report = execute_plan(
        plan,
        result.source_root,
        result.dest_root,
        verify_mode=config["verify_mode"].value.upper(),
        use_trash=config["use_trash"],
    )

    return config, comparison, plan, report


# ── Tests: MIRROR_EXACT ──────────────────────────────────────────────────────


class TestPresetMirrorExact:
    def test_dest_only_deleted_permanently(self, mixed_scenario: ScenarioResult):
        _, _, plan, report = _run_with_preset(mixed_scenario, SyncPreset.MIRROR_EXACT)

        dest_only_entries = [e for e in plan.entries if e.diff_type == DiffType.DEST_ONLY]
        for entry in dest_only_entries:
            assert entry.action in (SyncAction.DELETE_FROM_DEST, SyncAction.MOVE_TO_TRASH)

    def test_no_trash_used(self, mixed_scenario: ScenarioResult):
        config, _, _, report = _run_with_preset(mixed_scenario, SyncPreset.MIRROR_EXACT)
        assert config["use_trash"] is False

    def test_conflicts_source_wins(self, mixed_scenario: ScenarioResult):
        config, _, _, _ = _run_with_preset(mixed_scenario, SyncPreset.MIRROR_EXACT)
        assert config["conflict_policy"] == ConflictPolicy.SOURCE_WINS


# ── Tests: MIRROR_SAFE ──────────────────────────────────────────────────────


class TestPresetMirrorSafe:
    def test_dest_only_trashed(self, mixed_scenario: ScenarioResult):
        _, _, plan, _ = _run_with_preset(mixed_scenario, SyncPreset.MIRROR_SAFE)

        dest_only_entries = [e for e in plan.entries if e.diff_type == DiffType.DEST_ONLY]
        for entry in dest_only_entries:
            assert entry.action == SyncAction.MOVE_TO_TRASH

    def test_trash_enabled(self, mixed_scenario: ScenarioResult):
        config, _, _, _ = _run_with_preset(mixed_scenario, SyncPreset.MIRROR_SAFE)
        assert config["use_trash"] is True

    def test_source_only_copied(self, mixed_scenario: ScenarioResult):
        _, _, plan, report = _run_with_preset(mixed_scenario, SyncPreset.MIRROR_SAFE)
        assert report.copied >= 1


# ── Tests: COPY_ONLY ─────────────────────────────────────────────────────────


class TestPresetCopyOnly:
    def test_dest_only_skipped(self, mixed_scenario: ScenarioResult):
        _, comparison, plan, _ = _run_with_preset(mixed_scenario, SyncPreset.COPY_ONLY)

        dest_only_entries = [e for e in plan.entries if e.diff_type == DiffType.DEST_ONLY]
        for entry in dest_only_entries:
            assert entry.action == SyncAction.SKIP

    def test_nothing_deleted(self, mixed_scenario: ScenarioResult):
        _, _, _, report = _run_with_preset(mixed_scenario, SyncPreset.COPY_ONLY)
        assert report.deleted == 0
        assert report.trashed == 0

    def test_source_only_still_copied(self, mixed_scenario: ScenarioResult):
        _, _, _, report = _run_with_preset(mixed_scenario, SyncPreset.COPY_ONLY)
        assert report.copied >= 1

    def test_uses_fast_compare(self, mixed_scenario: ScenarioResult):
        config, _, _, _ = _run_with_preset(mixed_scenario, SyncPreset.COPY_ONLY)
        assert config["compare_mode"] == CompareMode.FAST


# ── Tests: CUSTOM ────────────────────────────────────────────────────────────


class TestPresetCustom:
    def test_custom_defaults_mark_pending(self):
        config = apply_preset(SyncPreset.CUSTOM)
        assert config["conflict_policy"] == ConflictPolicy.MARK_PENDING

    def test_custom_override_policy(self):
        config = apply_preset(
            SyncPreset.CUSTOM,
            conflict_policy=ConflictPolicy.SOURCE_WINS,
        )
        assert config["conflict_policy"] == ConflictPolicy.SOURCE_WINS

    def test_custom_override_trash(self):
        config = apply_preset(SyncPreset.CUSTOM, use_trash=False)
        assert config["use_trash"] is False


# ── Tests: Preset Config Validation ──────────────────────────────────────────


class TestPresetConfig:
    @pytest.mark.parametrize("preset", list(SyncPreset))
    def test_all_presets_have_required_keys(self, preset: SyncPreset):
        config = SYNC_PRESET_CONFIGS[preset]
        assert "compare_mode" in config
        assert "conflict_policy" in config
        assert "dest_only_action" in config
        assert "verify_mode" in config
        assert "use_trash" in config

    @pytest.mark.parametrize("preset", list(SyncPreset))
    def test_apply_preset_returns_all_keys(self, preset: SyncPreset):
        config = apply_preset(preset)
        assert "compare_mode" in config
        assert "conflict_policy" in config
        assert "dest_only_action" in config
        assert "verify_mode" in config
        assert "use_trash" in config


# ── Tests: Empty directory cleanup in mirror modes ───────────────────────────


def _run_with_cleanup(result: ScenarioResult, preset: SyncPreset):
    config = apply_preset(preset)
    src_scan = scan_directory(result.source_root)
    dst_scan = scan_directory(result.dest_root)

    comparison = compare(
        src_scan.entries,
        dst_scan.entries,
        mode=config["compare_mode"],
        policy=config["conflict_policy"],
        dest_only_default=config["dest_only_action"],
    )

    plan = build_plan(
        comparison,
        verify_mode=config["verify_mode"],
        use_trash=config["use_trash"],
    )

    cleanup = preset in (
        SyncPreset.MIRROR_EXACT,
        SyncPreset.MIRROR_SAFE,
        SyncPreset.MIRROR_HASH,
        SyncPreset.TWO_WAY_EXACT,
        SyncPreset.TWO_WAY_HASH,
    )

    report = execute_plan(
        plan,
        result.source_root,
        result.dest_root,
        verify_mode=config["verify_mode"].value.upper(),
        use_trash=config["use_trash"],
        cleanup_empty_dirs=cleanup,
    )

    return config, comparison, plan, report, cleanup


class TestEmptyDirCleanup:

    def test_mirror_exact_removes_empty_dest_dirs(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "keep.txt").write_text("data")
        orphan_dir = dest / "orphan_folder"
        orphan_dir.mkdir()
        (orphan_dir / "orphan.txt").write_text("orphan")
        nested_empty = dest / "a" / "b" / "c"
        nested_empty.mkdir(parents=True)

        result = ScenarioResult(source_root=source, dest_root=dest, name="empty_dir_test", expectations=[])
        _, _, _, _, cleanup = _run_with_cleanup(result, SyncPreset.MIRROR_EXACT)

        assert cleanup is True
        assert not orphan_dir.exists()
        assert not (dest / "a").exists()
        assert (dest / "keep.txt").exists()

    def test_mirror_safe_removes_empty_dest_dirs_after_trash(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "keep.txt").write_text("data")
        orphan_dir = dest / "orphan_folder"
        orphan_dir.mkdir()
        (orphan_dir / "orphan.txt").write_text("orphan")

        result = ScenarioResult(source_root=source, dest_root=dest, name="empty_dir_test", expectations=[])
        _, _, _, _, cleanup = _run_with_cleanup(result, SyncPreset.MIRROR_SAFE)

        assert cleanup is True
        assert not orphan_dir.exists()
        assert (dest / "keep.txt").exists()

    def test_copy_only_keeps_empty_dest_dirs(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "keep.txt").write_text("data")
        orphan_dir = dest / "orphan_folder"
        orphan_dir.mkdir()

        result = ScenarioResult(source_root=source, dest_root=dest, name="empty_dir_test", expectations=[])
        _, _, _, _, cleanup = _run_with_cleanup(result, SyncPreset.COPY_ONLY)

        assert cleanup is False
        assert orphan_dir.exists()

    def test_no_extra_dirs_remain_after_mirror(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "file1.txt").write_text("data1")
        (source / "sub").mkdir(parents=True, exist_ok=True)
        (source / "sub" / "file2.txt").write_text("data2")

        for d in ["old_dir1", "old_dir2", "old_dir3/nested"]:
            (dest / d).mkdir(parents=True, exist_ok=True)
            (dest / d / "old_file.txt").write_text("old")

        result = ScenarioResult(source_root=source, dest_root=dest, name="empty_dir_test", expectations=[])
        _, _, _, report, _ = _run_with_cleanup(result, SyncPreset.MIRROR_EXACT)

        assert report.deleted == 3
        dest_dirs = [d for d in dest.iterdir() if d.is_dir()]
        assert len(dest_dirs) == 1
        assert (dest / "sub").exists()


# ── Tests: System files in dest are detected and removed in mirror mode ────


class TestSystemFilesRemovedInMirror:
    """Regression: .DS_Store, desktop.ini, Thumbs.db in dest must be detected
    as DEST_ONLY and removed in mirror mode, even when SYSTEM_FILES exclusion
    is active on the source scan."""

    def test_system_files_in_dest_detected_as_dest_only(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "file1.txt").write_text("hello")
        (source / "sub").mkdir()
        (source / "sub" / "file2.txt").write_text("world")

        (dest / "file1.txt").write_text("hello")
        (dest / "sub").mkdir()
        (dest / "sub" / "file2.txt").write_text("world")
        (dest / ".DS_Store").write_bytes(b"\x00" * 10)
        (dest / "desktop.ini").write_text("[.ShellClassInfo]")
        (dest / "sub" / "Thumbs.db").write_bytes(b"\x00" * 20)

        from services.exclusion_engine import get_preset_patterns
        from services.models import ExclusionPreset

        exclusions = get_preset_patterns([ExclusionPreset.SYSTEM_FILES, ExclusionPreset.TRASH_FOLDERS])

        src_scan = scan_directory(source, exclusions=exclusions)
        dst_scan = scan_directory(dest, exclusions=[])

        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.SMART,
            policy=ConflictPolicy.SOURCE_WINS,
            dest_only_default=SyncAction.DELETE_FROM_DEST,
        )

        dest_only = [e for e in comparison if e.diff_type == DiffType.DEST_ONLY]
        dest_only_names = {e.rel_path for e in dest_only}
        assert ".DS_Store" in dest_only_names
        assert "desktop.ini" in dest_only_names
        assert "sub/Thumbs.db" in dest_only_names

    def test_system_files_removed_in_mirror_exact(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "file1.txt").write_text("hello")
        (dest / "file1.txt").write_text("hello")
        (dest / ".DS_Store").write_bytes(b"\x00" * 10)
        (dest / "desktop.ini").write_text("[.ShellClassInfo]")

        from services.exclusion_engine import get_preset_patterns
        from services.models import ExclusionPreset

        exclusions = get_preset_patterns([ExclusionPreset.SYSTEM_FILES, ExclusionPreset.TRASH_FOLDERS])

        src_scan = scan_directory(source, exclusions=exclusions)
        dst_scan = scan_directory(dest, exclusions=[])

        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.SMART,
            policy=ConflictPolicy.SOURCE_WINS,
            dest_only_default=SyncAction.DELETE_FROM_DEST,
        )

        plan = build_plan(comparison, verify_mode=VerifyMode.FULL, use_trash=False)
        report = execute_plan(plan, source, dest, verify_mode="FULL", use_trash=False)

        assert not (dest / ".DS_Store").exists()
        assert not (dest / "desktop.ini").exists()
        assert (dest / "file1.txt").exists()

    def test_dest_only_directory_with_system_files_fully_removed(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "file1.txt").write_text("hello")

        (dest / "file1.txt").write_text("hello")
        backup_dir = dest / "BACKUPS_DROPBOX"
        backup_dir.mkdir()
        (backup_dir / "desktop.ini").write_text("[.ShellClassInfo]")
        (backup_dir / ".DS_Store").write_bytes(b"\x00" * 10)
        (backup_dir / "data.txt").write_text("old backup")
        nested = backup_dir / "nested"
        nested.mkdir()
        (nested / "Thumbs.db").write_bytes(b"\x00" * 20)
        (nested / "backup.bak").write_text("old")

        from services.exclusion_engine import get_preset_patterns
        from services.models import ExclusionPreset
        from services.cleanup import cleanup_empty_dirs

        exclusions = get_preset_patterns([ExclusionPreset.SYSTEM_FILES, ExclusionPreset.TRASH_FOLDERS])

        src_scan = scan_directory(source, exclusions=exclusions)
        dst_scan = scan_directory(dest, exclusions=[])

        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.SMART,
            policy=ConflictPolicy.SOURCE_WINS,
            dest_only_default=SyncAction.DELETE_FROM_DEST,
        )

        plan = build_plan(comparison, verify_mode=VerifyMode.FULL, use_trash=False)
        execute_plan(plan, source, dest, verify_mode="FULL", use_trash=False)
        cleanup_empty_dirs(dest)

        assert not backup_dir.exists()
        assert (dest / "file1.txt").exists()
