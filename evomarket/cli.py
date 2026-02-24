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
        default="results",
        help="Output directory (default: results)",
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

    # Apply overrides
    if args.seed is not None:
        config = SimulationConfig(**{**config.to_json(), "seed": args.seed})
    if args.ticks is not None:
        config = SimulationConfig(
            **{**config.to_json(), "ticks_per_episode": args.ticks}
        )

    fast_mode = args.fast
    if fast_mode:
        config = SimulationConfig(
            **{**config.to_json(), "checkpoint_interval": 0, "verbose_logging": False}
        )

    output_dir = Path(args.output_dir) if not fast_mode else None
    factory = HeuristicAgentFactory(config)

    print(
        f"Running episode: seed={config.seed}, ticks={config.ticks_per_episode}, "
        f"agents={config.population_size}"
    )

    start = time.time()
    result = run_episode(
        config,
        factory,
        output_dir=output_dir,
        enable_logging=not fast_mode,
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
    from evomarket.agents.heuristic_agent import HeuristicAgentFactory
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
