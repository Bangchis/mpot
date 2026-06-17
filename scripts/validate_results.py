#!/usr/bin/env python3
"""Validate result artifacts before copying claims into the report."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.validation import (
    validate_benchmark_budget,
    validate_benchmark_plan,
    validate_communication_analysis,
    validate_correctness_report,
    validate_defense_guide,
    validate_environment_report,
    validate_experiment_index,
    validate_granularity_analysis,
    validate_report_bundle,
    validate_report_sync,
    validate_results_summary,
    validate_result_tables_manifest,
    validate_ownership_report,
    validate_report_figures,
    validate_run_dir,
    validate_solution_quality_report,
    validate_submission_package_manifest,
    validate_sweep_coverage,
    write_validation_report,
)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--serial-run", required=True, help="Serial run directory.")
    parser.add_argument("--mpi-run", required=True, help="MPI run directory.")
    parser.add_argument("--correctness", required=True, help="correctness_report.json path.")
    parser.add_argument("--figures", default="report/figures", help="Report figures directory.")
    parser.add_argument(
        "--required-figure",
        action="append",
        default=[],
        help="Required figure filename inside --figures. May be passed more than once.",
    )
    parser.add_argument("--bundle-manifest", default=None, help="Optional report/artifacts/<bundle>/manifest.json.")
    parser.add_argument("--tables-manifest", default=None, help="Optional report/tables/tables_manifest*.json.")
    parser.add_argument("--results-summary", default=None, help="Optional report/RESULTS_SUMMARY_<label>.json.")
    parser.add_argument("--environment", default=None, help="Optional environment JSON from capture_environment.py.")
    parser.add_argument("--benchmark-plan", default=None, help="Optional report/BENCHMARK_PLAN.json.")
    parser.add_argument("--benchmark-budget", default=None, help="Optional report/BENCHMARK_BUDGET_<label>.json.")
    parser.add_argument("--granularity", default=None, help="Optional granularity analysis JSON.")
    parser.add_argument("--communication", default=None, help="Optional communication analysis JSON.")
    parser.add_argument("--solution-quality", default=None, help="Optional solution quality JSON.")
    parser.add_argument("--ownership", default=None, help="Optional team ownership JSON.")
    parser.add_argument("--defense-guide", default=None, help="Optional member defense guide JSON.")
    parser.add_argument("--ownership-min-lines", type=int, default=250, help="Minimum ownership lines per member.")
    parser.add_argument("--ownership-max-lines", type=int, default=700, help="Recommended maximum primary-defense lines per member.")
    parser.add_argument("--experiment-index", default=None, help="Optional experiment index JSON.")
    parser.add_argument("--report-sync", default=None, help="Optional report sync JSON from check_report_sync.py.")
    parser.add_argument("--submission-package", default=None, help="Optional submission/SUBMISSION_MANIFEST.json.")
    parser.add_argument("--sweep-label", default=None, help="Optional sweep label to validate.")
    parser.add_argument("--results", default="results", help="Results directory for sweep validation.")
    parser.add_argument("--output", default="results/validation_report.json", help="Output validation JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    items = []
    items.extend(validate_run_dir(args.serial_run, require_rank_timings=False))
    items.extend(validate_run_dir(args.mpi_run, require_rank_timings=True))
    items.extend(validate_correctness_report(args.correctness))
    required_figures = args.required_figure or [
        "best_path_smoke.png",
        "runtime_vs_input_size.png",
        "rank_time_breakdown.png",
        "speedup.png",
    ]
    items.extend(validate_report_figures(args.figures, required_figures))
    if args.sweep_label:
        items.extend(validate_sweep_coverage(args.results, args.sweep_label))
    if args.bundle_manifest:
        items.extend(validate_report_bundle(args.bundle_manifest))
    if args.tables_manifest:
        items.extend(validate_result_tables_manifest(args.tables_manifest))
    if args.results_summary:
        items.extend(validate_results_summary(args.results_summary))
    if args.environment:
        items.extend(validate_environment_report(args.environment))
    if args.benchmark_plan:
        items.extend(validate_benchmark_plan(args.benchmark_plan))
    if args.benchmark_budget:
        items.extend(validate_benchmark_budget(args.benchmark_budget))
    if args.granularity:
        items.extend(validate_granularity_analysis(args.granularity))
    if args.communication:
        items.extend(validate_communication_analysis(args.communication))
    if args.solution_quality:
        items.extend(validate_solution_quality_report(args.solution_quality))
    if args.ownership:
        items.extend(
            validate_ownership_report(
                args.ownership,
                minimum_lines_per_member=args.ownership_min_lines,
                recommended_max_lines_per_member=args.ownership_max_lines,
            )
        )
    if args.defense_guide:
        items.extend(validate_defense_guide(args.defense_guide))
    if args.experiment_index:
        items.extend(validate_experiment_index(args.experiment_index))
    if args.report_sync:
        items.extend(validate_report_sync(args.report_sync))
    if args.submission_package:
        items.extend(validate_submission_package_manifest(args.submission_package))

    payload = write_validation_report(args.output, items)
    for item in items:
        mark = "PASS" if item.passed else "FAIL"
        print(f"[{mark}] {item.name}: {item.detail}")
    print(f"validation report written to {Path(args.output).resolve()}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
