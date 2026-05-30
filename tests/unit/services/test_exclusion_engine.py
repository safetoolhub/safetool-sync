# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.exclusion_engine."""
from __future__ import annotations

import pytest

from services.models import ExclusionPreset, FileEntry, EXCLUSION_PATTERNS
from services.exclusion_engine import get_preset_patterns, should_exclude, should_exclude_path, filter_entries


class TestGetPresetPatterns:
    def test_system_files(self):
        patterns = get_preset_patterns([ExclusionPreset.SYSTEM_FILES])
        assert ".DS_Store" in patterns
        assert "Thumbs.db" in patterns
        assert "desktop.ini" in patterns

    def test_trash_folders(self):
        patterns = get_preset_patterns([ExclusionPreset.TRASH_FOLDERS])
        assert ".Trash*" in patterns
        assert "$RECYCLE.BIN" in patterns

    def test_dev_folders(self):
        patterns = get_preset_patterns([ExclusionPreset.DEV_FOLDERS])
        assert ".git" in patterns
        assert "node_modules" in patterns

    def test_temp_files(self):
        patterns = get_preset_patterns([ExclusionPreset.TEMP_FILES])
        assert "*.tmp" in patterns
        assert "*.bak" in patterns

    def test_multiple_presets(self):
        patterns = get_preset_patterns([ExclusionPreset.SYSTEM_FILES, ExclusionPreset.TRASH_FOLDERS])
        assert len(patterns) == len(EXCLUSION_PATTERNS[ExclusionPreset.SYSTEM_FILES]) + len(EXCLUSION_PATTERNS[ExclusionPreset.TRASH_FOLDERS])

    def test_empty_presets(self):
        patterns = get_preset_patterns([])
        assert patterns == []


class TestShouldExclude:
    def test_exclude_by_filename_pattern(self):
        entry = FileEntry(rel_path="test.tmp", size=10, mtime=0.0, is_dir=False)
        assert should_exclude(entry, custom_patterns=["*.tmp"]) is True

    def test_include_normal_file(self):
        entry = FileEntry(rel_path="document.pdf", size=100, mtime=0.0, is_dir=False)
        assert should_exclude(entry, custom_patterns=["*.tmp"]) is False

    def test_exclude_system_file_with_preset(self):
        entry = FileEntry(rel_path=".DS_Store", size=0, mtime=0.0, is_dir=False)
        assert should_exclude(entry, active_presets=[ExclusionPreset.SYSTEM_FILES]) is True

    def test_exclude_by_path_component(self):
        entry = FileEntry(rel_path="node_modules/module/index.js", size=100, mtime=0.0, is_dir=False)
        assert should_exclude(entry, active_presets=[ExclusionPreset.DEV_FOLDERS]) is True

    def test_no_patterns_no_exclusion(self):
        entry = FileEntry(rel_path="anything.txt", size=10, mtime=0.0, is_dir=False)
        assert should_exclude(entry) is False

    def test_combined_preset_and_custom(self):
        entry = FileEntry(rel_path=".DS_Store", size=0, mtime=0.0, is_dir=False)
        assert should_exclude(entry, active_presets=[ExclusionPreset.SYSTEM_FILES], custom_patterns=["*.log"]) is True

        entry2 = FileEntry(rel_path="debug.log", size=5, mtime=0.0, is_dir=False)
        assert should_exclude(entry2, active_presets=[ExclusionPreset.SYSTEM_FILES], custom_patterns=["*.log"]) is True


class TestShouldExcludePath:
    def test_path_exclusion(self):
        assert should_exclude_path("file.tmp", is_dir=False, custom_patterns=["*.tmp"]) is True

    def test_path_inclusion(self):
        assert should_exclude_path("file.txt", is_dir=False, custom_patterns=["*.tmp"]) is False


class TestFilterEntries:
    def test_filter_removes_excluded(self):
        entries = [
            FileEntry(rel_path="keep.txt", size=10, mtime=0.0, is_dir=False),
            FileEntry(rel_path="skip.tmp", size=10, mtime=0.0, is_dir=False),
        ]
        result = filter_entries(entries, custom_patterns=["*.tmp"])
        assert len(result) == 1
        assert result[0].rel_path == "keep.txt"

    def test_filter_keeps_all_when_no_patterns(self):
        entries = [
            FileEntry(rel_path="a.txt", size=10, mtime=0.0, is_dir=False),
            FileEntry(rel_path="b.tmp", size=10, mtime=0.0, is_dir=False),
        ]
        result = filter_entries(entries)
        assert len(result) == 2