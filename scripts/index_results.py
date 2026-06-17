#!/usr/bin/env python3
"""Build an index of benchmark/report artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.experiment_index import build_experiment_index, write_experiment_index


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results", help="Results directory to scan.")
    parser.add_argument("--report-dir", default="report", help="Report directory to scan.")
    parser.add_argument("--label", default=None, help="Optional label filter.")
    parser.add_argument("--output", default=None, help="Output index JSON path.")
    parser.add_argument("--markdown", default=None, help="Output index Markdown path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suffix = f"_{args.label}" if args.label else ""
    output = args.output or f"report/EXPERIMENT_INDEX{suffix}.json"
    markdown = args.markdown or f"report/EXPERIMENT_INDEX{suffix}.md"
    try:
        payload = build_experiment_index(results_dir=args.results, report_dir=args.report_dir, label=args.label)
        json_path, markdown_path = write_experiment_index(payload, output, markdown)
    except Exception as exc:
        print(f"index failed: {exc}", file=sys.stderr)
        return 1

    print(f"experiment_index_json: {json_path}")
    print(f"experiment_index_markdown: {markdown_path}")
    print(f"runs: {payload['counts']['runs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
