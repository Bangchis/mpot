"""Local benchmark pipeline orchestration.

This module ties the smaller scripts together for the final-project workflow:
run a sweep, generate plots, compare serial/MPI correctness, export artifact
bundles, export report tables, and validate everything before the report uses
the results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import shlex
import subprocess
import sys

from mpot.benchmarks.cli import parse_int_list
from mpot.benchmarks.report_bundle import slugify


@dataclass
class PipelineRunIds:
    """Deterministic run ids used by the pipeline for one selected N/P."""

    label: str
    final_n: int
    final_processes: int
    load_balance_n: int
    output_dir: str
    report_dir: str
    bundle_name: str
    submission_dir: str = "submission"

    @property
    def serial_run_id(self) -> str:
        return f"serial-{self.label}-N{self.final_n}"

    @property
    def mpi_run_id(self) -> str:
        return f"mpi-{self.label}-N{self.final_n}-P{self.final_processes}"

    @property
    def load_balance_mpi_run_id(self) -> str:
        return f"mpi-{self.label}-N{self.load_balance_n}-P{self.final_processes}"

    @property
    def compare_run_id(self) -> str:
        return f"compare-{self.label}-N{self.final_n}-P{self.final_processes}"

    @property
    def validation_run_id(self) -> str:
        return f"validation-{self.label}-N{self.final_n}-P{self.final_processes}"

    @property
    def serial_run_dir(self) -> str:
        return str(Path(self.output_dir) / self.serial_run_id)

    @property
    def mpi_run_dir(self) -> str:
        return str(Path(self.output_dir) / self.mpi_run_id)

    @property
    def load_balance_mpi_run_dir(self) -> str:
        return str(Path(self.output_dir) / self.load_balance_mpi_run_id)

    @property
    def correctness_report(self) -> str:
        return str(Path(self.output_dir) / self.compare_run_id / "correctness_report.json")

    @property
    def bundle_manifest(self) -> str:
        return str(Path(self.report_dir) / "artifacts" / self.bundle_name / "manifest.json")

    @property
    def tables_manifest(self) -> str:
        return str(Path(self.report_dir) / "tables" / f"tables_manifest_{self.label}.json")

    @property
    def runtime_figure_name(self) -> str:
        return f"runtime_vs_input_size_{self.label}.png"

    @property
    def speedup_figure_name(self) -> str:
        return f"speedup_{self.label}.png"

    @property
    def trajectory_gif_name(self) -> str:
        return f"trajectory_{self.label}.gif"

    @property
    def trajectory_gif(self) -> str:
        return str(Path(self.report_dir) / "figures" / self.trajectory_gif_name)

    @property
    def algorithm_trace_gif_name(self) -> str:
        return f"algorithm_trace_{self.label}.gif"

    @property
    def algorithm_trace_gif(self) -> str:
        return str(Path(self.report_dir) / "figures" / self.algorithm_trace_gif_name)

    @property
    def algorithm_trace_json(self) -> str:
        return str(Path(self.report_dir) / f"ALGORITHM_TRACE_{self.label}.json")

    @property
    def bundled_rank_breakdown_name(self) -> str:
        base = f"{self.bundle_name}_mpi_{slugify(self.load_balance_mpi_run_id)}_rank_time_breakdown"
        return f"{slugify(base)}.png"

    @property
    def validation_report(self) -> str:
        return str(Path(self.output_dir) / f"{self.validation_run_id}.json")

    @property
    def environment_json(self) -> str:
        return str(Path(self.output_dir) / f"environment-{self.label}.json")

    @property
    def environment_markdown(self) -> str:
        return str(Path(self.report_dir) / f"ENVIRONMENT_{self.label}.md")

    @property
    def ownership_json(self) -> str:
        return str(Path(self.report_dir) / "TEAM_OWNERSHIP_REPORT.json")

    @property
    def ownership_markdown(self) -> str:
        return str(Path(self.report_dir) / "TEAM_OWNERSHIP_REPORT.md")

    @property
    def defense_guide_json(self) -> str:
        return str(Path(self.report_dir) / "MEMBER_DEFENSE_GUIDE.json")

    @property
    def defense_guide_markdown(self) -> str:
        return str(Path(self.report_dir) / "MEMBER_DEFENSE_GUIDE.md")

    @property
    def granularity_json(self) -> str:
        return str(Path(self.output_dir) / f"granularity-{self.label}-N{self.load_balance_n}-P{self.final_processes}.json")

    @property
    def granularity_markdown(self) -> str:
        return str(Path(self.report_dir) / f"GRANULARITY_{self.label}.md")

    @property
    def communication_json(self) -> str:
        return str(Path(self.output_dir) / f"communication-{self.label}-N{self.final_n}-P{self.final_processes}.json")

    @property
    def communication_markdown(self) -> str:
        return str(Path(self.report_dir) / f"COMMUNICATION_{self.label}.md")

    @property
    def solution_quality_json(self) -> str:
        return str(Path(self.output_dir) / f"solution-quality-{self.label}-N{self.final_n}-P{self.final_processes}.json")

    @property
    def solution_quality_markdown(self) -> str:
        return str(Path(self.report_dir) / f"SOLUTION_QUALITY_{self.label}.md")

    @property
    def experiment_index_json(self) -> str:
        return str(Path(self.report_dir) / f"EXPERIMENT_INDEX_{self.label}.json")

    @property
    def experiment_index_markdown(self) -> str:
        return str(Path(self.report_dir) / f"EXPERIMENT_INDEX_{self.label}.md")

    @property
    def report_sync_json(self) -> str:
        return str(Path(self.report_dir) / f"REPORT_SYNC_{self.label}.json")

    @property
    def report_sync_markdown(self) -> str:
        return str(Path(self.report_dir) / f"REPORT_SYNC_{self.label}.md")

    @property
    def results_summary_json(self) -> str:
        return str(Path(self.report_dir) / f"RESULTS_SUMMARY_{self.label}.json")

    @property
    def results_summary_markdown(self) -> str:
        return str(Path(self.report_dir) / f"RESULTS_SUMMARY_{self.label}.md")

    @property
    def benchmark_budget_json(self) -> str:
        return str(Path(self.report_dir) / f"BENCHMARK_BUDGET_{self.label}.json")

    @property
    def benchmark_budget_markdown(self) -> str:
        return str(Path(self.report_dir) / f"BENCHMARK_BUDGET_{self.label}.md")

    @property
    def final_audit_json(self) -> str:
        return str(Path(self.report_dir) / f"FINAL_AUDIT_{self.label}.json")

    @property
    def final_audit_markdown(self) -> str:
        return str(Path(self.report_dir) / f"FINAL_AUDIT_{self.label}.md")

    @property
    def submission_manifest_json(self) -> str:
        return str(Path(self.submission_dir) / self.label / "SUBMISSION_MANIFEST.json")

    @property
    def submission_manifest_markdown(self) -> str:
        return str(Path(self.submission_dir) / self.label / "SUBMISSION_MANIFEST.md")


@dataclass
class PipelineCommand:
    """One command in the local benchmark pipeline."""

    name: str
    command: list[str]

    def display(self) -> str:
        return shlex.join(self.command)


def select_final_value(values: Iterable[int], requested: int | None, label: str) -> int:
    """Choose the largest value unless the caller explicitly selects one."""

    parsed = list(values)
    if not parsed:
        raise ValueError(f"{label} must not be empty.")
    if requested is None:
        return max(parsed)
    if requested not in parsed:
        raise ValueError(f"Requested {label}={requested} is not in {parsed}.")
    return requested


def build_pipeline_commands(
    *,
    python: str,
    config: str,
    input_sizes: list[int],
    process_counts: list[int],
    label: str,
    output_dir: str,
    report_dir: str,
    final_n: int,
    final_processes: int,
    bundle_name: str,
    skip_sweep: bool,
    skip_existing_runs: bool = False,
    load_balance_n: int | None = None,
    benchmark_plan: str | None = None,
    sweep_extra: list[str] | None = None,
    submission_dir: str = "submission",
) -> tuple[PipelineRunIds, list[PipelineCommand]]:
    """Build the commands required for one local benchmark pipeline run."""

    run_ids = PipelineRunIds(
        label=label,
        final_n=final_n,
        final_processes=final_processes,
        load_balance_n=load_balance_n or final_n,
        output_dir=output_dir,
        report_dir=report_dir,
        bundle_name=bundle_name,
        submission_dir=submission_dir,
    )
    commands: list[PipelineCommand] = []
    sweep_extra = sweep_extra or []

    commands.append(
        PipelineCommand(
            "capture environment",
            [
                python,
                "scripts/capture_environment.py",
                "--label",
                label,
                "--output",
                run_ids.environment_json,
                "--markdown",
                run_ids.environment_markdown,
            ],
        )
    )
    commands.append(
        PipelineCommand(
            "generate ownership report",
            [
                python,
                "scripts/generate_ownership_report.py",
                "--repo-root",
                ".",
                "--output",
                run_ids.ownership_json,
                "--markdown",
                run_ids.ownership_markdown,
            ],
        )
    )
    commands.append(
        PipelineCommand(
            "generate member defense guide",
            [
                python,
                "scripts/generate_defense_guide.py",
                "--repo-root",
                ".",
                "--output",
                run_ids.defense_guide_json,
                "--markdown",
                run_ids.defense_guide_markdown,
            ],
        )
    )

    validation_extra_args = []
    if benchmark_plan:
        validation_extra_args.extend(["--benchmark-plan", benchmark_plan])
        validation_extra_args.extend(["--benchmark-budget", run_ids.benchmark_budget_json])
        commands.append(
            PipelineCommand(
                "estimate benchmark budget",
                [
                    python,
                    "scripts/estimate_benchmark_budget.py",
                    "--plan",
                    benchmark_plan,
                    "--output",
                    run_ids.benchmark_budget_json,
                    "--markdown",
                    run_ids.benchmark_budget_markdown,
                    "--label",
                    label,
                    "--run-label",
                    label,
                    "--results-dir",
                    output_dir,
                ]
                + ([] if not skip_existing_runs else ["--reuse-existing"])
                + sweep_extra,
            )
        )

    if not skip_sweep:
        commands.append(
            PipelineCommand(
                "run sweep",
                [
                    python,
                    "scripts/run_sweep.py",
                    "--config",
                    config,
                    "--input-sizes",
                    ",".join(str(n) for n in input_sizes),
                    "--process-counts",
                    ",".join(str(p) for p in process_counts),
                    "--label",
                    label,
                    "--output-dir",
                    output_dir,
                ]
                + ([] if not skip_existing_runs else ["--skip-existing"])
                + sweep_extra,
            )
        )

    bundle_mpi_args = ["--mpi-run", run_ids.mpi_run_dir]
    if run_ids.load_balance_mpi_run_dir != run_ids.mpi_run_dir:
        bundle_mpi_args.extend(["--mpi-run", run_ids.load_balance_mpi_run_dir])

    commands.extend(
        [
            PipelineCommand(
                "plot aggregate figures",
                [
                    python,
                    "scripts/plot_results.py",
                    "--results",
                    output_dir,
                    "--output",
                    str(Path(report_dir) / "figures"),
                    "--label",
                    label,
                    "--input-size",
                    str(final_n),
                ],
            ),
            PipelineCommand(
                "compare serial and MPI",
                [
                    python,
                    "scripts/compare_serial_mpi.py",
                    "--serial",
                    run_ids.serial_run_dir,
                    "--mpi",
                    run_ids.mpi_run_dir,
                    "--output-dir",
                    output_dir,
                    "--run-id",
                    run_ids.compare_run_id,
                ],
            ),
            PipelineCommand(
                "animate best trajectory",
                [
                    python,
                    "scripts/animate_trajectory.py",
                    "--run-dir",
                    run_ids.mpi_run_dir,
                    "--output",
                    run_ids.trajectory_gif,
                ],
            ),
            PipelineCommand(
                "animate algorithm trace",
                [
                    python,
                    "scripts/animate_algorithm_trace.py",
                    "--run-dir",
                    run_ids.mpi_run_dir,
                    "--output",
                    run_ids.algorithm_trace_gif,
                    "--trace-output",
                    run_ids.algorithm_trace_json,
                ],
            ),
            PipelineCommand(
                "export report tables",
                [
                    python,
                    "scripts/export_result_tables.py",
                    "--results",
                    output_dir,
                    "--output",
                    str(Path(report_dir) / "tables"),
                    "--label",
                    label,
                    "--input-size",
                    str(final_n),
                    "--load-balance-run",
                    run_ids.load_balance_mpi_run_dir,
                ],
            ),
            PipelineCommand(
                "validate solution quality",
                [
                    python,
                    "scripts/validate_solution_quality.py",
                    "--run-dir",
                    run_ids.mpi_run_dir,
                    "--output",
                    run_ids.solution_quality_json,
                    "--markdown",
                    run_ids.solution_quality_markdown,
                    "--label",
                    label,
                ],
            ),
            PipelineCommand(
                "analyze granularity",
                [
                    python,
                    "scripts/analyze_granularity.py",
                    "--run-dir",
                    run_ids.load_balance_mpi_run_dir,
                    "--output",
                    run_ids.granularity_json,
                    "--markdown",
                    run_ids.granularity_markdown,
                    "--label",
                    label,
                ],
            ),
            PipelineCommand(
                "analyze communication",
                [
                    python,
                    "scripts/analyze_communication.py",
                    "--run-dir",
                    run_ids.mpi_run_dir,
                    "--output",
                    run_ids.communication_json,
                    "--markdown",
                    run_ids.communication_markdown,
                    "--label",
                    label,
                ],
            ),
            PipelineCommand(
                "export report artifact bundle",
                [
                    python,
                    "scripts/export_report_bundle.py",
                    "--bundle-name",
                    bundle_name,
                    "--clean",
                    "--serial-run",
                    run_ids.serial_run_dir,
                    *bundle_mpi_args,
                    "--correctness",
                    run_ids.correctness_report,
                    "--results",
                    output_dir,
                    "--report-dir",
                    report_dir,
                    "--label",
                    label,
                    "--input-size",
                    str(final_n),
                ],
            ),
            PipelineCommand(
                "index experiment artifacts",
                [
                    python,
                    "scripts/index_results.py",
                    "--results",
                    output_dir,
                    "--report-dir",
                    report_dir,
                    "--label",
                    label,
                    "--output",
                    run_ids.experiment_index_json,
                    "--markdown",
                    run_ids.experiment_index_markdown,
                ],
            ),
            PipelineCommand(
                "check report sync",
                [
                    python,
                    "scripts/check_report_sync.py",
                    "--label",
                    label,
                    "--output",
                    run_ids.report_sync_json,
                    "--markdown",
                    run_ids.report_sync_markdown,
                ],
            ),
            PipelineCommand(
                "export results summary",
                [
                    python,
                    "scripts/export_results_summary.py",
                    "--label",
                    label,
                    "--serial-run",
                    run_ids.serial_run_dir,
                    "--mpi-run",
                    run_ids.mpi_run_dir,
                    "--correctness",
                    run_ids.correctness_report,
                    "--tables-manifest",
                    run_ids.tables_manifest,
                    "--granularity",
                    run_ids.granularity_json,
                    "--communication",
                    run_ids.communication_json,
                    "--solution-quality",
                    run_ids.solution_quality_json,
                    "--output",
                    run_ids.results_summary_json,
                    "--markdown",
                    run_ids.results_summary_markdown,
                    "--figure",
                    str(Path(report_dir) / "figures" / run_ids.runtime_figure_name),
                    "--figure",
                    str(Path(report_dir) / "figures" / run_ids.speedup_figure_name),
                    "--figure",
                    str(Path(report_dir) / "figures" / run_ids.bundled_rank_breakdown_name),
                    "--figure",
                    run_ids.trajectory_gif,
                    "--figure",
                    run_ids.algorithm_trace_gif,
                ]
                + ([] if not benchmark_plan else ["--benchmark-budget", run_ids.benchmark_budget_json]),
            ),
            PipelineCommand(
                "validate report artifacts",
                [
                    python,
                    "scripts/validate_results.py",
                    "--serial-run",
                    run_ids.serial_run_dir,
                    "--mpi-run",
                    run_ids.mpi_run_dir,
                    "--correctness",
                    run_ids.correctness_report,
                    "--figures",
                    str(Path(report_dir) / "figures"),
                    "--required-figure",
                    run_ids.runtime_figure_name,
                    "--required-figure",
                    run_ids.speedup_figure_name,
                    "--required-figure",
                    run_ids.bundled_rank_breakdown_name,
                    "--bundle-manifest",
                    run_ids.bundle_manifest,
                    "--tables-manifest",
                    run_ids.tables_manifest,
                    "--results-summary",
                    run_ids.results_summary_json,
                    "--environment",
                    run_ids.environment_json,
                    "--granularity",
                    run_ids.granularity_json,
                    "--communication",
                    run_ids.communication_json,
                    "--solution-quality",
                    run_ids.solution_quality_json,
                    "--ownership",
                    run_ids.ownership_json,
                    "--defense-guide",
                    run_ids.defense_guide_json,
                    "--experiment-index",
                    run_ids.experiment_index_json,
                    "--report-sync",
                    run_ids.report_sync_json,
                    *validation_extra_args,
                    "--sweep-label",
                    label,
                    "--results",
                    output_dir,
                    "--output",
                    run_ids.validation_report,
                ],
            ),
            PipelineCommand(
                "audit final experiment readiness",
                [
                    python,
                    "scripts/audit_final_results.py",
                    "--results",
                    output_dir,
                    "--report-dir",
                    report_dir,
                    "--label",
                    label,
                    "--input-sizes",
                    ",".join(str(n) for n in input_sizes),
                    "--process-counts",
                    ",".join(str(p) for p in process_counts),
                    "--n",
                    str(run_ids.load_balance_n),
                    "--speedup-n",
                    str(run_ids.final_n),
                    "--final-processes",
                    str(final_processes),
                    "--bundle-name",
                    bundle_name,
                    "--validation",
                    run_ids.validation_report,
                    "--communication",
                    run_ids.communication_json,
                    "--solution-quality",
                    run_ids.solution_quality_json,
                    "--ownership",
                    run_ids.ownership_json,
                    "--defense-guide",
                    run_ids.defense_guide_json,
                    "--output",
                    run_ids.final_audit_json,
                    "--markdown",
                    run_ids.final_audit_markdown,
                ]
                + ([] if not benchmark_plan else ["--benchmark-plan", benchmark_plan]),
            ),
            PipelineCommand(
                "export submission package",
                [
                    python,
                    "scripts/export_submission_package.py",
                    "--label",
                    label,
                    "--report-dir",
                    report_dir,
                    "--docs-dir",
                    "docs",
                    "--output-dir",
                    run_ids.submission_dir,
                    "--clean",
                ],
            ),
        ]
    )
    return run_ids, commands


def run_pipeline_commands(commands: list[PipelineCommand], *, cwd: str | Path, dry_run: bool) -> None:
    """Run or print the pipeline commands in order."""

    for item in commands:
        print(f"\n[{item.name}]", flush=True)
        print("+ " + item.display(), flush=True)
        if not dry_run:
            subprocess.run(item.command, cwd=cwd, check=True)


def parse_pipeline_ints(value: str, name: str) -> list[int]:
    """Parse a comma-separated integer list with a friendlier error message."""

    try:
        return parse_int_list(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {name}: {value}") from exc


def default_python() -> str:
    """Return the current Python executable used for child scripts."""

    return sys.executable
