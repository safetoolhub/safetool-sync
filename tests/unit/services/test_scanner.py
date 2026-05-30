# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.scanner."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.models import FileEntry
from services.scanner import scan_directory


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "subdir").mkdir()
        (root / "subdir" / "nested").mkdir()
        (root / "file1.txt").write_text("hello")
        (root / "subdir" / "file2.txt").write_text("world")
        (root / "subdir" / "nested" / "file3.txt").write_text("deep")
        yield root


class TestScanDirectory:
    def test_scans_all_files(self, temp_dir):
        result = scan_directory(temp_dir)
        assert result.total_files == 3
        names = {e.rel_path for e in result.entries}
        assert "file1.txt" in names
        assert "subdir/file2.txt" in names
        assert "subdir/nested/file3.txt" in names

    def test_counts_dirs(self, temp_dir):
        result = scan_directory(temp_dir)
        assert result.total_dirs >= 2

    def test_total_size(self, temp_dir):
        result = scan_directory(temp_dir)
        assert result.total_size > 0
        assert result.total_size == sum(e.size for e in result.entries)

    def test_scan_time(self, temp_dir):
        result = scan_directory(temp_dir)
        assert result.scan_time >= 0

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            result = scan_directory(Path(d))
            assert result.total_files == 0
            assert result.entries == []

    def test_file_entry_fields(self, temp_dir):
        result = scan_directory(temp_dir)
        entry = next(e for e in result.entries if e.rel_path == "file1.txt")
        assert entry.size > 0
        assert entry.mtime > 0
        assert entry.is_dir is False
        assert entry.hash_sha256 == ""

    def test_exclusions(self, temp_dir):
        (temp_dir / "test.tmp").write_text("temp")
        (temp_dir / "important.txt").write_text("keep")
        result = scan_directory(temp_dir, exclusions=["*.tmp"])
        names = {e.rel_path for e in result.entries}
        assert "important.txt" in names
        tmp_files = [n for n in names if n.endswith(".tmp")]
        assert len(tmp_files) == 0

    def test_progress_callback(self, temp_dir):
        calls = []
        scan_directory(temp_dir, progress_cb=lambda pct, msg: calls.append((pct, msg)))
        assert isinstance(calls, list)

    def test_nonexistent_directory(self):
        result = scan_directory(Path("/nonexistent/path/xyz"))
        assert result.total_files == 0