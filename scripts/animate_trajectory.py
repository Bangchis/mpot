#!/usr/bin/env python3
"""Create a short GIF for the best 2D trajectory of one run."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.animation import animate_best_path


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Run directory containing summary.json and task_results.json.")
    parser.add_argument("--output", default=None, help="Output GIF path. Defaults to <run-dir>/best_path.gif.")
    parser.add_argument("--fps", type=int, default=8, help="Animation frames per second.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        out = animate_best_path(args.run_dir, output=args.output, fps=args.fps)
    except Exception as exc:
        print(f"animation failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
