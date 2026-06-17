#!/usr/bin/env python3
"""Validate the saved best trajectory for one serial or MPI run."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.solution_quality import validate_solution_quality, write_solution_quality


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Run directory containing summary.json and task_results.json.")
    parser.add_argument("--start-tolerance", type=float, default=1.0e-3, help="Allowed start position error.")
    parser.add_argument("--goal-tolerance", type=float, default=1.0e-3, help="Allowed goal position error.")
    parser.add_argument("--max-collision-fraction", type=float, default=0.0, help="Allowed hard-obstacle collision fraction.")
    parser.add_argument("--bounds-tolerance", type=float, default=1.0e-6, help="Allowed workspace bounds violation.")
    parser.add_argument("--output", default=None, help="Output JSON path.")
    parser.add_argument("--markdown", default=None, help="Output Markdown path.")
    parser.add_argument("--label", default=None, help="Optional label for default output filenames.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    label = args.label or run_dir.name
    output = args.output or f"results/solution-quality-{label}.json"
    markdown = args.markdown or f"report/SOLUTION_QUALITY_{label}.md"
    try:
        payload = validate_solution_quality(
            run_dir,
            start_tolerance=args.start_tolerance,
            goal_tolerance=args.goal_tolerance,
            max_collision_fraction=args.max_collision_fraction,
            bounds_tolerance=args.bounds_tolerance,
        )
        json_path, markdown_path = write_solution_quality(
            payload=payload,
            json_path=output,
            markdown_path=markdown,
        )
    except Exception as exc:
        print(f"solution quality validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"solution_quality_json: {json_path}")
    print(f"solution_quality_markdown: {markdown_path}")
    print(f"passed: {payload['passed']}")
    print(f"goal_error: {payload['goal_error']}")
    print(f"hard_collision_fraction: {payload['hard_collision_fraction']}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
