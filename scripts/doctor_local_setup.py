#!/usr/bin/env python3
"""Check whether this machine is ready for the local MPOT/MPI benchmark."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.doctor import build_setup_doctor, write_setup_doctor


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="local_setup", help="Label written into output artifacts.")
    parser.add_argument("--output", default=None, help="Output JSON path. Defaults to results/setup_doctor_<label>.json.")
    parser.add_argument("--markdown", default=None, help="Output Markdown path. Defaults to report/SETUP_DOCTOR_<label>.md.")
    parser.add_argument("--packages", default=None, help="Comma-separated package names to check.")
    parser.add_argument("--min-python", default="3.9", help="Minimum Python version, for example 3.9.")
    parser.add_argument("--no-require-mpirun", action="store_true", help="Do not fail if mpirun is missing.")
    parser.add_argument("--run-mpi-probe", action="store_true", help="Run a tiny mpi4py job with mpirun.")
    parser.add_argument("--mpi-processes", type=int, default=2, help="Process count for --run-mpi-probe.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout in seconds for the MPI probe.")
    return parser.parse_args()


def _parse_min_python(value: str) -> tuple[int, int]:
    parts = value.split(".")
    if len(parts) < 2:
        raise ValueError("--min-python must look like 3.9")
    return int(parts[0]), int(parts[1])


def _parse_packages(value: str | None) -> list[str] | None:
    if not value:
        return None
    packages = [part.strip() for part in value.split(",") if part.strip()]
    if not packages:
        raise ValueError("--packages must contain at least one package name")
    return packages


def main() -> int:
    args = parse_args()
    try:
        min_python = _parse_min_python(args.min_python)
        packages = _parse_packages(args.packages)
    except ValueError as exc:
        print(f"setup doctor failed: {exc}", file=sys.stderr)
        return 2

    output = args.output or f"results/setup_doctor_{args.label}.json"
    markdown = args.markdown or f"report/SETUP_DOCTOR_{args.label}.md"
    payload = build_setup_doctor(
        repo_root=ROOT,
        label=args.label,
        packages=packages,
        min_python=min_python,
        require_mpirun=not args.no_require_mpirun,
        run_probe=args.run_mpi_probe,
        probe_processes=args.mpi_processes,
        timeout_s=args.timeout,
    )
    json_path, markdown_path = write_setup_doctor(payload, output, markdown)

    for item in payload["items"]:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"[{mark}] {item['name']}: {item['detail']}")
    print(f"setup_doctor_json: {json_path}")
    print(f"setup_doctor_markdown: {markdown_path}")
    print(f"ready: {payload['ready']}")
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
