#!/usr/bin/env python3
"""Audit whether a benchmark label is ready for the final report."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.cli import parse_int_list
from mpot.benchmarks.final_audit import build_final_audit, write_final_audit


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results", help="Results directory.")
    parser.add_argument("--report-dir", default="report", help="Report directory.")
    parser.add_argument("--label", required=True, help="Experiment label to audit.")
    parser.add_argument("--input-sizes", required=True, help="Comma-separated input sizes used in the sweep.")
    parser.add_argument("--process-counts", required=True, help="Comma-separated process counts used in the sweep.")
    parser.add_argument("--n", type=int, required=True, help="N used for runtime/load-balance checks.")
    parser.add_argument("--speedup-n", type=int, default=None, help="Input size used for speedup/correctness. Defaults to 2*N.")
    parser.add_argument("--final-processes", type=int, required=True, help="Process count used for correctness/load balance.")
    parser.add_argument("--bundle-name", default=None, help="Report artifact bundle name. Defaults to label.")
    parser.add_argument("--validation", default=None, help="Pipeline validation JSON path.")
    parser.add_argument("--communication", default=None, help="Communication analysis JSON path.")
    parser.add_argument("--solution-quality", default=None, help="Solution quality JSON path.")
    parser.add_argument("--ownership", default=None, help="Team ownership report JSON path.")
    parser.add_argument("--defense-guide", default=None, help="Member defense guide JSON path.")
    parser.add_argument("--benchmark-plan", default=None, help="Optional BENCHMARK_PLAN.json path.")
    parser.add_argument("--output", default=None, help="Output audit JSON. Defaults to report/FINAL_AUDIT_<label>.json.")
    parser.add_argument("--markdown", default=None, help="Output audit Markdown. Defaults to report/FINAL_AUDIT_<label>.md.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_sizes = parse_int_list(args.input_sizes)
    process_counts = parse_int_list(args.process_counts)
    speedup_n = args.speedup_n or (2 * args.n)
    output = args.output or f"report/FINAL_AUDIT_{args.label}.json"
    markdown = args.markdown or f"report/FINAL_AUDIT_{args.label}.md"

    payload = build_final_audit(
        results_dir=args.results,
        report_dir=args.report_dir,
        label=args.label,
        input_sizes=input_sizes,
        process_counts=process_counts,
        n=args.n,
        speedup_n=speedup_n,
        final_processes=args.final_processes,
        bundle_name=args.bundle_name,
        validation_report=args.validation,
        benchmark_plan=args.benchmark_plan,
        communication_report=args.communication,
        solution_quality_report=args.solution_quality,
        ownership_report=args.ownership,
        defense_guide=args.defense_guide,
    )
    json_path, markdown_path = write_final_audit(payload, output, markdown)

    for item in payload["items"]:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"[{mark}] {item['name']}: {item['detail']}")
    print(f"final_audit_json: {json_path}")
    print(f"final_audit_markdown: {markdown_path}")
    print(f"final_ready: {payload['final_ready']}")
    return 0 if payload["final_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
