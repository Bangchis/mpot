#!/usr/bin/env python3
"""Generate a per-member study guide for final demo defense."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.defense_pack import (
    DEFAULT_MAX_SYMBOLS_PER_FILE,
    build_defense_guide,
    write_defense_guide,
)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to inspect.")
    parser.add_argument(
        "--max-symbols-per-file",
        type=int,
        default=DEFAULT_MAX_SYMBOLS_PER_FILE,
        help="Maximum top-level symbols/config keys to show per file.",
    )
    parser.add_argument("--output", default="report/MEMBER_DEFENSE_GUIDE.json", help="Output JSON path.")
    parser.add_argument("--markdown", default="report/MEMBER_DEFENSE_GUIDE.md", help="Output Markdown path.")
    parser.add_argument("--allow-fail", action="store_true", help="Return exit code 0 even if generation finds missing files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_defense_guide(
        repo_root=args.repo_root,
        max_symbols_per_file=args.max_symbols_per_file,
    )
    json_path, markdown_path = write_defense_guide(
        payload=payload,
        json_path=args.output,
        markdown_path=args.markdown,
    )

    print(f"defense_guide_json: {json_path}")
    print(f"defense_guide_markdown: {markdown_path}")
    print(f"passed: {payload['passed']}")
    for member in payload["members"]:
        print(
            "{member}: {files} files, {lines} meaningful lines, {questions} practice questions".format(
                member=member["member"],
                files=len(member["files"]),
                lines=member["meaningful_lines"],
                questions=len(member["practice_questions"]),
            )
        )
    return 0 if payload["passed"] or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
