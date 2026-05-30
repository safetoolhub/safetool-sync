# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Analysis export — save, load, and compare analysis results as JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from services.models import (
    ComparisonEntry,
    DiffType,
    SyncAction,
    SyncReport,
)


def export_analysis(
    entries: list[ComparisonEntry],
    path: Path,
    metadata: Optional[dict] = None,
) -> None:
    """Save a list of ComparisonEntry as JSON for offline review.

    Args:
        entries: List of ComparisonEntry to export.
        path: Output file path.
        metadata: Optional dict with extra info (source, dest, timestamp, etc).
    """
    data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "entry_count": len(entries),
        "metadata": metadata or {},
        "entries": [_entry_to_dict(e) for e in entries],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def import_analysis(path: Path) -> list[ComparisonEntry]:
    """Load a previously exported analysis from JSON.

    Args:
        path: Path to the JSON file.

    Returns:
        List of ComparisonEntry.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [_dict_to_entry(d) for d in data.get("entries", [])]


def compare_analyses(
    old_entries: list[ComparisonEntry],
    new_entries: list[ComparisonEntry],
) -> list[ComparisonEntry]:
    """Compare two analyses to see what changed.

    Returns entries from the new analysis that are different from the old
    (new files, changed diff_type, or changed action).

    Args:
        old_entries: Previous analysis entries.
        new_entries: Current analysis entries.

    Returns:
        List of ComparisonEntry that changed or are new.
    """
    old_index: dict[str, ComparisonEntry] = {e.rel_path: e for e in old_entries}
    changes: list[ComparisonEntry] = []

    for new_entry in new_entries:
        if new_entry.rel_path not in old_index:
            changes.append(new_entry)
            continue

        old_entry = old_index[new_entry.rel_path]
        if (
            new_entry.diff_type != old_entry.diff_type
            or new_entry.action != old_entry.action
        ):
            changes.append(new_entry)

    return changes


def _entry_to_dict(entry: ComparisonEntry) -> dict:
    """Convert a ComparisonEntry to a JSON-serializable dict."""
    result: dict = {
        "rel_path": entry.rel_path,
        "diff_type": entry.diff_type.value,
        "action": entry.action.value,
        "error_msg": entry.error_msg,
    }
    if entry.source:
        result["source"] = {
            "rel_path": entry.source.rel_path,
            "size": entry.source.size,
            "mtime": entry.source.mtime,
            "is_dir": entry.source.is_dir,
            "hash_sha256": entry.source.hash_sha256,
        }
    else:
        result["source"] = None

    if entry.dest:
        result["dest"] = {
            "rel_path": entry.dest.rel_path,
            "size": entry.dest.size,
            "mtime": entry.dest.mtime,
            "is_dir": entry.dest.is_dir,
            "hash_sha256": entry.dest.hash_sha256,
        }
    else:
        result["dest"] = None

    return result


def _dict_to_entry(data: dict) -> ComparisonEntry:
    """Convert a JSON dict back to a ComparisonEntry."""
    from services.models import FileEntry

    source = None
    if data.get("source"):
        s = data["source"]
        source = FileEntry(
            rel_path=s["rel_path"],
            size=s["size"],
            mtime=s["mtime"],
            is_dir=s["is_dir"],
            hash_sha256=s.get("hash_sha256", ""),
        )

    dest = None
    if data.get("dest"):
        d = data["dest"]
        dest = FileEntry(
            rel_path=d["rel_path"],
            size=d["size"],
            mtime=d["mtime"],
            is_dir=d["is_dir"],
            hash_sha256=d.get("hash_sha256", ""),
        )

    return ComparisonEntry(
        rel_path=data["rel_path"],
        diff_type=DiffType(data["diff_type"]),
        source=source,
        dest=dest,
        action=SyncAction(data["action"]),
        error_msg=data.get("error_msg", ""),
    )


def export_sync_log(
    report: SyncReport,
    entries: list[ComparisonEntry],
    path: Path,
    source: str = "",
    dest: str = "",
) -> None:
    """Export a human-readable TXT log of all sync operations.

    Sections:
      1. Header — date, source, dest, global counters
      2. OPERATIONS PERFORMED — actions that modified files (copy, overwrite,
         delete, trash, rename)
      3. OPERATIONS NOT PERFORMED — kept, skipped, pending review, identical
      4. ERRORS — per-file error messages (if any)

    Args:
        report: SyncReport with counters and error list.
        entries: ComparisonEntry list from the analysis.
        path: Output .txt file path.
        source: Source path string (for header).
        dest: Destination path string (for header).
    """
    _ACTION_LABELS: dict[SyncAction, str] = {
        SyncAction.COPY_TO_DEST: "COPY TO DESTINATION",
        SyncAction.COPY_TO_SOURCE: "COPY TO SOURCE",
        SyncAction.OVERWRITE_DEST: "OVERWRITE DESTINATION",
        SyncAction.OVERWRITE_SOURCE: "OVERWRITE SOURCE",
        SyncAction.DELETE_FROM_DEST: "DELETE FROM DESTINATION",
        SyncAction.MOVE_TO_TRASH: "MOVE TO TRASH",
        SyncAction.RENAME_IN_DEST: "RENAME IN DESTINATION",
        SyncAction.KEEP_DEST: "KEEP DESTINATION (no change)",
        SyncAction.KEEP_SOURCE: "KEEP SOURCE (no change)",
        SyncAction.SKIP: "SKIPPED",
        SyncAction.MARK_REVIEW: "PENDING REVIEW",
    }

    _PERFORMED_ACTIONS = {
        SyncAction.COPY_TO_DEST,
        SyncAction.COPY_TO_SOURCE,
        SyncAction.OVERWRITE_DEST,
        SyncAction.OVERWRITE_SOURCE,
        SyncAction.DELETE_FROM_DEST,
        SyncAction.MOVE_TO_TRASH,
        SyncAction.RENAME_IN_DEST,
    }

    _NOT_PERFORMED_ACTIONS = [
        SyncAction.KEEP_DEST,
        SyncAction.KEEP_SOURCE,
        SyncAction.SKIP,
        SyncAction.MARK_REVIEW,
    ]

    _PERFORMED_ORDER = [
        SyncAction.COPY_TO_DEST,
        SyncAction.COPY_TO_SOURCE,
        SyncAction.OVERWRITE_DEST,
        SyncAction.OVERWRITE_SOURCE,
        SyncAction.RENAME_IN_DEST,
        SyncAction.DELETE_FROM_DEST,
        SyncAction.MOVE_TO_TRASH,
    ]

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines.append("=" * 72)
    lines.append("  SAFETOOL SYNC - OPERATION LOG")
    lines.append("=" * 72)
    lines.append(f"  Date        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if source:
        lines.append(f"  Source      : {source}")
    if dest:
        lines.append(f"  Destination : {dest}")
    lines.append("")
    lines.append("  SUMMARY")
    lines.append("  " + "-" * 68)
    lines.append(f"  Copied               : {report.copied}")
    lines.append(f"  Overwritten          : {report.overwritten}")
    lines.append(f"  Deleted              : {report.deleted}")
    lines.append(f"  Moved to trash       : {report.trashed}")
    lines.append(f"  Renamed              : {report.renamed}")
    lines.append(f"  Skipped / not changed: {report.skipped}")
    lines.append(f"  Verified (SHA-256)   : {report.verified}")
    lines.append(f"  Verification failures: {report.verification_failures}")
    lines.append(f"  Errors               : {len(report.errors)}")
    if report.duration:
        h = int(report.duration // 3600)
        m = int((report.duration % 3600) // 60)
        s = int(report.duration % 60)
        if h:
            lines.append(f"  Duration             : {h}h {m}m {s}s")
        elif m:
            lines.append(f"  Duration             : {m}m {s}s")
        else:
            lines.append(f"  Duration             : {s}s")
    if report.total_bytes:
        lines.append(f"  Total transferred    : {_fmt_size(report.total_bytes)}")
    lines.append("=" * 72)

    # ── Group entries ─────────────────────────────────────────────────────────
    grouped: dict[SyncAction, list[ComparisonEntry]] = {}
    identical_entries: list[ComparisonEntry] = []
    for entry in entries:
        if entry.diff_type == DiffType.IDENTICAL:
            identical_entries.append(entry)
        else:
            grouped.setdefault(entry.action, []).append(entry)

    # ── Section 1: Operations performed ───────────────────────────────────────
    performed_total = sum(
        len(grouped.get(a, [])) for a in _PERFORMED_ORDER
    )
    lines.append("")
    lines.append(f"  OPERATIONS PERFORMED  ({performed_total} files)")
    lines.append("  " + "=" * 68)

    has_performed = False
    for action in _PERFORMED_ORDER:
        bucket = grouped.get(action)
        if not bucket:
            continue
        has_performed = True
        label = _ACTION_LABELS[action]
        lines.append("")
        lines.append(f"  >> {label}  ({len(bucket)} files)")
        lines.append("  " + "-" * 68)
        for e in sorted(bucket, key=lambda x: x.rel_path):
            lines.append(_format_entry_line(e))

    if not has_performed:
        lines.append("")
        lines.append("    (no operations performed)")

    # ── Section 2: Operations not performed ───────────────────────────────────
    not_performed_total = (
        sum(len(grouped.get(a, [])) for a in _NOT_PERFORMED_ACTIONS)
        + len(identical_entries)
    )
    lines.append("")
    lines.append(f"  OPERATIONS NOT PERFORMED  ({not_performed_total} files)")
    lines.append("  " + "=" * 68)

    for action in _NOT_PERFORMED_ACTIONS:
        bucket = grouped.get(action)
        if not bucket:
            continue
        label = _ACTION_LABELS[action]
        lines.append("")
        lines.append(f"  -- {label}  ({len(bucket)} files)")
        lines.append("  " + "-" * 68)
        for e in sorted(bucket, key=lambda x: x.rel_path):
            lines.append(_format_entry_line(e))

    if identical_entries:
        lines.append("")
        lines.append(f"  -- IDENTICAL - NO ACTION NEEDED  ({len(identical_entries)} files)")
        lines.append("  " + "-" * 68)
        for e in sorted(identical_entries, key=lambda x: x.rel_path):
            lines.append(_format_entry_line(e))

    if not_performed_total == 0:
        lines.append("")
        lines.append("    (all files were processed)")

    # ── Section 3: Errors ─────────────────────────────────────────────────────
    if report.errors:
        lines.append("")
        lines.append(f"  ERRORS  ({len(report.errors)})")
        lines.append("  " + "=" * 68)
        for err in report.errors:
            lines.append(f"    [!] {err}")

    lines.append("")
    lines.append("=" * 72)
    lines.append("  END OF LOG")
    lines.append("=" * 72)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _format_entry_line(entry: ComparisonEntry) -> str:
    """Format a single ComparisonEntry as a readable log line.

    Shows: path, diff type, source size/mtime, dest size/mtime (when relevant).
    """
    diff_tag = f"[{entry.diff_type.value}]"
    parts: list[str] = [f"    {entry.rel_path:<55} {diff_tag}"]

    detail_parts: list[str] = []
    if entry.source:
        src_mtime = datetime.fromtimestamp(entry.source.mtime).strftime("%Y-%m-%d %H:%M") if entry.source.mtime else "?"
        detail_parts.append(f"src: {_fmt_size(entry.source.size):>10}  {src_mtime}")
    if entry.dest:
        dst_mtime = datetime.fromtimestamp(entry.dest.mtime).strftime("%Y-%m-%d %H:%M") if entry.dest.mtime else "?"
        detail_parts.append(f"dst: {_fmt_size(entry.dest.size):>10}  {dst_mtime}")
    if detail_parts:
        parts.append("      " + "   |   ".join(detail_parts))

    if entry.error_msg:
        parts.append(f"      ERROR: {entry.error_msg}")

    return "\n".join(parts)


def _fmt_size(size: int) -> str:
    """Format byte count as human-readable string."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.2f} GB"
