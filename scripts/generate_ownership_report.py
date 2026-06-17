#!/usr/bin/env python3
"""Generate per-member code ownership and line-count evidence."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.ownership import (
    DEFAULT_MINIMUM_LINES_PER_MEMBER,
    DEFAULT_RECOMMENDED_MAX_LINES_PER_MEMBER,
    build_ownership_report,
    write_ownership_report,
)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to inspect.")
    parser.add_argument(
        "--minimum-lines",
        type=int,
        default=DEFAULT_MINIMUM_LINES_PER_MEMBER,
        help="Minimum meaningful code/config lines required per member.",
    )
    parser.add_argument(
        "--recommended-max-lines",
        type=int,
        default=DEFAULT_RECOMMENDED_MAX_LINES_PER_MEMBER,
        help="Recommended maximum primary-defense lines per member.",
    )
    parser.add_argument("--output", default="report/TEAM_OWNERSHIP_REPORT.json", help="Output JSON path.")
    parser.add_argument("--markdown", default="report/TEAM_OWNERSHIP_REPORT.md", help="Output Markdown path.")
    parser.add_argument(
        "--allow-fail",
        action="store_true",
        help="Write the report but return exit code 0 even if a member is under the threshold.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_ownership_report(
        repo_root=args.repo_root,
        minimum_lines_per_member=args.minimum_lines,
        recommended_max_lines_per_member=args.recommended_max_lines,
    )
    json_path, markdown_path = write_ownership_report(
        payload=payload,
        json_path=args.output,
        markdown_path=args.markdown,
    )

    print(f"ownership_json: {json_path}")
    print(f"ownership_markdown: {markdown_path}")
    print(f"passed: {payload['passed']}")
    print(f"total_meaningful_lines: {payload['total_meaningful_lines']}")
    for member in payload["members"]:
        print(
            "{member}: {lines} meaningful lines, minimum {minimum}, passed={passed}".format(
                member=member["member"],
                lines=member["meaningful_lines"],
                minimum=member["minimum_lines"],
                passed=member["passed"],
            )
        )
    return 0 if payload["passed"] or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
