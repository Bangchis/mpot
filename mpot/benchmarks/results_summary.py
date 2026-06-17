"""Build a report-ready Results summary from real benchmark artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import time

from mpot.benchmarks.artifacts import read_json, write_json


def _csv_row_count(path: str | Path) -> int:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def _source(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False}
    candidate = Path(path)
    return {"path": str(candidate), "exists": candidate.exists()}


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _read_dict(path: str | Path, label: str) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return payload


def build_results_summary(
    *,
    label: str,
    serial_run: str | Path,
    mpi_run: str | Path,
    correctness_report: str | Path,
    tables_manifest: str | Path,
    granularity_report: str | Path,
    communication_report: str | Path,
    solution_quality_report: str | Path,
    figure_paths: list[str | Path] | None = None,
    benchmark_budget: str | Path | None = None,
) -> dict[str, Any]:
    """Build a compact summary that can be pasted into the living report."""

    serial_summary_path = Path(serial_run) / "summary.json"
    mpi_summary_path = Path(mpi_run) / "summary.json"
    serial_summary = _read_dict(serial_summary_path, "serial summary")
    mpi_summary = _read_dict(mpi_summary_path, "MPI summary")
    correctness = _read_dict(correctness_report, "correctness report")
    tables = _read_dict(tables_manifest, "tables manifest")
    granularity = _read_dict(granularity_report, "granularity report")
    communication = _read_dict(communication_report, "communication report")
    solution = _read_dict(solution_quality_report, "solution quality report")
    budget = _read_dict(benchmark_budget, "benchmark budget") if benchmark_budget else {}

    table_paths = tables.get("paths", {})
    runtime_csv = table_paths.get("runtime_csv", "")
    speedup_csv = table_paths.get("speedup_csv", "")
    load_balance_csv = table_paths.get("load_balance_csv", "")
    figure_paths = figure_paths or []

    sources = {
        "serial_summary": _source(serial_summary_path),
        "mpi_summary": _source(mpi_summary_path),
        "correctness_report": _source(correctness_report),
        "tables_manifest": _source(tables_manifest),
        "runtime_csv": _source(runtime_csv),
        "speedup_csv": _source(speedup_csv),
        "load_balance_csv": _source(load_balance_csv),
        "granularity_report": _source(granularity_report),
        "communication_report": _source(communication_report),
        "solution_quality_report": _source(solution_quality_report),
        "benchmark_budget": _source(benchmark_budget),
        "figures": [_source(path) for path in figure_paths],
    }

    correctness_task = correctness.get("task_level", {})
    checks = [
        _check("serial summary exists", sources["serial_summary"]["exists"], sources["serial_summary"]["path"]),
        _check("MPI summary exists", sources["mpi_summary"]["exists"], sources["mpi_summary"]["path"]),
        _check("correctness passed", bool(correctness.get("passed")), f"passed={correctness.get('passed')}"),
        _check(
            "task-level correctness passed",
            bool(correctness_task.get("tasks_passed", True)),
            f"tasks_passed={correctness_task.get('tasks_passed', 'not recorded')}",
        ),
        _check("solution quality passed", bool(solution.get("passed")), f"passed={solution.get('passed')}"),
        _check(
            "communication analysis passed",
            bool(communication.get("has_expected_collectives")) and bool(communication.get("all_events_blocking")),
            (
                f"collectives={communication.get('observed_collectives')}, "
                f"blocking={communication.get('all_events_blocking')}"
            ),
        ),
        _check(
            "granularity under threshold",
            bool(granularity.get("balanced_under_threshold")),
            f"idle_fraction={granularity.get('idle_fraction')}",
        ),
        _check(
            "result tables have rows",
            int(tables.get("num_runtime_rows", 0)) > 0
            and int(tables.get("num_speedup_rows", 0)) > 0
            and int(tables.get("num_load_balance_rows", 0)) > 0,
            (
                f"runtime={tables.get('num_runtime_rows')}, "
                f"speedup={tables.get('num_speedup_rows')}, "
                f"load_balance={tables.get('num_load_balance_rows')}"
            ),
        ),
    ]
    for item in sources["figures"]:
        checks.append(_check("figure exists", bool(item["exists"]), str(item["path"])))

    failed = [item for item in checks if not item["passed"]]
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "label": label,
        "passed": not failed,
        "num_failed": len(failed),
        "checks": checks,
        "serial": {
            "run_id": serial_summary.get("run_id"),
            "input_size_n": int(serial_summary.get("total_tasks", 0)),
            "best_task_id": int(serial_summary.get("best_task_id", -1)),
            "best_seed": int(serial_summary.get("best_seed", -1)),
            "best_cost": float(serial_summary.get("best_cost", 0.0)),
            "runtime_with_communication_s": float(serial_summary.get("runtime_with_communication_s", 0.0)),
        },
        "mpi": {
            "run_id": mpi_summary.get("run_id"),
            "input_size_n": int(mpi_summary.get("total_tasks", 0)),
            "processes": int(mpi_summary.get("size", 0)),
            "best_task_id": int(mpi_summary.get("best_task_id", -1)),
            "best_seed": int(mpi_summary.get("best_seed", -1)),
            "best_cost": float(mpi_summary.get("best_cost", 0.0)),
            "runtime_with_communication_s": float(mpi_summary.get("runtime_with_communication_s", 0.0)),
            "runtime_without_communication_s": float(mpi_summary.get("runtime_without_communication_s", 0.0)),
        },
        "correctness": {
            "passed": bool(correctness.get("passed")),
            "same_best_task": bool(correctness.get("same_best_task")),
            "same_best_seed": bool(correctness.get("same_best_seed")),
            "best_cost_difference": float(correctness.get("best_cost_difference", correctness.get("cost_difference", 0.0))),
            "num_compared_tasks": int(correctness_task.get("num_compared_tasks", 0)),
        },
        "solution_quality": {
            "passed": bool(solution.get("passed")),
            "goal_error": float(solution.get("goal_error", 0.0)),
            "hard_collision_fraction": float(solution.get("hard_collision_fraction", 0.0)),
            "max_bounds_violation": float(solution.get("max_bounds_violation", 0.0)),
        },
        "communication": {
            "topology": communication.get("topology", ""),
            "strategy": communication.get("communication_strategy", ""),
            "observed_collectives": communication.get("observed_collectives", []),
            "all_events_blocking": bool(communication.get("all_events_blocking")),
            "num_event_rows": int(communication.get("num_event_rows", 0)),
        },
        "granularity": {
            "balanced_under_threshold": bool(granularity.get("balanced_under_threshold")),
            "idle_fraction": float(granularity.get("idle_fraction", 0.0)),
            "communication_fraction_of_slowest_rank": float(
                granularity.get("communication_fraction_of_slowest_rank", 0.0)
            ),
            "recommendation": granularity.get("recommendation", ""),
        },
        "tables": {
            "num_runtime_rows": int(tables.get("num_runtime_rows", 0)),
            "num_speedup_rows": int(tables.get("num_speedup_rows", 0)),
            "num_load_balance_rows": int(tables.get("num_load_balance_rows", 0)),
            "runtime_csv_rows": _csv_row_count(runtime_csv) if runtime_csv else 0,
            "speedup_csv_rows": _csv_row_count(speedup_csv) if speedup_csv else 0,
            "load_balance_csv_rows": _csv_row_count(load_balance_csv) if load_balance_csv else 0,
        },
        "benchmark_budget": {
            "present": bool(budget),
            "estimated_total_minutes": budget.get("estimated_total_minutes"),
            "note": budget.get("note", ""),
        },
        "sources": sources,
        "note": "Generated only from existing benchmark artifacts. Do not use this file to invent missing results.",
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def results_summary_markdown(payload: dict[str, Any]) -> str:
    """Render a Results summary as Markdown."""

    verdict = "PASS" if payload.get("passed") else "FAIL"
    serial = payload["serial"]
    mpi = payload["mpi"]
    correctness = payload["correctness"]
    solution = payload["solution_quality"]
    communication = payload["communication"]
    granularity = payload["granularity"]
    tables = payload["tables"]

    lines = [
        "# Results Summary",
        "",
        "This summary is generated from real benchmark artifacts. It can be used",
        "as a report-writing helper, but it does not create new measurements.",
        "",
        f"- label: `{payload['label']}`",
        f"- verdict: **{verdict}**",
        f"- generated_at: `{payload['created_at']}`",
        "",
        "## Correctness",
        "",
        f"- serial run: `{serial['run_id']}`",
        f"- MPI run: `{mpi['run_id']}`",
        f"- same best task: `{_fmt(correctness['same_best_task'])}`",
        f"- same best seed: `{_fmt(correctness['same_best_seed'])}`",
        f"- best cost difference: `{_fmt(correctness['best_cost_difference'])}`",
        f"- compared tasks: `{correctness['num_compared_tasks']}`",
        "",
        "## Solution Quality",
        "",
        f"- MPI best task: `{mpi['best_task_id']}`",
        f"- MPI best seed: `{mpi['best_seed']}`",
        f"- MPI best cost: `{_fmt(mpi['best_cost'])}`",
        f"- goal error: `{_fmt(solution['goal_error'])}`",
        f"- hard collision fraction: `{_fmt(solution['hard_collision_fraction'])}`",
        f"- max bounds violation: `{_fmt(solution['max_bounds_violation'])}`",
        "",
        "## Communication and Load Balance",
        "",
        f"- topology: `{communication['topology']}`",
        f"- strategy: `{communication['strategy']}`",
        f"- observed collectives: `{_fmt(communication['observed_collectives'])}`",
        f"- all events blocking: `{_fmt(communication['all_events_blocking'])}`",
        f"- idle fraction: `{_fmt(granularity['idle_fraction'])}`",
        f"- balanced under threshold: `{_fmt(granularity['balanced_under_threshold'])}`",
        f"- recommendation: {granularity['recommendation']}",
        "",
        "## Generated Tables",
        "",
        f"- runtime rows: `{tables['num_runtime_rows']}`",
        f"- speedup rows: `{tables['num_speedup_rows']}`",
        f"- load-balance rows: `{tables['num_load_balance_rows']}`",
        "",
        "## Checks",
        "",
        "| status | check | detail |",
        "|---|---|---|",
    ]
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"| {status} | {check['name']} | `{check['detail']}` |")

    lines.extend(["", "## Sources", "", "| artifact | path |", "|---|---|"])
    for key, source in payload["sources"].items():
        if key == "figures":
            for figure in source:
                lines.append(f"| figure | `{figure['path']}` |")
            continue
        if source.get("path"):
            lines.append(f"| {key} | `{source['path']}` |")
    lines.extend(["", payload["note"], ""])
    return "\n".join(lines)


def write_results_summary(
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write Results summary JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(results_summary_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
