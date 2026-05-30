# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Exclusion engine — filters files by fnmatch patterns and presets."""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath

from services.models import ExclusionPreset, EXCLUSION_PATTERNS, FileEntry


def get_preset_patterns(presets: list[ExclusionPreset]) -> list[str]:
    """Expand a list of exclusion presets into a flat list of fnmatch patterns.

    Args:
        presets: List of ExclusionPreset enum values.

    Returns:
        Combined list of fnmatch pattern strings.
    """
    patterns: list[str] = []
    for preset in presets:
        if preset in EXCLUSION_PATTERNS:
            patterns.extend(EXCLUSION_PATTERNS[preset])
    return patterns


def should_exclude(
    entry: FileEntry,
    active_presets: list[ExclusionPreset] | None = None,
    custom_patterns: list[str] | None = None,
) -> bool:
    """Determine if a FileEntry should be excluded based on presets and custom patterns.

    Args:
        entry: The FileEntry to check.
        active_presets: List of ExclusionPreset values to apply.
        custom_patterns: List of additional fnmatch patterns.

    Returns:
        True if the entry should be excluded.
    """
    all_patterns = get_preset_patterns(active_presets or [])
    all_patterns.extend(custom_patterns or [])

    name = PurePosixPath(entry.rel_path).name
    parent_parts = PurePosixPath(entry.rel_path).parts

    for pattern in all_patterns:
        if fnmatch(name, pattern):
            return True

        if entry.is_dir and name == pattern.rstrip("*"):
            if pattern.startswith(".") or pattern.startswith("$"):
                if fnmatch(name, pattern):
                    return True

        for part in parent_parts:
            if fnmatch(part, pattern):
                return True

    return False


def should_exclude_path(
    rel_path: str,
    is_dir: bool,
    active_presets: list[ExclusionPreset] | None = None,
    custom_patterns: list[str] | None = None,
) -> bool:
    """Determine if a relative path should be excluded.

    Args:
        rel_path: Relative path string.
        is_dir: Whether the path is a directory.
        active_presets: List of ExclusionPreset values to apply.
        custom_patterns: List of additional fnmatch patterns.

    Returns:
        True if the path should be excluded.
    """
    entry = FileEntry(
        rel_path=rel_path,
        size=0,
        mtime=0.0,
        is_dir=is_dir,
    )
    return should_exclude(entry, active_presets, custom_patterns)


def filter_entries(
    entries: list[FileEntry],
    active_presets: list[ExclusionPreset] | None = None,
    custom_patterns: list[str] | None = None,
) -> list[FileEntry]:
    """Filter a list of FileEntry objects, removing excluded ones.

    Args:
        entries: List of FileEntry to filter.
        active_presets: List of ExclusionPreset values to apply.
        custom_patterns: List of additional fnmatch patterns.

    Returns:
        Filtered list with excluded entries removed.
    """
    return [
        entry for entry in entries
        if not should_exclude(entry, active_presets, custom_patterns)
    ]