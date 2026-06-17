#!/usr/bin/env python3
"""Export report-ready result tables from real benchmark artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.result_tables import export_result_tables


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results", help="Directory containing benchmark run subdirectories.")
    parser.add_argument("--output", default="report/tables", help="Directory for generated CSV/Markdown tables.")
    parser.add_argument("--label", default=None, help="Only include runs whose run_id or experiment_name contains this label.")
    parser.add_argument("--input-size", type=int, default=None, help="N used for speedup and load-balance tables.")
    parser.add_argument("--fixed-size", type=int, default=None, help="For runtime-vs-N, include only this process count.")
    parser.add_argument("--load-balance-run", default=None, help="Explicit MPI run directory for per-rank table.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = export_result_tables(
            results_dir=args.results,
            output_dir=args.output,
            label=args.label,
            input_size=args.input_size,
            fixed_size=args.fixed_size,
            load_balance_run=args.load_balance_run,
        )
    except Exception as exc:
        print(f"table export failed: {exc}", file=sys.stderr)
        return 1

    for name, path in paths.to_json().items():
        if path:
            print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
