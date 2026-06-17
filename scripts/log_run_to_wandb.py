#!/usr/bin/env python3
"""Log an existing benchmark run directory to W&B.

This is useful when a run already exists under results/<run_id>/ and should be
uploaded without rerunning the benchmark.
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.cli import add_wandb_args
from mpot.wandb_logger import log_run_directory_to_wandb, wandb_settings_from_namespace


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Existing run directory containing summary.json.")
    parser.add_argument(
        "--extra-path",
        action="append",
        default=[],
        help="Extra PNG/GIF/CSV/JSON file to attach. Can be repeated.",
    )
    add_wandb_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    if not (run_dir / "summary.json").exists():
        print(f"missing summary.json under {run_dir}", file=sys.stderr)
        return 2
    settings = wandb_settings_from_namespace(args)
    if not settings.enabled:
        print("W&B disabled. Add --use-wandb to upload this run.", file=sys.stderr)
        return 2
    outcome = log_run_directory_to_wandb(
        run_dir,
        settings=settings,
        extra_paths=args.extra_path,
    )
    print(f"wandb status: {outcome['status']}")
    print(f"manifest: {outcome['manifest']}")
    print(f"artifact files: {outcome['num_artifact_files']}")
    print(f"images: {outcome['num_images']}")
    print(f"animations: {outcome['num_animations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
