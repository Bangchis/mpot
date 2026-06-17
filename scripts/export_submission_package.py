#!/usr/bin/env python3
"""Export a compact soft-submission folder from real report artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.submission_package import SubmissionPackageError, create_submission_package


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Experiment/report label, e.g. mini_sweep.")
    parser.add_argument("--report-dir", default="report", help="Directory containing report artifacts.")
    parser.add_argument("--docs-dir", default="docs", help="Directory containing project docs.")
    parser.add_argument("--output-dir", default="submission", help="Directory where the package folder is created.")
    parser.add_argument("--clean", action="store_true", help="Remove an existing submission/<label> folder first.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned manifest without copying files.")
    parser.add_argument("--strict", action="store_true", help="Stop immediately when a required file is missing.")
    parser.add_argument("--allow-fail", action="store_true", help="Return success even when the package is incomplete.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = create_submission_package(
            label=args.label,
            report_dir=args.report_dir,
            docs_dir=args.docs_dir,
            output_dir=args.output_dir,
            clean=args.clean,
            dry_run=args.dry_run,
            strict=args.strict,
        )
    except SubmissionPackageError as exc:
        print(f"submission package failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"submission package: {payload['package_dir']}")
        print(f"manifest: {payload['manifest_json']}")
        print(f"markdown: {payload['manifest_markdown']}")
        print(f"entries: {payload['num_entries']}")
        print(f"missing required: {payload['num_missing_required']}")
        print(f"final ready: {payload['final_ready']}")

    if payload["passed"] or args.allow_fail:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
