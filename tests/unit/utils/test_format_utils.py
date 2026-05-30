# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for utils.format_utils."""
from __future__ import annotations

import pytest

from utils.format_utils import format_size, format_number, format_file_count, format_duration, format_speed, format_percentage


class TestFormatSize:
    def test_bytes(self):
        assert format_size(500) == "500 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_terabytes(self):
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_zero(self):
        assert format_size(0) == "0 B"

    def test_none(self):
        assert format_size(None) == "—"

    def test_negative(self):
        assert format_size(-1) == "—"


class TestFormatNumber:
    def test_small_number(self):
        assert format_number(42) == "42"

    def test_thousands(self):
        assert format_number(1500) == "1.5K"

    def test_millions(self):
        assert format_number(2500000) == "2.5M"

    def test_none(self):
        assert format_number(None) == "—"


class TestFormatFileCount:
    def test_count(self):
        assert format_file_count(1000) == "1,000"

    def test_none(self):
        assert format_file_count(None) == "—"


class TestFormatDuration:
    def test_seconds(self):
        assert format_duration(30) == "30s"

    def test_minutes_seconds(self):
        assert format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        assert format_duration(3665) == "1h 1m 5s"

    def test_none(self):
        assert format_duration(None) == "—"

    def test_negative(self):
        assert format_duration(-5) == "—"

    def test_zero(self):
        assert format_duration(0) == "0s"


class TestFormatSpeed:
    def test_bytes_per_second(self):
        assert format_speed(500) == "500 B/s"

    def test_kilobytes_per_second(self):
        assert format_speed(1024) == "1.0 KB/s"

    def test_megabytes_per_second(self):
        assert format_speed(1024 * 1024) == "1.0 MB/s"

    def test_none(self):
        assert format_speed(None) == "—"

    def test_zero(self):
        assert format_speed(0) == "—"


class TestFormatPercentage:
    def test_percentage(self):
        assert format_percentage(75.0, 100.0) == "75.0%"

    def test_standalone(self):
        assert format_percentage(42.5) == "42.5%"

    def test_none(self):
        assert format_percentage(None) == "—"