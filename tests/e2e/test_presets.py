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
