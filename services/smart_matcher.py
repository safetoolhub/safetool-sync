# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Smart matcher — finds likely matches between SOURCE_ONLY and DEST_ONLY entries.

Detects files that are probably the same but have different names due to
suffixes (e.g. "report.pdf" vs "report_v2.pdf", "photo.jpg" vs "photo (1).jpg").

Matching criteria:
- Same file size (exact match)
- Same base name prefix (the dest name starts with the source stem or vice versa)
- Suffix difference is at most MAX_SUFFIX_LEN characters
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from services.models import ComparisonEntry, DiffType, SyncAction

MAX_SUFFIX_LEN = 20


@dataclass
class SmartMatch:
    source_entry: ComparisonEntry
    dest_entry: ComparisonEntry
    confidence: str = "size+prefix"


@dataclass
class SmartMatchResult:
    matches: list[SmartMatch] = field(default_factory=list)
    unmatched_source: list[ComparisonEntry] = field(default_factory=list)
    unmatched_dest: list[ComparisonEntry] = field(default_factory=list)


def _stem_and_ext(rel_path: str) -> tuple[str, str]:
    name = os.path.basename(rel_path.replace("\\", "/"))
    dot_idx = name.rfind(".")
    if dot_idx > 0:
        return name[:dot_idx], name[dot_idx:]
    return name, ""


def _is_prefix_match(stem_a: str, stem_b: str) -> bool:
    if not stem_a or not stem_b:
        return False
    shorter = stem_a if len(stem_a) <= len(stem_b) else stem_b
    longer = stem_b if len(stem_a) <= len(stem_b) else stem_a
    if not longer.startswith(shorter):
        return False
    suffix_part = longer[len(shorter):]
    if len(suffix_part) > MAX_SUFFIX_LEN:
        return False
    return True


def find_smart_matches(entries: list[ComparisonEntry]) -> SmartMatchResult:
    source_only = [e for e in entries if e.diff_type == DiffType.SOURCE_ONLY]
    dest_only = [e for e in entries if e.diff_type == DiffType.DEST_ONLY]

    if not source_only or not dest_only:
        return SmartMatchResult(
            matches=[],
            unmatched_source=list(source_only),
            unmatched_dest=list(dest_only),
        )

    dest_by_size: dict[int, list[ComparisonEntry]] = {}
    for d in dest_only:
        size = d.dest.size if d.dest else 0
        dest_by_size.setdefault(size, []).append(d)

    matched_source: set[int] = set()
    matched_dest: set[int] = set()
    matches: list[SmartMatch] = []

    for i, src in enumerate(source_only):
        src_size = src.source.size if src.source else 0
        candidates = dest_by_size.get(src_size, [])
        if not candidates:
            continue

        src_stem, src_ext = _stem_and_ext(src.rel_path)

        for j, dst in enumerate(candidates):
            if id(dst) in matched_dest:
                continue

            dst_stem, dst_ext = _stem_and_ext(dst.rel_path)

            if src_ext.lower() != dst_ext.lower():
                continue

            if _is_prefix_match(src_stem, dst_stem):
                matches.append(SmartMatch(source_entry=src, dest_entry=dst))
                matched_source.add(i)
                matched_dest.add(id(dst))
                break

    unmatched_source = [e for i, e in enumerate(source_only) if i not in matched_source]
    unmatched_dest = [e for e in dest_only if id(e) not in matched_dest]

    return SmartMatchResult(
        matches=matches,
        unmatched_source=unmatched_source,
        unmatched_dest=unmatched_dest,
    )
