#!/usr/bin/env python3
"""Copy real benchmark artifacts into report folders and write a manifest."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.report_bundle import BundleError, create_report_bundle, default_bundle_name


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serial-run",
        action="append",
        default=[],
        help="Serial run directory to include. May be passed more than once.",
    )
    parser.add_argument(
        "--mpi-run",
        action="append",
        default=[],
        help="MPI run directory to include. May be passed more than once.",
    )
    parser.add_argument(
        "--correctness",
        action="append",
        default=[],
        help="correctness_report.json path to include. May be passed more than once.",
    )
    parser.add_argument(
        "--validation",
        action="append",
        default=[],
        help="validation_report.json path to include. May be passed more than once.",
    )
    parser.add_argument("--results", default="results", help="Directory containing run subdirectories.")
    parser.add_argument("--report-dir", default="report", help="Report directory.")
    parser.add_argument("--bundle-name", default=None, help="Stable name for this artifact bundle.")
    parser.add_argument(
        "--label",
        default=None,
        help="Optional run label used to generate filtered aggregate figures.",
    )
    parser.add_argument(
        "--fixed-size",
        type=int,
        default=None,
        help="For runtime-vs-N, include only this process count.",
    )
    parser.add_argument(
        "--input-size",
        type=int,
        default=None,
        help="For speedup, plot this input size N.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Only copy run/report artifacts; do not regenerate aggregate plots.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the existing report/artifacts/<bundle-name>/ directory before exporting.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Write a manifest even if an expected artifact is missing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned manifest without copying files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    has_inputs = any([args.serial_run, args.mpi_run, args.correctness, args.validation, args.label])
    if not has_inputs:
        print("No artifacts requested. Pass at least one run, report, or --label.", file=sys.stderr)
        return 2

    bundle_name = args.bundle_name or default_bundle_name(args.label)
    try:
        manifest = create_report_bundle(
            report_dir=args.report_dir,
            bundle_name=bundle_name,
            serial_runs=args.serial_run,
            mpi_runs=args.mpi_run,
            correctness_reports=args.correctness,
            validation_reports=args.validation,
            results_dir=args.results,
            label=args.label,
            fixed_size=args.fixed_size,
            input_size=args.input_size,
            generate_plots=not args.no_plots,
            clean_existing=args.clean,
            strict=not args.allow_missing,
            dry_run=args.dry_run,
        )
    except BundleError as exc:
        print(f"bundle failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"manifest: {manifest['manifest_path']}")
        print(f"markdown: {manifest['markdown_path']}")
        print(f"entries: {len(manifest['entries'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
