"""Tests for CLI."""

import json
from pathlib import Path

import pytest

from evomarket.cli import main, _create_parser


class TestArgumentParsing:
    def test_run_defaults(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["run"])
        assert args.command == "run"
        assert args.config is None
        assert args.seed is None
        assert args.output_dir == "runs/results"
        assert args.fast is False

    def test_run_with_flags(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["run", "--seed", "123", "--fast", "--ticks", "50"])
        assert args.seed == 123
        assert args.fast is True
        assert args.ticks == 50

    def test_analyze_arg(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["analyze", "results/episode.sqlite"])
        assert args.command == "analyze"
        assert args.db_path == "results/episode.sqlite"

    def test_resume_arg(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["resume", "checkpoint.json"])
        assert args.command == "resume"
        assert args.checkpoint == "checkpoint.json"

    def test_no_command_exits(self) -> None:
        """With no command, should print help and exit 0."""
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 0


class TestAgentModeDetection:
    def test_default_heuristic(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["run"])
        assert args.agent_type is None  # auto-detect

    def test_explicit_mixed(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["run", "--agent-type", "mixed"])
        assert args.agent_type == "mixed"

    def test_explicit_llm(self) -> None:
        parser = _create_parser()
        args = parser.parse_args(["run", "--agent-type", "llm"])
        assert args.agent_type == "llm"


class TestRunCommand:
    def test_fast_mode(self, tmp_path: Path) -> None:
        """Fast mode should run without creating output files."""
        main(["run", "--fast", "--seed", "42", "--ticks", "5"])
        # No output dir to check in fast mode

    def test_run_with_output(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "test_run"
        main(["run", "--output-dir", str(output_dir), "--ticks", "5", "--seed", "42"])
        assert (output_dir / "config.json").exists()
        assert (output_dir / "result.json").exists()
        assert (output_dir / "episode.sqlite").exists()

    def test_run_with_config_file(self, tmp_path: Path) -> None:
        from evomarket.simulation.config import SimulationConfig

        config = SimulationConfig(
            seed=99,
            population_size=5,
            num_nodes=5,
            num_commodity_types=2,
            total_credit_supply=5000.0,
            starting_credits=30.0,
            ticks_per_episode=5,
            checkpoint_interval=0,
            agent_mix={"harvester": 3, "trader": 2},
        )
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(config.to_json(), f)

        output_dir = tmp_path / "output"
        main(["run", "--config", str(config_path), "--output-dir", str(output_dir)])

        result = json.loads((output_dir / "result.json").read_text())
        assert result["ticks_executed"] == 5
