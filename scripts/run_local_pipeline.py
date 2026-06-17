#!/usr/bin/env python3
"""Run the local benchmark-to-report pipeline.

This command is the one-stop local workflow for the final project:

1. optionally run serial/MPI sweep
2. generate team ownership evidence
3. generate member defense guide
4. estimate benchmark runtime budget when a benchmark plan is provided
5. generate aggregate plots
6. compare serial and MPI correctness for the selected N/P
7. create a short trajectory GIF for demo slides
8. export report-ready tables
9. export traceable report artifact bundle
10. check report/code path synchronization
11. export a report-ready Results summary
12. validate the artifacts before the report uses them
13. audit final-report readiness against the course rubric
14. export a compact submission package
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.pipeline import (
    build_pipeline_commands,
    default_python,
    parse_pipeline_ints,
    run_pipeline_commands,
    select_final_value,
)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Base JSON config for serial and MPI runs.")
    parser.add_argument("--input-sizes", required=True, help="Comma-separated N values, e.g. 8,16,32.")
    parser.add_argument("--process-counts", required=True, help="Comma-separated process counts, e.g. 1,2,4.")
    parser.add_argument("--label", default="local_pipeline", help="Label embedded in run ids and report tables.")
    parser.add_argument("--output-dir", default="results", help="Directory for run outputs.")
    parser.add_argument("--report-dir", default="report", help="Directory for report artifacts.")
    parser.add_argument("--submission-dir", default="submission", help="Directory for generated submission packages.")
    parser.add_argument("--final-n", type=int, default=None, help="N used for correctness, speedup, and bundle.")
    parser.add_argument("--final-processes", type=int, default=None, help="MPI process count used for correctness and bundle.")
    parser.add_argument("--load-balance-n", type=int, default=None, help="N used for per-rank load-balance table/figure.")
    parser.add_argument("--bundle-name", default=None, help="Report artifact bundle name. Defaults to label.")
    parser.add_argument("--benchmark-plan", default=None, help="Optional BENCHMARK_PLAN.json to validate at the end.")
    parser.add_argument("--skip-sweep", action="store_true", help="Use existing runs and only execute post-processing.")
    parser.add_argument(
        "--skip-existing-runs",
        action="store_true",
        help="During the sweep, skip any run directory that already has summary.json.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    args, unknown = parser.parse_known_args()
    args.sweep_extra = unknown
    return args


def main() -> int:
    args = parse_args()
    try:
        input_sizes = parse_pipeline_ints(args.input_sizes, "input sizes")
        process_counts = parse_pipeline_ints(args.process_counts, "process counts")
        final_n = select_final_value(input_sizes, args.final_n, "final_n")
        final_processes = select_final_value(process_counts, args.final_processes, "final_processes")
        load_balance_n = select_final_value(input_sizes, args.load_balance_n, "load_balance_n")
        bundle_name = args.bundle_name or args.label
        run_ids, commands = build_pipeline_commands(
            python=default_python(),
            config=args.config,
            input_sizes=input_sizes,
            process_counts=process_counts,
            label=args.label,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            final_n=final_n,
            final_processes=final_processes,
            load_balance_n=load_balance_n,
            bundle_name=bundle_name,
            skip_sweep=args.skip_sweep,
            skip_existing_runs=args.skip_existing_runs,
            benchmark_plan=args.benchmark_plan,
            sweep_extra=args.sweep_extra,
            submission_dir=args.submission_dir,
        )
    except ValueError as exc:
        print(f"pipeline setup failed: {exc}", file=sys.stderr)
        return 2

    print("local pipeline configuration")
    print(f"  label: {args.label}")
    print(f"  final N: {final_n}")
    print(f"  load-balance N: {load_balance_n}")
    print(f"  final processes: {final_processes}")
    print(f"  skip existing runs: {args.skip_existing_runs}")
    print(f"  serial run: {run_ids.serial_run_dir}")
    print(f"  mpi run: {run_ids.mpi_run_dir}")
    print(f"  correctness: {run_ids.correctness_report}")
    print(f"  environment: {run_ids.environment_json}")
    print(f"  ownership: {run_ids.ownership_json}")
    print(f"  defense guide: {run_ids.defense_guide_json}")
    print(f"  granularity: {run_ids.granularity_json}")
    print(f"  communication: {run_ids.communication_json}")
    print(f"  solution quality: {run_ids.solution_quality_json}")
    print(f"  experiment index: {run_ids.experiment_index_json}")
    print(f"  report sync: {run_ids.report_sync_json}")
    print(f"  results summary: {run_ids.results_summary_json}")
    print(f"  benchmark budget: {run_ids.benchmark_budget_json}")
    print(f"  trajectory gif: {run_ids.trajectory_gif}")
    print(f"  algorithm trace gif: {run_ids.algorithm_trace_gif}")
    print(f"  bundle manifest: {run_ids.bundle_manifest}")
    print(f"  tables manifest: {run_ids.tables_manifest}")
    print(f"  validation: {run_ids.validation_report}")
    print(f"  final audit: {run_ids.final_audit_json}")
    print(f"  submission manifest: {run_ids.submission_manifest_json}")

    try:
        run_pipeline_commands(commands, cwd=ROOT, dry_run=args.dry_run)
    except Exception as exc:
        print(f"pipeline failed: {exc}", file=sys.stderr)
        return 1

    print("\nlocal pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
