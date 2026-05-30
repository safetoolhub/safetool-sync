# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Internationalization core module — JSON-based translation system."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES: dict[str, str] = {"es": "Español", "en": "English"}
DEFAULT_LANGUAGE: str = "es"

_translations: dict[str, Any] = {}
_fallback: dict[str, Any] = {}
_current_language: str = DEFAULT_LANGUAGE
_initialized: bool = False

_I18N_DIR: Path = Path(__file__).resolve().parent


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge(overlay: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = _merge(value, result[key])
        else:
            result[key] = value
    return result


def init_i18n(language: str = DEFAULT_LANGUAGE) -> None:
    global _translations, _fallback, _current_language, _initialized

    _current_language = language

    _fallback = _load(_I18N_DIR / "es.json")

    if language == "es":
        _translations = dict(_fallback)
    else:
        overlay = _load(_I18N_DIR / f"{language}.json")
        _translations = _merge(overlay, _fallback)

    _initialized = True


def _resolve(key: str, data: dict[str, Any]) -> str | None:
    parts = key.split(".")
    node: Any = data
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return str(node) if not isinstance(node, dict) else None


def tr(key: str, **kwargs: Any) -> str:
    if not _initialized:
        init_i18n()

    value = _resolve(key, _translations)
    if value is None:
        value = _resolve(key, _fallback)
    if value is None:
        return key

    for k, v in kwargs.items():
        value = value.replace(f"{{{k}}}", str(v))

    return value


def get_current_language() -> str:
    return _current_language


def get_supported_languages() -> dict[str, str]:
    return dict(SUPPORTED_LANGUAGES)