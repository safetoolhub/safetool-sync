# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""E2E tests — scenario builder self-validation and CLI smoke test."""
from __future__ import annotations

import subprocess
import sys

import pytest
from pathlib import Path

from tests.fixtures.scenario_builder import (
    ScenarioName,
    ScenarioResult,
    build_mixed_scenario,
    build_scenario,
    list_scenarios,
)


class TestScenarioBuilder:
    def test_all_scenarios_build_without_error(self, tmp_path: Path):
        for scenario in ScenarioName:
            if scenario == ScenarioName.MIXED_ALL:
                continue
            result = build_scenario(tmp_path / scenario.value, scenario)
            assert result.source_root.exists()
            assert result.dest_root.exists()
            assert len(result.expectations) > 0

    def test_mixed_scenario_builds(self, tmp_path: Path):
        result = build_mixed_scenario(tmp_path / "mixed")
        assert result.source_root.exists()
        assert result.dest_root.exists()
        assert len(result.expectations) > 20

    def test_list_scenarios_returns_all(self):
        names = list_scenarios()
        assert len(names) == len(ScenarioName)
        assert "identical" in names
        assert "mixed_all" in names
        assert "conflict_both_changed" in names

    @pytest.mark.parametrize("scenario", [s for s in ScenarioName if s != ScenarioName.MIXED_ALL])
    def test_each_scenario_has_expectations(self, tmp_path: Path, scenario: ScenarioName):
        result = build_scenario(tmp_path / scenario.value, scenario)
        assert len(result.expectations) > 0

    @pytest.mark.parametrize("scenario", [s for s in ScenarioName if s != ScenarioName.MIXED_ALL])
    def test_each_scenario_files_exist(self, tmp_path: Path, scenario: ScenarioName):
        result = build_scenario(tmp_path / scenario.value, scenario)

        for exp in result.expectations:
            src_path = result.source_root / exp.rel_path
            dst_path = result.dest_root / exp.rel_path

            if exp.expected_diff_type == "source_only":
                assert src_path.exists(), f"Expected source file: {exp.rel_path}"
            elif exp.expected_diff_type == "dest_only":
                assert dst_path.exists(), f"Expected dest file: {exp.rel_path}"
            elif exp.expected_diff_type in ("identical", "modified"):
                assert src_path.exists(), f"Expected source file: {exp.rel_path}"
                assert dst_path.exists(), f"Expected dest file: {exp.rel_path}"

    def test_no_path_collisions_in_mixed(self, tmp_path: Path):
        result = build_mixed_scenario(tmp_path / "mixed")
        paths = [exp.rel_path for exp in result.expectations]
        assert len(paths) == len(set(paths)), "Duplicate rel_paths in mixed scenario"

    def test_cli_list(self):
        proc = subprocess.run(
            [sys.executable, "-m", "tests.fixtures.scenario_builder", "--list"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert proc.returncode == 0
        assert "identical" in proc.stdout
        assert "mixed_all" in proc.stdout

    def test_cli_build_scenario(self, tmp_path: Path):
        output_dir = tmp_path / "cli_output"
        proc = subprocess.run(
            [
                sys.executable, "-m", "tests.fixtures.scenario_builder",
                "--scenario", "source_only",
                "--output", str(output_dir),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert proc.returncode == 0
        assert (output_dir / "source").exists()
        assert (output_dir / "dest").exists()

    def test_cli_build_mixed(self, tmp_path: Path):
        output_dir = tmp_path / "cli_mixed"
        proc = subprocess.run(
            [
                sys.executable, "-m", "tests.fixtures.scenario_builder",
                "--scenario", "mixed_all",
                "--output", str(output_dir),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert proc.returncode == 0
        assert (output_dir / "source").exists()
        assert (output_dir / "dest").exists()
