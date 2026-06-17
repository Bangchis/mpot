"""Deterministic result selection shared by serial and MPI runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable
import math


@dataclass
class TaskResult:
    """Best trajectory summary produced by one task/seed."""

    task_id: int
    seed: int
    rank: int
    best_cost: float
    opt_iters: int
    runtime_s: float
    num_particles: int
    traj_len: int
    collision_fraction: float
    trajectory: list[list[float]]

    def to_record(self, run_id: str) -> dict[str, Any]:
        """Return a CSV/JSON friendly row without the full trajectory payload."""

        return {
            "run_id": run_id,
            "rank": self.rank,
            "task_id": self.task_id,
            "seed": self.seed,
            "num_particles": self.num_particles,
            "traj_len": self.traj_len,
            "opt_iters": self.opt_iters,
            "runtime_s": self.runtime_s,
            "best_cost": self.best_cost,
            "collision_fraction": self.collision_fraction,
        }

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RankTiming:
    """Per-rank timing summary gathered by rank 0."""

    rank: int
    size: int
    hostname: str
    num_tasks: int
    compute_time_s: float
    communication_time_s: float
    total_time_s: float
    best_cost: float

    def to_record(self, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "rank": self.rank,
            "size": self.size,
            "hostname": self.hostname,
            "num_tasks": self.num_tasks,
            "compute_time_s": self.compute_time_s,
            "communication_time_s": self.communication_time_s,
            "total_time_s": self.total_time_s,
            "best_cost": self.best_cost,
        }


def result_key(result: TaskResult) -> tuple[float, int, int]:
    """Sort key used by both serial and MPI result reduction.

    Lower cost is better. If two tasks have the same cost within normal floating
    point sorting, lower task id wins, then lower seed wins. This rule is simple
    enough for every group member to explain during the demo.
    """

    cost = float(result.best_cost)
    if math.isnan(cost):
        cost = math.inf
    return (cost, int(result.task_id), int(result.seed))


def choose_best(results: Iterable[TaskResult]) -> TaskResult:
    """Return the deterministic best result from a non-empty iterable."""

    materialized = list(results)
    if not materialized:
        raise ValueError("Cannot choose a best result from an empty result list.")
    return min(materialized, key=result_key)


def flatten_result_groups(groups: Iterable[Iterable[TaskResult]]) -> list[TaskResult]:
    """Flatten gathered per-rank result lists into one task-result list."""

    flat: list[TaskResult] = []
    for group in groups:
        flat.extend(group)
    return flat


def task_results_from_json(rows: Iterable[dict[str, Any]]) -> list[TaskResult]:
    """Rebuild TaskResult objects from JSON data."""

    return [
        TaskResult(
            task_id=int(row["task_id"]),
            seed=int(row["seed"]),
            rank=int(row["rank"]),
            best_cost=float(row["best_cost"]),
            opt_iters=int(row["opt_iters"]),
            runtime_s=float(row["runtime_s"]),
            num_particles=int(row["num_particles"]),
            traj_len=int(row["traj_len"]),
            collision_fraction=float(row["collision_fraction"]),
            trajectory=[[float(v) for v in state] for state in row["trajectory"]],
        )
        for row in rows
    ]

