# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Shared pytest fixtures for E2E tests."""
from __future__ import annotations

import pytest
from pathlib import Path

from tests.fixtures.scenario_builder import (
    ScenarioName,
    ScenarioResult,
    build_mixed_scenario,
    build_scenario,
)


@pytest.fixture
def scenario_dir(tmp_path: Path):
    """Factory fixture — returns a callable that builds any scenario."""
    def _build(scenario: ScenarioName) -> ScenarioResult:
        scenario_path = tmp_path / scenario.value
        scenario_path.mkdir(parents=True, exist_ok=True)
        return build_scenario(scenario_path, scenario)
    return _build


@pytest.fixture
def mixed_scenario(tmp_path: Path) -> ScenarioResult:
    """Pre-built mixed scenario with all file state types."""
    return build_mixed_scenario(tmp_path / "mixed")


@pytest.fixture
def identical_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "identical", ScenarioName.IDENTICAL)


@pytest.fixture
def source_only_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "source_only", ScenarioName.SOURCE_ONLY)


@pytest.fixture
def dest_only_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "dest_only", ScenarioName.DEST_ONLY)


@pytest.fixture
def conflict_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "conflict", ScenarioName.CONFLICT_BOTH_CHANGED)


@pytest.fixture
def conflict_stealth_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "stealth", ScenarioName.CONFLICT_SAME_SIZE_DIFF_CONTENT)


@pytest.fixture
def conflict_bidir_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "bidir", ScenarioName.CONFLICT_BIDIRECTIONAL)


@pytest.fixture
def conflict_batch_ext_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "batch_ext", ScenarioName.CONFLICT_BATCH_BY_EXT)


@pytest.fixture
def conflict_batch_folder_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "batch_folder", ScenarioName.CONFLICT_BATCH_BY_FOLDER)


@pytest.fixture
def rename_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "rename", ScenarioName.RENAMED_FILE)


@pytest.fixture
def rename_cross_dir_scenario(tmp_path: Path) -> ScenarioResult:
    return build_scenario(tmp_path / "rename_cross", ScenarioName.RENAMED_ACROSS_DIRS)
