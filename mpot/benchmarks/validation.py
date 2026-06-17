"""Validate experiment artifacts before they are used in the report.

The report rubric asks for correctness, runtime-vs-N, granularity, and speedup
evidence. This module checks whether a result set contains the files needed for
those claims and writes a small JSON validation report.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mpot.benchmarks.artifacts import read_json, write_json
from mpot.benchmarks.plots import collect_summaries


@dataclass
class ValidationItem:
    """One pass/fail item in a report artifact validation."""

    name: str
    passed: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }


def _exists(path: Path, name: str) -> ValidationItem:
    return ValidationItem(name=name, passed=path.exists(), detail=str(path))


def validate_run_dir(run_dir: str | Path, require_rank_timings: bool) -> list[ValidationItem]:
    """Validate one serial or MPI run directory."""

    root = Path(run_dir)
    items = [
        _exists(root / "summary.json", "summary.json exists"),
        _exists(root / "task_results.csv", "task_results.csv exists"),
        _exists(root / "task_results.json", "task_results.json exists"),
        _exists(root / "best_trajectory.npy", "best_trajectory.npy exists"),
        _exists(root / "best_path.png", "best_path.png exists"),
        _exists(root / "cost_by_task.png", "cost_by_task.png exists"),
    ]
    if require_rank_timings:
        items.append(_exists(root / "rank_timings.csv", "rank_timings.csv exists"))
        items.append(_exists(root / "comm_events.csv", "comm_events.csv exists"))
        items.append(_exists(root / "task_assignment.csv", "task_assignment.csv exists"))
        items.append(_exists(root / "rank_time_breakdown.png", "rank_time_breakdown.png exists"))

    summary_path = root / "summary.json"
    if summary_path.exists():
        summary = read_json(summary_path)
        expected_mode = "mpi" if require_rank_timings else "serial"
        items.append(
            ValidationItem(
                name=f"summary mode is {expected_mode}",
                passed=summary.get("mode") == expected_mode,
                detail=f"mode={summary.get('mode')}",
            )
        )
        items.append(
            ValidationItem(
                name="summary has total_tasks",
                passed=int(summary.get("total_tasks", 0)) > 0,
                detail=f"total_tasks={summary.get('total_tasks')}",
            )
        )
        items.append(
            ValidationItem(
                name="summary has best_cost",
                passed="best_cost" in summary,
                detail=f"best_cost={summary.get('best_cost')}",
            )
        )
        if require_rank_timings:
            assignment = summary.get("task_assignment")
            items.append(
                ValidationItem(
                    name="summary has task assignment",
                    passed=isinstance(assignment, list) and bool(assignment),
                    detail=f"assignment_rows={len(assignment) if isinstance(assignment, list) else 0}",
                )
            )
            comm_events_count = int(summary.get("communication_events_count", 0))
            items.append(
                ValidationItem(
                    name="summary has communication events",
                    passed=comm_events_count > 0,
                    detail=f"communication_events_count={comm_events_count}",
                )
            )
    return items


def validate_correctness_report(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/compare_serial_mpi.py."""

    report_path = Path(path)
    items = [_exists(report_path, "correctness_report.json exists")]
    if report_path.exists():
        payload = read_json(report_path)
        items.extend(
            [
                ValidationItem("correctness passed", bool(payload.get("passed")), f"passed={payload.get('passed')}"),
                ValidationItem(
                    "same best task",
                    bool(payload.get("same_best_task")),
                    f"same_best_task={payload.get('same_best_task')}",
                ),
                ValidationItem(
                    "same best seed",
                    bool(payload.get("same_best_seed")),
                    f"same_best_seed={payload.get('same_best_seed')}",
                ),
            ]
        )
        if "same_total_tasks" in payload:
            items.append(
                ValidationItem(
                    "same total tasks",
                    bool(payload.get("same_total_tasks")),
                    f"same_total_tasks={payload.get('same_total_tasks')}",
                )
            )
        task_level = payload.get("task_level")
        if isinstance(task_level, dict):
            items.extend(
                [
                    ValidationItem(
                        "task-level correctness passed",
                        bool(task_level.get("tasks_passed")),
                        f"tasks_passed={task_level.get('tasks_passed')}",
                    ),
                    ValidationItem(
                        "same task ids",
                        bool(task_level.get("same_task_ids")),
                        f"same_task_ids={task_level.get('same_task_ids')}",
                    ),
                    ValidationItem(
                        "all task seeds match",
                        bool(task_level.get("all_seeds_match")),
                        f"all_seeds_match={task_level.get('all_seeds_match')}",
                    ),
                    ValidationItem(
                        "all task costs close",
                        bool(task_level.get("all_task_costs_close")),
                        f"all_task_costs_close={task_level.get('all_task_costs_close')}",
                    ),
                ]
            )
        if payload.get("task_comparison_csv"):
            items.append(_exists(Path(payload["task_comparison_csv"]), "task_comparison.csv exists"))
    return items


def validate_report_figures(figures_dir: str | Path, required_names: list[str]) -> list[ValidationItem]:
    """Validate report figure files."""

    root = Path(figures_dir)
    return [_exists(root / name, f"figure {name} exists") for name in required_names]


def validate_report_bundle(manifest_path: str | Path) -> list[ValidationItem]:
    """Validate a report artifact bundle manifest.

    The manifest is useful only if every copied/generated destination still
    exists. Sources that are literal files are also checked; generated plot
    sources are descriptions such as "generated from results" and are skipped.
    """

    path = Path(manifest_path)
    items = [_exists(path, "report artifact manifest exists")]
    if not path.exists():
        return items

    payload = read_json(path)
    entries = payload.get("entries", [])
    items.append(
        ValidationItem(
            name="report artifact manifest has entries",
            passed=bool(entries),
            detail=f"entries={len(entries)}",
        )
    )

    for index, entry in enumerate(entries):
        destination = Path(str(entry.get("destination", "")))
        role = str(entry.get("role", f"entry {index}"))
        items.append(
            ValidationItem(
                name=f"bundle destination exists: {role}",
                passed=destination.exists(),
                detail=str(destination),
            )
        )

        source_text = str(entry.get("source", ""))
        if source_text.startswith("generated from") or source_text.startswith("would generate"):
            continue
        source = Path(source_text)
        items.append(
            ValidationItem(
                name=f"bundle source exists: {role}",
                passed=source.exists(),
                detail=str(source),
            )
        )
    return items


def validate_result_tables_manifest(manifest_path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/export_result_tables.py."""

    path = Path(manifest_path)
    items = [_exists(path, "result tables manifest exists")]
    if not path.exists():
        return items

    payload = read_json(path)
    paths = payload.get("paths", {})
    for key in ["runtime_csv", "speedup_csv", "load_balance_csv", "markdown", "manifest_json"]:
        value = paths.get(key)
        if not value:
            items.append(ValidationItem(f"result table path recorded: {key}", False, "missing"))
            continue
        items.append(_exists(Path(value), f"result table file exists: {key}"))

    for key in ["num_runtime_rows", "num_speedup_rows", "num_load_balance_rows"]:
        count = int(payload.get(key, 0))
        items.append(
            ValidationItem(
                name=f"result table has rows: {key}",
                passed=count > 0,
                detail=f"{key}={count}",
            )
        )
    return items


def validate_results_summary(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/export_results_summary.py."""

    summary_path = Path(path)
    items = [_exists(summary_path, "results summary exists")]
    if not summary_path.exists():
        return items

    payload = read_json(summary_path)
    sources = payload.get("sources", {})
    checks = payload.get("checks", [])
    failed_checks = [check for check in checks if not check.get("passed")]
    items.extend(
        [
            ValidationItem(
                "results summary passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, num_failed={payload.get('num_failed')}",
            ),
            ValidationItem(
                "results summary has checks",
                bool(checks),
                f"checks={len(checks)}, failed={len(failed_checks)}",
            ),
            ValidationItem(
                "results summary has source paths",
                bool(sources),
                f"sources={len(sources) if isinstance(sources, dict) else 0}",
            ),
            ValidationItem(
                "results summary is artifact-derived",
                "existing benchmark artifacts" in str(payload.get("note", "")),
                str(payload.get("note", "")),
            ),
        ]
    )

    for key, source in sources.items():
        if key == "figures":
            for index, figure in enumerate(source):
                path_text = str(figure.get("path", ""))
                items.append(_exists(Path(path_text), f"results summary figure source exists {index}"))
            continue
        path_text = str(source.get("path", ""))
        if path_text:
            items.append(_exists(Path(path_text), f"results summary source exists: {key}"))
    return items


def validate_environment_report(path: str | Path) -> list[ValidationItem]:
    """Validate environment JSON from scripts/capture_environment.py."""

    report_path = Path(path)
    items = [_exists(report_path, "environment report exists")]
    if not report_path.exists():
        return items

    payload = read_json(report_path)
    packages = payload.get("packages", [])
    mpi = payload.get("mpi", {})
    items.extend(
        [
            ValidationItem(
                "environment has python version",
                bool(payload.get("python", {}).get("version")),
                f"python={payload.get('python', {}).get('version')}",
            ),
            ValidationItem(
                "environment has platform",
                bool(payload.get("platform", {}).get("system")),
                f"system={payload.get('platform', {}).get('system')}",
            ),
            ValidationItem(
                "environment has package rows",
                bool(packages),
                f"packages={len(packages)}",
            ),
            ValidationItem(
                "environment has mpi section",
                bool(mpi),
                f"mpi_keys={sorted(mpi.keys()) if isinstance(mpi, dict) else []}",
            ),
        ]
    )
    missing_packages = [p.get("name", "") for p in packages if not p.get("installed")]
    items.append(
        ValidationItem(
            "required python packages installed",
            not missing_packages,
            f"missing={missing_packages}",
        )
    )
    return items


def validate_benchmark_plan(path: str | Path) -> list[ValidationItem]:
    """Validate JSON output from scripts/plan_benchmark.py."""

    plan_path = Path(path)
    items = [_exists(plan_path, "benchmark plan exists")]
    if not plan_path.exists():
        return items

    payload = read_json(plan_path)
    input_sizes = [int(v) for v in payload.get("input_sizes", [])]
    process_counts = [int(v) for v in payload.get("process_counts", [])]
    chosen_n = int(payload.get("chosen_n", 0))
    speedup_n = int(payload.get("speedup_n", 0))
    command = payload.get("pipeline_command", [])
    items.extend(
        [
            ValidationItem("benchmark plan has positive N", chosen_n > 0, f"chosen_n={chosen_n}"),
            ValidationItem("benchmark plan has 2N", speedup_n == 2 * chosen_n, f"speedup_n={speedup_n}"),
            ValidationItem(
                "benchmark plan input sizes include N",
                chosen_n in input_sizes,
                f"input_sizes={input_sizes}",
            ),
            ValidationItem(
                "benchmark plan input sizes include 2N",
                speedup_n in input_sizes,
                f"input_sizes={input_sizes}",
            ),
            ValidationItem(
                "benchmark plan process counts include 1",
                1 in process_counts,
                f"process_counts={process_counts}",
            ),
            ValidationItem(
                "benchmark plan has pipeline command",
                bool(command),
                " ".join(str(v) for v in command),
            ),
        ]
    )
    return items


def validate_benchmark_budget(path: str | Path) -> list[ValidationItem]:
    """Validate JSON output from scripts/estimate_benchmark_budget.py."""

    budget_path = Path(path)
    items = [_exists(budget_path, "benchmark budget exists")]
    if not budget_path.exists():
        return items

    payload = read_json(budget_path)
    rows = payload.get("rows", [])
    total = float(payload.get("estimated_total_seconds", 0.0))
    remaining = float(payload.get("estimated_remaining_seconds", total))
    largest = float(payload.get("largest_run_seconds", 0.0))
    largest_remaining = float(payload.get("largest_remaining_run_seconds", largest))
    valid_statuses = {"planned", "reusable", "missing_or_mismatch"}
    row_statuses = [str(row.get("status", "")) for row in rows if isinstance(row, dict)]
    items.extend(
        [
            ValidationItem(
                "benchmark budget passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, warnings={payload.get('warnings', [])}",
            ),
            ValidationItem(
                "benchmark budget has planned rows",
                bool(rows),
                f"rows={len(rows)}",
            ),
            ValidationItem(
                "benchmark budget total is positive",
                total > 0.0,
                f"estimated_total_seconds={total}",
            ),
            ValidationItem(
                "benchmark budget largest run is positive",
                largest > 0.0,
                f"largest_run_seconds={largest}",
            ),
            ValidationItem(
                "benchmark budget remaining time is non-negative",
                0.0 <= remaining <= total,
                f"estimated_remaining_seconds={remaining}, estimated_total_seconds={total}",
            ),
            ValidationItem(
                "benchmark budget largest remaining run is non-negative",
                0.0 <= largest_remaining <= largest,
                f"largest_remaining_run_seconds={largest_remaining}, largest_run_seconds={largest}",
            ),
            ValidationItem(
                "benchmark budget rows have reuse status",
                bool(rows) and all(status in valid_statuses for status in row_statuses),
                f"statuses={sorted(set(row_statuses))}",
            ),
            ValidationItem(
                "benchmark budget warns it is not measured data",
                "not" in str(payload.get("note", "")).lower()
                and "result" in str(payload.get("note", "")).lower(),
                str(payload.get("note", "")),
            ),
        ]
    )
    return items


def validate_granularity_analysis(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/analyze_granularity.py."""

    analysis_path = Path(path)
    items = [_exists(analysis_path, "granularity analysis exists")]
    if not analysis_path.exists():
        return items

    payload = read_json(analysis_path)
    rank_rows = payload.get("rank_rows", [])
    items.extend(
        [
            ValidationItem(
                "granularity has rank rows",
                bool(rank_rows),
                f"rank_rows={len(rank_rows)}",
            ),
            ValidationItem(
                "granularity has idle fraction",
                "idle_fraction" in payload,
                f"idle_fraction={payload.get('idle_fraction')}",
            ),
            ValidationItem(
                "granularity has recommendation",
                bool(payload.get("recommendation")),
                str(payload.get("recommendation", "")),
            ),
            ValidationItem(
                "granularity threshold is valid",
                0 < float(payload.get("threshold", 0)) <= 1,
                f"threshold={payload.get('threshold')}",
            ),
        ]
    )
    return items


def validate_communication_analysis(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/analyze_communication.py."""

    analysis_path = Path(path)
    items = [_exists(analysis_path, "communication analysis exists")]
    if not analysis_path.exists():
        return items

    payload = read_json(analysis_path)
    event_rows = payload.get("event_rows", [])
    observed = set(payload.get("observed_collectives", []))
    items.extend(
        [
            ValidationItem(
                "communication has event rows",
                bool(event_rows),
                f"event_rows={len(event_rows)}",
            ),
            ValidationItem(
                "communication events are blocking",
                bool(payload.get("all_events_blocking")),
                f"all_events_blocking={payload.get('all_events_blocking')}",
            ),
            ValidationItem(
                "communication has bcast/scatter/gather",
                {"bcast", "scatter", "gather"}.issubset(observed),
                f"observed={sorted(observed)}",
            ),
            ValidationItem(
                "communication topology recorded",
                bool(payload.get("topology")),
                str(payload.get("topology", "")),
            ),
        ]
    )
    return items


def validate_solution_quality_report(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/validate_solution_quality.py."""

    report_path = Path(path)
    items = [_exists(report_path, "solution quality report exists")]
    if not report_path.exists():
        return items

    payload = read_json(report_path)
    checks = payload.get("checks", [])
    items.extend(
        [
            ValidationItem(
                "solution quality passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, num_failed={payload.get('num_failed')}",
            ),
            ValidationItem(
                "solution quality has checks",
                bool(checks),
                f"checks={len(checks)}",
            ),
            ValidationItem(
                "solution reaches goal",
                float(payload.get("goal_error", 1.0e9)) <= 1.0e-3,
                f"goal_error={payload.get('goal_error')}",
            ),
            ValidationItem(
                "solution collision-free",
                float(payload.get("hard_collision_fraction", 1.0)) <= 0.0,
                f"hard_collision_fraction={payload.get('hard_collision_fraction')}",
            ),
        ]
    )
    return items


def validate_ownership_report(
    path: str | Path,
    minimum_lines_per_member: int = 250,
    recommended_max_lines_per_member: int = 700,
) -> list[ValidationItem]:
    """Validate output from scripts/generate_ownership_report.py."""

    report_path = Path(path)
    items = [_exists(report_path, "team ownership report exists")]
    if not report_path.exists():
        return items

    payload = read_json(report_path)
    members = payload.get("members", [])
    failed_members = [member.get("member", "") for member in members if not member.get("passed")]
    oversized_members = [
        member.get("member", "")
        for member in members
        if int(member.get("meaningful_lines", 0)) > int(recommended_max_lines_per_member)
    ]
    duplicate_files = payload.get("duplicate_files", [])
    items.extend(
        [
            ValidationItem(
                "team ownership report passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, failed_members={failed_members}",
            ),
            ValidationItem(
                "team ownership has four members",
                int(payload.get("num_members", 0)) == 4,
                f"num_members={payload.get('num_members')}",
            ),
            ValidationItem(
                "each member reaches LOC threshold",
                not failed_members,
                f"minimum={minimum_lines_per_member}, failed_members={failed_members}",
            ),
            ValidationItem(
                "each member stays within readable size",
                not oversized_members,
                f"recommended_max={recommended_max_lines_per_member}, oversized_members={oversized_members}",
            ),
            ValidationItem(
                "team ownership has no duplicate counted files",
                not duplicate_files,
                f"duplicates={duplicate_files}",
            ),
            ValidationItem(
                "team total reaches 1000 LOC target",
                int(payload.get("total_meaningful_lines", 0)) >= 4 * int(minimum_lines_per_member),
                f"total_meaningful_lines={payload.get('total_meaningful_lines')}",
            ),
        ]
    )
    return items


def validate_defense_guide(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/generate_defense_guide.py."""

    guide_path = Path(path)
    items = [_exists(guide_path, "member defense guide exists")]
    if not guide_path.exists():
        return items

    payload = read_json(guide_path)
    members = payload.get("members", [])
    missing_files = payload.get("missing_files", [])
    members_without_files = [member.get("member", "") for member in members if not member.get("files")]
    members_without_commands = [member.get("member", "") for member in members if not member.get("demo_commands")]
    members_without_questions = [member.get("member", "") for member in members if not member.get("practice_questions")]
    items.extend(
        [
            ValidationItem(
                "member defense guide passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, missing_files={missing_files}",
            ),
            ValidationItem(
                "member defense guide has four members",
                int(payload.get("num_members", 0)) == 4,
                f"num_members={payload.get('num_members')}",
            ),
            ValidationItem(
                "each member has defense files",
                not members_without_files,
                f"members_without_files={members_without_files}",
            ),
            ValidationItem(
                "each member has demo commands",
                not members_without_commands,
                f"members_without_commands={members_without_commands}",
            ),
            ValidationItem(
                "each member has practice questions",
                not members_without_questions,
                f"members_without_questions={members_without_questions}",
            ),
        ]
    )
    return items


def validate_experiment_index(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/index_results.py."""

    index_path = Path(path)
    items = [_exists(index_path, "experiment index exists")]
    if not index_path.exists():
        return items

    payload = read_json(index_path)
    counts = payload.get("counts", {})
    items.extend(
        [
            ValidationItem(
                "experiment index has runs",
                int(counts.get("runs", 0)) > 0,
                f"runs={counts.get('runs')}",
            ),
            ValidationItem(
                "experiment index has mpi runs",
                int(counts.get("mpi_runs", 0)) > 0,
                f"mpi_runs={counts.get('mpi_runs')}",
            ),
            ValidationItem(
                "experiment index has serial runs",
                int(counts.get("serial_runs", 0)) > 0,
                f"serial_runs={counts.get('serial_runs')}",
            ),
        ]
    )
    return items


def validate_submission_package_manifest(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/export_submission_package.py."""

    manifest_path = Path(path)
    items = [_exists(manifest_path, "submission package manifest exists")]
    if not manifest_path.exists():
        return items

    payload = read_json(manifest_path)
    entries = payload.get("entries", [])
    required_entries = [entry for entry in entries if entry.get("required")]
    missing_required = [entry for entry in required_entries if not entry.get("exists")]
    items.extend(
        [
            ValidationItem(
                "submission package passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, missing={payload.get('num_missing_required')}",
            ),
            ValidationItem(
                "submission package has entries",
                bool(entries),
                f"entries={len(entries)}",
            ),
            ValidationItem(
                "submission package has required entries",
                bool(required_entries),
                f"required_entries={len(required_entries)}",
            ),
            ValidationItem(
                "submission package final audit ready",
                payload.get("final_ready") is not False,
                f"final_ready={payload.get('final_ready')}",
            ),
            ValidationItem(
                "submission package has no missing required files",
                not missing_required,
                f"missing_required={len(missing_required)}",
            ),
        ]
    )

    for entry in entries:
        destination = Path(str(entry.get("destination", "")))
        role = str(entry.get("role", "entry"))
        if entry.get("exists"):
            items.append(_exists(destination, f"submission destination exists: {role}"))
    return items


def validate_report_sync(path: str | Path) -> list[ValidationItem]:
    """Validate output from scripts/check_report_sync.py."""

    sync_path = Path(path)
    items = [_exists(sync_path, "report sync check exists")]
    if not sync_path.exists():
        return items

    payload = read_json(sync_path)
    items.extend(
        [
            ValidationItem(
                "report sync passed",
                bool(payload.get("passed")),
                f"passed={payload.get('passed')}, missing={payload.get('num_missing')}",
            ),
            ValidationItem(
                "report sync checked references",
                int(payload.get("num_checked", 0)) > 0,
                f"num_checked={payload.get('num_checked')}",
            ),
            ValidationItem(
                "report sync has no missing concrete paths",
                int(payload.get("num_missing", 0)) == 0,
                f"num_missing={payload.get('num_missing')}",
            ),
        ]
    )
    return items


def validate_sweep_coverage(results_dir: str | Path, label: str, min_process_counts: int = 2) -> list[ValidationItem]:
    """Check that a sweep has enough runs to support speedup plots."""

    summaries = collect_summaries(results_dir, label=label, mode="mpi")
    process_counts = sorted({int(s["size"]) for s in summaries})
    input_sizes = sorted({int(s["total_tasks"]) for s in summaries})
    return [
        ValidationItem(
            name="sweep has MPI summaries",
            passed=bool(summaries),
            detail=f"count={len(summaries)}",
        ),
        ValidationItem(
            name="sweep has multiple process counts",
            passed=len(process_counts) >= min_process_counts,
            detail=f"process_counts={process_counts}",
        ),
        ValidationItem(
            name="sweep has at least one input size",
            passed=bool(input_sizes),
            detail=f"input_sizes={input_sizes}",
        ),
    ]


def validation_summary(items: list[ValidationItem]) -> dict[str, Any]:
    """Return a JSON-friendly aggregate validation summary."""

    failed = [item for item in items if not item.passed]
    return {
        "passed": not failed,
        "num_items": len(items),
        "num_failed": len(failed),
        "items": [item.to_json() for item in items],
    }


def write_validation_report(path: str | Path, items: list[ValidationItem]) -> dict[str, Any]:
    """Write validation summary JSON and return it."""

    payload = validation_summary(items)
    write_json(path, payload)
    return payload
