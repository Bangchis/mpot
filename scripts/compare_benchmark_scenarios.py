#!/usr/bin/env python3
"""Compare candidate final benchmark scenarios without running experiments."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.benchmark_plan import parse_float_list
from mpot.benchmarks.benchmark_scenarios import (
    build_benchmark_scenarios,
    parse_scenario_names,
    parse_target_seconds,
    write_benchmark_scenarios,
)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/local_benchmark.json", help="Benchmark config.")
    parser.add_argument("--label", default="final_macbook_air_2d", help="Base label for generated scenario commands.")
    parser.add_argument("--sample-summary", default=None, help="Existing sample summary.json.")
    parser.add_argument("--seconds-per-task", type=float, default=None, help="Manual seconds per task estimate.")
    parser.add_argument("--target-seconds", default="60,150", help="Comma-separated target seconds for N at max P.")
    parser.add_argument("--scenario-names", default="safe_local,strict_2min_N", help="Comma-separated scenario names.")
    parser.add_argument("--target-processes", type=int, default=4, help="Max process count used in planning.")
    parser.add_argument("--parallel-efficiency", type=float, default=0.75, help="Planning efficiency assumption.")
    parser.add_argument("--runtime-factors", default="0.5,1.0,2.0", help="Input-size factors around N.")
    parser.add_argument("--max-total-seconds", type=float, default=3600.0, help="Full-sweep budget guard.")
    parser.add_argument("--output", default="report/BENCHMARK_SCENARIOS.json", help="Scenario JSON output.")
    parser.add_argument("--markdown", default="report/BENCHMARK_SCENARIOS.md", help="Scenario Markdown output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = build_benchmark_scenarios(
            config=args.config,
            label=args.label,
            target_seconds=parse_target_seconds(args.target_seconds),
            target_processes=args.target_processes,
            assumed_parallel_efficiency=args.parallel_efficiency,
            sample_summary=args.sample_summary,
            seconds_per_task=args.seconds_per_task,
            runtime_factors=parse_float_list(args.runtime_factors),
            max_total_seconds=args.max_total_seconds,
            scenario_names=parse_scenario_names(args.scenario_names),
        )
        json_path, markdown_path = write_benchmark_scenarios(payload, args.output, args.markdown)
    except Exception as exc:
        print(f"benchmark scenario comparison failed: {exc}", file=sys.stderr)
        return 1

    print(f"benchmark_scenarios_json: {json_path}")
    print(f"benchmark_scenarios_markdown: {markdown_path}")
    for scenario in payload["scenarios"]:
        print(
            "{name}: N={n}, 2N={two_n}, full_sweep_min={minutes:.2f}, passed={passed}".format(
                name=scenario["name"],
                n=scenario["chosen_n"],
                two_n=scenario["speedup_n"],
                minutes=float(scenario["estimated_total_minutes"]),
                passed=scenario["passed_budget"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
