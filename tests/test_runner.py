"""Tests for SimulationRunner."""

from pathlib import Path


from evomarket.agents.heuristic_agent import HeuristicAgentFactory
from evomarket.agents.random_agent import RandomAgentFactory
from evomarket.simulation.config import SimulationConfig
from evomarket.simulation.runner import run_episode, resume_from_checkpoint


def _small_config(**overrides) -> SimulationConfig:
    """Create a small, fast config for testing."""
    defaults = dict(
        seed=42,
        num_nodes=5,
        num_commodity_types=2,
        population_size=5,
        total_credit_supply=5000.0,
        starting_credits=30.0,
        ticks_per_episode=20,
        checkpoint_interval=10,
        agent_mix={"harvester": 2, "trader": 2, "explorer": 1},
    )
    defaults.update(overrides)
    return SimulationConfig(**defaults)


class TestFullEpisode:
    def test_episode_completes(self) -> None:
        config = _small_config()
        factory = HeuristicAgentFactory(config)
        result = run_episode(config, factory, enable_logging=False)

        assert result.episode_metrics.ticks_executed == config.ticks_per_episode
        assert len(result.tick_metrics) == config.ticks_per_episode
        assert len(result.agent_summaries) > 0

    def test_no_invariant_violations(self) -> None:
        config = _small_config(verify_invariant_every_phase=True)
        factory = HeuristicAgentFactory(config)
        # Should complete without AssertionError
        result = run_episode(config, factory, enable_logging=False)
        assert result.episode_metrics.ticks_executed > 0

    def test_agent_summaries_populated(self) -> None:
        config = _small_config()
        factory = HeuristicAgentFactory(config)
        result = run_episode(config, factory, enable_logging=False)

        for summary in result.agent_summaries:
            assert summary.agent_id.startswith("agent_")
            assert summary.lifetime >= 0
            assert summary.final_credits >= 0

    def test_episode_metrics_valid(self) -> None:
        config = _small_config()
        factory = HeuristicAgentFactory(config)
        result = run_episode(config, factory, enable_logging=False)

        metrics = result.episode_metrics
        assert metrics.ticks_executed > 0
        assert metrics.mean_lifetime > 0
        assert metrics.max_lifetime > 0
        assert metrics.final_treasury >= 0


class TestEarlyTermination:
    def test_high_tax_causes_deaths(self) -> None:
        # High tax should cause deaths even if respawning continues
        config = _small_config(
            survival_tax=50.0,
            starting_credits=10.0,
            total_credit_supply=5000.0,
            ticks_per_episode=50,
        )
        factory = HeuristicAgentFactory(config)
        result = run_episode(config, factory, enable_logging=False)
        assert result.episode_metrics.total_deaths > 0


class TestDeterminism:
    def test_same_seed_same_result(self) -> None:
        config = _small_config(ticks_per_episode=30)
        factory1 = HeuristicAgentFactory(config)
        factory2 = HeuristicAgentFactory(config)

        result1 = run_episode(config, factory1, enable_logging=False)
        result2 = run_episode(config, factory2, enable_logging=False)

        assert (
            result1.episode_metrics.ticks_executed
            == result2.episode_metrics.ticks_executed
        )
        assert len(result1.tick_metrics) == len(result2.tick_metrics)

        for m1, m2 in zip(result1.tick_metrics, result2.tick_metrics):
            assert m1.agents_alive == m2.agents_alive
            assert m1.agents_died == m2.agents_died
            assert m1.total_trade_volume == m2.total_trade_volume


class TestCheckpointing:
    def test_checkpoint_created(self, tmp_path: Path) -> None:
        config = _small_config(checkpoint_interval=5, ticks_per_episode=10)
        factory = HeuristicAgentFactory(config)
        run_episode(config, factory, output_dir=tmp_path, enable_logging=False)

        checkpoint_dir = tmp_path / "checkpoints"
        checkpoints = list(checkpoint_dir.glob("checkpoint_tick_*.json"))
        assert len(checkpoints) >= 1

    def test_output_files_created(self, tmp_path: Path) -> None:
        config = _small_config(ticks_per_episode=5, checkpoint_interval=0)
        factory = HeuristicAgentFactory(config)
        run_episode(config, factory, output_dir=tmp_path, enable_logging=False)

        assert (tmp_path / "config.json").exists()
        assert (tmp_path / "result.json").exists()

    def test_resume_from_checkpoint(self, tmp_path: Path) -> None:
        config = _small_config(checkpoint_interval=5, ticks_per_episode=15)
        factory = HeuristicAgentFactory(config)
        run_episode(config, factory, output_dir=tmp_path, enable_logging=False)

        # Find a checkpoint
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoints = sorted(checkpoint_dir.glob("checkpoint_tick_*.json"))
        assert len(checkpoints) > 0

        # Resume from the first checkpoint
        resume_dir = tmp_path / "resumed"
        factory2 = HeuristicAgentFactory(config)
        result = resume_from_checkpoint(
            checkpoints[0],
            config,
            factory2,
            output_dir=resume_dir,
            enable_logging=False,
        )
        assert result.episode_metrics.ticks_executed > 0


class TestWithRandomAgents:
    def test_random_agents_complete(self) -> None:
        config = SimulationConfig(
            seed=42,
            num_nodes=5,
            num_commodity_types=2,
            population_size=5,
            total_credit_supply=5000.0,
            starting_credits=30.0,
            ticks_per_episode=10,
            checkpoint_interval=0,
            agent_mix={"random": 5},
        )
        factory = RandomAgentFactory(base_seed=42)
        factory.set_config(config)
        result = run_episode(config, factory, enable_logging=False)
        assert result.episode_metrics.ticks_executed > 0


class TestWithLogging:
    def test_sqlite_logging(self, tmp_path: Path) -> None:
        config = _small_config(ticks_per_episode=5, checkpoint_interval=0)
        factory = HeuristicAgentFactory(config)
        run_episode(config, factory, output_dir=tmp_path, enable_logging=True)

        db_path = tmp_path / "episode.sqlite"
        assert db_path.exists()

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        tick_count = conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
        assert tick_count == 5
        action_count = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        assert action_count > 0
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM agent_snapshots"
        ).fetchone()[0]
        assert snapshot_count > 0
        conn.close()
