#!/usr/bin/env python3
"""Generate aggregate report figures from real result summaries."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.plots import plot_runtime_vs_input_size, plot_speedup


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results", help="Directory containing run subdirectories.")
    parser.add_argument("--output", default="report/figures", help="Directory for aggregate report figures.")
    parser.add_argument("--label", default=None, help="Only include runs whose run_id or experiment_name contains this label.")
    parser.add_argument("--fixed-size", type=int, default=None, help="For runtime-vs-N, only include this process count.")
    parser.add_argument("--input-size", type=int, default=None, help="For speedup, plot this N instead of the largest N.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    try:
        out = plot_runtime_vs_input_size(
            args.results,
            output,
            label=args.label,
            fixed_size=args.fixed_size,
        )
        print(f"wrote {out}")
    except Exception as exc:
        print(f"runtime plot skipped: {exc}")

    try:
        out = plot_speedup(
            args.results,
            output,
            label=args.label,
            input_size=args.input_size,
        )
        print(f"wrote {out}")
    except Exception as exc:
        print(f"speedup plot skipped: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
