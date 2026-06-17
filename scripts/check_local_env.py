#!/usr/bin/env python3
"""Print local environment information for the MPOT/MPI course project."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.environment import capture_environment


def main() -> int:
    env = capture_environment(repo_root=ROOT)
    print("MPOT local environment check")
    print(f"repo root: {ROOT}")
    print(f"python: {env['python']['executable']}")
    print(f"python version: {env['python']['version']}")
    for package in env["packages"]:
        status = package["version"] if package["installed"] else f"MISSING ({package['error']})"
        print(f"{package['name']}: {status}")
    mpirun = env["mpi"]["mpirun"]
    first_line = mpirun["output"].splitlines()[0] if mpirun["output"] else ""
    print(f"mpirun: {mpirun['executable'] or 'MISSING'} - {first_line}")
    print()
    print("Expected local setup:")
    print("  python -m pip install -r requirements-local.txt")
    print("  python -m pip install -e . --no-deps")
    print()
    print("Strict setup doctor:")
    print("  python scripts/doctor_local_setup.py --label teammate --run-mpi-probe --mpi-processes 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
