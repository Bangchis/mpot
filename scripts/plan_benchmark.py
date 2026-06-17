#!/usr/bin/env python3
"""Create a final benchmark plan from sample timing artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.benchmark_plan import create_benchmark_plan, parse_float_list, write_benchmark_plan


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/local_benchmark.json", help="Config for final benchmark pipeline.")
    parser.add_argument("--label", default="final_macbook_air_2d", help="Label for planned final runs.")
    parser.add_argument("--sample-summary", default=None, help="Existing serial sample summary.json.")
    parser.add_argument("--seconds-per-task", type=float, default=None, help="Manual seconds per task estimate.")
    parser.add_argument("--target-seconds", type=float, default=150.0, help="Target runtime for N at max processes.")
    parser.add_argument("--target-processes", type=int, default=None, help="Max process count, defaults to os.cpu_count().")
    parser.add_argument(
        "--parallel-efficiency",
        type=float,
        default=0.8,
        help="Planning assumption in (0, 1]; not a measured result.",
    )
    parser.add_argument(
        "--runtime-factors",
        default="0.5,1.0,2.0",
        help="N factors for runtime-vs-input-size plan.",
    )
    parser.add_argument(
        "--no-include-max-processes",
        action="store_true",
        help="Use only powers of two up to max processes; do not append max if non-power-of-two.",
    )
    parser.add_argument("--output", default="report/BENCHMARK_PLAN.json", help="Output plan JSON.")
    parser.add_argument("--markdown", default="report/BENCHMARK_PLAN.md", help="Output plan Markdown.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = create_benchmark_plan(
            config=args.config,
            label=args.label,
            target_seconds=args.target_seconds,
            target_processes=args.target_processes,
            assumed_parallel_efficiency=args.parallel_efficiency,
            sample_summary=args.sample_summary,
            seconds_per_task=args.seconds_per_task,
            runtime_factors=parse_float_list(args.runtime_factors),
            include_max_processes=not args.no_include_max_processes,
        )
        plan.pipeline_command.extend(["--benchmark-plan", args.output])
        json_path, markdown_path = write_benchmark_plan(plan, args.output, args.markdown)
    except Exception as exc:
        print(f"benchmark plan failed: {exc}", file=sys.stderr)
        return 1

    print(f"benchmark_plan_json: {json_path}")
    print(f"benchmark_plan_markdown: {markdown_path}")
    print("pipeline_command: " + " ".join(plan.pipeline_command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
