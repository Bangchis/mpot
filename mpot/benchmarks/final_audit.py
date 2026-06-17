"""Audit whether a benchmark run is ready for the final report.

The normal validation step checks individual files. This module checks the
course-rubric shape of the whole experiment: selected input sizes, process
counts, speedup baseline, correctness report, solution-quality report,
communication analysis, ownership/defense evidence, load-balance analysis, and
report artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import time

from mpot.benchmarks.artifacts import read_json, write_json
from mpot.benchmarks.plots import collect_summaries
from mpot.benchmarks.report_bundle import slugify


@dataclass
class AuditItem:
    """One final-report readiness check."""

    name: str
    passed: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }


def _exists(path: str | Path, name: str) -> AuditItem:
    candidate = Path(path)
    return AuditItem(name=name, passed=candidate.exists(), detail=str(candidate))


def _summary_key(summary: dict[str, Any]) -> tuple[int, int, str]:
    return (int(summary.get("total_tasks", 0)), int(summary.get("size", 0)), str(summary.get("mode", "")))


def _summary_exists(summaries: list[dict[str, Any]], *, mode: str, n: int, processes: int | None = None) -> bool:
    for summary in summaries:
        if summary.get("mode") != mode:
            continue
        if int(summary.get("total_tasks", 0)) != int(n):
            continue
        if processes is not None and int(summary.get("size", 0)) != int(processes):
            continue
        return True
    return False


def _process_counts_for_n(summaries: list[dict[str, Any]], *, n: int) -> list[int]:
    return sorted(
        {
            int(summary.get("size", 0))
            for summary in summaries
            if summary.get("mode") == "mpi" and int(summary.get("total_tasks", 0)) == int(n)
        }
    )


def _input_sizes_for_processes(summaries: list[dict[str, Any]], *, processes: int) -> list[int]:
    return sorted(
        {
            int(summary.get("total_tasks", 0))
            for summary in summaries
            if summary.get("mode") == "mpi" and int(summary.get("size", 0)) == int(processes)
        }
    )


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _validation_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "pipeline validation report exists")
    return AuditItem(
        name="pipeline validation passed",
        passed=bool(payload.get("passed")),
        detail=f"passed={payload.get('passed')}, num_failed={payload.get('num_failed')}",
    )


def _correctness_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "correctness report exists")
    task_level = payload.get("task_level", {})
    return AuditItem(
        name="serial/MPI correctness passed",
        passed=bool(payload.get("passed")) and bool(task_level.get("tasks_passed", True)),
        detail=f"passed={payload.get('passed')}, task_level={task_level.get('tasks_passed', 'not recorded')}",
    )


def _granularity_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "granularity analysis exists")
    return AuditItem(
        name="granularity under 25 percent threshold",
        passed=bool(payload.get("balanced_under_threshold")),
        detail=f"idle_fraction={payload.get('idle_fraction')}, threshold={payload.get('threshold')}",
    )


def _communication_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "communication analysis exists")
    observed = set(payload.get("observed_collectives", []))
    return AuditItem(
        name="communication analysis passed",
        passed=bool(payload.get("has_expected_collectives")) and bool(payload.get("all_events_blocking")),
        detail=(
            f"has_expected_collectives={payload.get('has_expected_collectives')}, "
            f"all_events_blocking={payload.get('all_events_blocking')}, "
            f"observed={sorted(observed)}"
        ),
    )


def _solution_quality_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "solution quality report exists")
    goal_error = float(payload.get("goal_error", 1.0e9))
    collision_fraction = float(payload.get("hard_collision_fraction", 1.0))
    return AuditItem(
        name="solution quality passed",
        passed=bool(payload.get("passed")) and goal_error <= 1.0e-3 and collision_fraction <= 0.0,
        detail=(
            f"passed={payload.get('passed')}, "
            f"num_failed={payload.get('num_failed')}, "
            f"goal_error={payload.get('goal_error')}, "
            f"hard_collision_fraction={payload.get('hard_collision_fraction')}"
        ),
    )


def _ownership_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "team ownership report exists")
    members = payload.get("members", [])
    member_lines = {
        str(member.get("member", "")): int(member.get("meaningful_lines", 0))
        for member in members
    }
    return AuditItem(
        name="team ownership report passed",
        passed=bool(payload.get("passed")) and int(payload.get("num_members", 0)) == 4,
        detail=(
            f"passed={payload.get('passed')}, "
            f"num_members={payload.get('num_members')}, "
            f"minimum={payload.get('minimum_lines_per_member')}, "
            f"recommended_max={payload.get('recommended_max_lines_per_member')}, "
            f"member_lines={member_lines}"
        ),
    )


def _defense_guide_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "member defense guide exists")
    members = payload.get("members", [])
    return AuditItem(
        name="member defense guide passed",
        passed=bool(payload.get("passed")) and int(payload.get("num_members", 0)) == 4,
        detail=(
            f"passed={payload.get('passed')}, "
            f"num_members={payload.get('num_members')}, "
            f"member_files={[len(member.get('files', [])) for member in members]}"
        ),
    )


def _table_manifest_passed(path: Path) -> AuditItem:
    payload = _load_json_if_exists(path)
    if not payload:
        return _exists(path, "result tables manifest exists")
    counts = {
        key: int(payload.get(key, 0))
        for key in ["num_runtime_rows", "num_speedup_rows", "num_load_balance_rows"]
    }
    return AuditItem(
        name="result tables have rows",
        passed=all(value > 0 for value in counts.values()),
        detail=str(counts),
    )


def build_final_audit(
    *,
    results_dir: str | Path = "results",
    report_dir: str | Path = "report",
    label: str,
    input_sizes: list[int],
    process_counts: list[int],
    n: int,
    speedup_n: int,
    final_processes: int,
    bundle_name: str | None = None,
    validation_report: str | Path | None = None,
    benchmark_plan: str | Path | None = None,
    communication_report: str | Path | None = None,
    solution_quality_report: str | Path | None = None,
    ownership_report: str | Path | None = None,
    defense_guide: str | Path | None = None,
) -> dict[str, Any]:
    """Build a final-report readiness audit payload."""

    results_root = Path(results_dir)
    report_root = Path(report_dir)
    bundle_name = bundle_name or label
    summaries = sorted(collect_summaries(results_root, label=label), key=_summary_key)
    mpi_summaries = [summary for summary in summaries if summary.get("mode") == "mpi"]
    serial_summaries = [summary for summary in summaries if summary.get("mode") == "serial"]

    expected_input_sizes = sorted({int(value) for value in input_sizes})
    expected_process_counts = sorted({int(value) for value in process_counts})
    speedup_counts = _process_counts_for_n(summaries, n=speedup_n)
    runtime_sizes = _input_sizes_for_processes(summaries, processes=final_processes)

    compare_path = results_root / f"compare-{label}-N{speedup_n}-P{final_processes}" / "correctness_report.json"
    communication_path = (
        Path(communication_report)
        if communication_report
        else results_root / f"communication-{label}-N{speedup_n}-P{final_processes}.json"
    )
    solution_quality_path = (
        Path(solution_quality_report)
        if solution_quality_report
        else results_root / f"solution-quality-{label}-N{speedup_n}-P{final_processes}.json"
    )
    ownership_path = Path(ownership_report) if ownership_report else report_root / "TEAM_OWNERSHIP_REPORT.json"
    defense_guide_path = Path(defense_guide) if defense_guide else report_root / "MEMBER_DEFENSE_GUIDE.json"
    granularity_path = results_root / f"granularity-{label}-N{n}-P{final_processes}.json"
    validation_path = Path(validation_report) if validation_report else results_root / f"validation-{label}-N{speedup_n}-P{final_processes}.json"
    bundle_manifest = report_root / "artifacts" / bundle_name / "manifest.json"
    tables_manifest = report_root / "tables" / f"tables_manifest_{label}.json"
    results_summary = report_root / f"RESULTS_SUMMARY_{label}.json"
    environment_json = results_root / f"environment-{label}.json"
    experiment_index = report_root / f"EXPERIMENT_INDEX_{label}.json"
    runtime_figure = report_root / "figures" / f"runtime_vs_input_size_{label}.png"
    speedup_figure = report_root / "figures" / f"speedup_{label}.png"
    comm_events_csv = results_root / f"mpi-{label}-N{speedup_n}-P{final_processes}" / "comm_events.csv"
    task_assignment_csv = results_root / f"mpi-{label}-N{speedup_n}-P{final_processes}" / "task_assignment.csv"
    rank_base = f"{bundle_name}_mpi_{slugify(f'mpi-{label}-N{n}-P{final_processes}')}_rank_time_breakdown"
    rank_figure = report_root / "figures" / f"{slugify(rank_base)}.png"

    items = [
        AuditItem("serial summaries exist", bool(serial_summaries), f"count={len(serial_summaries)}"),
        AuditItem("MPI summaries exist", bool(mpi_summaries), f"count={len(mpi_summaries)}"),
        AuditItem(
            "runtime-vs-N input sizes are present at final process count",
            all(size in runtime_sizes for size in expected_input_sizes),
            f"expected={expected_input_sizes}, found_for_P{final_processes}={runtime_sizes}",
        ),
        AuditItem(
            "serial baselines are present for expected input sizes",
            all(_summary_exists(summaries, mode="serial", n=size) for size in expected_input_sizes),
            f"expected={expected_input_sizes}",
        ),
        AuditItem(
            "speedup input size has requested process counts",
            all(process in speedup_counts for process in expected_process_counts),
            f"N={speedup_n}, expected={expected_process_counts}, found={speedup_counts}",
        ),
        AuditItem(
            "speedup has P=1 MPI baseline",
            1 in speedup_counts,
            f"N={speedup_n}, found={speedup_counts}",
        ),
        AuditItem(
            "correctness serial run exists",
            _summary_exists(summaries, mode="serial", n=speedup_n),
            f"N={speedup_n}",
        ),
        AuditItem(
            "correctness MPI run exists",
            _summary_exists(summaries, mode="mpi", n=speedup_n, processes=final_processes),
            f"N={speedup_n}, P={final_processes}",
        ),
        _correctness_passed(compare_path),
        _solution_quality_passed(solution_quality_path),
        _exists(comm_events_csv, "MPI communication events CSV exists"),
        _communication_passed(communication_path),
        _exists(task_assignment_csv, "MPI task assignment CSV exists"),
        _granularity_passed(granularity_path),
        _exists(runtime_figure, "runtime-vs-N figure exists"),
        _exists(speedup_figure, "speedup figure exists"),
        _exists(rank_figure, "rank time breakdown figure exists"),
        _exists(bundle_manifest, "report artifact bundle manifest exists"),
        _table_manifest_passed(tables_manifest),
        _exists(results_summary, "results summary exists"),
        _exists(environment_json, "environment capture exists"),
        _ownership_passed(ownership_path),
        _defense_guide_passed(defense_guide_path),
        _exists(experiment_index, "experiment index exists"),
        _validation_passed(validation_path),
    ]
    if benchmark_plan:
        items.append(_exists(benchmark_plan, "benchmark plan exists"))

    failed = [item for item in items if not item.passed]
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "label": label,
        "results_dir": str(results_root),
        "report_dir": str(report_root),
        "n": int(n),
        "speedup_n": int(speedup_n),
        "final_processes": int(final_processes),
        "input_sizes": expected_input_sizes,
        "process_counts": expected_process_counts,
        "final_ready": not failed,
        "num_items": len(items),
        "num_failed": len(failed),
        "items": [item.to_json() for item in items],
        "discovered_runs": [
            {
                "run_id": summary.get("run_id", ""),
                "mode": summary.get("mode", ""),
                "input_size_n": int(summary.get("total_tasks", 0)),
                "processes": int(summary.get("size", 0)),
                "summary_json": str(Path(summary.get("_run_dir", "")) / "summary.json"),
            }
            for summary in summaries
        ],
        "important_artifacts": {
            "correctness_report": str(compare_path),
            "solution_quality_report": str(solution_quality_path),
            "communication_report": str(communication_path),
            "granularity_report": str(granularity_path),
            "validation_report": str(validation_path),
            "bundle_manifest": str(bundle_manifest),
            "tables_manifest": str(tables_manifest),
            "results_summary": str(results_summary),
            "environment_json": str(environment_json),
            "ownership_report": str(ownership_path),
            "defense_guide": str(defense_guide_path),
            "experiment_index": str(experiment_index),
            "runtime_figure": str(runtime_figure),
            "speedup_figure": str(speedup_figure),
            "comm_events_csv": str(comm_events_csv),
            "task_assignment_csv": str(task_assignment_csv),
            "rank_time_breakdown_figure": str(rank_figure),
            "benchmark_plan": "" if benchmark_plan is None else str(benchmark_plan),
        },
        "note": "Final-ready means required artifact structure exists and checks pass. It does not invent or modify results.",
    }


def final_audit_markdown(payload: dict[str, Any]) -> str:
    """Render a final audit payload as Markdown."""

    verdict = "PASS" if payload.get("final_ready") else "FAIL"
    lines = [
        "# Final Experiment Audit",
        "",
        "This file is generated from real local artifacts. Use it as a checklist",
        "before copying experiment claims into the final report.",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- label: `{payload['label']}`",
        f"- verdict: **{verdict}**",
        f"- N for runtime/load-balance: `{payload['n']}`",
        f"- 2N for speedup/correctness: `{payload['speedup_n']}`",
        f"- final_processes: `{payload['final_processes']}`",
        f"- failed_checks: `{payload['num_failed']}`",
        "",
        "## Checks",
        "",
        "| status | check | detail |",
        "|---|---|---|",
    ]
    for item in payload["items"]:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(f"| {status} | {item['name']} | `{item['detail']}` |")

    lines.extend(["", "## Important Artifacts", "", "| artifact | path |", "|---|---|"])
    for key, value in payload["important_artifacts"].items():
        if value:
            lines.append(f"| {key} | `{value}` |")

    lines.extend(["", "## Discovered Runs", "", "| run_id | mode | N | processes | summary |", "|---|---|---:|---:|---|"])
    for run in payload["discovered_runs"]:
        lines.append(
            "| {run_id} | {mode} | {n} | {p} | `{summary}` |".format(
                run_id=run["run_id"],
                mode=run["mode"],
                n=run["input_size_n"],
                p=run["processes"],
                summary=run["summary_json"],
            )
        )
    lines.extend(["", payload["note"], ""])
    return "\n".join(lines)


def write_final_audit(payload: dict[str, Any], json_path: str | Path, markdown_path: str | Path) -> tuple[Path, Path]:
    """Write final audit JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(final_audit_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
