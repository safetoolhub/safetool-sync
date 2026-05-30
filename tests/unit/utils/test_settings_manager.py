# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for utils.settings_manager."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from services.models import CompareMode, ConflictPolicy, VerifyMode
from utils.storage import JsonStorageBackend
from utils.settings_manager import SettingsManager


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "test_settings.json"
        backend = JsonStorageBackend(path=path)
        mgr = SettingsManager(backend=backend)
        yield mgr


class TestBasicGetSet:
    def test_get_default(self, manager):
        assert manager.get("nonexistent", "default") == "default"

    def test_set_and_get(self, manager):
        manager.set("test/key", "value")
        assert manager.get("test/key") == "value"

    def test_get_bool(self, manager):
        manager.set("flag", True)
        assert manager.get_bool("flag") is True

    def test_get_bool_default(self, manager):
        assert manager.get_bool("missing", False) is False

    def test_get_int(self, manager):
        manager.set("count", 42)
        assert manager.get_int("count") == 42

    def test_get_int_default(self, manager):
        assert manager.get_int("missing", 0) == 0

    def test_get_str(self, manager):
        manager.set("name", "test")
        assert manager.get_str("name") == "test"

    def test_get_str_default(self, manager):
        assert manager.get_str("missing", "default") == "default"


class TestLanguage:
    def test_default_language(self, manager):
        assert manager.get_language() == "es"

    def test_set_and_get(self, manager):
        manager.set_language("en")
        assert manager.get_language() == "en"


class TestCompareMode:
    def test_default(self, manager):
        assert manager.get_compare_mode() == CompareMode.SMART

    def test_set_and_get(self, manager):
        manager.set_compare_mode(CompareMode.FAST)
        assert manager.get_compare_mode() == CompareMode.FAST


class TestConflictPolicy:
    def test_default(self, manager):
        assert manager.get_conflict_policy() == ConflictPolicy.SOURCE_WINS

    def test_set_and_get(self, manager):
        manager.set_conflict_policy(ConflictPolicy.KEEP_DEST)
        assert manager.get_conflict_policy() == ConflictPolicy.KEEP_DEST


class TestVerifyMode:
    def test_default(self, manager):
        assert manager.get_verify_mode() == VerifyMode.FULL

    def test_set_and_get(self, manager):
        manager.set_verify_mode(VerifyMode.SPOT_CHECK)
        assert manager.get_verify_mode() == VerifyMode.SPOT_CHECK


class TestUseTrash:
    def test_default(self, manager):
        assert manager.get_use_trash() is True

    def test_set_and_get(self, manager):
        manager.set_use_trash(False)
        assert manager.get_use_trash() is False


class TestPathHistory:
    def test_empty_history(self, manager):
        assert manager.get_path_history() == []

    def test_add_path(self, manager):
        manager.add_path_history("/test/path")
        history = manager.get_path_history()
        assert "/test/path" in history

    def test_add_multiple_paths(self, manager):
        manager.add_path_history("/path/a")
        manager.add_path_history("/path/b")
        history = manager.get_path_history()
        assert len(history) == 2
        assert history[0] == "/path/b"

    def test_dedup_path(self, manager):
        manager.add_path_history("/path/a")
        manager.add_path_history("/path/b")
        manager.add_path_history("/path/a")
        history = manager.get_path_history()
        assert history[0] == "/path/a"
        assert len(history) == 2


class TestExclusions:
    def test_default_exclusion_presets(self, manager):
        presets = manager.get_active_exclusion_presets()
        assert isinstance(presets, list)

    def test_set_custom_exclusions(self, manager):
        manager.set_custom_exclusions(["*.tmp", "*.log"])
        assert manager.get_custom_exclusions() == ["*.tmp", "*.log"]