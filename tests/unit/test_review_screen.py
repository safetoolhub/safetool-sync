# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
import pytest

from sync_app.screens.review_screen import ReviewScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_export_empty_folders(qapp, tmp_path):
    screen = ReviewScreen()
    screen.set_base_paths(str(tmp_path / "source"), str(tmp_path / "dest"))
    screen.set_entries(
        [],
        source_empty_dirs=["empty_src_dir"],
        dest_empty_dirs=["empty_dst_dir"],
    )

    export_file = tmp_path / "empty_folders.txt"

    with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(export_file), "txt")), \
         patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
        screen._on_export_empty_folders()
        mock_info.assert_called_once()

    assert export_file.exists()
    content = export_file.read_text(encoding="utf-8")
    assert "empty_src_dir" in content
    assert "empty_dst_dir" in content
    assert str(tmp_path / "source") in content
    assert str(tmp_path / "dest") in content
