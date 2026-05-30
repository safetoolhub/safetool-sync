# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.analysis_export."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from services.models import ComparisonEntry, DiffType, FileEntry, SyncAction
from services.analysis_export import export_analysis, import_analysis, compare_analyses


def _entry(rel_path: str, size: int = 100, mtime: float = 1000.0, hash_sha256: str = "") -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=mtime, is_dir=False, hash_sha256=hash_sha256)


def _comparison(rel_path: str, diff_type: DiffType, action: SyncAction, source: FileEntry | None = None, dest: FileEntry | None = None) -> ComparisonEntry:
    return ComparisonEntry(rel_path=rel_path, diff_type=diff_type, source=source, dest=dest, action=action)


class TestExportAnalysis:
    def test_export_creates_json(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt")),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "analysis.json"
            export_analysis(entries, path)
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["version"] == "1.0"
            assert data["entry_count"] == 1
            assert len(data["entries"]) == 1

    def test_export_with_metadata(self):
        entries = [_comparison("a.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("a.txt"), dest=_entry("a.txt"))]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "analysis.json"
            export_analysis(entries, path, metadata={"source": "/src", "dest": "/dst"})
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["metadata"]["source"] == "/src"

    def test_export_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "analysis.json"
            export_analysis([], path)
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["entry_count"] == 0


class TestImportAnalysis:
    def test_roundtrip(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=500)),
            _comparison("b.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("b.txt", size=200, hash_sha256="abc"), dest=_entry("b.txt", size=100)),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "analysis.json"
            export_analysis(entries, path)
            loaded = import_analysis(path)
            assert len(loaded) == 2
            assert loaded[0].rel_path == "a.txt"
            assert loaded[0].diff_type == DiffType.SOURCE_ONLY
            assert loaded[0].action == SyncAction.COPY_TO_DEST
            assert loaded[0].source.size == 500

    def test_import_with_dest_none(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt")),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "analysis.json"
            export_analysis(entries, path)
            loaded = import_analysis(path)
            assert loaded[0].dest is None


class TestCompareAnalyses:
    def test_new_entry_detected(self):
        old = [_comparison("a.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("a.txt"))]
        new = [
            _comparison("a.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("a.txt")),
            _comparison("b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("b.txt")),
        ]
        changes = compare_analyses(old, new)
        assert len(changes) == 1
        assert changes[0].rel_path == "b.txt"

    def test_changed_diff_type(self):
        old = [_comparison("a.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("a.txt"))]
        new = [_comparison("a.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("a.txt"))]
        changes = compare_analyses(old, new)
        assert len(changes) == 1
        assert changes[0].diff_type == DiffType.MODIFIED

    def test_changed_action(self):
        old = [_comparison("a.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=_entry("a.txt"))]
        new = [_comparison("a.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH, dest=_entry("a.txt"))]
        changes = compare_analyses(old, new)
        assert len(changes) == 1
        assert changes[0].action == SyncAction.MOVE_TO_TRASH

    def test_no_changes(self):
        entries = [_comparison("a.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("a.txt"))]
        changes = compare_analyses(entries, entries)
        assert len(changes) == 0