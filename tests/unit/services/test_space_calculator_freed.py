# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Comprehensive unit tests for space calculator with freed space accounting.

Covers all scenarios:
- Not enough space initially, but enough after deletions (MIRROR_EXACT)
- Not enough space initially, but enough after overwriting modified files
- Enough space initially, deletions free even more
- Not enough space even after deletions
- Bidirectional mode with space freed on both sides
- Mixed actions: copies + deletes + overwrites + trash
- Edge cases: zero-size files, no deletions, all deletions
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.models import ComparisonEntry, DiffType, FileEntry, SyncAction, SyncPlan
from services.space_calculator import (
    calculate_freed_space_per_side,
    calculate_required_space,
    calculate_required_space_per_side,
    check_destination_space,
    reorder_plan_for_space,
)


_DEFAULT_SOURCE: object = object()


def _entry(rel_path: str, size: int = 100) -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False, hash_sha256="")


def _comparison(
    rel_path: str,
    diff_type: DiffType,
    action: SyncAction,
    source: FileEntry | None | object = _DEFAULT_SOURCE,
    dest: FileEntry | None = None,
) -> ComparisonEntry:
    if source is _DEFAULT_SOURCE:
        source = _entry(rel_path)
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=diff_type,
        source=source,  # type: ignore[arg-type]
        dest=dest,
        action=action,
    )


def _plan(entries: list[ComparisonEntry]) -> SyncPlan:
    return SyncPlan(
        entries=entries,
        total_copy_bytes=0,
        total_delete_count=0,
        total_overwrite_count=0,
        total_rename_count=0,
    )


class TestCalculateFreedSpacePerSide:
    def test_delete_from_dest_frees_dest_space(self):
        entries = [
            _comparison("old1.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("old1.txt", size=500)),
            _comparison("old2.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("old2.txt", size=300)),
        ]
        dest_freed, src_freed = calculate_freed_space_per_side(_plan(entries))
        assert dest_freed == 800
        assert src_freed == 0

    def test_move_to_trash_frees_dest_space(self):
        entries = [
            _comparison("trash1.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH, source=None, dest=_entry("trash1.txt", size=1000)),
        ]
        dest_freed, src_freed = calculate_freed_space_per_side(_plan(entries))
        assert dest_freed == 1000
        assert src_freed == 0

    def test_copy_and_overwrite_do_not_free_space(self):
        entries = [
            _comparison("new.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("new.txt", size=500)),
            _comparison("mod.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("mod.txt", size=200), dest=_entry("mod.txt", size=100)),
        ]
        dest_freed, src_freed = calculate_freed_space_per_side(_plan(entries))
        assert dest_freed == 0
        assert src_freed == 0

    def test_skip_and_keep_do_not_free_space(self):
        entries = [
            _comparison("same.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("same.txt", size=100), dest=_entry("same.txt", size=100)),
            _comparison("keep.txt", DiffType.MODIFIED, SyncAction.KEEP_DEST, source=_entry("keep.txt", size=200), dest=_entry("keep.txt", size=300)),
        ]
        dest_freed, src_freed = calculate_freed_space_per_side(_plan(entries))
        assert dest_freed == 0
        assert src_freed == 0

    def test_mixed_actions_frees_correct_amount(self):
        entries = [
            _comparison("copy.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("copy.txt", size=100)),
            _comparison("delete.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("delete.txt", size=500)),
            _comparison("trash.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH, source=None, dest=_entry("trash.txt", size=300)),
            _comparison("overwrite.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("overwrite.txt", size=200), dest=_entry("overwrite.txt", size=150)),
        ]
        dest_freed, src_freed = calculate_freed_space_per_side(_plan(entries))
        assert dest_freed == 800
        assert src_freed == 0

    def test_empty_plan_frees_zero(self):
        dest_freed, src_freed = calculate_freed_space_per_side(_plan([]))
        assert dest_freed == 0
        assert src_freed == 0

    def test_none_dest_entry_does_not_contribute(self):
        entries = [
            _comparison("missing.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=None),
        ]
        dest_freed, src_freed = calculate_freed_space_per_side(_plan(entries))
        assert dest_freed == 0
        assert src_freed == 0


class TestCheckDestinationSpaceWithFreed:
    def test_no_freed_space_uses_original_logic(self):
        with tempfile.TemporaryDirectory() as d:
            result = check_destination_space(Path(d), 1000, freed_bytes=0)
            assert result.freed_bytes == 0
            assert result.required_bytes == 1000
            assert result.shortfall_bytes == max(0, 1000 - result.free_bytes)

    def test_freed_space_makes_insufficient_sufficient(self):
        with tempfile.TemporaryDirectory() as d:
            free = result.free_bytes if (result := check_destination_space(Path(d), 0)) else 0
            huge_required = free + 5000
            result = check_destination_space(Path(d), huge_required, freed_bytes=6000)
            assert result.sufficient is True
            assert result.shortfall_bytes == 0
            assert result.freed_bytes == 6000

    def test_freed_space_partial_still_insufficient(self):
        with tempfile.TemporaryDirectory() as d:
            free = result.free_bytes if (result := check_destination_space(Path(d), 0)) else 0
            huge_required = free + 10000
            result = check_destination_space(Path(d), huge_required, freed_bytes=2000)
            assert result.sufficient is False
            expected_shortfall = (huge_required - 2000) - free
            assert result.shortfall_bytes == expected_shortfall

    def test_freed_exceeds_required_net_is_zero(self):
        with tempfile.TemporaryDirectory() as d:
            result = check_destination_space(Path(d), 1000, freed_bytes=5000)
            assert result.sufficient is True
            assert result.shortfall_bytes == 0

    def test_zero_required_with_freed_is_sufficient(self):
        with tempfile.TemporaryDirectory() as d:
            result = check_destination_space(Path(d), 0, freed_bytes=1000)
            assert result.sufficient is True
            assert result.shortfall_bytes == 0

    def test_shortfall_accounts_for_freed(self):
        with tempfile.TemporaryDirectory() as d:
            free = result.free_bytes if (result := check_destination_space(Path(d), 0)) else 0
            required = free + 3000
            freed = 1000
            result = check_destination_space(Path(d), required, freed_bytes=freed)
            assert result.shortfall_bytes == 2000


class TestMirrorExactScenario:
    """Simulates the user's bug: MIRROR_EXACT with many DEST_ONLY files to delete."""

    def test_mirror_exact_no_space_initially_but_enough_after_deletions(self):
        entries = [
            _comparison("new_source.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("new_source.txt", size=1_000_000)),
            _comparison("old_dest_1.dat", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("old_dest_1.dat", size=5_000_000)),
            _comparison("old_dest_2.dat", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("old_dest_2.dat", size=5_000_000)),
        ]
        plan = _plan(entries)

        dest_required, src_required = calculate_required_space_per_side(plan)
        dest_freed, src_freed = calculate_freed_space_per_side(plan)

        assert dest_required == 1_000_000
        assert dest_freed == 10_000_000
        assert src_required == 0
        assert src_freed == 0

        with tempfile.TemporaryDirectory() as d:
            dest_space = check_destination_space(Path(d), dest_required, freed_bytes=dest_freed)
            assert dest_space.sufficient is True
            assert dest_space.shortfall_bytes == 0

    def test_mirror_exact_still_not_enough_even_after_deletions(self):
        entries = [
            _comparison("huge_new.bin", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("huge_new.bin", size=100_000_000)),
            _comparison("old_small.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("old_small.txt", size=1_000)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 100_000_000
        assert dest_freed == 1_000

        with tempfile.TemporaryDirectory() as d:
            free = check_destination_space(Path(d), 0).free_bytes
            if free < 99_999_000:
                dest_space = check_destination_space(Path(d), dest_required, freed_bytes=dest_freed)
                assert dest_space.sufficient is False
                assert dest_space.shortfall_bytes > 0


class TestOverwriteScenario:
    """Tests space calculation when overwriting modified files."""

    def test_overwrite_larger_files_needs_space(self):
        entries = [
            _comparison("bigger.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("bigger.txt", size=5000), dest=_entry("bigger.txt", size=1000)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 5000
        assert dest_freed == 0

    def test_overwrite_smaller_files_still_counts_full_size(self):
        entries = [
            _comparison("smaller.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("smaller.txt", size=100), dest=_entry("smaller.txt", size=5000)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 100
        assert dest_freed == 0

    def test_overwrite_with_deletions_combined(self):
        entries = [
            _comparison("modified.doc", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("modified.doc", size=2000), dest=_entry("modified.doc", size=1500)),
            _comparison("obsolete.pdf", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("obsolete.pdf", size=10000)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 2000
        assert dest_freed == 10000

        with tempfile.TemporaryDirectory() as d:
            dest_space = check_destination_space(Path(d), dest_required, freed_bytes=dest_freed)
            assert dest_space.sufficient is True


class TestBidirectionalScenario:
    """Tests bidirectional sync space calculation."""

    def test_bidirectional_copies_both_sides(self):
        entries = [
            _comparison("src_only.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("src_only.txt", size=3000)),
            _comparison("dest_only.txt", DiffType.DEST_ONLY, SyncAction.COPY_TO_SOURCE, source=None, dest=_entry("dest_only.txt", size=2000)),
        ]
        plan = _plan(entries)

        dest_required, src_required = calculate_required_space_per_side(plan)
        dest_freed, src_freed = calculate_freed_space_per_side(plan)

        assert dest_required == 3000
        assert src_required == 2000
        assert dest_freed == 0
        assert src_freed == 0

    def test_bidirectional_with_copy_to_source_frees_no_space(self):
        entries = [
            _comparison("dest_only.txt", DiffType.DEST_ONLY, SyncAction.COPY_TO_SOURCE, source=None, dest=_entry("dest_only.txt", size=5000)),
        ]
        plan = _plan(entries)

        dest_required, src_required = calculate_required_space_per_side(plan)
        dest_freed, src_freed = calculate_freed_space_per_side(plan)

        assert dest_required == 0
        assert src_required == 5000
        assert dest_freed == 0
        assert src_freed == 0


class TestMixedActionsScenario:
    """Tests complex plans with multiple action types."""

    def test_complex_mirror_plan(self):
        entries = [
            _comparison("identical.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("identical.txt", size=100), dest=_entry("identical.txt", size=100)),
            _comparison("new1.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("new1.txt", size=1000)),
            _comparison("new2.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("new2.txt", size=2000)),
            _comparison("modified.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("modified.txt", size=500), dest=_entry("modified.txt", size=400)),
            _comparison("delete1.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("delete1.txt", size=8000)),
            _comparison("delete2.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("delete2.txt", size=4000)),
            _comparison("trash1.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH, source=None, dest=_entry("trash1.txt", size=3000)),
            _comparison("renamed.txt", DiffType.RENAMED, SyncAction.RENAME_IN_DEST, source=_entry("renamed.txt", size=600), dest=_entry("old_name.txt", size=600)),
        ]
        plan = _plan(entries)

        dest_required, src_required = calculate_required_space_per_side(plan)
        dest_freed, src_freed = calculate_freed_space_per_side(plan)

        assert dest_required == 1000 + 2000 + 500
        assert dest_freed == 8000 + 4000 + 3000
        assert src_required == 0
        assert src_freed == 0

        with tempfile.TemporaryDirectory() as d:
            dest_space = check_destination_space(Path(d), dest_required, freed_bytes=dest_freed)
            assert dest_space.sufficient is True
            assert dest_space.freed_bytes == 15000

    def test_all_deletions_no_copies(self):
        entries = [
            _comparison("del1.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("del1.txt", size=1000)),
            _comparison("del2.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("del2.txt", size=2000)),
            _comparison("del3.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("del3.txt", size=3000)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 0
        assert dest_freed == 6000

        with tempfile.TemporaryDirectory() as d:
            dest_space = check_destination_space(Path(d), dest_required, freed_bytes=dest_freed)
            assert dest_space.sufficient is True
            assert dest_space.shortfall_bytes == 0

    def test_all_copies_no_deletions(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=1000)),
            _comparison("b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("b.txt", size=2000)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 3000
        assert dest_freed == 0


class TestEdgeCases:
    def test_zero_size_files(self):
        entries = [
            _comparison("empty.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("empty.txt", size=0)),
            _comparison("empty_dest.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("empty_dest.txt", size=0)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 0
        assert dest_freed == 0

    def test_very_large_numbers(self):
        tb = 1_000_000_000_000
        entries = [
            _comparison("huge.bin", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("huge.bin", size=2 * tb)),
            _comparison("huge_dest.bin", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("huge_dest.bin", size=5 * tb)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 2 * tb
        assert dest_freed == 5 * tb

    def test_single_entry_delete(self):
        entries = [
            _comparison("solo.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("solo.txt", size=999)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 0
        assert dest_freed == 999

    def test_single_entry_copy(self):
        entries = [
            _comparison("solo.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("solo.txt", size=777)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 777
        assert dest_freed == 0

    def test_rename_does_not_affect_space(self):
        entries = [
            _comparison("new_name.txt", DiffType.RENAMED, SyncAction.RENAME_IN_DEST, source=_entry("new_name.txt", size=500), dest=_entry("old_name.txt", size=500)),
        ]
        plan = _plan(entries)

        dest_required, _ = calculate_required_space_per_side(plan)
        dest_freed, _ = calculate_freed_space_per_side(plan)

        assert dest_required == 0
        assert dest_freed == 0

    def test_keep_actions_do_not_affect_space(self):
        entries = [
            _comparison("keep_dest.txt", DiffType.MODIFIED, SyncAction.KEEP_DEST, source=_entry("keep_dest.txt", size=1000), dest=_entry("keep_dest.txt", size=2000)),
            _comparison("keep_src.txt", DiffType.MODIFIED, SyncAction.KEEP_SOURCE, source=_entry("keep_src.txt", size=3000), dest=_entry("keep_src.txt", size=4000)),
        ]
        plan = _plan(entries)

        dest_required, src_required = calculate_required_space_per_side(plan)
        dest_freed, src_freed = calculate_freed_space_per_side(plan)

        assert dest_required == 0
        assert src_required == 0
        assert dest_freed == 0
        assert src_freed == 0


class TestCalculateRequiredSpaceBackwardsCompat:
    def test_original_function_still_works(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=500)),
            _comparison("b.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("b.txt", size=300)),
        ]
        plan = SyncPlan(entries=entries, total_copy_bytes=800, total_delete_count=0, total_overwrite_count=1, total_rename_count=0)
        assert calculate_required_space(plan) == 800


class TestReorderPlanForSpace:
    def test_reorders_when_space_tight_but_enough_after_deletions(self, monkeypatch):
        entries = [
            _comparison("copy_first.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("copy_first.txt", size=5000)),
            _comparison("delete_me.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("delete_me.txt", size=10000)),
            _comparison("overwrite_me.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("overwrite_me.txt", size=3000), dest=_entry("overwrite_me.txt", size=2000)),
        ]
        plan = _plan(entries)

        import services.space_calculator as sc_module
        monkeypatch.setattr(sc_module, "_get_free_space", lambda path: 2000)

        new_plan = reorder_plan_for_space(plan, Path("dummy"))
        assert new_plan is not plan
        actions = [e.action for e in new_plan.entries]
        assert actions[0] == SyncAction.DELETE_FROM_DEST

    def test_no_reorder_when_space_already_sufficient(self, monkeypatch):
        entries = [
            _comparison("copy.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("copy.txt", size=100)),
            _comparison("delete.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("delete.txt", size=500)),
        ]
        plan = _plan(entries)

        import services.space_calculator as sc_module
        monkeypatch.setattr(sc_module, "_get_free_space", lambda path: 10000)

        new_plan = reorder_plan_for_space(plan, Path("dummy"))
        assert new_plan is plan

    def test_no_reorder_when_not_even_enough_after_deletions(self, monkeypatch):
        entries = [
            _comparison("huge.bin", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("huge.bin", size=1_000_000_000)),
            _comparison("small.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("small.txt", size=100)),
        ]
        plan = _plan(entries)

        import services.space_calculator as sc_module
        monkeypatch.setattr(sc_module, "_get_free_space", lambda path: 500)

        new_plan = reorder_plan_for_space(plan, Path("dummy"))
        assert new_plan is plan

    def test_reorder_puts_deletions_before_copies(self, monkeypatch):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=1000)),
            _comparison("b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("b.txt", size=2000)),
            _comparison("c.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("c.txt", size=5000)),
            _comparison("d.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH, source=None, dest=_entry("d.txt", size=3000)),
            _comparison("e.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("e.txt", size=500), dest=_entry("e.txt", size=400)),
        ]
        plan = _plan(entries)

        import services.space_calculator as sc_module
        monkeypatch.setattr(sc_module, "_get_free_space", lambda path: 1000)

        new_plan = reorder_plan_for_space(plan, Path("dummy"))
        actions = [e.action for e in new_plan.entries]
        delete_indices = [i for i, a in enumerate(actions) if a in (SyncAction.DELETE_FROM_DEST, SyncAction.MOVE_TO_TRASH)]
        copy_indices = [i for i, a in enumerate(actions) if a in (SyncAction.COPY_TO_DEST, SyncAction.OVERWRITE_DEST)]
        assert max(delete_indices) < min(copy_indices)

    def test_reorder_sorts_deletions_by_size_descending(self, monkeypatch):
        entries = [
            _comparison("small.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("small.txt", size=100)),
            _comparison("medium.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("medium.txt", size=500)),
            _comparison("large.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("large.txt", size=1000)),
            _comparison("copy.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("copy.txt", size=2000)),
        ]
        plan = _plan(entries)

        import services.space_calculator as sc_module
        monkeypatch.setattr(sc_module, "_get_free_space", lambda path: 500)

        new_plan = reorder_plan_for_space(plan, Path("dummy"))
        delete_entries = [e for e in new_plan.entries if e.action == SyncAction.DELETE_FROM_DEST]
        sizes = [e.dest.size for e in delete_entries]
        assert sizes == sorted(sizes, reverse=True)

    def test_empty_plan_returns_same(self):
        plan = _plan([])
        with tempfile.TemporaryDirectory() as d:
            new_plan = reorder_plan_for_space(plan, Path(d))
            assert new_plan is plan

    def test_no_deletions_returns_same(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=100)),
        ]
        plan = _plan(entries)
        with tempfile.TemporaryDirectory() as d:
            new_plan = reorder_plan_for_space(plan, Path(d))
            assert new_plan is plan

    def test_preserves_all_entries_after_reorder(self, monkeypatch):
        entries = [
            _comparison("copy.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("copy.txt", size=1000)),
            _comparison("delete.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, source=None, dest=_entry("delete.txt", size=5000)),
            _comparison("skip.txt", DiffType.IDENTICAL, SyncAction.SKIP, source=_entry("skip.txt", size=100), dest=_entry("skip.txt", size=100)),
            _comparison("rename.txt", DiffType.RENAMED, SyncAction.RENAME_IN_DEST, source=_entry("rename.txt", size=200), dest=_entry("old.txt", size=200)),
        ]
        plan = _plan(entries)

        import services.space_calculator as sc_module
        monkeypatch.setattr(sc_module, "_get_free_space", lambda path: 500)

        new_plan = reorder_plan_for_space(plan, Path("dummy"))
        assert len(new_plan.entries) == len(plan.entries)
        original_paths = {e.rel_path for e in plan.entries}
        reordered_paths = {e.rel_path for e in new_plan.entries}
        assert original_paths == reordered_paths
