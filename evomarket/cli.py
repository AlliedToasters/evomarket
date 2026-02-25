"""Command-line interface for EvoMarket simulation."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from evomarket.core.types import to_display_credits
from evomarket.simulation.config import SimulationConfig


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evomarket",
        description="EvoMarket simulation runner",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run a simulation episode")
    run_parser.add_argument(
        "--config", type=str, default=None, help="Path to JSON config file"
    )
    run_parser.add_argument(
        "--seed", type=int, default=None, help="Random seed override"
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default="runs/results",
        help="Output directory (default: runs/results)",
    )
    run_parser.add_argument(
        "--fast",
        action="store_true",
        help="Hyperfast mode: disable logging and checkpoints",
    )
    run_parser.add_argument(
        "--ticks",
        type=int,
        default=None,
        help="Override ticks_per_episode",
    )
    run_parser.add_argument(
        "--agent-type",
        type=str,
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Agent type (default: heuristic)",
    )
    run_parser.add_argument(
        "--model",
        type=str,
        default="qwen3:8b",
        help="LLM model name (default: qwen3:8b)",
    )
    run_parser.add_argument(
        "--llm-url",
        type=str,
        default="http://localhost:11434/v1",
        help="LLM API base URL (default: http://localhost:11434/v1)",
    )
    run_parser.add_argument(
        "--llm-api-key",
        type=str,
        default="",
        help="API key for remote LLM providers",
    )
    run_parser.add_argument(
        "--population",
        type=int,
        default=None,
        help="Override population_size",
    )
    run_parser.add_argument(
        "--max-idle-ticks",
        type=int,
        default=0,
        help="Early stop after N ticks with no productive actions (0=disabled)",
    )

    # analyze
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze a completed episode"
    )
    analyze_parser.add_argument(
        "db_path", type=str, help="Path to episode SQLite database"
    )

    # resume
    resume_parser = subparsers.add_parser("resume", help="Resume from a checkpoint")
    resume_parser.add_argument(
        "checkpoint", type=str, help="Path to checkpoint JSON file"
    )
    resume_parser.add_argument(
        "--config", type=str, default=None, help="Path to JSON config file"
    )
    resume_parser.add_argument(
        "--output-dir", type=str, default=None, help="Output directory"
    )
    resume_parser.add_argument(
        "--agent-type",
        type=str,
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Agent type (default: heuristic)",
    )
    resume_parser.add_argument(
        "--model", type=str, default="qwen3:8b", help="LLM model name"
    )
    resume_parser.add_argument(
        "--llm-url",
        type=str,
        default="http://localhost:11434/v1",
        help="LLM API base URL",
    )
    resume_parser.add_argument(
        "--llm-api-key", type=str, default="", help="API key for remote LLM providers"
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> None:
    """Execute the 'run' subcommand."""
    from evomarket.agents.heuristic_agent import HeuristicAgentFactory
    from evomarket.simulation.runner import run_episode

    # Load or create config
    if args.config is not None:
        with open(args.config) as f:
            config = SimulationConfig.from_json(json.load(f))
    else:
        config = SimulationConfig()

    config_overrides: dict = {**config.to_json()}

    # Apply overrides
    if args.seed is not None:
        config_overrides["seed"] = args.seed
    if args.ticks is not None:
        config_overrides["ticks_per_episode"] = args.ticks
    if args.population is not None:
        config_overrides["population_size"] = args.population

    is_llm = args.agent_type == "llm"

    # For LLM mode, build an LLM-compatible agent_mix
    if is_llm:
        pop = config_overrides.get("population_size", config.population_size)
        config_overrides["agent_mix"] = {"llm": pop}

    fast_mode = args.fast
    if fast_mode:
        config_overrides["checkpoint_interval"] = 0
        config_overrides["verbose_logging"] = False

    config = SimulationConfig(**config_overrides)

    output_dir = Path(args.output_dir) if not fast_mode else None

    # Create the appropriate agent factory
    if is_llm:
        from evomarket.agents.llm_agent import LLMAgentFactory
        from evomarket.agents.llm_backend import LLMBackend

        backend = LLMBackend(
            model=args.model,
            base_url=args.llm_url,
            api_key=args.llm_api_key,
        )
        factory = LLMAgentFactory(backend, config)
        print(
            f"Running LLM episode: model={args.model}, url={args.llm_url}, "
            f"seed={config.seed}, ticks={config.ticks_per_episode}, "
            f"agents={config.population_size}"
        )
    else:
        factory = HeuristicAgentFactory(config)
        print(
            f"Running episode: seed={config.seed}, ticks={config.ticks_per_episode}, "
            f"agents={config.population_size}"
        )

    # Set up early stopping
    stop_condition = None
    if args.max_idle_ticks > 0:
        from evomarket.simulation.runner import idle_streak_stop

        stop_condition = idle_streak_stop(args.max_idle_ticks)

    start = time.time()
    result = run_episode(
        config,
        factory,
        output_dir=output_dir,
        enable_logging=not fast_mode,
        tick_callback=_llm_tick_callback if is_llm else None,
        stop_condition=stop_condition,
    )
    elapsed = time.time() - start

    tps = result.episode_metrics.ticks_executed / max(elapsed, 0.001)

    print(f"\nEpisode complete in {elapsed:.2f}s ({tps:.0f} ticks/sec)")
    print(f"  Ticks: {result.episode_metrics.ticks_executed}")
    print(f"  Final agents alive: {result.episode_metrics.final_agents_alive}")
    print(f"  Total deaths: {result.episode_metrics.total_deaths}")
    print(f"  Total trades: {result.episode_metrics.total_trades}")
    print(f"  Final Gini: {result.episode_metrics.final_gini:.3f}")
    print(
        f"  Final treasury: {to_display_credits(result.episode_metrics.final_treasury):.1f}"
    )
    print(f"  Mean lifetime: {result.episode_metrics.mean_lifetime:.1f}")
    print(
        f"  Mean net worth: {to_display_credits(result.episode_metrics.mean_net_worth):.1f}"
    )

    if output_dir is not None:
        print(f"\nResults saved to {output_dir}/")


def _llm_tick_callback(tick_num: int, wall_time: float) -> None:
    """Print per-tick wall time for LLM mode."""
    print(f"  tick {tick_num}: {wall_time:.2f}s")


def _cmd_analyze(args: argparse.Namespace) -> None:
    """Execute the 'analyze' subcommand."""
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))

    tick_count = conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    action_count = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    trade_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    death_count = conn.execute("SELECT COUNT(*) FROM deaths").fetchone()[0]
    message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    # Agent statistics
    unique_agents = conn.execute(
        "SELECT COUNT(DISTINCT agent_id) FROM agent_snapshots"
    ).fetchone()[0]

    # Final tick metrics
    final_metrics_row = conn.execute(
        "SELECT metrics_json FROM ticks ORDER BY tick_number DESC LIMIT 1"
    ).fetchone()
    final_metrics = json.loads(final_metrics_row[0]) if final_metrics_row else {}

    print(f"Episode Analysis: {db_path}")
    print(f"  Total ticks: {tick_count}")
    print(f"  Total actions: {action_count}")
    print(f"  Total trades: {trade_count}")
    print(f"  Total deaths: {death_count}")
    print(f"  Total messages: {message_count}")
    print(f"  Unique agents: {unique_agents}")
    if final_metrics:
        print(f"  Final agents alive: {final_metrics.get('agents_alive', '?')}")
        print(f"  Final Gini: {final_metrics.get('agent_credit_gini', '?'):.3f}")

    conn.close()


def _cmd_resume(args: argparse.Namespace) -> None:
    """Execute the 'resume' subcommand."""
    from evomarket.simulation.runner import resume_from_checkpoint

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.exists():
        print(f"Error: checkpoint not found: {checkpoint_path}", file=sys.stderr)
        sys.exit(1)

    if args.config is not None:
        with open(args.config) as f:
            config = SimulationConfig.from_json(json.load(f))
    else:
        config = SimulationConfig()

    output_dir = Path(args.output_dir) if args.output_dir else None

    is_llm = args.agent_type == "llm"
    if is_llm:
        from evomarket.agents.llm_agent import LLMAgentFactory
        from evomarket.agents.llm_backend import LLMBackend

        backend = LLMBackend(
            model=args.model,
            base_url=args.llm_url,
            api_key=args.llm_api_key,
        )
        factory = LLMAgentFactory(backend, config)
    else:
        from evomarket.agents.heuristic_agent import HeuristicAgentFactory

        factory = HeuristicAgentFactory(config)

    print(f"Resuming from {checkpoint_path}...")
    start = time.time()
    result = resume_from_checkpoint(
        checkpoint_path, config, factory, output_dir=output_dir
    )
    elapsed = time.time() - start

    print(f"\nResume complete in {elapsed:.2f}s")
    print(f"  Ticks executed: {result.episode_metrics.ticks_executed}")
    print(f"  Final agents alive: {result.episode_metrics.final_agents_alive}")
    print(f"  Total deaths: {result.episode_metrics.total_deaths}")


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    parser = _create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "analyze":
        _cmd_analyze(args)
    elif args.command == "resume":
        _cmd_resume(args)
    else:
        parser.print_help()
        sys.exit(1)
