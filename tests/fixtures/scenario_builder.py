# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Scenario builder — generates synthetic source/dest directory trees for testing.

This module creates deterministic file structures that produce every possible
DiffType and SyncAction combination.  It can be used:

  • Inside pytest fixtures (``build_scenario(tmp_path, ...)``).
  • From the CLI to create manual-testing sandboxes::

        uv run python -m tests.fixtures.scenario_builder --scenario all --output /tmp/sync_sandbox

Each *scenario* is a named recipe that populates a ``source/`` and ``dest/``
directory pair.  The builder returns a ``ScenarioResult`` dataclass with paths
and a manifest describing what DiffType/SyncAction is expected for every file.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class ScenarioName(Enum):
    IDENTICAL = "identical"
    SOURCE_ONLY = "source_only"
    DEST_ONLY = "dest_only"
    MODIFIED_SIZE = "modified_size"
    MODIFIED_MTIME = "modified_mtime"
    MODIFIED_CONTENT = "modified_content"
    CONFLICT_BOTH_CHANGED = "conflict_both_changed"
    CONFLICT_SAME_SIZE_DIFF_CONTENT = "conflict_same_size_diff_content"
    CONFLICT_BIDIRECTIONAL = "conflict_bidirectional"
    RENAMED_FILE = "renamed_file"
    RENAMED_ACROSS_DIRS = "renamed_across_dirs"
    NESTED_DIRS = "nested_dirs"
    EMPTY_FILES = "empty_files"
    LARGE_FILE = "large_file"
    SPECIAL_CHARS = "special_chars"
    DEEP_NESTING = "deep_nesting"
    MIXED_ALL = "mixed_all"
    CONFLICT_BATCH_BY_EXT = "conflict_batch_by_ext"
    CONFLICT_BATCH_BY_FOLDER = "conflict_batch_by_folder"


@dataclass
class ExpectedEntry:
    """What we expect the comparator to produce for a given rel_path."""
    rel_path: str
    expected_diff_type: str
    expected_default_action: str
    description: str = ""


@dataclass
class ScenarioResult:
    """Result of building a scenario on disk."""
    source_root: Path
    dest_root: Path
    name: str
    expectations: list[ExpectedEntry] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_file(path: Path, content: bytes | str, mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    if mtime is not None:
        os.utime(str(path), (mtime, mtime))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _generate_content(label: str, size: int = 256) -> bytes:
    base = label.encode("utf-8")
    data = base * (size // len(base) + 1)
    return data[:size]


# ── Individual scenario builders ─────────────────────────────────────────────

_NOW = time.time()
_OLD = _NOW - 86400
_OLDER = _NOW - 172800


def _build_identical(src: Path, dst: Path) -> list[ExpectedEntry]:
    content = _generate_content("identical_file")
    _write_file(src / "shared.txt", content, mtime=_OLD)
    _write_file(dst / "shared.txt", content, mtime=_OLD)

    _write_file(src / "docs" / "manual.pdf", _generate_content("manual_pdf", 1024), mtime=_OLD)
    _write_file(dst / "docs" / "manual.pdf", _generate_content("manual_pdf", 1024), mtime=_OLD)

    return [
        ExpectedEntry("shared.txt", "identical", "skip", "Same content, same mtime"),
        ExpectedEntry("docs/manual.pdf", "identical", "skip", "Same content in subdir"),
    ]


def _build_source_only(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "new_report.docx", _generate_content("new_report", 512), mtime=_NOW)
    _write_file(src / "images" / "photo.png", _generate_content("photo_png", 2048), mtime=_NOW)
    _write_file(src / "data" / "records" / "2024.csv", _generate_content("csv_data", 300), mtime=_NOW)

    return [
        ExpectedEntry("new_report.docx", "source_only", "copy_to_dest", "File only in source"),
        ExpectedEntry("images/photo.png", "source_only", "copy_to_dest", "File in source subdir"),
        ExpectedEntry("data/records/2024.csv", "source_only", "copy_to_dest", "Deeply nested source-only"),
    ]


def _build_dest_only(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(dst / "obsolete.log", _generate_content("old_log", 128), mtime=_OLDER)
    _write_file(dst / "backup" / "archive.tar", _generate_content("archive", 4096), mtime=_OLDER)

    return [
        ExpectedEntry("obsolete.log", "dest_only", "move_to_trash", "Orphaned file in dest"),
        ExpectedEntry("backup/archive.tar", "dest_only", "move_to_trash", "Orphaned file in dest subdir"),
    ]


def _build_modified_size(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "growing.log", _generate_content("src_growing", 500), mtime=_NOW)
    _write_file(dst / "growing.log", _generate_content("dst_growing", 200), mtime=_OLD)

    return [
        ExpectedEntry("growing.log", "modified", "overwrite_dest", "Different size → modified"),
    ]


def _build_modified_mtime(src: Path, dst: Path) -> list[ExpectedEntry]:
    content = _generate_content("mtime_file", 300)
    _write_file(src / "touched.cfg", content, mtime=_NOW)
    _write_file(dst / "touched.cfg", content, mtime=_OLDER)

    return [
        ExpectedEntry("touched.cfg", "modified", "overwrite_dest", "Same content, different mtime (>1s diff)"),
    ]


def _build_modified_content(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "config.json", b'{"version": 2, "debug": false}', mtime=_NOW)
    _write_file(dst / "config.json", b'{"version": 1, "debug": true}', mtime=_OLD)

    return [
        ExpectedEntry("config.json", "modified", "overwrite_dest", "Different content and mtime"),
    ]


def _build_conflict_both_changed(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "notes.txt", _generate_content("src_notes_v2", 400), mtime=_NOW)
    _write_file(dst / "notes.txt", _generate_content("dst_notes_v2", 350), mtime=_NOW - 10)

    _write_file(src / "project" / "main.py", _generate_content("src_main_py", 600), mtime=_NOW)
    _write_file(dst / "project" / "main.py", _generate_content("dst_main_py", 580), mtime=_NOW - 5)

    return [
        ExpectedEntry("notes.txt", "modified", "overwrite_dest",
                       "Both sides changed — different size/content, source newer"),
        ExpectedEntry("project/main.py", "modified", "overwrite_dest",
                       "Both sides changed in subdir"),
    ]


def _build_conflict_same_size_diff_content(src: Path, dst: Path) -> list[ExpectedEntry]:
    size = 256
    src_content = b"A" * (size - 16) + b"_SOURCE_CONTENT_"
    dst_content = b"A" * (size - 16) + b"_DESTIN_CONTENT_"
    _write_file(src / "stealth_conflict.dat", src_content, mtime=_OLD)
    _write_file(dst / "stealth_conflict.dat", dst_content, mtime=_OLD)

    return [
        ExpectedEntry("stealth_conflict.dat", "modified", "overwrite_dest",
                       "Same size, same mtime, different content — invisible to FAST mode, requires hash to detect"),
    ]


def _build_conflict_bidirectional(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "shared_doc.odt", _generate_content("src_odt_v3", 800), mtime=_NOW)
    _write_file(dst / "shared_doc.odt", _generate_content("dst_odt_v4", 900), mtime=_NOW + 10)

    _write_file(src / "budget.xlsx", _generate_content("src_budget_q2", 700), mtime=_NOW - 60)
    _write_file(dst / "budget.xlsx", _generate_content("dst_budget_q3", 750), mtime=_NOW)

    return [
        ExpectedEntry("shared_doc.odt", "modified", "overwrite_dest",
                       "Dest is NEWER than source — bidirectional conflict"),
        ExpectedEntry("budget.xlsx", "modified", "overwrite_dest",
                       "Source is older — another bidirectional scenario"),
    ]


def _build_renamed_file(src: Path, dst: Path) -> list[ExpectedEntry]:
    content = _generate_content("rename_me_content", 512)
    _write_file(src / "report_final.pdf", content, mtime=_OLD)
    _write_file(dst / "report_draft.pdf", content, mtime=_OLD)

    return [
        ExpectedEntry("report_final.pdf", "source_only", "copy_to_dest",
                       "Source side of rename — initially detected as source_only"),
        ExpectedEntry("report_draft.pdf", "dest_only", "move_to_trash",
                       "Dest side of rename — initially detected as dest_only, "
                       "becomes RENAMED after detect_renames() with hashes"),
    ]


def _build_renamed_across_dirs(src: Path, dst: Path) -> list[ExpectedEntry]:
    content = _generate_content("cross_dir_rename", 768)
    _write_file(src / "2024" / "summary.csv", content, mtime=_OLD)
    _write_file(dst / "archive" / "summary.csv", content, mtime=_OLD)

    return [
        ExpectedEntry("2024/summary.csv", "source_only", "copy_to_dest",
                       "Cross-dir rename source side"),
        ExpectedEntry("archive/summary.csv", "dest_only", "move_to_trash",
                       "Cross-dir rename dest side — becomes RENAMED with hashes"),
    ]


def _build_nested_dirs(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "a" / "b" / "c" / "deep.txt", b"deep content", mtime=_OLD)
    _write_file(dst / "a" / "b" / "c" / "deep.txt", b"deep content", mtime=_OLD)

    _write_file(src / "a" / "b" / "new_in_branch.md", b"# new", mtime=_NOW)

    _write_file(dst / "a" / "old_branch" / "legacy.dat", b"old", mtime=_OLDER)

    return [
        ExpectedEntry("a/b/c/deep.txt", "identical", "skip", "Deeply nested identical"),
        ExpectedEntry("a/b/new_in_branch.md", "source_only", "copy_to_dest", "New file in nested src"),
        ExpectedEntry("a/old_branch/legacy.dat", "dest_only", "move_to_trash", "Orphan in nested dest"),
    ]


def _build_empty_files(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / ".gitkeep", b"", mtime=_OLD)
    _write_file(dst / ".gitkeep", b"", mtime=_OLD)

    _write_file(src / "empty_new.txt", b"", mtime=_NOW)

    return [
        ExpectedEntry(".gitkeep", "identical", "skip", "Empty file identical both sides"),
        ExpectedEntry("empty_new.txt", "source_only", "copy_to_dest", "Empty file source-only"),
    ]


def _build_large_file(src: Path, dst: Path) -> list[ExpectedEntry]:
    large_src = b"S" * (1024 * 1024)
    large_dst = b"D" * (1024 * 1024)
    _write_file(src / "big_data.bin", large_src, mtime=_NOW)
    _write_file(dst / "big_data.bin", large_dst, mtime=_OLD)

    return [
        ExpectedEntry("big_data.bin", "modified", "overwrite_dest", "1 MB file, different content"),
    ]


def _build_special_chars(src: Path, dst: Path) -> list[ExpectedEntry]:
    _write_file(src / "file with spaces.txt", b"spaces", mtime=_OLD)
    _write_file(dst / "file with spaces.txt", b"spaces", mtime=_OLD)

    _write_file(src / "special-chars_v2 (copy).log", b"special", mtime=_NOW)

    return [
        ExpectedEntry("file with spaces.txt", "identical", "skip", "Filename with spaces"),
        ExpectedEntry("special-chars_v2 (copy).log", "source_only", "copy_to_dest",
                       "Filename with special chars"),
    ]


def _build_deep_nesting(src: Path, dst: Path) -> list[ExpectedEntry]:
    deep_path = Path(*[f"level_{i}" for i in range(10)])
    _write_file(src / deep_path / "bottom.txt", b"bottom", mtime=_OLD)
    _write_file(dst / deep_path / "bottom.txt", b"bottom modified", mtime=_NOW)

    rel = str(deep_path / "bottom.txt").replace(os.sep, "/")
    return [
        ExpectedEntry(rel, "modified", "overwrite_dest", "10-level deep nesting, modified"),
    ]


def _build_conflict_batch_by_ext(src: Path, dst: Path) -> list[ExpectedEntry]:
    expectations = []
    for i in range(5):
        fname = f"document_{i}.docx"
        _write_file(src / fname, _generate_content(f"src_doc_{i}", 400 + i * 10), mtime=_NOW)
        _write_file(dst / fname, _generate_content(f"dst_doc_{i}", 400 + i * 5), mtime=_NOW - 30)
        expectations.append(
            ExpectedEntry(fname, "modified", "overwrite_dest",
                          f"Batch conflict .docx #{i} — for group-by-extension resolution")
        )

    for i in range(3):
        fname = f"image_{i}.png"
        _write_file(src / fname, _generate_content(f"src_img_{i}", 2000 + i * 100), mtime=_NOW)
        _write_file(dst / fname, _generate_content(f"dst_img_{i}", 1800 + i * 50), mtime=_NOW - 20)
        expectations.append(
            ExpectedEntry(fname, "modified", "overwrite_dest",
                          f"Batch conflict .png #{i} — for group-by-extension resolution")
        )

    return expectations


def _build_conflict_batch_by_folder(src: Path, dst: Path) -> list[ExpectedEntry]:
    expectations = []
    for folder in ("reports", "invoices", "drafts"):
        for i in range(3):
            fname = f"{folder}/file_{i}.txt"
            _write_file(
                src / fname,
                _generate_content(f"src_{folder}_{i}", 300 + i * 20),
                mtime=_NOW,
            )
            _write_file(
                dst / fname,
                _generate_content(f"dst_{folder}_{i}", 280 + i * 15),
                mtime=_NOW - 60,
            )
            expectations.append(
                ExpectedEntry(fname, "modified", "overwrite_dest",
                              f"Batch conflict in {folder}/ — for group-by-folder resolution")
            )

    return expectations


# ── Scenario registry ────────────────────────────────────────────────────────

_BUILDERS: dict[ScenarioName, Callable[[Path, Path], list[ExpectedEntry]]] = {
    ScenarioName.IDENTICAL: _build_identical,
    ScenarioName.SOURCE_ONLY: _build_source_only,
    ScenarioName.DEST_ONLY: _build_dest_only,
    ScenarioName.MODIFIED_SIZE: _build_modified_size,
    ScenarioName.MODIFIED_MTIME: _build_modified_mtime,
    ScenarioName.MODIFIED_CONTENT: _build_modified_content,
    ScenarioName.CONFLICT_BOTH_CHANGED: _build_conflict_both_changed,
    ScenarioName.CONFLICT_SAME_SIZE_DIFF_CONTENT: _build_conflict_same_size_diff_content,
    ScenarioName.CONFLICT_BIDIRECTIONAL: _build_conflict_bidirectional,
    ScenarioName.RENAMED_FILE: _build_renamed_file,
    ScenarioName.RENAMED_ACROSS_DIRS: _build_renamed_across_dirs,
    ScenarioName.NESTED_DIRS: _build_nested_dirs,
    ScenarioName.EMPTY_FILES: _build_empty_files,
    ScenarioName.LARGE_FILE: _build_large_file,
    ScenarioName.SPECIAL_CHARS: _build_special_chars,
    ScenarioName.DEEP_NESTING: _build_deep_nesting,
    ScenarioName.CONFLICT_BATCH_BY_EXT: _build_conflict_batch_by_ext,
    ScenarioName.CONFLICT_BATCH_BY_FOLDER: _build_conflict_batch_by_folder,
}


# ── Public API ────────────────────────────────────────────────────────────────


def build_scenario(
    base_dir: Path,
    scenario: ScenarioName,
) -> ScenarioResult:
    """Build a single named scenario under ``base_dir``.

    Creates ``base_dir/source/`` and ``base_dir/dest/`` with the appropriate
    files and returns a ScenarioResult with expectations.

    Args:
        base_dir: Parent directory where source/ and dest/ will be created.
        scenario: Which scenario to build.

    Returns:
        ScenarioResult with paths and expected diff types/actions.
    """
    src = base_dir / "source"
    dst = base_dir / "dest"
    src.mkdir(parents=True, exist_ok=True)
    dst.mkdir(parents=True, exist_ok=True)

    builder = _BUILDERS[scenario]
    expectations = builder(src, dst)

    return ScenarioResult(
        source_root=src,
        dest_root=dst,
        name=scenario.value,
        expectations=expectations,
    )


def build_mixed_scenario(base_dir: Path) -> ScenarioResult:
    """Build a single directory pair containing ALL scenario types.

    Every scenario writes into the same ``source/`` and ``dest/``, creating a
    comprehensive test environment.  File paths are prefixed by scenario name
    to avoid collisions.

    Args:
        base_dir: Parent directory where source/ and dest/ will be created.

    Returns:
        ScenarioResult with aggregated expectations from all scenarios.
    """
    src = base_dir / "source"
    dst = base_dir / "dest"
    src.mkdir(parents=True, exist_ok=True)
    dst.mkdir(parents=True, exist_ok=True)

    all_expectations: list[ExpectedEntry] = []

    for scenario_name, builder in _BUILDERS.items():
        if scenario_name == ScenarioName.MIXED_ALL:
            continue
        prefix = scenario_name.value
        prefixed_src = src / prefix
        prefixed_dst = dst / prefix
        prefixed_src.mkdir(parents=True, exist_ok=True)
        prefixed_dst.mkdir(parents=True, exist_ok=True)

        expectations = builder(prefixed_src, prefixed_dst)
        for exp in expectations:
            all_expectations.append(ExpectedEntry(
                rel_path=f"{prefix}/{exp.rel_path}",
                expected_diff_type=exp.expected_diff_type,
                expected_default_action=exp.expected_default_action,
                description=f"[{prefix}] {exp.description}",
            ))

    return ScenarioResult(
        source_root=src,
        dest_root=dst,
        name="mixed_all",
        expectations=all_expectations,
    )


_BUILDERS[ScenarioName.MIXED_ALL] = lambda s, d: []


def list_scenarios() -> list[str]:
    """Return all available scenario names."""
    return [s.value for s in ScenarioName]


def print_manifest(result: ScenarioResult) -> None:
    """Print a human-readable manifest of the scenario expectations."""
    print(f"\n{'=' * 72}")
    print(f"  Scenario: {result.name}")
    print(f"  Source:   {result.source_root}")
    print(f"  Dest:     {result.dest_root}")
    print(f"  Expected entries: {len(result.expectations)}")
    print(f"{'=' * 72}")

    for exp in result.expectations:
        print(f"  {exp.rel_path:<45} {exp.expected_diff_type:<15} → {exp.expected_default_action}")
        if exp.description:
            print(f"    └─ {exp.description}")
    print()


# ── CLI entry point ──────────────────────────────────────────────────────────


def _main() -> None:
    import argparse
    import sys

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="SafeTool Sync — synthetic scenario builder for E2E testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python -m tests.fixtures.scenario_builder --list\n"
            "  uv run python -m tests.fixtures.scenario_builder --scenario mixed_all --output /tmp/sync_sandbox\n"
            "  uv run python -m tests.fixtures.scenario_builder --scenario conflict_both_changed --output /tmp/conflicts\n"
        ),
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available scenarios and exit.",
    )
    parser.add_argument(
        "--scenario", type=str, default="mixed_all",
        help="Scenario name to build (default: mixed_all).",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: /tmp/safetool_sync_sandbox).",
    )

    args = parser.parse_args()

    if args.list:
        print("Available scenarios:")
        for name in list_scenarios():
            print(f"  • {name}")
        sys.exit(0)

    output_dir = Path(args.output) if args.output else Path("/tmp/safetool_sync_sandbox")

    if output_dir.exists():
        import shutil
        shutil.rmtree(str(output_dir))

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        scenario_enum = ScenarioName(args.scenario)
    except ValueError:
        print(f"ERROR: Unknown scenario '{args.scenario}'")
        print(f"Available: {', '.join(list_scenarios())}")
        sys.exit(1)

    if scenario_enum == ScenarioName.MIXED_ALL:
        result = build_mixed_scenario(output_dir)
    else:
        result = build_scenario(output_dir, scenario_enum)

    print_manifest(result)
    print(f"✓ Scenario '{result.name}' created at: {output_dir}")


if __name__ == "__main__":
    _main()
