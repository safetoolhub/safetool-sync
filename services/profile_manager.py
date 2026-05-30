# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Profile manager — CRUD for sync profiles stored as JSON files."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import Config
from services.models import (
    CompareMode,
    ConflictPolicy,
    ExclusionPreset,
    SyncPreset,
    SyncProfile,
    VerifyMode,
)


class ProfileManager:
    """Manage saved sync profiles as JSON files."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self._profiles_dir = profiles_dir or Config.PROFILES_DIR
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, name: str) -> Path:
        safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self._profiles_dir / f"{safe_name}.json"

    def save_profile(self, profile: SyncProfile) -> Path:
        """Save a sync profile to a JSON file.

        Args:
            profile: The SyncProfile to save.

        Returns:
            Path to the saved profile file.
        """
        path = self._profile_path(profile.name)
        data = _profile_to_dict(profile)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def load_profile(self, name: str) -> Optional[SyncProfile]:
        """Load a profile by name.

        Args:
            name: Profile name.

        Returns:
            SyncProfile or None if not found.
        """
        path = self._profile_path(name)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _dict_to_profile(data)

    def delete_profile(self, name: str) -> bool:
        """Delete a profile by name.

        Returns:
            True if the profile was deleted.
        """
        path = self._profile_path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_profiles(self) -> list[str]:
        """List all saved profile names.

        Returns:
            List of profile name strings.
        """
        if not self._profiles_dir.exists():
            return []
        return sorted(
            p.stem for p in self._profiles_dir.glob("*.json")
        )

    def load_all_profiles(self) -> list[SyncProfile]:
        """Load all saved profiles.

        Returns:
            List of SyncProfile objects.
        """
        profiles = []
        for name in self.list_profiles():
            profile = self.load_profile(name)
            if profile is not None:
                profiles.append(profile)
        return profiles

    def get_builtin_profiles(self) -> dict[str, SyncProfile]:
        """Get the built-in preset profiles.

        Returns:
            Dict mapping preset name → SyncProfile.
        """
        return {
            "Espejo Exacto": SyncProfile(
                name="Espejo Exacto",
                source="",
                dest="",
                compare_mode=CompareMode.SMART,
                conflict_policy=ConflictPolicy.SOURCE_WINS,
                verify_mode=VerifyMode.FULL,
                use_trash=False,
                exclusion_presets=[ExclusionPreset.SYSTEM_FILES, ExclusionPreset.TRASH_FOLDERS],
                custom_exclusions=[],
                preset=SyncPreset.MIRROR_EXACT,
            ),
            "Espejo Seguro": SyncProfile(
                name="Espejo Seguro",
                source="",
                dest="",
                compare_mode=CompareMode.SMART,
                conflict_policy=ConflictPolicy.SOURCE_WINS,
                verify_mode=VerifyMode.FULL,
                use_trash=True,
                exclusion_presets=[ExclusionPreset.SYSTEM_FILES, ExclusionPreset.TRASH_FOLDERS],
                custom_exclusions=[],
                preset=SyncPreset.MIRROR_SAFE,
            ),
            "Solo Copia": SyncProfile(
                name="Solo Copia",
                source="",
                dest="",
                compare_mode=CompareMode.FAST,
                conflict_policy=ConflictPolicy.SOURCE_WINS,
                verify_mode=VerifyMode.SPOT_CHECK,
                use_trash=False,
                exclusion_presets=[ExclusionPreset.SYSTEM_FILES],
                custom_exclusions=[],
                preset=SyncPreset.COPY_ONLY,
            ),
        }


def _profile_to_dict(profile: SyncProfile) -> dict:
    """Serialize a SyncProfile to a JSON-compatible dict."""
    return {
        "version": "1.0",
        "name": profile.name,
        "source": profile.source,
        "dest": profile.dest,
        "compare_mode": profile.compare_mode.value,
        "conflict_policy": profile.conflict_policy.value,
        "verify_mode": profile.verify_mode.value,
        "use_trash": profile.use_trash,
        "exclusion_presets": [p.value for p in profile.exclusion_presets],
        "custom_exclusions": profile.custom_exclusions,
        "preset": profile.preset.value,
    }


def _dict_to_profile(data: dict) -> SyncProfile:
    """Deserialize a JSON dict to a SyncProfile."""
    raw_policy = data.get("conflict_policy", "source_wins")
    if raw_policy == "ask_each":
        raw_policy = "mark_pending"
    return SyncProfile(
        name=data.get("name", "Unknown"),
        source=data.get("source", ""),
        dest=data.get("dest", ""),
        compare_mode=CompareMode(data.get("compare_mode", "smart")),
        conflict_policy=ConflictPolicy(raw_policy),
        verify_mode=VerifyMode(data.get("verify_mode", "full")),
        use_trash=data.get("use_trash", True),
        exclusion_presets=[ExclusionPreset(v) for v in data.get("exclusion_presets", [])],
        custom_exclusions=data.get("custom_exclusions", []),
        preset=SyncPreset(data.get("preset", "mirror_safe")),
    )