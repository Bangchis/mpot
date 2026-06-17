"""Build a readable index of benchmark artifacts.

The final report should be traceable to concrete files. This module scans the
results/report directories and writes a compact index of available runs,
correctness checks, communication analyses, solution-quality checks,
ownership/defense evidence, validation reports, environment captures, and
granularity analyses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import time

from mpot.benchmarks.artifacts import read_json, write_json


@dataclass
class IndexedRun:
    """One serial or MPI run discovered from summary.json."""

    run_id: str
    mode: str
    input_size_n: int
    processes: int
    best_cost: float
    runtime_with_communication_s: float
    runtime_without_communication_s: float
    run_dir: str
    summary_json: str
    has_rank_timings: bool
    has_comm_events: bool
    has_task_assignment: bool
    has_best_path: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "input_size_n": self.input_size_n,
            "processes": self.processes,
            "best_cost": self.best_cost,
            "runtime_with_communication_s": self.runtime_with_communication_s,
            "runtime_without_communication_s": self.runtime_without_communication_s,
            "run_dir": self.run_dir,
            "summary_json": self.summary_json,
            "has_rank_timings": self.has_rank_timings,
            "has_comm_events": self.has_comm_events,
            "has_task_assignment": self.has_task_assignment,
            "has_best_path": self.has_best_path,
        }


def _matches_label(path: Path, payload: dict[str, Any] | None, label: str | None) -> bool:
    if not label:
        return True
    run_id = "" if payload is None else str(payload.get("run_id", ""))
    experiment = "" if payload is None else str(payload.get("config", {}).get("experiment_name", ""))
    return label in path.as_posix() or label in run_id or label in experiment


def discover_runs(results_dir: str | Path, label: str | None = None) -> list[IndexedRun]:
    """Discover serial/MPI runs by scanning summary.json files."""

    root = Path(results_dir)
    runs: list[IndexedRun] = []
    for summary_path in sorted(root.glob("*/summary.json")):
        payload = read_json(summary_path)
        if not _matches_label(summary_path, payload, label):
            continue
        run_dir = summary_path.parent
        runs.append(
            IndexedRun(
                run_id=str(payload.get("run_id", run_dir.name)),
                mode=str(payload.get("mode", "")),
                input_size_n=int(payload.get("total_tasks", 0)),
                processes=int(payload.get("size", 1)),
                best_cost=float(payload.get("best_cost", 0.0)),
                runtime_with_communication_s=float(payload.get("runtime_with_communication_s", 0.0)),
                runtime_without_communication_s=float(payload.get("runtime_without_communication_s", 0.0)),
                run_dir=str(run_dir),
                summary_json=str(summary_path),
                has_rank_timings=(run_dir / "rank_timings.csv").exists(),
                has_comm_events=(run_dir / "comm_events.csv").exists(),
                has_task_assignment=(run_dir / "task_assignment.csv").exists(),
                has_best_path=(run_dir / "best_path.png").exists(),
            )
        )
    return sorted(runs, key=lambda r: (r.input_size_n, r.processes, r.mode, r.run_id))


def _discover_json_files(root: Path, pattern: str, label: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.glob(pattern)):
        try:
            payload = read_json(path)
        except Exception:
            payload = {}
        if not _matches_label(path, payload, label):
            continue
        passed = payload.get("passed", "")
        if passed == "" and "has_expected_collectives" in payload:
            passed = payload.get("has_expected_collectives")
        if passed == "" and "balanced_under_threshold" in payload:
            passed = payload.get("balanced_under_threshold")
        if passed == "" and "final_ready" in payload:
            passed = payload.get("final_ready")
        rows.append(
            {
                "path": str(path),
                "run_id": payload.get("run_id", path.parent.name if path.name != path.parent.name else path.stem),
                "passed": passed,
                "label": payload.get("label", ""),
            }
        )
    return rows


def build_experiment_index(
    *,
    results_dir: str | Path = "results",
    report_dir: str | Path = "report",
    label: str | None = None,
) -> dict[str, Any]:
    """Build an index payload from discovered artifacts."""

    results_root = Path(results_dir)
    report_root = Path(report_dir)
    runs = discover_runs(results_root, label=label)
    correctness = _discover_json_files(results_root, "compare*/correctness_report.json", label=label)
    validations = _discover_json_files(results_root, "*validation*.json", label=label)
    environments = _discover_json_files(results_root, "environment*.json", label=label)
    granularities = _discover_json_files(results_root, "granularity*.json", label=label)
    communications = _discover_json_files(results_root, "communication*.json", label=label)
    solution_quality = _discover_json_files(results_root, "solution-quality*.json", label=label)
    ownership = _discover_json_files(report_root, "TEAM_OWNERSHIP_REPORT.json", label=None)
    defense_guides = _discover_json_files(report_root, "MEMBER_DEFENSE_GUIDE.json", label=None)
    report_manifests = _discover_json_files(report_root, "artifacts/*/manifest.json", label=label)
    table_manifests = _discover_json_files(report_root, "tables/tables_manifest*.json", label=label)

    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "results_dir": str(results_root),
        "report_dir": str(report_root),
        "label": label or "",
        "counts": {
            "runs": len(runs),
            "serial_runs": sum(1 for run in runs if run.mode == "serial"),
            "mpi_runs": sum(1 for run in runs if run.mode == "mpi"),
            "correctness_reports": len(correctness),
            "validation_reports": len(validations),
            "environment_reports": len(environments),
            "granularity_reports": len(granularities),
            "communication_reports": len(communications),
            "solution_quality_reports": len(solution_quality),
            "ownership_reports": len(ownership),
            "defense_guides": len(defense_guides),
            "report_manifests": len(report_manifests),
            "table_manifests": len(table_manifests),
        },
        "runs": [run.to_json() for run in runs],
        "correctness_reports": correctness,
        "validation_reports": validations,
        "environment_reports": environments,
        "granularity_reports": granularities,
        "communication_reports": communications,
        "solution_quality_reports": solution_quality,
        "ownership_reports": ownership,
        "defense_guides": defense_guides,
        "report_manifests": report_manifests,
        "table_manifests": table_manifests,
        "note": "Index only lists discovered artifacts. It does not create benchmark results.",
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _simple_path_table(rows: list[dict[str, Any]], title: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["No matching artifacts found.", ""])
        return lines
    lines.extend(["| path | run_id | passed |", "|---|---|---:|"])
    for row in rows:
        lines.append(f"| `{row['path']}` | `{row.get('run_id', '')}` | {_fmt(row.get('passed', ''))} |")
    lines.append("")
    return lines


def experiment_index_markdown(payload: dict[str, Any]) -> str:
    """Render an experiment index as Markdown."""

    lines = [
        "# Experiment Index",
        "",
        "This index is generated from local artifacts. Use it to navigate real",
        "runs and report evidence without guessing filenames.",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- label: `{payload.get('label', '')}`",
        f"- results_dir: `{payload['results_dir']}`",
        f"- report_dir: `{payload['report_dir']}`",
        "",
        "## Counts",
        "",
        "| item | count |",
        "|---|---:|",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| run_id | mode | N | processes | runtime_with_comm_s | runtime_without_comm_s | rank_timings | comm_events | task_assignment | summary |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for run in payload["runs"]:
        lines.append(
            "| {run_id} | {mode} | {n} | {p} | {with_comm} | {without_comm} | {rank} | {comm} | {assignment} | `{summary}` |".format(
                run_id=run["run_id"],
                mode=run["mode"],
                n=run["input_size_n"],
                p=run["processes"],
                with_comm=_fmt(run["runtime_with_communication_s"]),
                without_comm=_fmt(run["runtime_without_communication_s"]),
                rank=_fmt(run["has_rank_timings"]),
                comm=_fmt(run["has_comm_events"]),
                assignment=_fmt(run["has_task_assignment"]),
                summary=run["summary_json"],
            )
        )
    lines.append("")
    lines.extend(_simple_path_table(payload["correctness_reports"], "Correctness Reports"))
    lines.extend(_simple_path_table(payload["validation_reports"], "Validation Reports"))
    lines.extend(_simple_path_table(payload["environment_reports"], "Environment Reports"))
    lines.extend(_simple_path_table(payload["granularity_reports"], "Granularity Reports"))
    lines.extend(_simple_path_table(payload["communication_reports"], "Communication Reports"))
    lines.extend(_simple_path_table(payload["solution_quality_reports"], "Solution Quality Reports"))
    lines.extend(_simple_path_table(payload["ownership_reports"], "Team Ownership Reports"))
    lines.extend(_simple_path_table(payload["defense_guides"], "Member Defense Guides"))
    lines.extend(_simple_path_table(payload["report_manifests"], "Report Manifests"))
    lines.extend(_simple_path_table(payload["table_manifests"], "Table Manifests"))
    return "\n".join(lines)


def write_experiment_index(payload: dict[str, Any], json_path: str | Path, markdown_path: str | Path) -> tuple[Path, Path]:
    """Write index JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(experiment_index_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
