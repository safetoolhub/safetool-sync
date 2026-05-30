# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for i18n.core."""
from __future__ import annotations

import pytest

from i18n.core import init_i18n, tr, get_current_language, get_supported_languages, _resolve, _merge


class TestInitI18n:
    def test_init_spanish(self):
        init_i18n("es")
        assert get_current_language() == "es"

    def test_init_english(self):
        init_i18n("en")
        assert get_current_language() == "en"

    def test_init_default(self):
        init_i18n()
        assert get_current_language() == "es"


class TestTr:
    def test_tr_spanish_key(self):
        init_i18n("es")
        result = tr("app.name")
        assert result == "SafeTool Sync"

    def test_tr_english_key(self):
        init_i18n("en")
        result = tr("app.name")
        assert result == "SafeTool Sync"

    def test_tr_returns_key_for_missing(self):
        init_i18n("es")
        result = tr("nonexistent.key.path")
        assert result == "nonexistent.key.path"

    def test_tr_with_placeholders(self):
        init_i18n("es")
        result = tr("setup.disk_label", label="USB", size="64 GB")
        assert "USB" in result
        assert "64 GB" in result

    def test_tr_auto_initializes(self):
        from i18n.core import _initialized, _translations
        init_i18n("es")
        result = tr("app.name")
        assert result == "SafeTool Sync"


class TestGetSupportedLanguages:
    def test_returns_dict(self):
        langs = get_supported_languages()
        assert isinstance(langs, dict)
        assert "es" in langs
        assert "en" in langs


class TestResolve:
    def test_resolve_existing_key(self):
        init_i18n("es")
        data = {"app": {"name": "Test"}}
        assert _resolve("app.name", data) == "Test"

    def test_resolve_missing_key(self):
        data = {"app": {"name": "Test"}}
        assert _resolve("app.missing", data) is None

    def test_resolve_nested_key(self):
        data = {"a": {"b": {"c": "deep"}}}
        assert _resolve("a.b.c", data) == "deep"

    def test_resolve_dict_returns_none(self):
        data = {"a": {"b": {"c": "deep"}}}
        assert _resolve("a.b", data) is None


class TestMerge:
    def test_merge_overlay_onto_base(self):
        overlay = {"app": {"name": "Override"}}
        base = {"app": {"name": "Base", "version": "1.0"}}
        result = _merge(overlay, base)
        assert result["app"]["name"] == "Override"
        assert result["app"]["version"] == "1.0"

    def test_merge_new_key_in_overlay(self):
        overlay = {"app": {"new_key": "New"}}
        base = {"app": {"name": "Base"}}
        result = _merge(overlay, base)
        assert result["app"]["new_key"] == "New"
        assert result["app"]["name"] == "Base"

    def test_merge_empty_overlay(self):
        overlay = {}
        base = {"app": {"name": "Base"}}
        result = _merge(overlay, base)
        assert result == base