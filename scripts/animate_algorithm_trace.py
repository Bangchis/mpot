#!/usr/bin/env python3
"""Create a GIF showing MPOT particles over optimization iterations."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.animation import animate_algorithm_trace


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Completed run directory containing summary.json.")
    parser.add_argument("--output", default=None, help="Output GIF path. Defaults to <run-dir>/algorithm_trace.gif.")
    parser.add_argument("--trace-output", default=None, help="Optional JSON file storing the regenerated trace frames.")
    parser.add_argument("--fps", type=int, default=3, help="Animation frames per second.")
    parser.add_argument("--max-particles", type=int, default=24, help="Maximum particles drawn per frame.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        out = animate_algorithm_trace(
            args.run_dir,
            output=args.output,
            trace_output=args.trace_output,
            fps=args.fps,
            max_particles=args.max_particles,
        )
    except Exception as exc:
        print(f"algorithm trace animation failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
