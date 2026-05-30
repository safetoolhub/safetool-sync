# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.profile_manager."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.models import CompareMode, ConflictPolicy, ExclusionPreset, SyncPreset, SyncProfile, VerifyMode
from services.profile_manager import ProfileManager


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as d:
        mgr = ProfileManager(profiles_dir=Path(d))
        yield mgr


def _profile(name: str = "Test Profile") -> SyncProfile:
    return SyncProfile(
        name=name,
        source="/source",
        dest="/dest",
        compare_mode=CompareMode.SMART,
        conflict_policy=ConflictPolicy.SOURCE_WINS,
        verify_mode=VerifyMode.FULL,
        use_trash=True,
        exclusion_presets=[ExclusionPreset.SYSTEM_FILES],
        custom_exclusions=["*.log"],
        preset=SyncPreset.MIRROR_SAFE,
    )


class TestSaveAndLoad:
    def test_save_and_load(self, manager):
        profile = _profile()
        path = manager.save_profile(profile)
        assert path.exists()

        loaded = manager.load_profile("Test Profile")
        assert loaded is not None
        assert loaded.name == "Test Profile"
        assert loaded.source == "/source"
        assert loaded.dest == "/dest"
        assert loaded.compare_mode == CompareMode.SMART
        assert loaded.conflict_policy == ConflictPolicy.SOURCE_WINS
        assert loaded.verify_mode == VerifyMode.FULL
        assert loaded.use_trash is True
        assert ExclusionPreset.SYSTEM_FILES in loaded.exclusion_presets
        assert "*.log" in loaded.custom_exclusions

    def test_load_nonexistent(self, manager):
        result = manager.load_profile("Does Not Exist")
        assert result is None


class TestDelete:
    def test_delete_profile(self, manager):
        profile = _profile()
        manager.save_profile(profile)
        assert manager.delete_profile("Test Profile") is True
        assert manager.load_profile("Test Profile") is None

    def test_delete_nonexistent(self, manager):
        assert manager.delete_profile("Does Not Exist") is False


class TestListProfiles:
    def test_list_empty(self, manager):
        assert manager.list_profiles() == []

    def test_list_after_save(self, manager):
        manager.save_profile(_profile("Profile A"))
        manager.save_profile(_profile("Profile B"))
        names = manager.list_profiles()
        assert len(names) == 2
        assert "Profile A" in names
        assert "Profile B" in names


class TestLoadAllProfiles:
    def test_load_all(self, manager):
        manager.save_profile(_profile("Profile A"))
        manager.save_profile(_profile("Profile B"))
        profiles = manager.load_all_profiles()
        assert len(profiles) == 2


class TestGetBuiltinProfiles:
    def test_builtin_profiles(self, manager):
        builtins = manager.get_builtin_profiles()
        assert "Espejo Exacto" in builtins
        assert "Espejo Seguro" in builtins
        assert "Solo Copia" in builtins

    def test_builtin_mirror_exact(self, manager):
        builtins = manager.get_builtin_profiles()
        exact = builtins["Espejo Exacto"]
        assert exact.preset == SyncPreset.MIRROR_EXACT
        assert exact.use_trash is False

    def test_builtin_mirror_safe(self, manager):
        builtins = manager.get_builtin_profiles()
        safe = builtins["Espejo Seguro"]
        assert safe.preset == SyncPreset.MIRROR_SAFE
        assert safe.use_trash is True