#!/usr/bin/env python3
"""Export a report-ready Results summary from real benchmark artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.results_summary import build_results_summary, write_results_summary


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Benchmark label written into the summary.")
    parser.add_argument("--serial-run", required=True, help="Serial run directory.")
    parser.add_argument("--mpi-run", required=True, help="MPI run directory.")
    parser.add_argument("--correctness", required=True, help="correctness_report.json path.")
    parser.add_argument("--tables-manifest", required=True, help="Result tables manifest JSON.")
    parser.add_argument("--granularity", required=True, help="Granularity analysis JSON.")
    parser.add_argument("--communication", required=True, help="Communication analysis JSON.")
    parser.add_argument("--solution-quality", required=True, help="Solution quality JSON.")
    parser.add_argument("--benchmark-budget", default=None, help="Optional benchmark budget JSON.")
    parser.add_argument("--figure", action="append", default=[], help="Figure path to verify and list. Repeatable.")
    parser.add_argument("--output", default=None, help="Output JSON. Defaults to report/RESULTS_SUMMARY_<label>.json.")
    parser.add_argument("--markdown", default=None, help="Output Markdown. Defaults to report/RESULTS_SUMMARY_<label>.md.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output or f"report/RESULTS_SUMMARY_{args.label}.json"
    markdown = args.markdown or f"report/RESULTS_SUMMARY_{args.label}.md"
    try:
        payload = build_results_summary(
            label=args.label,
            serial_run=args.serial_run,
            mpi_run=args.mpi_run,
            correctness_report=args.correctness,
            tables_manifest=args.tables_manifest,
            granularity_report=args.granularity,
            communication_report=args.communication,
            solution_quality_report=args.solution_quality,
            benchmark_budget=args.benchmark_budget,
            figure_paths=args.figure,
        )
        json_path, markdown_path = write_results_summary(payload, output, markdown)
    except Exception as exc:
        print(f"results summary export failed: {exc}", file=sys.stderr)
        return 1

    print(f"results_summary_json: {json_path}")
    print(f"results_summary_markdown: {markdown_path}")
    print(f"passed: {payload['passed']}")
    print(f"num_failed: {payload['num_failed']}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
