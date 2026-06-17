#!/usr/bin/env python3
"""Analyze MPI communication events from comm_events.csv."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.communication import analyze_communication, write_communication_analysis


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="MPI run directory containing summary.json and comm_events.csv.")
    parser.add_argument("--output", default=None, help="Output JSON path.")
    parser.add_argument("--markdown", default=None, help="Output Markdown path.")
    parser.add_argument("--label", default=None, help="Optional label for default output filenames.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    label = args.label or run_dir.name
    output = args.output or f"results/communication-{label}.json"
    markdown = args.markdown or f"report/COMMUNICATION_{label}.md"
    try:
        payload = analyze_communication(run_dir)
        json_path, markdown_path = write_communication_analysis(
            payload=payload,
            json_path=output,
            markdown_path=markdown,
        )
    except Exception as exc:
        print(f"communication analysis failed: {exc}", file=sys.stderr)
        return 1

    print(f"communication_json: {json_path}")
    print(f"communication_markdown: {markdown_path}")
    print(f"all_events_blocking: {payload['all_events_blocking']}")
    print(f"observed_collectives: {','.join(payload['observed_collectives'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
