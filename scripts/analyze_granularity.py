#!/usr/bin/env python3
"""Analyze MPI granularity/load balance from rank timing artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.granularity import analyze_granularity, write_granularity_analysis


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="MPI run directory containing summary.json and rank_timings.csv.")
    parser.add_argument("--threshold", type=float, default=0.25, help="Allowed idle-time imbalance fraction.")
    parser.add_argument("--output", default=None, help="Output JSON path.")
    parser.add_argument("--markdown", default=None, help="Output Markdown path.")
    parser.add_argument("--label", default=None, help="Optional label for default output filenames.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    label = args.label or run_dir.name
    output = args.output or f"results/granularity-{label}.json"
    markdown = args.markdown or f"report/GRANULARITY_{label}.md"
    try:
        payload = analyze_granularity(run_dir, threshold=args.threshold)
        json_path, markdown_path = write_granularity_analysis(
            payload=payload,
            json_path=output,
            markdown_path=markdown,
        )
    except Exception as exc:
        print(f"granularity analysis failed: {exc}", file=sys.stderr)
        return 1

    print(f"granularity_json: {json_path}")
    print(f"granularity_markdown: {markdown_path}")
    print(f"balanced_under_threshold: {payload['balanced_under_threshold']}")
    print(f"idle_fraction: {payload['idle_fraction']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
