#!/usr/bin/env python3
"""Run the MPI version of the local-first MPOT benchmark."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.cli import add_config_override_args, apply_config_overrides
from mpot.benchmarks.config import load_config
from mpot.benchmarks.mpi_runner import require_mpi4py, run_mpi_benchmark


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to JSON experiment config.")
    parser.add_argument("--run-id", default=None, help="Optional run id for output directory.")
    parser.add_argument("--use-wandb", action="store_true", help="Enable optional rank-0 W&B logging.")
    add_config_override_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    MPI = require_mpi4py()
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    config = apply_config_overrides(load_config(args.config), args) if rank == 0 else None
    run_mpi_benchmark(comm=comm, config=config, run_id=args.run_id, use_wandb=args.use_wandb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
