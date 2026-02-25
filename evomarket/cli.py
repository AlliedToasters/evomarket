"""Command-line interface for EvoMarket simulation."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

from evomarket.agents.base import AgentFactory
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
        choices=["heuristic", "llm", "mixed"],
        default=None,
        help="Agent type (default: auto-detect from config)",
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
        choices=["heuristic", "llm", "mixed"],
        default=None,
        help="Agent type (default: auto-detect from config)",
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


def _has_llm_keys(agent_mix: dict[str, int]) -> bool:
    """Return True if agent_mix contains any llm or llm:* keys."""
    return any(k == "llm" or k.startswith("llm:") for k in agent_mix)


def _detect_agent_mode(args: argparse.Namespace, agent_mix: dict[str, int]) -> str:
    """Determine the effective agent mode from CLI flags and config."""
    if args.agent_type is not None:
        return args.agent_type
    if _has_llm_keys(agent_mix):
        return "mixed"
    return "heuristic"


def _build_factory(
    mode: str,
    config: SimulationConfig,
    args: argparse.Namespace,
) -> AgentFactory:
    """Build the appropriate AgentFactory for the given mode."""
    from evomarket.agents.heuristic_agent import HeuristicAgentFactory

    if mode == "heuristic":
        return HeuristicAgentFactory(config)

    from evomarket.agents.llm_agent import LLMAgentFactory, MixedAgentFactory
    from evomarket.agents.llm_backend import LLMBackend

    if mode == "llm":
        # Legacy single-backend mode
        backend = LLMBackend(
            model=args.model,
            base_url=args.llm_url,
            api_key=args.llm_api_key,
        )
        return LLMAgentFactory(backend, config)

    # Mixed mode — build backends from config + CLI key
    api_key = args.llm_api_key
    backends: dict[str, LLMBackend] = {}

    # Named backends from config's llm_backends
    for name, spec in config.llm_backends.items():
        backends[name] = LLMBackend(
            model=spec["model"],
            base_url=spec.get("base_url", "http://localhost:11434/v1"),
            api_key=api_key,
        )

    # Bare "llm" key support — use CLI --model / --llm-url
    if "llm" in config.agent_mix and "" not in backends:
        backends[""] = LLMBackend(
            model=args.model,
            base_url=args.llm_url,
            api_key=api_key,
        )

    return MixedAgentFactory(config, llm_backends=backends)


def _cmd_run(args: argparse.Namespace) -> None:
    """Execute the 'run' subcommand."""
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

    # For legacy --agent-type llm, override agent_mix to all-LLM
    if args.agent_type == "llm":
        pop = config_overrides.get("population_size", config.population_size)
        config_overrides["agent_mix"] = {"llm": pop}

    fast_mode = args.fast
    if fast_mode:
        config_overrides["checkpoint_interval"] = 0
        config_overrides["verbose_logging"] = False

    config = SimulationConfig(**config_overrides)

    mode = _detect_agent_mode(args, config.agent_mix)
    has_llm = mode in ("llm", "mixed")

    output_dir = Path(args.output_dir) if not fast_mode else None

    factory = _build_factory(mode, config, args)

    if mode == "llm":
        print(
            f"Running LLM episode: model={args.model}, url={args.llm_url}, "
            f"seed={config.seed}, ticks={config.ticks_per_episode}, "
            f"agents={config.population_size}"
        )
    elif mode == "mixed":
        llm_keys = [k for k in config.agent_mix if k == "llm" or k.startswith("llm:")]
        print(
            f"Running mixed episode: llm_types={llm_keys}, "
            f"seed={config.seed}, ticks={config.ticks_per_episode}, "
            f"agents={config.population_size}"
        )
    else:
        print(
            f"Running episode: seed={config.seed}, ticks={config.ticks_per_episode}, "
            f"agents={config.population_size}"
        )

    # Set up early stopping
    stop_condition = None
    if args.max_idle_ticks > 0:
        from evomarket.simulation.runner import idle_streak_stop

        stop_condition = idle_streak_stop(args.max_idle_ticks)

    tick_callback = None
    if has_llm:
        tracker = _LLMTickTracker()
        tick_callback = tracker.tick_callback

    start = time.time()
    result = run_episode(
        config,
        factory,
        output_dir=output_dir,
        enable_logging=not fast_mode,
        tick_callback=tick_callback,
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


class _LLMTickTracker:
    """Collects per-model stats from LLMAgent log records between ticks."""

    def __init__(self) -> None:
        import re

        self._pattern = re.compile(r"^\[([^\]]+)\] (agent_\w+): (.+?) \((\d+\.\d+)s\)")
        self._records: list[
            tuple[str, str, str, float]
        ] = []  # model, agent, outcome, secs

        # Install a log handler on the llm_agent logger to capture records
        self._handler = logging.Handler()
        self._handler.emit = self._capture  # type: ignore[assignment]
        self._handler.setLevel(logging.DEBUG)
        llm_logger = logging.getLogger("evomarket.agents.llm_agent")
        llm_logger.addHandler(self._handler)
        llm_logger.setLevel(logging.DEBUG)

    def _capture(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        import re

        msg = record.getMessage()
        m = re.match(r"^\[([^\]]+)\] (agent_\w+): (.+?) \((\d+\.\d+)s\)", msg)
        if m:
            model, agent_id, outcome, secs = (
                m.group(1),
                m.group(2),
                m.group(3),
                float(m.group(4)),
            )
            self._records.append((model, agent_id, outcome, secs))

    def tick_callback(self, tick_num: int, wall_time: float) -> None:
        records = self._records
        self._records = []
        print(f"  tick {tick_num}: {wall_time:.2f}s")
        if not records:
            return
        # Aggregate per model
        from collections import defaultdict

        stats: dict[str, dict] = defaultdict(
            lambda: {"ok": 0, "empty": 0, "parse_fail": 0, "total_s": 0.0, "calls": 0}
        )
        for model, _agent_id, outcome, secs in records:
            s = stats[model]
            s["calls"] += 1
            s["total_s"] += secs
            if "empty response" in outcome:
                s["empty"] += 1
            elif "parse failed" in outcome:
                s["parse_fail"] += 1
            else:
                s["ok"] += 1
        for model, s in sorted(stats.items()):
            avg = s["total_s"] / max(s["calls"], 1)
            parts = [f"{s['ok']}ok"]
            if s["empty"]:
                parts.append(f"{s['empty']}empty")
            if s["parse_fail"]:
                parts.append(f"{s['parse_fail']}parse_fail")
            print(f"    {model}: {'/'.join(parts)}  avg={avg:.1f}s")


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
        # Auto-detect config from checkpoint's output directory
        auto_config_path = checkpoint_path.parent.parent / "config.json"
        if auto_config_path.exists():
            print(f"Auto-loaded config from {auto_config_path}")
            with open(auto_config_path) as f:
                config = SimulationConfig.from_json(json.load(f))
        else:
            config = SimulationConfig()

    output_dir = Path(args.output_dir) if args.output_dir else None

    mode = _detect_agent_mode(args, config.agent_mix)
    factory = _build_factory(mode, config, args)

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
