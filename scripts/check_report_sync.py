#!/usr/bin/env python3
"""Check that living-report file references still exist."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.report_sync import DEFAULT_SYNC_DOCS, build_report_sync, write_report_sync


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--label", default="", help="Optional label written into the sync report.")
    parser.add_argument(
        "--doc",
        action="append",
        default=[],
        help="Markdown document to scan. May be passed more than once. Defaults to core report docs.",
    )
    parser.add_argument("--output", default="report/REPORT_SYNC.json", help="Output JSON path.")
    parser.add_argument("--markdown", default="report/REPORT_SYNC.md", help="Output Markdown path.")
    parser.add_argument("--allow-fail", action="store_true", help="Return success even if missing paths are found.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    documents = args.doc or DEFAULT_SYNC_DOCS
    payload = build_report_sync(repo_root=args.repo_root, documents=documents, label=args.label)
    json_path, markdown_path = write_report_sync(
        payload=payload,
        json_path=args.output,
        markdown_path=args.markdown,
    )
    print(f"report_sync_json: {json_path}")
    print(f"report_sync_markdown: {markdown_path}")
    print(f"passed: {payload['passed']}")
    print(f"checked: {payload['num_checked']}")
    print(f"missing: {payload['num_missing']}")
    if payload["missing"]:
        for item in payload["missing"][:20]:
            print(f"missing: {item['document']}:{item['line']} {item['path']}")
    return 0 if payload["passed"] or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
