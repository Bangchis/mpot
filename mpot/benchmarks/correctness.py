"""Correctness checks between serial and MPI benchmark runs.

For this project, MPI correctness means that parallel execution covers the same
deterministic tasks as the serial baseline and returns equivalent per-task
optimization results. The final best trajectory is then a deterministic
reduction over the same task set.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import math

from mpot.benchmarks.artifacts import read_json
from mpot.benchmarks.reduction import TaskResult, task_results_from_json


@dataclass
class TaskComparison:
    """One row comparing a serial task result with the MPI task result."""

    task_id: int
    serial_seed: int | None
    mpi_seed: int | None
    serial_rank: int | None
    mpi_rank: int | None
    serial_best_cost: float | None
    mpi_best_cost: float | None
    cost_difference: float | None
    seed_match: bool
    cost_close: bool
    present_in_serial: bool
    present_in_mpi: bool
    passed: bool

    def to_record(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "serial_seed": "" if self.serial_seed is None else self.serial_seed,
            "mpi_seed": "" if self.mpi_seed is None else self.mpi_seed,
            "serial_rank": "" if self.serial_rank is None else self.serial_rank,
            "mpi_rank": "" if self.mpi_rank is None else self.mpi_rank,
            "serial_best_cost": "" if self.serial_best_cost is None else self.serial_best_cost,
            "mpi_best_cost": "" if self.mpi_best_cost is None else self.mpi_best_cost,
            "cost_difference": "" if self.cost_difference is None else self.cost_difference,
            "seed_match": self.seed_match,
            "cost_close": self.cost_close,
            "present_in_serial": self.present_in_serial,
            "present_in_mpi": self.present_in_mpi,
            "passed": self.passed,
        }


TASK_COMPARISON_FIELDS = [
    "task_id",
    "serial_seed",
    "mpi_seed",
    "serial_rank",
    "mpi_rank",
    "serial_best_cost",
    "mpi_best_cost",
    "cost_difference",
    "seed_match",
    "cost_close",
    "present_in_serial",
    "present_in_mpi",
    "passed",
]


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance or math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def _task_index(results: Iterable[TaskResult]) -> tuple[dict[int, TaskResult], list[int]]:
    index: dict[int, TaskResult] = {}
    duplicates: list[int] = []
    for result in results:
        task_id = int(result.task_id)
        if task_id in index:
            duplicates.append(task_id)
        else:
            index[task_id] = result
    return index, duplicates


def compare_task_results(
    serial_results: Iterable[TaskResult],
    mpi_results: Iterable[TaskResult],
    tolerance: float,
) -> tuple[list[TaskComparison], dict[str, Any]]:
    """Compare serial and MPI task-level outputs."""

    serial_index, serial_duplicates = _task_index(serial_results)
    mpi_index, mpi_duplicates = _task_index(mpi_results)
    all_task_ids = sorted(set(serial_index) | set(mpi_index))
    rows: list[TaskComparison] = []

    for task_id in all_task_ids:
        serial = serial_index.get(task_id)
        mpi = mpi_index.get(task_id)
        present_in_serial = serial is not None
        present_in_mpi = mpi is not None
        seed_match = bool(serial and mpi and int(serial.seed) == int(mpi.seed))
        if serial is not None and mpi is not None:
            cost_difference = abs(float(serial.best_cost) - float(mpi.best_cost))
            cost_close = _close(float(serial.best_cost), float(mpi.best_cost), tolerance)
        else:
            cost_difference = None
            cost_close = False

        passed = present_in_serial and present_in_mpi and seed_match and cost_close
        rows.append(
            TaskComparison(
                task_id=task_id,
                serial_seed=None if serial is None else int(serial.seed),
                mpi_seed=None if mpi is None else int(mpi.seed),
                serial_rank=None if serial is None else int(serial.rank),
                mpi_rank=None if mpi is None else int(mpi.rank),
                serial_best_cost=None if serial is None else float(serial.best_cost),
                mpi_best_cost=None if mpi is None else float(mpi.best_cost),
                cost_difference=cost_difference,
                seed_match=seed_match,
                cost_close=cost_close,
                present_in_serial=present_in_serial,
                present_in_mpi=present_in_mpi,
                passed=passed,
            )
        )

    failed_rows = [row for row in rows if not row.passed]
    cost_differences = [row.cost_difference for row in rows if row.cost_difference is not None]
    summary = {
        "num_serial_tasks": len(serial_index),
        "num_mpi_tasks": len(mpi_index),
        "num_compared_tasks": len(rows),
        "num_failed_tasks": len(failed_rows),
        "same_task_ids": set(serial_index) == set(mpi_index),
        "all_seeds_match": all(row.seed_match for row in rows),
        "all_task_costs_close": all(row.cost_close for row in rows),
        "max_task_cost_difference": max(cost_differences) if cost_differences else None,
        "serial_duplicate_task_ids": sorted(serial_duplicates),
        "mpi_duplicate_task_ids": sorted(mpi_duplicates),
        "missing_in_mpi": sorted(set(serial_index) - set(mpi_index)),
        "extra_in_mpi": sorted(set(mpi_index) - set(serial_index)),
        "failed_task_samples": [row.to_record() for row in failed_rows[:10]],
    }
    summary["tasks_passed"] = (
        summary["same_task_ids"]
        and summary["all_seeds_match"]
        and summary["all_task_costs_close"]
        and not summary["serial_duplicate_task_ids"]
        and not summary["mpi_duplicate_task_ids"]
    )
    return rows, summary


def load_run_task_results(run_dir: str | Path) -> list[TaskResult]:
    """Load task results from a standard run directory."""

    return task_results_from_json(read_json(Path(run_dir) / "task_results.json"))


def compare_run_directories(
    serial_dir: str | Path,
    mpi_dir: str | Path,
    tolerance: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compare two standard run directories and return report payload plus rows."""

    serial_dir = Path(serial_dir)
    mpi_dir = Path(mpi_dir)
    serial_summary = read_json(serial_dir / "summary.json")
    mpi_summary = read_json(mpi_dir / "summary.json")
    serial_results = load_run_task_results(serial_dir)
    mpi_results = load_run_task_results(mpi_dir)
    task_rows, task_summary = compare_task_results(serial_results, mpi_results, tolerance)

    same_total_tasks = int(serial_summary["total_tasks"]) == int(mpi_summary["total_tasks"])
    same_best_task = int(serial_summary["best_task_id"]) == int(mpi_summary["best_task_id"])
    same_best_seed = int(serial_summary["best_seed"]) == int(mpi_summary["best_seed"])
    best_cost_difference = abs(float(serial_summary["best_cost"]) - float(mpi_summary["best_cost"]))
    best_cost_close = _close(float(serial_summary["best_cost"]), float(mpi_summary["best_cost"]), tolerance)
    passed = same_total_tasks and same_best_task and same_best_seed and best_cost_close and task_summary["tasks_passed"]

    payload = {
        "serial_run": str(serial_dir),
        "mpi_run": str(mpi_dir),
        "serial_run_id": serial_summary.get("run_id", serial_dir.name),
        "mpi_run_id": mpi_summary.get("run_id", mpi_dir.name),
        "serial_total_tasks": int(serial_summary["total_tasks"]),
        "mpi_total_tasks": int(mpi_summary["total_tasks"]),
        "same_total_tasks": same_total_tasks,
        "same_best_task": same_best_task,
        "same_best_seed": same_best_seed,
        "best_cost_difference": best_cost_difference,
        "cost_difference": best_cost_difference,
        "best_cost_close": best_cost_close,
        "tolerance": tolerance,
        "task_level": task_summary,
        "passed": passed,
    }
    return payload, [row.to_record() for row in task_rows]
