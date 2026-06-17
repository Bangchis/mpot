#!/usr/bin/env python3
"""Estimate whether a benchmark plan is reasonable before running it."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.benchmark_budget import build_benchmark_budget, write_benchmark_budget


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="report/BENCHMARK_PLAN.json", help="Benchmark plan JSON.")
    parser.add_argument("--output", default="report/BENCHMARK_BUDGET.json", help="Output budget JSON.")
    parser.add_argument("--markdown", default="report/BENCHMARK_BUDGET.md", help="Output budget Markdown.")
    parser.add_argument(
        "--max-total-seconds",
        type=float,
        default=3600.0,
        help="Fail the guard if estimated total sweep time is above this value.",
    )
    parser.add_argument(
        "--min-largest-run-seconds",
        type=float,
        default=1.0,
        help="Fail the guard if the largest planned run is below this value.",
    )
    parser.add_argument(
        "--mpi-startup-seconds",
        type=float,
        default=1.0,
        help="Small per-MPI-run startup allowance used by the estimate.",
    )
    parser.add_argument(
        "--mpi-overhead-factor",
        type=float,
        default=1.05,
        help="Multiplier for MPI P=1 estimates relative to serial.",
    )
    parser.add_argument("--label", default=None, help="Optional label stored in the budget report.")
    parser.add_argument("--run-label", default=None, help="Optional run label used to construct expected run ids.")
    parser.add_argument("--results-dir", default="results", help="Results directory checked when --reuse-existing is set.")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Estimate only missing/mismatched runs by reusing matching summary.json artifacts.",
    )
    parser.add_argument("--no-serial", action="store_true", help="Do not include serial sweep runs in the estimate.")
    parser.add_argument("--allow-fail", action="store_true", help="Write reports but return 0 even if the budget fails.")
    parser.add_argument("--extra", nargs="*", default=[], help="Config override args used by the sweep runners.")
    args, unknown = parser.parse_known_args()
    args.extra.extend(unknown)
    return args


def main() -> int:
    args = parse_args()
    try:
        payload = build_benchmark_budget(
            args.plan,
            max_total_seconds=args.max_total_seconds,
            min_largest_run_seconds=args.min_largest_run_seconds,
            mpi_startup_seconds=args.mpi_startup_seconds,
            mpi_overhead_factor=args.mpi_overhead_factor,
            include_serial=not args.no_serial,
            label=args.label,
            results_dir=args.results_dir,
            reuse_existing=args.reuse_existing,
            run_label=args.run_label,
            extra=args.extra,
        )
        json_path, markdown_path = write_benchmark_budget(payload, args.output, args.markdown)
    except Exception as exc:
        print(f"benchmark budget failed: {exc}", file=sys.stderr)
        return 1

    print(f"benchmark_budget_json: {json_path}")
    print(f"benchmark_budget_markdown: {markdown_path}")
    print(f"passed: {payload['passed']}")
    print(f"estimated_total_seconds: {payload['estimated_total_seconds']:.2f}")
    print(f"estimated_total_minutes: {payload['estimated_total_minutes']:.2f}")
    print(f"estimated_remaining_seconds: {payload['estimated_remaining_seconds']:.2f}")
    print(f"estimated_remaining_minutes: {payload['estimated_remaining_minutes']:.2f}")
    print(f"num_reusable_rows: {payload['num_reusable_rows']}")
    print(f"num_remaining_rows: {payload['num_remaining_rows']}")
    print(f"largest_run_seconds: {payload['largest_run_seconds']:.2f}")
    print(f"largest_remaining_run_seconds: {payload['largest_remaining_run_seconds']:.2f}")
    for warning in payload.get("warnings", []):
        print(f"warning: {warning}")
    return 0 if payload["passed"] or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
