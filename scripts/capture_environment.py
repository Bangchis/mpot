#!/usr/bin/env python3
"""Capture reproducibility metadata for benchmark/report artifacts."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.environment import capture_environment, write_environment_artifacts


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="", help="Experiment label.")
    parser.add_argument("--output", default="results/environment.json", help="Output environment JSON path.")
    parser.add_argument("--markdown", default="report/ENVIRONMENT.md", help="Output Markdown path.")
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        help="Package to record. May be passed more than once. Defaults to project packages.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = capture_environment(
        repo_root=ROOT,
        label=args.label,
        packages=args.package or None,
    )
    json_path, markdown_path = write_environment_artifacts(
        payload=payload,
        json_path=args.output,
        markdown_path=args.markdown,
    )
    print(f"environment_json: {json_path}")
    print(f"environment_markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
