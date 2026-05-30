# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""E2E tests — SyncAction execution: plan → execute → verify file system state."""
from __future__ import annotations

import pytest
from pathlib import Path

from services.comparator import compare, detect_renames
from services.executor import execute_plan
from services.hasher import hash_file
from services.models import (
    CompareMode,
    ComparisonEntry,
    ConflictPolicy,
    DiffType,
    FileEntry,
    SyncAction,
    SyncPlan,
    VerifyMode,
)
from services.planner import build_plan
from services.scanner import scan_directory
from tests.fixtures.scenario_builder import ScenarioName, ScenarioResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _full_pipeline(
    result: ScenarioResult,
    mode: CompareMode = CompareMode.FAST,
    policy: ConflictPolicy = ConflictPolicy.SOURCE_WINS,
    use_trash: bool = False,
    verify: str = "OFF",
) -> tuple:
    src_scan = scan_directory(result.source_root)
    dst_scan = scan_directory(result.dest_root)

    comparison = compare(
        src_scan.entries,
        dst_scan.entries,
        mode=mode,
        policy=policy,
    )
    plan = build_plan(comparison, use_trash=use_trash)
    report = execute_plan(
        plan,
        result.source_root,
        result.dest_root,
        verify_mode=verify,
        use_trash=use_trash,
    )
    return comparison, plan, report


# ── Tests: COPY_TO_DEST ─────────────────────────────────────────────────────


class TestActionCopyToDest:
    def test_source_only_files_copied(self, source_only_scenario: ScenarioResult):
        _, _, report = _full_pipeline(source_only_scenario)

        assert report.copied >= 3
        assert len(report.errors) == 0

        assert (source_only_scenario.dest_root / "new_report.docx").exists()
        assert (source_only_scenario.dest_root / "images" / "photo.png").exists()
        assert (source_only_scenario.dest_root / "data" / "records" / "2024.csv").exists()

    def test_copied_content_matches_source(self, source_only_scenario: ScenarioResult):
        _full_pipeline(source_only_scenario)

        src_content = (source_only_scenario.source_root / "new_report.docx").read_bytes()
        dst_content = (source_only_scenario.dest_root / "new_report.docx").read_bytes()
        assert src_content == dst_content

    def test_copy_creates_parent_dirs(self, source_only_scenario: ScenarioResult):
        _full_pipeline(source_only_scenario)

        assert (source_only_scenario.dest_root / "data" / "records").is_dir()

    def test_copy_with_verification(self, source_only_scenario: ScenarioResult):
        _, _, report = _full_pipeline(source_only_scenario, verify="FULL")

        assert report.verified >= 3
        assert report.verification_failures == 0


# ── Tests: OVERWRITE_DEST ────────────────────────────────────────────────────


class TestActionOverwriteDest:
    def test_modified_files_overwritten(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_CONTENT)
        _, _, report = _full_pipeline(result)

        assert report.overwritten >= 1
        assert len(report.errors) == 0

        src_content = (result.source_root / "config.json").read_bytes()
        dst_content = (result.dest_root / "config.json").read_bytes()
        assert src_content == dst_content

    def test_overwrite_larger_with_smaller(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_SIZE)
        _full_pipeline(result)

        src_size = (result.source_root / "growing.log").stat().st_size
        dst_size = (result.dest_root / "growing.log").stat().st_size
        assert src_size == dst_size

    def test_overwrite_with_verification(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_CONTENT)
        _, _, report = _full_pipeline(result, verify="FULL")

        assert report.verification_failures == 0

    def test_overwrite_preserves_other_files(self, scenario_dir):
        result = scenario_dir(ScenarioName.MODIFIED_CONTENT)
        dummy = result.dest_root / "untouched.txt"
        dummy.write_text("do not touch me")
        src_dummy = result.source_root / "untouched.txt"
        src_dummy.write_text("do not touch me")

        _full_pipeline(result)

        assert dummy.exists()
        assert dummy.read_text() == "do not touch me"


# ── Tests: DELETE_FROM_DEST ──────────────────────────────────────────────────


class TestActionDeleteFromDest:
    def test_dest_only_files_deleted(self, dest_only_scenario: ScenarioResult):
        src_scan = scan_directory(dest_only_scenario.source_root)
        dst_scan = scan_directory(dest_only_scenario.dest_root)

        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            dest_only_default=SyncAction.DELETE_FROM_DEST,
        )
        plan = build_plan(comparison, use_trash=False)
        report = execute_plan(
            plan,
            dest_only_scenario.source_root,
            dest_only_scenario.dest_root,
            use_trash=False,
        )

        assert report.deleted >= 2
        assert not (dest_only_scenario.dest_root / "obsolete.log").exists()
        assert not (dest_only_scenario.dest_root / "backup" / "archive.tar").exists()

    def test_delete_removes_file_permanently(self, dest_only_scenario: ScenarioResult):
        target = dest_only_scenario.dest_root / "obsolete.log"
        assert target.exists()

        src_scan = scan_directory(dest_only_scenario.source_root)
        dst_scan = scan_directory(dest_only_scenario.dest_root)
        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            dest_only_default=SyncAction.DELETE_FROM_DEST,
        )
        plan = build_plan(comparison, use_trash=False)
        execute_plan(plan, dest_only_scenario.source_root, dest_only_scenario.dest_root, use_trash=False)

        assert not target.exists()


# ── Tests: SKIP ──────────────────────────────────────────────────────────────


class TestActionSkip:
    def test_identical_files_skipped(self, identical_scenario: ScenarioResult):
        _, _, report = _full_pipeline(identical_scenario)

        assert report.skipped >= 2
        assert report.copied == 0
        assert report.overwritten == 0

    def test_skip_preserves_dest_content(self, identical_scenario: ScenarioResult):
        dst_before = (identical_scenario.dest_root / "shared.txt").read_bytes()
        _full_pipeline(identical_scenario)
        dst_after = (identical_scenario.dest_root / "shared.txt").read_bytes()

        assert dst_before == dst_after

    def test_dest_only_skip_policy(self, dest_only_scenario: ScenarioResult):
        src_scan = scan_directory(dest_only_scenario.source_root)
        dst_scan = scan_directory(dest_only_scenario.dest_root)

        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            dest_only_default=SyncAction.SKIP,
        )
        plan = build_plan(comparison, use_trash=False)
        report = execute_plan(
            plan,
            dest_only_scenario.source_root,
            dest_only_scenario.dest_root,
        )

        assert report.deleted == 0
        assert report.trashed == 0
        assert (dest_only_scenario.dest_root / "obsolete.log").exists()


# ── Tests: KEEP_DEST ─────────────────────────────────────────────────────────


class TestActionKeepDest:
    def test_keep_dest_preserves_file(self, scenario_dir):
        result = scenario_dir(ScenarioName.CONFLICT_BIDIRECTIONAL)

        dst_before = (result.dest_root / "shared_doc.odt").read_bytes()

        src_scan = scan_directory(result.source_root)
        dst_scan = scan_directory(result.dest_root)
        comparison = compare(
            src_scan.entries,
            dst_scan.entries,
            mode=CompareMode.FAST,
            policy=ConflictPolicy.KEEP_DEST,
        )

        for i, entry in enumerate(comparison):
            if entry.rel_path == "shared_doc.odt":
                comparison[i] = ComparisonEntry(
                    rel_path=entry.rel_path,
                    diff_type=entry.diff_type,
                    source=entry.source,
                    dest=entry.dest,
                    action=SyncAction.KEEP_DEST,
                    error_msg=entry.error_msg,
                )

        plan = build_plan(comparison, use_trash=False)

        for i, entry in enumerate(plan.entries):
            if entry.rel_path == "shared_doc.odt":
                plan.entries[i] = ComparisonEntry(
                    rel_path=entry.rel_path,
                    diff_type=entry.diff_type,
                    source=entry.source,
                    dest=entry.dest,
                    action=SyncAction.KEEP_DEST,
                    error_msg=entry.error_msg,
                )

        report = execute_plan(plan, result.source_root, result.dest_root)

        dst_after = (result.dest_root / "shared_doc.odt").read_bytes()
        assert dst_before == dst_after
        assert report.skipped >= 1


# ── Tests: Verification Modes ────────────────────────────────────────────────


class TestVerificationModes:
    def test_verify_off_no_verification(self, source_only_scenario: ScenarioResult):
        _, _, report = _full_pipeline(source_only_scenario, verify="OFF")
        assert report.verification_failures == 0

    def test_verify_full(self, source_only_scenario: ScenarioResult):
        _, _, report = _full_pipeline(source_only_scenario, verify="FULL")
        assert report.verified >= report.copied
        assert report.verification_failures == 0

    def test_verify_spot_check(self, source_only_scenario: ScenarioResult):
        _, _, report = _full_pipeline(source_only_scenario, verify="SPOT_CHECK")
        assert report.verification_failures == 0


# ── Tests: Full Pipeline — Mixed ─────────────────────────────────────────────


class TestFullPipelineMixed:
    def test_mixed_scenario_no_errors(self, mixed_scenario: ScenarioResult):
        _, _, report = _full_pipeline(mixed_scenario, use_trash=False)
        assert len(report.errors) == 0

    def test_mixed_scenario_report_totals(self, mixed_scenario: ScenarioResult):
        _, plan, report = _full_pipeline(mixed_scenario, use_trash=False)
        total_actions = report.copied + report.overwritten + report.deleted + report.trashed + report.skipped
        assert total_actions == len(plan.entries)

    def test_rescan_after_sync_shows_identical(self, source_only_scenario: ScenarioResult):
        _full_pipeline(source_only_scenario)

        src_scan = scan_directory(source_only_scenario.source_root)
        dst_scan = scan_directory(source_only_scenario.dest_root)
        comparison = compare(src_scan.entries, dst_scan.entries, mode=CompareMode.FAST)

        source_only_after = [e for e in comparison if e.diff_type == DiffType.SOURCE_ONLY]
        assert len(source_only_after) == 0


# ── Tests: Cancel Support ────────────────────────────────────────────────────


class TestCancelSupport:
    def test_cancel_stops_execution(self, source_only_scenario: ScenarioResult):
        src_scan = scan_directory(source_only_scenario.source_root)
        dst_scan = scan_directory(source_only_scenario.dest_root)
        comparison = compare(src_scan.entries, dst_scan.entries)
        plan = build_plan(comparison)

        call_count = 0

        def cancel_after_first() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1

        report = execute_plan(
            plan,
            source_only_scenario.source_root,
            source_only_scenario.dest_root,
            cancel_check=cancel_after_first,
        )

        assert "Cancelled by user" in report.errors

    def test_cancel_preserves_already_completed(self, scenario_dir):
        result = scenario_dir(ScenarioName.MIXED_ALL)
        src_scan = scan_directory(result.source_root)
        dst_scan = scan_directory(result.dest_root)
        comparison = compare(src_scan.entries, dst_scan.entries)
        plan = build_plan(comparison, use_trash=False)

        completed_files = []

        def track_file(rel_path: str, success: bool) -> None:
            completed_files.append((rel_path, success))

        call_count = 0

        def cancel_at_five() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 5

        execute_plan(
            plan,
            result.source_root,
            result.dest_root,
            file_completed_cb=track_file,
            cancel_check=cancel_at_five,
        )

        assert len(completed_files) <= 6


# ── Tests: Progress Callbacks ────────────────────────────────────────────────


class TestProgressCallbacks:
    def test_progress_callback_called(self, source_only_scenario: ScenarioResult):
        src_scan = scan_directory(source_only_scenario.source_root)
        dst_scan = scan_directory(source_only_scenario.dest_root)
        comparison = compare(src_scan.entries, dst_scan.entries)
        plan = build_plan(comparison)

        progress_updates = []

        def on_progress(pct: int, msg: str) -> None:
            progress_updates.append((pct, msg))

        execute_plan(
            plan,
            source_only_scenario.source_root,
            source_only_scenario.dest_root,
            progress_cb=on_progress,
        )

        assert len(progress_updates) > 0
        assert progress_updates[-1][0] == 100

    def test_file_completed_callback(self, source_only_scenario: ScenarioResult):
        src_scan = scan_directory(source_only_scenario.source_root)
        dst_scan = scan_directory(source_only_scenario.dest_root)
        comparison = compare(src_scan.entries, dst_scan.entries)
        plan = build_plan(comparison)

        completed = []

        def on_file(path: str, success: bool) -> None:
            completed.append((path, success))

        execute_plan(
            plan,
            source_only_scenario.source_root,
            source_only_scenario.dest_root,
            file_completed_cb=on_file,
        )

        assert len(completed) == len(plan.entries)
        assert all(success for _, success in completed)

    def test_error_callback(self, tmp_path: Path):
        fake_src = FileEntry("nonexistent.txt", 100, 1000.0, False)
        entries = [ComparisonEntry(
            rel_path="nonexistent.txt",
            diff_type=DiffType.SOURCE_ONLY,
            source=fake_src,
            dest=None,
            action=SyncAction.COPY_TO_DEST,
        )]
        plan = SyncPlan(
            entries=entries,
            total_copy_bytes=100,
            total_delete_count=0,
            total_overwrite_count=0,
            total_rename_count=0,
        )

        errors = []

        def on_error(msg: str) -> None:
            errors.append(msg)

        execute_plan(
            plan,
            tmp_path / "fake_source",
            tmp_path / "fake_dest",
            error_cb=on_error,
        )

        assert len(errors) > 0
