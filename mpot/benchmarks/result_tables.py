"""Export report-ready tables from real benchmark artifacts.

The course report needs runtime-vs-N, speedup, and per-rank load-balance
tables. This module reads existing summary JSON and rank timing CSV files, then
writes derived CSV/Markdown tables. It never fabricates missing measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import csv
import math

from mpot.benchmarks.artifacts import read_json, write_csv, write_json
from mpot.benchmarks.metrics import compute_efficiency, compute_speedup
from mpot.benchmarks.plots import collect_summaries


RUNTIME_TABLE_FIELDS = [
    "run_id",
    "mode",
    "input_size_n",
    "processes",
    "runtime_with_communication_s",
    "runtime_without_communication_s",
    "communication_overhead_s",
    "best_cost",
    "balanced_under_25_percent",
    "source_summary",
]

SPEEDUP_TABLE_FIELDS = [
    "run_id",
    "input_size_n",
    "processes",
    "runtime_with_communication_s",
    "runtime_without_communication_s",
    "speedup_with_communication",
    "speedup_without_communication",
    "efficiency_with_communication",
    "efficiency_without_communication",
    "source_summary",
]

LOAD_BALANCE_TABLE_FIELDS = [
    "run_id",
    "rank",
    "processes",
    "hostname",
    "num_tasks",
    "compute_time_s",
    "communication_time_s",
    "total_time_s",
    "idle_time_s",
    "idle_fraction_of_slowest_rank",
    "best_cost",
    "source_rank_timings",
]


@dataclass
class ResultTablePaths:
    """Output paths written by export_result_tables."""

    runtime_csv: Path
    speedup_csv: Path
    load_balance_csv: Path | None
    markdown: Path
    manifest_json: Path

    def to_json(self) -> dict[str, str | None]:
        return {
            "runtime_csv": str(self.runtime_csv),
            "speedup_csv": str(self.speedup_csv),
            "load_balance_csv": None if self.load_balance_csv is None else str(self.load_balance_csv),
            "markdown": str(self.markdown),
            "manifest_json": str(self.manifest_json),
        }


def _finite_or_blank(value: float) -> float | str:
    return "" if math.isnan(value) or math.isinf(value) else value


def _fmt(value: Any) -> str:
    """Format values compactly for Markdown without hiding the raw CSV values."""

    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.6g}"
    return str(value)


def _read_rank_timing_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _summary_source(summary: dict[str, Any]) -> str:
    run_dir = Path(summary["_run_dir"])
    return str(run_dir / "summary.json")


def build_runtime_rows(
    results_dir: str | Path,
    *,
    label: str | None = None,
    fixed_size: int | None = None,
    input_size: int | None = None,
) -> list[dict[str, Any]]:
    """Build runtime-vs-N rows from summary.json files."""

    summaries = collect_summaries(results_dir, label=label)
    if fixed_size is not None:
        summaries = [s for s in summaries if int(s["size"]) == fixed_size]
    if input_size is not None:
        summaries = [s for s in summaries if int(s["total_tasks"]) == input_size]
    summaries = sorted(summaries, key=lambda s: (int(s["total_tasks"]), int(s["size"]), str(s["mode"])))

    rows = []
    for summary in summaries:
        with_comm = float(summary["runtime_with_communication_s"])
        without_comm = float(summary["runtime_without_communication_s"])
        load_balance = summary.get("load_balance") or {}
        rows.append(
            {
                "run_id": summary["run_id"],
                "mode": summary["mode"],
                "input_size_n": int(summary["total_tasks"]),
                "processes": int(summary["size"]),
                "runtime_with_communication_s": with_comm,
                "runtime_without_communication_s": without_comm,
                "communication_overhead_s": max(0.0, with_comm - without_comm),
                "best_cost": float(summary["best_cost"]),
                "balanced_under_25_percent": load_balance.get("balanced_under_25_percent", ""),
                "source_summary": _summary_source(summary),
            }
        )
    return rows


def _select_speedup_summaries(
    results_dir: str | Path,
    *,
    label: str | None,
    input_size: int | None,
) -> tuple[int, list[dict[str, Any]]]:
    summaries = collect_summaries(results_dir, label=label, mode="mpi")
    if not summaries:
        raise ValueError("No MPI summary.json files found for speedup table.")
    selected_n = input_size if input_size is not None else max(int(s["total_tasks"]) for s in summaries)
    chosen = [s for s in summaries if int(s["total_tasks"]) == selected_n]
    chosen = sorted(chosen, key=lambda s: int(s["size"]))
    if not chosen:
        raise ValueError(f"No MPI summaries found for N={selected_n}.")
    if not any(int(s["size"]) == 1 for s in chosen):
        raise ValueError("Speedup table requires an MPI run with process count 1.")
    return selected_n, chosen


def build_speedup_rows(
    results_dir: str | Path,
    *,
    label: str | None = None,
    input_size: int | None = None,
) -> list[dict[str, Any]]:
    """Build speedup rows from MPI summary.json files."""

    selected_n, summaries = _select_speedup_summaries(results_dir, label=label, input_size=input_size)
    baseline = next(s for s in summaries if int(s["size"]) == 1)
    baseline_with = float(baseline["runtime_with_communication_s"])
    baseline_without = float(baseline["runtime_without_communication_s"])

    rows = []
    for summary in summaries:
        processes = int(summary["size"])
        with_comm = float(summary["runtime_with_communication_s"])
        without_comm = float(summary["runtime_without_communication_s"])
        speedup_with = compute_speedup(baseline_with, with_comm)
        speedup_without = compute_speedup(baseline_without, without_comm)
        rows.append(
            {
                "run_id": summary["run_id"],
                "input_size_n": selected_n,
                "processes": processes,
                "runtime_with_communication_s": with_comm,
                "runtime_without_communication_s": without_comm,
                "speedup_with_communication": _finite_or_blank(speedup_with),
                "speedup_without_communication": _finite_or_blank(speedup_without),
                "efficiency_with_communication": _finite_or_blank(compute_efficiency(speedup_with, processes)),
                "efficiency_without_communication": _finite_or_blank(compute_efficiency(speedup_without, processes)),
                "source_summary": _summary_source(summary),
            }
        )
    return rows


def choose_default_load_balance_run(
    results_dir: str | Path,
    *,
    label: str | None = None,
    input_size: int | None = None,
) -> Path:
    """Choose the largest matching MPI run for the load-balance table."""

    summaries = collect_summaries(results_dir, label=label, mode="mpi")
    if input_size is not None:
        summaries = [s for s in summaries if int(s["total_tasks"]) == input_size]
    if not summaries:
        raise ValueError("No MPI summaries found for load-balance table.")
    chosen = max(summaries, key=lambda s: (int(s["total_tasks"]), int(s["size"])))
    return Path(chosen["_run_dir"])


def build_load_balance_rows(run_dir: str | Path) -> list[dict[str, Any]]:
    """Build per-rank timing rows for one MPI run directory."""

    root = Path(run_dir)
    summary = read_json(root / "summary.json")
    timing_path = root / "rank_timings.csv"
    raw_rows = _read_rank_timing_rows(timing_path)
    if not raw_rows:
        raise ValueError(f"No rank timing rows found in {timing_path}.")

    max_total = max(float(row["total_time_s"]) for row in raw_rows)
    rows = []
    for row in raw_rows:
        total = float(row["total_time_s"])
        idle_time = max_total - total
        rows.append(
            {
                "run_id": summary["run_id"],
                "rank": int(row["rank"]),
                "processes": int(row["size"]),
                "hostname": row["hostname"],
                "num_tasks": int(row["num_tasks"]),
                "compute_time_s": float(row["compute_time_s"]),
                "communication_time_s": float(row["communication_time_s"]),
                "total_time_s": total,
                "idle_time_s": idle_time,
                "idle_fraction_of_slowest_rank": 0.0 if max_total <= 0 else idle_time / max_total,
                "best_cost": float(row["best_cost"]),
                "source_rank_timings": str(timing_path),
            }
        )
    return rows


def _markdown_table(rows: list[dict[str, Any]], fields: list[str], max_rows: int = 30) -> list[str]:
    if not rows:
        return ["No rows available."]

    shown = rows[:max_rows]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in shown:
        lines.append("| " + " | ".join(_fmt(row.get(field, "")) for field in fields) + " |")
    if len(rows) > max_rows:
        lines.append("")
        lines.append(f"Showing first {max_rows} of {len(rows)} rows. See CSV for the full table.")
    return lines


def build_results_markdown(
    *,
    runtime_rows: list[dict[str, Any]],
    speedup_rows: list[dict[str, Any]],
    load_balance_rows: list[dict[str, Any]],
    label: str | None,
    input_size: int | None,
    fixed_size: int | None,
) -> str:
    """Build a Markdown snippet that can be copied into the living report."""

    lines = [
        "# Generated Results Tables",
        "",
        "These tables are generated from existing CSV/JSON artifacts. Do not edit",
        "numbers by hand; regenerate the tables after running new experiments.",
        "",
        "## Filters",
        "",
        f"- label: `{label or ''}`",
        f"- input_size: `{'' if input_size is None else input_size}`",
        f"- fixed_size: `{'' if fixed_size is None else fixed_size}`",
        "",
        "## Runtime vs Input Size N",
        "",
    ]
    lines.extend(_markdown_table(runtime_rows, RUNTIME_TABLE_FIELDS))
    lines.extend(["", "## Speedup", ""])
    lines.extend(_markdown_table(speedup_rows, SPEEDUP_TABLE_FIELDS))
    lines.extend(["", "## Granularity and Load Balance", ""])
    lines.extend(_markdown_table(load_balance_rows, LOAD_BALANCE_TABLE_FIELDS))
    lines.append("")
    return "\n".join(lines)


def export_result_tables(
    *,
    results_dir: str | Path = "results",
    output_dir: str | Path = "report/tables",
    label: str | None = None,
    input_size: int | None = None,
    fixed_size: int | None = None,
    load_balance_run: str | Path | None = None,
) -> ResultTablePaths:
    """Write report-ready result tables and a small manifest."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    runtime_rows = build_runtime_rows(
        results_dir,
        label=label,
        fixed_size=fixed_size,
        input_size=None,
    )
    speedup_rows = build_speedup_rows(results_dir, label=label, input_size=input_size)
    load_run = Path(load_balance_run) if load_balance_run else choose_default_load_balance_run(
        results_dir,
        label=label,
        input_size=input_size,
    )
    load_rows = build_load_balance_rows(load_run)

    suffix = f"_{label}" if label else ""
    runtime_csv = out / f"runtime_table{suffix}.csv"
    speedup_csv = out / f"speedup_table{suffix}.csv"
    load_csv = out / f"load_balance_table{suffix}.csv"
    markdown = out / f"RESULTS_TABLES{suffix}.md"
    manifest_json = out / f"tables_manifest{suffix}.json"

    write_csv(runtime_csv, runtime_rows, RUNTIME_TABLE_FIELDS)
    write_csv(speedup_csv, speedup_rows, SPEEDUP_TABLE_FIELDS)
    write_csv(load_csv, load_rows, LOAD_BALANCE_TABLE_FIELDS)
    markdown.write_text(
        build_results_markdown(
            runtime_rows=runtime_rows,
            speedup_rows=speedup_rows,
            load_balance_rows=load_rows,
            label=label,
            input_size=input_size,
            fixed_size=fixed_size,
        ),
        encoding="utf-8",
    )

    paths = ResultTablePaths(
        runtime_csv=runtime_csv,
        speedup_csv=speedup_csv,
        load_balance_csv=load_csv,
        markdown=markdown,
        manifest_json=manifest_json,
    )
    write_json(
        manifest_json,
        {
            "results_dir": str(results_dir),
            "output_dir": str(output_dir),
            "label": label,
            "input_size": input_size,
            "fixed_size": fixed_size,
            "load_balance_run": str(load_run),
            "num_runtime_rows": len(runtime_rows),
            "num_speedup_rows": len(speedup_rows),
            "num_load_balance_rows": len(load_rows),
            "paths": paths.to_json(),
            "note": "Tables are derived from real benchmark artifacts only.",
        },
    )
    return paths
