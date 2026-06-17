#!/usr/bin/env python3
"""Run the serial baseline for the local-first MPOT benchmark."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.artifacts import make_run_dir, write_run_artifacts
from mpot.benchmarks.cli import add_config_override_args, apply_config_overrides
from mpot.benchmarks.config import load_config
from mpot.benchmarks.local_runner import run_tasks_serial
from mpot.benchmarks.mpi_scheduler import build_tasks
from mpot.benchmarks.plots import plot_best_path, plot_cost_by_task
from mpot.benchmarks.problem_2d import PlanningProblem2D, summarize_problem


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to JSON experiment config.")
    parser.add_argument("--run-id", default=None, help="Optional run id for output directory.")
    parser.add_argument("--no-plots", action="store_true", help="Skip PNG generation.")
    add_config_override_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = apply_config_overrides(load_config(args.config), args)
    run_id = args.run_id or config.make_run_id("serial")
    tasks = build_tasks(config.total_tasks, config.base_seed)
    results, best, total_time_s = run_tasks_serial(config, tasks)

    run_dir = make_run_dir(config, run_id)
    problem = PlanningProblem2D.from_config(config)
    summary = write_run_artifacts(
        run_dir=run_dir,
        run_id=run_id,
        mode="serial",
        config=config,
        best=best,
        results=results,
        problem_summary=summarize_problem(problem),
        total_time_s=total_time_s,
    )

    if not args.no_plots:
        for plotter in (plot_best_path, plot_cost_by_task):
            try:
                plotter(run_dir)
            except RuntimeError as exc:
                print(f"plot skipped: {exc}")

    print(f"serial run written to {run_dir.resolve()}")
    print(f"best task: {summary['best_task_id']}  best cost: {summary['best_cost']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
