"""Shared CLI helpers for benchmark scripts."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from mpot.benchmarks.config import ExperimentConfig, validate_config


def add_config_override_args(parser: ArgumentParser) -> None:
    """Add optional config overrides used by serial, MPI, and sweep scripts."""

    parser.add_argument("--experiment-name", default=None, help="Override config.experiment_name.")
    parser.add_argument("--output-dir", default=None, help="Override config.output_dir.")
    parser.add_argument("--total-tasks", type=int, default=None, help="Override total number of tasks N.")
    parser.add_argument("--base-seed", type=int, default=None, help="Override deterministic base seed.")
    parser.add_argument("--traj-len", type=int, default=None, help="Override trajectory length.")
    parser.add_argument("--num-particles", type=int, default=None, help="Override particles per local task.")
    parser.add_argument("--num-probe", type=int, default=None, help="Override probe count per direction.")
    parser.add_argument("--max-outer-iters", type=int, default=None, help="Override max MPOT outer iterations.")
    parser.add_argument("--max-inner-iters", type=int, default=None, help="Override Sinkhorn inner max iterations.")


def apply_config_overrides(config: ExperimentConfig, args: Namespace) -> ExperimentConfig:
    """Apply CLI overrides in-place and return the config.

    The config is modified before a run starts. The effective config is always
    written to `results/<run_id>/config.json`, so report numbers can be traced
    back to the exact command settings.
    """

    if getattr(args, "experiment_name", None) is not None:
        config.experiment_name = args.experiment_name
    if getattr(args, "output_dir", None) is not None:
        config.output_dir = args.output_dir
    if getattr(args, "total_tasks", None) is not None:
        config.total_tasks = args.total_tasks
    if getattr(args, "base_seed", None) is not None:
        config.base_seed = args.base_seed
    if getattr(args, "traj_len", None) is not None:
        config.problem.traj_len = args.traj_len
    if getattr(args, "num_particles", None) is not None:
        config.optimizer.num_particles = args.num_particles
    if getattr(args, "num_probe", None) is not None:
        config.optimizer.num_probe = args.num_probe
    if getattr(args, "max_outer_iters", None) is not None:
        config.optimizer.max_outer_iters = args.max_outer_iters
    if getattr(args, "max_inner_iters", None) is not None:
        config.optimizer.max_inner_iters = args.max_inner_iters
    validate_config(config)
    return config


def parse_int_list(value: str) -> list[int]:
    """Parse comma-separated positive integers."""

    out = []
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        number = int(item)
        if number <= 0:
            raise ValueError("List values must be positive integers.")
        out.append(number)
    if not out:
        raise ValueError("At least one integer is required.")
    return out

