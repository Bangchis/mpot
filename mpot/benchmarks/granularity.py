"""Granularity and load-balance analysis from MPI rank timing artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv
import json

from mpot.benchmarks.artifacts import read_json, write_json


@dataclass
class RankGranularityRow:
    """One per-rank row with derived idle-time fields."""

    run_id: str
    rank: int
    size: int
    hostname: str
    num_tasks: int
    compute_time_s: float
    communication_time_s: float
    total_time_s: float
    idle_time_s: float
    idle_fraction_of_slowest_rank: float
    best_cost: float

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "rank": self.rank,
            "size": self.size,
            "hostname": self.hostname,
            "num_tasks": self.num_tasks,
            "compute_time_s": self.compute_time_s,
            "communication_time_s": self.communication_time_s,
            "total_time_s": self.total_time_s,
            "idle_time_s": self.idle_time_s,
            "idle_fraction_of_slowest_rank": self.idle_fraction_of_slowest_rank,
            "best_cost": self.best_cost,
        }


def _read_rank_timing_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _recommendation(
    *,
    balanced: bool,
    idle_fraction: float,
    communication_fraction: float,
    min_tasks_per_rank: int,
    threshold: float,
) -> str:
    if not balanced and min_tasks_per_rank <= 1:
        return (
            f"Load imbalance is above {threshold:.0%}, and at least one rank has only "
            "one task. Increase N or split the work into more tasks so cyclic mapping "
            "has finer granularity."
        )
    if not balanced:
        return (
            f"Load imbalance is above {threshold:.0%}. The current task granularity is "
            "still too coarse or task costs vary too much; use finer tasks or consider "
            "dynamic scheduling as a future improvement."
        )
    if communication_fraction > 0.25:
        return (
            "Load balance is acceptable, but communication is a large fraction of the "
            "slowest rank time. Prefer coarser tasks or reduce gathered payloads."
        )
    return (
        "Load balance is within the 25% threshold. The current granularity is acceptable "
        "for this run, so no adjustment is required before using the result in the report."
    )


def analyze_granularity(
    run_dir: str | Path,
    *,
    threshold: float = 0.25,
) -> dict[str, Any]:
    """Analyze load balance and granularity for one MPI run directory."""

    root = Path(run_dir)
    summary = read_json(root / "summary.json")
    timing_path = root / "rank_timings.csv"
    raw_rows = _read_rank_timing_csv(timing_path)
    if not raw_rows:
        raise ValueError(f"No rows found in {timing_path}.")

    max_total = max(float(row["total_time_s"]) for row in raw_rows)
    min_total = min(float(row["total_time_s"]) for row in raw_rows)
    max_compute = max(float(row["compute_time_s"]) for row in raw_rows)
    max_comm = max(float(row["communication_time_s"]) for row in raw_rows)
    idle_fraction = 0.0 if max_total <= 0 else (max_total - min_total) / max_total
    communication_fraction = 0.0 if max_total <= 0 else max_comm / max_total
    balanced = idle_fraction <= threshold

    rows = []
    for row in raw_rows:
        total = float(row["total_time_s"])
        idle = max_total - total
        rows.append(
            RankGranularityRow(
                run_id=str(row["run_id"]),
                rank=int(row["rank"]),
                size=int(row["size"]),
                hostname=row["hostname"],
                num_tasks=int(row["num_tasks"]),
                compute_time_s=float(row["compute_time_s"]),
                communication_time_s=float(row["communication_time_s"]),
                total_time_s=total,
                idle_time_s=idle,
                idle_fraction_of_slowest_rank=0.0 if max_total <= 0 else idle / max_total,
                best_cost=float(row["best_cost"]),
            )
        )

    min_tasks = min(item.num_tasks for item in rows)
    max_tasks = max(item.num_tasks for item in rows)
    return {
        "run_dir": str(root),
        "rank_timings_csv": str(timing_path),
        "run_id": summary.get("run_id", root.name),
        "input_size_n": int(summary["total_tasks"]),
        "processes": int(summary["size"]),
        "threshold": threshold,
        "max_total_time_s": max_total,
        "min_total_time_s": min_total,
        "max_compute_time_s": max_compute,
        "max_communication_time_s": max_comm,
        "idle_fraction": idle_fraction,
        "communication_fraction_of_slowest_rank": communication_fraction,
        "balanced_under_threshold": balanced,
        "balanced_under_25_percent": idle_fraction <= 0.25,
        "min_tasks_per_rank": min_tasks,
        "max_tasks_per_rank": max_tasks,
        "task_count_spread": max_tasks - min_tasks,
        "recommendation": _recommendation(
            balanced=balanced,
            idle_fraction=idle_fraction,
            communication_fraction=communication_fraction,
            min_tasks_per_rank=min_tasks,
            threshold=threshold,
        ),
        "rank_rows": [item.to_json() for item in sorted(rows, key=lambda item: item.rank)],
        "note": "Derived only from real rank_timings.csv and summary.json artifacts.",
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def granularity_markdown(payload: dict[str, Any]) -> str:
    """Render a compact Markdown report for the Results section."""

    lines = [
        "# Granularity and Load Balance Analysis",
        "",
        "This analysis is generated from real MPI timing artifacts.",
        "",
        "## Summary",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- input_size_n: `{payload['input_size_n']}`",
        f"- processes: `{payload['processes']}`",
        f"- threshold: `{payload['threshold']}`",
        f"- idle_fraction: `{_fmt(payload['idle_fraction'])}`",
        f"- balanced_under_threshold: `{_fmt(payload['balanced_under_threshold'])}`",
        f"- communication_fraction_of_slowest_rank: `{_fmt(payload['communication_fraction_of_slowest_rank'])}`",
        "",
        "## Recommendation",
        "",
        payload["recommendation"],
        "",
        "## Per-Rank Timing",
        "",
        "| rank | num_tasks | compute_time_s | communication_time_s | total_time_s | idle_time_s | idle_fraction |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rank_rows"]:
        lines.append(
            "| {rank} | {num_tasks} | {compute} | {comm} | {total} | {idle} | {idle_frac} |".format(
                rank=row["rank"],
                num_tasks=row["num_tasks"],
                compute=_fmt(row["compute_time_s"]),
                comm=_fmt(row["communication_time_s"]),
                total=_fmt(row["total_time_s"]),
                idle=_fmt(row["idle_time_s"]),
                idle_frac=_fmt(row["idle_fraction_of_slowest_rank"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_granularity_analysis(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write granularity analysis JSON and Markdown files."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(granularity_markdown(payload), encoding="utf-8")
    return json_out, markdown_out


def load_granularity_analysis(path: str | Path) -> dict[str, Any]:
    """Load a granularity JSON artifact."""

    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)
