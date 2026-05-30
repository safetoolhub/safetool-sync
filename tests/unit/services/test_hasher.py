# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.hasher."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from services.hasher import hash_file, hash_files


@pytest.fixture
def temp_files():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        paths = []
        for i in range(5):
            p = root / f"file_{i}.txt"
            p.write_text(f"content_{i}")
            paths.append(p)
        yield root, paths


class TestHashFile:
    def test_hash_single_file(self, temp_files):
        root, paths = temp_files
        result = hash_file(paths[0])
        expected = hashlib.sha256(paths[0].read_bytes()).hexdigest()
        assert result == expected

    def test_hash_empty_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.txt"
            p.write_text("")
            result = hash_file(p)
            expected = hashlib.sha256(b"").hexdigest()
            assert result == expected

    def test_hash_nonexistent_file(self):
        with pytest.raises((FileNotFoundError, OSError)):
            hash_file(Path("/nonexistent/file.txt"))


class TestHashFiles:
    def test_hash_multiple_files(self, temp_files):
        root, paths = temp_files
        results = hash_files(paths)
        assert len(results) == len(paths)
        for path in paths:
            assert str(path) in results

    def test_hash_files_correct_digests(self, temp_files):
        root, paths = temp_files
        results = hash_files(paths)
        for path in paths:
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            assert results[str(path)] == expected

    def test_hash_files_with_progress(self, temp_files):
        root, paths = temp_files
        calls = []
        hash_files(paths, progress_cb=lambda c, p: calls.append((c, p)))
        assert len(calls) == len(paths)

    def test_hash_files_empty_list(self):
        results = hash_files([])
        assert results == {}

    def test_hash_files_with_cancel(self, temp_files):
        root, paths = temp_files
        cancel_after = [False]

        def cancel_check():
            cancel_after[0] = True
            return cancel_after[0]

        results = hash_files(paths, cancel_check=cancel_check)
        assert len(results) <= len(paths)