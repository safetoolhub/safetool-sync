# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.session_manager."""
from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path

import pytest

from services.models import (
    ComparisonEntry,
    DiffType,
    FileEntry,
    SyncAction,
    SyncDirection,
)
from services.session_manager import (
    ReviewSession,
    ReviewSessionEntry,
    SESSION_VERSION,
    SessionLoadResult,
    SessionVersionError,
    apply_session_to_entries,
    compute_analysis_hash,
    load_session,
    save_session,
)


ALLOWED_ACTIONS_TEST: dict[DiffType, list[SyncAction]] = {
    DiffType.IDENTICAL: [SyncAction.SKIP],
    DiffType.SOURCE_ONLY: [
        SyncAction.COPY_TO_DEST,
        SyncAction.SKIP,
        SyncAction.MARK_REVIEW,
    ],
    DiffType.DEST_ONLY: [
        SyncAction.DELETE_FROM_DEST,
        SyncAction.MOVE_TO_TRASH,
        SyncAction.COPY_TO_SOURCE,
        SyncAction.SKIP,
        SyncAction.MARK_REVIEW,
    ],
    DiffType.MODIFIED: [
        SyncAction.OVERWRITE_DEST,
        SyncAction.OVERWRITE_SOURCE,
        SyncAction.KEEP_DEST,
        SyncAction.KEEP_SOURCE,
        SyncAction.SKIP,
        SyncAction.MARK_REVIEW,
    ],
    DiffType.CONFLICT: [
        SyncAction.OVERWRITE_DEST,
        SyncAction.OVERWRITE_SOURCE,
        SyncAction.KEEP_DEST,
        SyncAction.KEEP_SOURCE,
        SyncAction.SKIP,
        SyncAction.MARK_REVIEW,
    ],
}


def make_entry(
    rel_path: str,
    diff_type: DiffType,
    action: SyncAction,
    src_size: int = 10,
    dst_size: int = 20,
) -> ComparisonEntry:
    source = FileEntry(
        rel_path=rel_path,
        size=src_size,
        mtime=1000.0,
        is_dir=False,
        hash_sha256="",
    )
    dest = FileEntry(
        rel_path=rel_path,
        size=dst_size,
        mtime=2000.0,
        is_dir=False,
        hash_sha256="",
    )
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=diff_type,
        source=source,
        dest=dest,
        action=action,
    )


def _clone_entries(entries: list[ComparisonEntry]) -> list[ComparisonEntry]:
    cloned: list[ComparisonEntry] = []
    for e in entries:
        cloned.append(
            ComparisonEntry(
                rel_path=e.rel_path,
                diff_type=e.diff_type,
                source=dataclasses.replace(e.source) if e.source else None,
                dest=dataclasses.replace(e.dest) if e.dest else None,
                action=e.action,
                error_msg=e.error_msg,
            )
        )
    return cloned


def _sample_entries() -> list[ComparisonEntry]:
    return [
        make_entry("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, src_size=100),
        make_entry("b.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, src_size=200, dst_size=150),
        make_entry("c.txt", DiffType.IDENTICAL, SyncAction.SKIP, src_size=50, dst_size=50),
    ]


class TestComputeAnalysisHash:
    def test_compute_hash_is_deterministic(self):
        entries = _sample_entries()
        h1 = compute_analysis_hash(entries)
        h2 = compute_analysis_hash(entries)
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_hash_is_order_independent(self):
        entries = _sample_entries()
        reversed_entries = list(reversed(entries))
        assert compute_analysis_hash(entries) == compute_analysis_hash(reversed_entries)

    def test_compute_hash_changes_when_entry_changes(self):
        entries = _sample_entries()
        original_hash = compute_analysis_hash(entries)

        mutated = _clone_entries(entries)
        assert mutated[0].source is not None
        mutated[0].source.mtime = mutated[0].source.mtime + 5000.0

        assert compute_analysis_hash(mutated) != original_hash

    def test_compute_hash_handles_none_sides(self):
        entries = [
            ComparisonEntry(
                rel_path="only_src.txt",
                diff_type=DiffType.SOURCE_ONLY,
                source=FileEntry(rel_path="only_src.txt", size=42, mtime=111.0, is_dir=False),
                dest=None,
                action=SyncAction.COPY_TO_DEST,
            ),
            ComparisonEntry(
                rel_path="only_dst.txt",
                diff_type=DiffType.DEST_ONLY,
                source=None,
                dest=FileEntry(rel_path="only_dst.txt", size=88, mtime=222.0, is_dir=False),
                action=SyncAction.DELETE_FROM_DEST,
            ),
        ]
        h1 = compute_analysis_hash(entries)
        h2 = compute_analysis_hash(entries)
        assert h1 == h2
        assert len(h1) == 16


class TestSaveLoadSession:
    def test_save_load_roundtrip(self, tmp_path: Path):
        entries = _sample_entries()
        path = tmp_path / "session.json"

        save_session(
            path=path,
            source="/src/path",
            dest="/dst/path",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=entries,
        )

        assert path.exists()

        loaded = load_session(path)
        assert isinstance(loaded, ReviewSession)
        assert loaded.version == SESSION_VERSION
        assert loaded.source_path == "/src/path"
        assert loaded.dest_path == "/dst/path"
        assert loaded.direction == SyncDirection.UNIDIRECTIONAL.value
        assert loaded.entry_count == len(entries)
        assert loaded.analysis_hash == compute_analysis_hash(entries)
        assert len(loaded.actions) == len(entries)

        for original, action_entry in zip(entries, loaded.actions):
            assert isinstance(action_entry, ReviewSessionEntry)
            assert action_entry.rel_path == original.rel_path
            assert action_entry.diff_type == original.diff_type.value
            assert action_entry.action == original.action.value

    def test_load_unsupported_version_raises(self, tmp_path: Path):
        path = tmp_path / "old_session.json"
        payload = {
            "version": "0.9",
            "saved_at": "2025-01-01T00:00:00",
            "source_path": "/src",
            "dest_path": "/dst",
            "direction": SyncDirection.UNIDIRECTIONAL.value,
            "entry_count": 0,
            "analysis_hash": "",
            "actions": [],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        with pytest.raises(SessionVersionError):
            load_session(path)


class TestApplySessionToEntries:
    def test_apply_session_assigns_valid_actions(self, tmp_path: Path):
        entries = _sample_entries()
        path = tmp_path / "session.json"
        save_session(
            path=path,
            source="/src",
            dest="/dst",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=entries,
        )
        session = load_session(path)

        target_entries = _clone_entries(entries)
        for e in target_entries:
            e.action = SyncAction.MARK_REVIEW

        result = apply_session_to_entries(session, target_entries, ALLOWED_ACTIONS_TEST)

        assert result.applied == len(session.actions)
        assert result.skipped_invalid == 0
        assert result.stale == 0
        assert result.analysis_drifted is False

        for original, applied in zip(entries, target_entries):
            assert applied.action == original.action

    def test_apply_session_skips_invalid_action_for_diff_type(self, tmp_path: Path):
        saved_entries = [
            make_entry("a.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST),
        ]
        path = tmp_path / "session.json"
        save_session(
            path=path,
            source="/src",
            dest="/dst",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=saved_entries,
        )
        session = load_session(path)

        current_entries = [
            make_entry("a.txt", DiffType.IDENTICAL, SyncAction.SKIP),
        ]
        result = apply_session_to_entries(session, current_entries, ALLOWED_ACTIONS_TEST)

        assert result.applied == 0
        assert result.skipped_invalid == 1
        assert result.stale == 0
        assert current_entries[0].action == SyncAction.SKIP

    def test_apply_session_counts_stale_entries(self, tmp_path: Path):
        saved_entries = [
            make_entry("present.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST),
            make_entry("ghost.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST),
        ]
        path = tmp_path / "session.json"
        save_session(
            path=path,
            source="/src",
            dest="/dst",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=saved_entries,
        )
        session = load_session(path)

        current_entries = [
            make_entry("present.txt", DiffType.SOURCE_ONLY, SyncAction.MARK_REVIEW),
        ]
        result = apply_session_to_entries(session, current_entries, ALLOWED_ACTIONS_TEST)

        assert result.applied == 1
        assert result.stale == 1
        assert result.skipped_invalid == 0
        assert current_entries[0].action == SyncAction.COPY_TO_DEST

    def test_apply_session_detects_drift(self, tmp_path: Path):
        entries = _sample_entries()
        path = tmp_path / "session.json"
        save_session(
            path=path,
            source="/src",
            dest="/dst",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=entries,
        )
        session = load_session(path)

        drifted_entries = _clone_entries(entries)
        assert drifted_entries[0].source is not None
        drifted_entries[0].source.mtime = drifted_entries[0].source.mtime + 9999.0

        result = apply_session_to_entries(session, drifted_entries, ALLOWED_ACTIONS_TEST)

        assert result.analysis_drifted is True

    def test_apply_session_no_drift_when_unchanged(self, tmp_path: Path):
        entries = _sample_entries()
        path = tmp_path / "session.json"
        save_session(
            path=path,
            source="/src",
            dest="/dst",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=entries,
        )
        session = load_session(path)

        result = apply_session_to_entries(session, entries, ALLOWED_ACTIONS_TEST)

        assert result.analysis_drifted is False

    def test_apply_session_counters_sum_to_total(self, tmp_path: Path):
        saved_entries = [
            make_entry("valid.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST),
            make_entry("invalid_for_diff.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST),
            make_entry("ghost.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST),
        ]
        path = tmp_path / "session.json"
        save_session(
            path=path,
            source="/src",
            dest="/dst",
            direction=SyncDirection.UNIDIRECTIONAL,
            entries=saved_entries,
        )
        session = load_session(path)

        current_entries = [
            make_entry("valid.txt", DiffType.SOURCE_ONLY, SyncAction.MARK_REVIEW),
            make_entry("invalid_for_diff.txt", DiffType.IDENTICAL, SyncAction.SKIP),
        ]
        result = apply_session_to_entries(session, current_entries, ALLOWED_ACTIONS_TEST)

        total = result.applied + result.skipped_invalid + result.stale
        assert total == len(session.actions)
        assert result.applied == 1
        assert result.skipped_invalid == 1
        assert result.stale == 1
