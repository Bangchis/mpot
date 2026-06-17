"""Artifact writers for serial and MPI benchmark runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import json

from mpot.benchmarks.config import ExperimentConfig, config_hash, config_to_dict, save_config
from mpot.benchmarks.metrics import (
    runtime_with_communication,
    runtime_without_communication,
    summarize_load_balance,
)
from mpot.benchmarks.reduction import RankTiming, TaskResult


def make_run_dir(config: ExperimentConfig, run_id: str) -> Path:
    """Create and return the output directory for one run."""

    path = Path(config.output_dir) / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: str | Path, payload: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Write CSV rows with stable column order."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def save_trajectory(path: str | Path, trajectory: list[list[float]]) -> str:
    """Save best trajectory as .npy when NumPy is available.

    The fallback JSON file keeps the run usable on incomplete environments, but
    the intended final artifact is the .npy file.
    """

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np

        np.save(out, np.asarray(trajectory, dtype=float))
        return str(out)
    except ModuleNotFoundError:
        fallback = out.with_suffix(".json")
        write_json(fallback, {"trajectory": trajectory})
        return str(fallback)


def task_csv_rows(run_id: str, results: list[TaskResult]) -> list[dict[str, Any]]:
    return [result.to_record(run_id) for result in sorted(results, key=lambda r: r.task_id)]


def rank_csv_rows(run_id: str, timings: list[RankTiming]) -> list[dict[str, Any]]:
    return [timing.to_record(run_id) for timing in sorted(timings, key=lambda t: t.rank)]


def assignment_csv_rows(run_id: str, assignment: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten cyclic task assignment into one readable row per task."""

    rows = []
    process_count = len(assignment)
    for rank_row in sorted(assignment, key=lambda row: int(row["rank"])):
        rank = int(rank_row["rank"])
        task_ids = [int(task_id) for task_id in rank_row.get("task_ids", [])]
        for local_index, task_id in enumerate(task_ids):
            rows.append(
                {
                    "run_id": run_id,
                    "process_count": process_count,
                    "rank": rank,
                    "local_index": local_index,
                    "task_id": task_id,
                    "mapping_rule": "task_id mod process_count",
                }
            )
    return sorted(rows, key=lambda row: int(row["task_id"]))


def comm_event_csv_rows(run_id: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return communication events with run_id and stable rank/event order."""

    rows = []
    for event in sorted(events, key=lambda row: (int(row["rank"]), int(row["event_index"]))):
        rows.append(
            {
                "run_id": run_id,
                "rank": event.get("rank", ""),
                "size": event.get("size", ""),
                "hostname": event.get("hostname", ""),
                "event_index": event.get("event_index", ""),
                "event": event.get("event", ""),
                "collective": event.get("collective", ""),
                "root": event.get("root", ""),
                "blocking": event.get("blocking", ""),
                "duration_s": event.get("duration_s", ""),
                "payload_count": event.get("payload_count", ""),
            }
        )
    return rows


def build_summary(
    *,
    run_id: str,
    mode: str,
    config: ExperimentConfig,
    best: TaskResult,
    results: list[TaskResult],
    rank_timings: list[RankTiming] | None,
    total_time_s: float,
    problem_summary: dict[str, Any],
    task_assignment: list[dict[str, Any]] | None = None,
    comm_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the JSON summary consumed by report/check scripts."""

    rank_timings = rank_timings or []
    if rank_timings:
        runtime_comm = runtime_with_communication(rank_timings)
        runtime_compute = runtime_without_communication(rank_timings)
        load_balance = summarize_load_balance(rank_timings).to_json()
        size = rank_timings[0].size
    else:
        runtime_comm = total_time_s
        runtime_compute = total_time_s
        load_balance = None
        size = 1

    return {
        "run_id": run_id,
        "mode": mode,
        "parallel_backend": "mpi4py" if mode == "mpi" else "serial",
        "device": config.device,
        "experiment_name": config.experiment_name,
        "config_hash": config_hash(config),
        "size": size,
        "total_tasks": config.total_tasks,
        "mapping": "cyclic" if mode == "mpi" else "sequential",
        "best_rank": best.rank,
        "best_task_id": best.task_id,
        "best_seed": best.seed,
        "best_cost": best.best_cost,
        "best_collision_fraction": best.collision_fraction,
        "total_time_s": total_time_s,
        "runtime_with_communication_s": runtime_comm,
        "runtime_without_communication_s": runtime_compute,
        "num_task_results": len(results),
        "load_balance": load_balance,
        "problem": problem_summary,
        "task_assignment": task_assignment,
        "communication_events_count": 0 if comm_events is None else len(comm_events),
    }


def write_run_artifacts(
    *,
    run_dir: Path,
    run_id: str,
    mode: str,
    config: ExperimentConfig,
    best: TaskResult,
    results: list[TaskResult],
    problem_summary: dict[str, Any],
    total_time_s: float,
    rank_timings: list[RankTiming] | None = None,
    task_assignment: list[dict[str, Any]] | None = None,
    comm_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write the standard artifact set for one benchmark run."""

    save_config(config, run_dir / "config.json")

    task_rows = task_csv_rows(run_id, results)
    write_csv(
        run_dir / "task_results.csv",
        task_rows,
        [
            "run_id",
            "rank",
            "task_id",
            "seed",
            "num_particles",
            "traj_len",
            "opt_iters",
            "runtime_s",
            "best_cost",
            "collision_fraction",
        ],
    )
    write_json(run_dir / "task_results.json", [result.to_json() for result in results])

    if rank_timings is not None:
        write_csv(
            run_dir / "rank_timings.csv",
            rank_csv_rows(run_id, rank_timings),
            [
                "run_id",
                "rank",
                "size",
                "hostname",
                "num_tasks",
                "compute_time_s",
                "communication_time_s",
                "total_time_s",
                "best_cost",
            ],
        )

    if task_assignment is not None:
        write_csv(
            run_dir / "task_assignment.csv",
            assignment_csv_rows(run_id, task_assignment),
            [
                "run_id",
                "process_count",
                "rank",
                "local_index",
                "task_id",
                "mapping_rule",
            ],
        )

    if comm_events is not None:
        write_csv(
            run_dir / "comm_events.csv",
            comm_event_csv_rows(run_id, comm_events),
            [
                "run_id",
                "rank",
                "size",
                "hostname",
                "event_index",
                "event",
                "collective",
                "root",
                "blocking",
                "duration_s",
                "payload_count",
            ],
        )

    trajectory_path = save_trajectory(run_dir / "best_trajectory.npy", best.trajectory)

    summary = build_summary(
        run_id=run_id,
        mode=mode,
        config=config,
        best=best,
        results=results,
        rank_timings=rank_timings,
        total_time_s=total_time_s,
        problem_summary=problem_summary,
        task_assignment=task_assignment,
        comm_events=comm_events,
    )
    summary["best_trajectory_path"] = trajectory_path
    summary["config"] = config_to_dict(config)
    write_json(run_dir / "summary.json", summary)
    return summary
