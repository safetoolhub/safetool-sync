# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Validate translation files — checks missing keys, extra keys, and placeholder mismatches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = PROJECT_ROOT / "i18n"
BASE_LANG = "es"
OVERLAY_LANGUAGES = ["en"]


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten_keys(data: dict, prefix: str = "") -> set[str]:
    keys = set()
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(flatten_keys(value, full_key))
        else:
            keys.add(full_key)
    return keys


def get_placeholders(data: dict, prefix: str = "") -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(get_placeholders(value, full_key))
        elif isinstance(value, str):
            import re
            placeholders = re.findall(r"\{(\w+)\}", value)
            if placeholders:
                result[full_key] = placeholders
    return result


def validate_translations() -> list[str]:
    errors: list[str] = []
    base_path = I18N_DIR / f"{BASE_LANG}.json"

    if not base_path.exists():
        errors.append(f"Base language file not found: {base_path}")
        return errors

    base_data = load_json(base_path)
    base_keys = flatten_keys(base_data)
    base_placeholders = get_placeholders(base_data)

    print(f"Base language ({BASE_LANG}): {len(base_keys)} keys")

    for lang in OVERLAY_LANGUAGES:
        lang_path = I18N_DIR / f"{lang}.json"
        if not lang_path.exists():
            errors.append(f"Language file not found: {lang_path}")
            continue

        lang_data = load_json(lang_path)
        lang_keys = flatten_keys(lang_data)
        lang_placeholders = get_placeholders(lang_data)

        print(f"Language ({lang}): {len(lang_keys)} keys")

        missing_keys = base_keys - lang_keys
        extra_keys = lang_keys - base_keys

        if missing_keys:
            for key in sorted(missing_keys):
                errors.append(f"[{lang}] Missing key: {key}")

        if extra_keys:
            for key in sorted(extra_keys):
                errors.append(f"[{lang}] Extra key (not in base): {key}")

        for key, base_ph in base_placeholders.items():
            if key in lang_placeholders:
                lang_ph = lang_placeholders[key]
                if sorted(base_ph) != sorted(lang_ph):
                    errors.append(
                        f"[{lang}] Placeholder mismatch in '{key}': "
                        f"base has {base_ph}, {lang} has {lang_ph}"
                    )
            elif key not in lang_keys:
                pass  # Already reported as missing key

        # Check for empty values
        for key in lang_keys:
            value = _get_nested(lang_data, key)
            if value is not None and isinstance(value, str) and value.strip() == "":
                errors.append(f"[{lang}] Empty value for key: {key}")

    return errors


def _get_nested(data: dict, dotted_key: str):
    parts = dotted_key.split(".")
    node = data
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def main() -> int:
    print("=== SafeTool Sync — Translation Validation ===\n")

    errors = validate_translations()

    if errors:
        print(f"\n❌ Found {len(errors)} error(s):\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    base_path = I18N_DIR / f"{BASE_LANG}.json"
    base_data = load_json(base_path)
    base_keys = flatten_keys(base_data)
    print(f"\n✅ All translations valid! {len(base_keys)} keys in base language.")
    return 0


if __name__ == "__main__":
    sys.exit(main())