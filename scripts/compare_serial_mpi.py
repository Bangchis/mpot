#!/usr/bin/env python3
"""Compare serial and MPI runs for correctness."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.artifacts import write_csv, write_json
from mpot.benchmarks.correctness import TASK_COMPARISON_FIELDS, compare_run_directories


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="Serial run directory.")
    parser.add_argument("--mpi", required=True, help="MPI run directory.")
    parser.add_argument("--tolerance", type=float, default=1.0e-5, help="Allowed best-cost difference.")
    parser.add_argument("--output-dir", default="results", help="Directory for comparison report.")
    parser.add_argument("--run-id", default=None, help="Optional deterministic comparison run id.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    serial_dir = Path(args.serial)
    mpi_dir = Path(args.mpi)
    payload, rows = compare_run_directories(serial_dir, mpi_dir, args.tolerance)

    run_id = args.run_id or f"compare-{time.strftime('%Y%m%d-%H%M%S')}"
    out_dir = Path(args.output_dir) / run_id
    payload["run_id"] = run_id
    payload["task_comparison_csv"] = str(out_dir / "task_comparison.csv")
    write_json(out_dir / "correctness_report.json", payload)
    write_csv(out_dir / "task_comparison.csv", rows, TASK_COMPARISON_FIELDS)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
