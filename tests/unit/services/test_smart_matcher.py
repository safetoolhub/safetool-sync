# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.smart_matcher."""
from __future__ import annotations

import pytest

from services.models import ComparisonEntry, DiffType, FileEntry, SyncAction
from services.smart_matcher import (
    MAX_SUFFIX_LEN,
    SmartMatch,
    SmartMatchResult,
    _is_prefix_match,
    _stem_and_ext,
    find_smart_matches,
)


def _src_entry(rel_path: str, size: int = 1000) -> ComparisonEntry:
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=DiffType.SOURCE_ONLY,
        source=FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False),
        dest=None,
        action=SyncAction.COPY_TO_DEST,
    )


def _dst_entry(rel_path: str, size: int = 1000) -> ComparisonEntry:
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=DiffType.DEST_ONLY,
        source=None,
        dest=FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False),
        action=SyncAction.MOVE_TO_TRASH,
    )


def _identical_entry(rel_path: str, size: int = 500) -> ComparisonEntry:
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=DiffType.IDENTICAL,
        source=FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False),
        dest=FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False),
        action=SyncAction.SKIP,
    )


class TestStemAndExt:
    def test_simple_file(self):
        assert _stem_and_ext("report.pdf") == ("report", ".pdf")

    def test_nested_path(self):
        assert _stem_and_ext("docs/folder/report.pdf") == ("report", ".pdf")

    def test_no_extension(self):
        assert _stem_and_ext("Makefile") == ("Makefile", "")

    def test_multiple_dots(self):
        assert _stem_and_ext("archive.tar.gz") == ("archive.tar", ".gz")

    def test_backslash_path(self):
        assert _stem_and_ext("docs\\folder\\file.txt") == ("file", ".txt")

    def test_hidden_file(self):
        assert _stem_and_ext(".gitignore") == (".gitignore", "")


class TestIsPrefixMatch:
    def test_exact_same(self):
        assert _is_prefix_match("report", "report") is True

    def test_suffix_added(self):
        assert _is_prefix_match("report", "report_v2") is True

    def test_suffix_copy(self):
        assert _is_prefix_match("photo", "photo (1)") is True

    def test_suffix_too_long(self):
        long_suffix = "a" * (MAX_SUFFIX_LEN + 1)
        assert _is_prefix_match("file", f"file{long_suffix}") is False

    def test_no_common_prefix(self):
        assert _is_prefix_match("alpha", "beta") is False

    def test_empty_stem(self):
        assert _is_prefix_match("", "something") is False

    def test_reversed_order(self):
        assert _is_prefix_match("report_final", "report") is True

    def test_suffix_exactly_max(self):
        suffix = "x" * MAX_SUFFIX_LEN
        assert _is_prefix_match("doc", f"doc{suffix}") is True


class TestFindSmartMatches:
    def test_basic_match_same_size_prefix(self):
        entries = [
            _src_entry("docs/report.pdf", size=5000),
            _dst_entry("docs/report_backup.pdf", size=5000),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1
        assert result.matches[0].source_entry == entries[0]
        assert result.matches[0].dest_entry == entries[1]
        assert result.unmatched_source == []
        assert result.unmatched_dest == []

    def test_no_match_different_size(self):
        entries = [
            _src_entry("file.txt", size=100),
            _dst_entry("file_v2.txt", size=200),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 0
        assert len(result.unmatched_source) == 1
        assert len(result.unmatched_dest) == 1

    def test_no_match_different_extension(self):
        entries = [
            _src_entry("data.csv", size=1000),
            _dst_entry("data_old.json", size=1000),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 0

    def test_no_match_no_prefix_relation(self):
        entries = [
            _src_entry("alpha.txt", size=500),
            _dst_entry("beta.txt", size=500),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 0

    def test_ignores_non_orphan_entries(self):
        entries = [
            _identical_entry("same.txt"),
            _src_entry("new.pdf", size=300),
            _dst_entry("new_copy.pdf", size=300),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1

    def test_multiple_matches(self):
        entries = [
            _src_entry("a.txt", size=100),
            _src_entry("b.pdf", size=200),
            _dst_entry("a_old.txt", size=100),
            _dst_entry("b_v2.pdf", size=200),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 2
        assert result.unmatched_source == []
        assert result.unmatched_dest == []

    def test_one_to_one_matching(self):
        entries = [
            _src_entry("doc.pdf", size=1000),
            _dst_entry("doc_v1.pdf", size=1000),
            _dst_entry("doc_v2.pdf", size=1000),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1
        assert len(result.unmatched_dest) == 1

    def test_empty_entries(self):
        result = find_smart_matches([])
        assert len(result.matches) == 0
        assert result.unmatched_source == []
        assert result.unmatched_dest == []

    def test_only_source_entries(self):
        entries = [_src_entry("a.txt"), _src_entry("b.txt")]
        result = find_smart_matches(entries)
        assert len(result.matches) == 0
        assert len(result.unmatched_source) == 2
        assert result.unmatched_dest == []

    def test_only_dest_entries(self):
        entries = [_dst_entry("x.txt"), _dst_entry("y.txt")]
        result = find_smart_matches(entries)
        assert len(result.matches) == 0
        assert result.unmatched_source == []
        assert len(result.unmatched_dest) == 2

    def test_suffix_with_parentheses(self):
        entries = [
            _src_entry("photo.jpg", size=2048),
            _dst_entry("photo (1).jpg", size=2048),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1

    def test_suffix_with_underscore_version(self):
        entries = [
            _src_entry("document.docx", size=4096),
            _dst_entry("document_final_v3.docx", size=4096),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1

    def test_case_insensitive_extension(self):
        entries = [
            _src_entry("image.JPG", size=1500),
            _dst_entry("image_edited.jpg", size=1500),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1

    def test_nested_paths_different_folders(self):
        entries = [
            _src_entry("photos/vacation/beach.png", size=3000),
            _dst_entry("backup/beach_copy.png", size=3000),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1

    def test_dest_name_is_prefix_of_source(self):
        entries = [
            _src_entry("report_2024_final.pdf", size=8000),
            _dst_entry("report.pdf", size=8000),
        ]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1


class TestSmartMatchActionApplication:
    """Tests that actions applied to matches propagate correctly."""

    def test_mark_review_applied_to_both_entries(self):
        src = _src_entry("report.pdf", size=5000)
        dst = _dst_entry("report_v2.pdf", size=5000)
        entries = [src, dst]
        result = find_smart_matches(entries)
        assert len(result.matches) == 1

        match = result.matches[0]
        match.source_entry.action = SyncAction.MARK_REVIEW
        match.dest_entry.action = SyncAction.MARK_REVIEW

        assert src.action == SyncAction.MARK_REVIEW
        assert dst.action == SyncAction.MARK_REVIEW

    def test_overwrite_dest_applied_to_match(self):
        src = _src_entry("data.csv", size=2000)
        dst = _dst_entry("data_backup.csv", size=2000)
        entries = [src, dst]
        result = find_smart_matches(entries)

        match = result.matches[0]
        match.source_entry.action = SyncAction.OVERWRITE_DEST
        match.dest_entry.action = SyncAction.OVERWRITE_DEST

        assert src.action == SyncAction.OVERWRITE_DEST
        assert dst.action == SyncAction.OVERWRITE_DEST

    def test_skip_leaves_entries_unchanged_from_skip(self):
        src = _src_entry("file.txt", size=100)
        dst = _dst_entry("file_old.txt", size=100)
        entries = [src, dst]
        result = find_smart_matches(entries)

        match = result.matches[0]
        match.source_entry.action = SyncAction.SKIP
        match.dest_entry.action = SyncAction.SKIP

        assert src.action == SyncAction.SKIP
        assert dst.action == SyncAction.SKIP

    def test_mark_review_entries_visible_in_conflict_pending_count(self):
        src = _src_entry("doc.pdf", size=4000)
        dst = _dst_entry("doc_copy.pdf", size=4000)
        identical = _identical_entry("other.txt")
        entries = [src, dst, identical]

        result = find_smart_matches(entries)
        match = result.matches[0]
        match.source_entry.action = SyncAction.MARK_REVIEW
        match.dest_entry.action = SyncAction.MARK_REVIEW

        mark_review_count = sum(
            1 for e in entries if e.action == SyncAction.MARK_REVIEW
        )
        assert mark_review_count == 2
