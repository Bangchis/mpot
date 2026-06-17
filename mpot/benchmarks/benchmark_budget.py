"""Estimate benchmark runtime before launching a full local sweep.

The budget is a planning guard, not experiment data. It helps the team decide
whether a generated benchmark plan is reasonable for a laptop before starting a
long run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import time

from mpot.benchmarks.artifacts import read_json, write_json
from mpot.benchmarks.run_reuse import existing_run_status, expected_run_metadata


@dataclass
class BudgetRow:
    """One planned run and its estimated wall-clock time."""

    kind: str
    run_id: str
    input_size_n: int
    processes: int
    estimated_seconds: float
    remaining_seconds: float
    status: str
    note: str
    reuse_reason: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "input_size_n": self.input_size_n,
            "processes": self.processes,
            "estimated_seconds": self.estimated_seconds,
            "remaining_seconds": self.remaining_seconds,
            "status": self.status,
            "note": self.note,
            "reuse_reason": self.reuse_reason,
        }


def estimate_run_seconds(
    *,
    seconds_per_task: float,
    input_size_n: int,
    processes: int,
    assumed_parallel_efficiency: float,
    kind: str,
    mpi_startup_seconds: float = 1.0,
    mpi_overhead_factor: float = 1.05,
) -> float:
    """Estimate one serial or MPI run time from the measured per-task sample."""

    if seconds_per_task <= 0:
        raise ValueError("seconds_per_task must be positive.")
    if input_size_n <= 0:
        raise ValueError("input_size_n must be positive.")
    if processes <= 0:
        raise ValueError("processes must be positive.")
    if not (0 < assumed_parallel_efficiency <= 1.0):
        raise ValueError("assumed_parallel_efficiency must be in (0, 1].")
    if mpi_startup_seconds < 0:
        raise ValueError("mpi_startup_seconds must be non-negative.")
    if mpi_overhead_factor <= 0:
        raise ValueError("mpi_overhead_factor must be positive.")

    serial_seconds = input_size_n * seconds_per_task
    if kind == "serial":
        return serial_seconds
    if kind != "mpi":
        raise ValueError("kind must be 'serial' or 'mpi'.")

    if processes == 1:
        return serial_seconds * mpi_overhead_factor + mpi_startup_seconds
    return serial_seconds / (processes * assumed_parallel_efficiency) + mpi_startup_seconds


def build_benchmark_budget(
    plan_path: str | Path,
    *,
    max_total_seconds: float = 3600.0,
    min_largest_run_seconds: float = 1.0,
    mpi_startup_seconds: float = 1.0,
    mpi_overhead_factor: float = 1.05,
    include_serial: bool = True,
    label: str | None = None,
    results_dir: str | Path = "results",
    reuse_existing: bool = False,
    run_label: str | None = None,
    extra: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-friendly runtime budget from ``BENCHMARK_PLAN.json``."""

    plan = read_json(plan_path)
    seconds_per_task = float(plan["seconds_per_task"])
    input_sizes = [int(n) for n in plan.get("input_sizes", [])]
    process_counts = [int(p) for p in plan.get("process_counts", [])]
    efficiency = float(plan.get("assumed_parallel_efficiency", 1.0))
    config_path = str(plan.get("config", ""))
    planned_label = run_label or str(plan.get("label") or label or "benchmark")
    extra = extra or []

    if not input_sizes:
        raise ValueError("benchmark plan has no input_sizes.")
    if not process_counts:
        raise ValueError("benchmark plan has no process_counts.")

    def row_for(kind: str, n: int, p: int, estimated_seconds: float, note: str) -> BudgetRow:
        mode = "serial" if kind == "serial" else "mpi"
        expected = expected_run_metadata(
            config_path=config_path,
            output_dir=str(results_dir),
            label=planned_label,
            input_size_n=n,
            mode=mode,
            processes=p,
            extra=extra,
        )
        reusable = False
        reason = "reuse check disabled"
        if reuse_existing:
            reusable, reason = existing_run_status(results_dir, expected["run_id"], expected=expected)
        status = "planned"
        if reuse_existing:
            status = "reusable" if reusable else "missing_or_mismatch"
        return BudgetRow(
            kind=kind,
            run_id=str(expected["run_id"]),
            input_size_n=n,
            processes=p,
            estimated_seconds=estimated_seconds,
            remaining_seconds=0.0 if reusable else estimated_seconds,
            status=status,
            note=note,
            reuse_reason=reason,
        )

    rows: list[BudgetRow] = []
    if include_serial:
        for n in input_sizes:
            estimated = estimate_run_seconds(
                seconds_per_task=seconds_per_task,
                input_size_n=n,
                processes=1,
                assumed_parallel_efficiency=efficiency,
                kind="serial",
                mpi_startup_seconds=mpi_startup_seconds,
                mpi_overhead_factor=mpi_overhead_factor,
            )
            rows.append(
                row_for(
                    kind="serial",
                    n=n,
                    p=1,
                    estimated_seconds=estimated,
                    note="serial baseline run generated by scripts/run_sweep.py",
                )
            )

    for n in input_sizes:
        for p in process_counts:
            estimated = estimate_run_seconds(
                seconds_per_task=seconds_per_task,
                input_size_n=n,
                processes=p,
                assumed_parallel_efficiency=efficiency,
                kind="mpi",
                mpi_startup_seconds=mpi_startup_seconds,
                mpi_overhead_factor=mpi_overhead_factor,
            )
            rows.append(
                row_for(
                    kind="mpi",
                    n=n,
                    p=p,
                    estimated_seconds=estimated,
                    note="MPI sweep run; estimate includes a small startup allowance",
                )
            )

    row_payloads = [row.to_json() for row in rows]
    total_seconds = sum(row.estimated_seconds for row in rows)
    remaining_seconds = sum(row.remaining_seconds for row in rows)
    largest_seconds = max(row.estimated_seconds for row in rows)
    largest_remaining_seconds = max((row.remaining_seconds for row in rows), default=0.0)
    logical_cpu_count = os.cpu_count() or 1
    warnings = []
    guard_seconds = remaining_seconds if reuse_existing else total_seconds

    if guard_seconds > max_total_seconds:
        warnings.append(
            "Estimated sweep time is above the selected budget. Reduce N, "
            "reduce process counts, or run unattended."
        )
    if largest_seconds < min_largest_run_seconds:
        warnings.append(
            "Largest planned run is very short. Increase N or optimizer work so "
            "the benchmark is not a toy timing."
        )
    if max(process_counts) > logical_cpu_count:
        warnings.append(
            f"Max process count {max(process_counts)} is above logical CPU count "
            f"{logical_cpu_count}; oversubscription may slow the local run."
        )

    passed = not warnings or all("above the selected budget" not in item for item in warnings)
    passed = passed and largest_seconds >= min_largest_run_seconds

    return {
        "label": label or plan.get("label", "benchmark_budget"),
        "run_label": planned_label,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "plan_path": str(plan_path),
        "plan_label": plan.get("label"),
        "config": plan.get("config"),
        "seconds_per_task": seconds_per_task,
        "assumed_parallel_efficiency": efficiency,
        "input_sizes": input_sizes,
        "process_counts": process_counts,
        "results_dir": str(results_dir),
        "reuse_existing": reuse_existing,
        "include_serial": include_serial,
        "max_total_seconds": max_total_seconds,
        "min_largest_run_seconds": min_largest_run_seconds,
        "mpi_startup_seconds": mpi_startup_seconds,
        "mpi_overhead_factor": mpi_overhead_factor,
        "estimated_total_seconds": total_seconds,
        "estimated_total_minutes": total_seconds / 60.0,
        "estimated_remaining_seconds": remaining_seconds,
        "estimated_remaining_minutes": remaining_seconds / 60.0,
        "largest_run_seconds": largest_seconds,
        "largest_remaining_run_seconds": largest_remaining_seconds,
        "num_rows": len(rows),
        "num_reusable_rows": sum(1 for row in rows if row.status == "reusable"),
        "num_remaining_rows": sum(1 for row in rows if row.remaining_seconds > 0.0),
        "rows": row_payloads,
        "warnings": warnings,
        "passed": passed,
        "pipeline_command": plan.get("pipeline_command", []),
        "note": (
            "This is only a pre-run budget estimate. Do not copy these estimates "
            "into the Results section as measured runtime or speedup data."
        ),
    }


def benchmark_budget_markdown(payload: dict[str, Any]) -> str:
    """Render the budget estimate as Markdown for teammates."""

    command = " ".join(str(part) for part in payload.get("pipeline_command", []))
    lines = [
        "# Benchmark Runtime Budget",
        "",
        "This file is a pre-run estimate. It is not final benchmark data.",
        "",
        "## Summary",
        "",
        f"- Label: `{payload.get('label')}`",
        f"- Plan label: `{payload.get('plan_label')}`",
        f"- Run label: `{payload.get('run_label')}`",
        f"- Config: `{payload.get('config')}`",
        f"- Results dir checked for reusable runs: `{payload.get('results_dir')}`",
        f"- Existing-run reuse enabled: `{payload.get('reuse_existing')}`",
        f"- Passed budget guard: `{payload.get('passed')}`",
        f"- Estimated total time: `{payload.get('estimated_total_seconds'):.2f}` s "
        f"(`{payload.get('estimated_total_minutes'):.2f}` min)",
        f"- Estimated remaining time: `{payload.get('estimated_remaining_seconds', payload.get('estimated_total_seconds')):.2f}` s "
        f"(`{payload.get('estimated_remaining_minutes', payload.get('estimated_total_minutes')):.2f}` min)",
        f"- Largest single planned run: `{payload.get('largest_run_seconds'):.2f}` s",
        f"- Largest remaining run: `{payload.get('largest_remaining_run_seconds', payload.get('largest_run_seconds')):.2f}` s",
        f"- Reusable runs: `{payload.get('num_reusable_rows', 0)}` / `{payload.get('num_rows', 0)}`",
        f"- Max allowed total time: `{payload.get('max_total_seconds')}` s",
        "",
        "## Planned Runs",
        "",
        "| Kind | Run ID | N | Processes | Status | Estimated seconds | Remaining seconds | Note |",
        "|---|---|---:|---:|---|---:|---:|---|",
    ]
    for row in payload.get("rows", []):
        note = row.get("note", "")
        reason = row.get("reuse_reason", "")
        if reason:
            note = f"{note}; {reason}"
        lines.append(
            f"| {row.get('kind')} | `{row.get('run_id')}` | {row.get('input_size_n')} | {row.get('processes')} | "
            f"{row.get('status')} | {float(row.get('estimated_seconds', 0.0)):.2f} | "
            f"{float(row.get('remaining_seconds', row.get('estimated_seconds', 0.0))):.2f} | {note} |"
        )

    warnings = payload.get("warnings", [])
    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No budget warning for the selected thresholds.")

    lines.extend(["", "## Planned Pipeline Command", "", "```bash", command, "```", ""])
    lines.append(str(payload.get("note", "")))
    lines.append("")
    return "\n".join(lines)


def write_benchmark_budget(
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown budget artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(benchmark_budget_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
