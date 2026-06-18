#!/usr/bin/env python3
"""Create a GIF that explains the MPI task assignment and reduction phases."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.animation import animate_parallel_schedule


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Completed MPI run directory containing summary.json.")
    parser.add_argument("--output", default=None, help="Output GIF path. Defaults to <run-dir>/parallel_schedule.gif.")
    parser.add_argument("--fps", type=int, default=1, help="Animation frames per second.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        out = animate_parallel_schedule(args.run_dir, output=args.output, fps=args.fps)
    except Exception as exc:
        print(f"parallel schedule animation failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
