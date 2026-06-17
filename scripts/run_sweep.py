#!/usr/bin/env python3
"""Run a local experiment sweep for report figures.

Examples:
  .venv/bin/python scripts/run_sweep.py \
      --config configs/local_smoke.json \
      --input-sizes 4,8 \
      --process-counts 1,2,4 \
      --label smoke_sweep
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.cli import parse_int_list
from mpot.benchmarks.run_reuse import existing_run_status, expected_run_metadata, run_is_complete


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Base JSON config.")
    parser.add_argument("--input-sizes", required=True, help="Comma-separated N values, e.g. 8,16,32.")
    parser.add_argument("--process-counts", required=True, help="Comma-separated process counts, e.g. 1,2,4.")
    parser.add_argument("--label", default="sweep", help="Label embedded into run ids and experiment names.")
    parser.add_argument("--output-dir", default="results", help="Output directory for runs.")
    parser.add_argument("--hostfile", default=None, help="Optional OpenMPI hostfile for LAN/Ubuntu VM runs.")
    parser.add_argument("--map-by", default=None, help="Optional OpenMPI mapping policy, for example slot.")
    parser.add_argument("--bind-to", default=None, help="Optional OpenMPI binding policy, for example none.")
    parser.add_argument(
        "--mca",
        action="append",
        nargs=2,
        default=[],
        metavar=("KEY", "VALUE"),
        help="Optional OpenMPI MCA option. Can be repeated.",
    )
    parser.add_argument("--skip-serial", action="store_true", help="Skip serial baselines for each N.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip a serial/MPI run when its output summary.json already exists.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument("--extra", nargs="*", default=[], help="Extra args appended to every runner command.")
    args, unknown = parser.parse_known_args()
    args.extra.extend(unknown)
    return args


def mpi_prefix(*, processes: int, hostfile: str | None = None, map_by: str | None = None, bind_to: str | None = None, mca: list[list[str]] | None = None) -> list[str]:
    """Build the mpirun prefix for local or hostfile-based cluster runs."""

    command = ["mpirun"]
    if hostfile:
        command.extend(["--hostfile", hostfile])
    command.extend(["-np", str(processes)])
    if map_by:
        command.extend(["--map-by", map_by])
    if bind_to:
        command.extend(["--bind-to", bind_to])
    for key, value in mca or []:
        command.extend(["--mca", key, value])
    return command


def run_command(
    command: list[str],
    dry_run: bool,
    *,
    output_dir: str | Path,
    run_id: str,
    skip_existing: bool,
    expected: dict | None = None,
) -> str:
    """Run one command unless an existing completed run should be reused."""

    if skip_existing:
        reusable, reason = existing_run_status(output_dir, run_id, expected=expected)
        if reusable:
            print(f"+ skip existing {run_id} ({reason})", flush=True)
            return "skipped"
        if (Path(output_dir) / run_id / "summary.json").exists():
            print(f"+ existing run not reusable: {reason}", flush=True)

    print("+ " + " ".join(command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=ROOT, check=True)
    return "planned" if dry_run else "ran"


def main() -> int:
    args = parse_args()
    input_sizes = parse_int_list(args.input_sizes)
    process_counts = parse_int_list(args.process_counts)
    python = sys.executable

    for n in input_sizes:
        experiment_name = f"{args.label}_N{n}"
        if not args.skip_serial:
            serial_run_id = f"serial-{args.label}-N{n}"
            serial_command = [
                python,
                "scripts/run_serial.py",
                "--config",
                args.config,
                "--run-id",
                serial_run_id,
                "--experiment-name",
                experiment_name,
                "--output-dir",
                args.output_dir,
                "--total-tasks",
                str(n),
            ] + args.extra
            run_command(
                serial_command,
                args.dry_run,
                output_dir=args.output_dir,
                run_id=serial_run_id,
                skip_existing=args.skip_existing,
                expected=expected_run_metadata(
                    config_path=args.config,
                    output_dir=args.output_dir,
                    label=args.label,
                    input_size_n=n,
                    mode="serial",
                    processes=1,
                    extra=args.extra,
                ),
            )

        for p in process_counts:
            run_id = f"mpi-{args.label}-N{n}-P{p}"
            mpi_command = mpi_prefix(
                processes=p,
                hostfile=args.hostfile,
                map_by=args.map_by,
                bind_to=args.bind_to,
                mca=args.mca,
            ) + [
                python,
                "scripts/run_mpi.py",
                "--config",
                args.config,
                "--run-id",
                run_id,
                "--experiment-name",
                experiment_name,
                "--output-dir",
                args.output_dir,
                "--total-tasks",
                str(n),
            ] + args.extra
            run_command(
                mpi_command,
                args.dry_run,
                output_dir=args.output_dir,
                run_id=run_id,
                skip_existing=args.skip_existing,
                expected=expected_run_metadata(
                    config_path=args.config,
                    output_dir=args.output_dir,
                    label=args.label,
                    input_size_n=n,
                    mode="mpi",
                    processes=p,
                    extra=args.extra,
                ),
            )

    print("sweep complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
