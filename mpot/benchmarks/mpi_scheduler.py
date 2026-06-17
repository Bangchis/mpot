"""Task assignment helpers for MPI runs.

This file belongs to the parallelization part of the project. The core idea is
1D cyclic mapping: task i goes to rank i mod P.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    """Minimal task description that can be sent to an MPI worker."""

    task_id: int
    seed: int


def build_tasks(total_tasks: int, base_seed: int) -> list[TaskSpec]:
    """Create deterministic tasks in task-id order."""

    if total_tasks <= 0:
        raise ValueError("total_tasks must be positive.")
    return [TaskSpec(task_id=i, seed=int(base_seed) + i) for i in range(total_tasks)]


def cyclic_owner(task_id: int, size: int) -> int:
    """Return the rank that owns one task under 1D cyclic mapping."""

    if size <= 0:
        raise ValueError("size must be positive.")
    if task_id < 0:
        raise ValueError("task_id must be non-negative.")
    return int(task_id) % int(size)


def cyclic_chunks(tasks: list[TaskSpec], size: int) -> list[list[TaskSpec]]:
    """Split tasks into one chunk per rank using cyclic mapping."""

    if size <= 0:
        raise ValueError("size must be positive.")
    chunks: list[list[TaskSpec]] = [[] for _ in range(size)]
    for task in tasks:
        chunks[cyclic_owner(task.task_id, size)].append(task)
    return chunks


def validate_assignment(tasks: list[TaskSpec], chunks: list[list[TaskSpec]]) -> None:
    """Check that every task appears exactly once in the chunk list."""

    expected = sorted(task.task_id for task in tasks)
    observed = sorted(task.task_id for chunk in chunks for task in chunk)
    if observed != expected:
        raise ValueError(f"Invalid task assignment: expected {expected}, observed {observed}")


def describe_chunks(chunks: list[list[TaskSpec]]) -> list[dict[str, int | list[int]]]:
    """Return a readable summary for logs and JSON output."""

    return [
        {
            "rank": rank,
            "num_tasks": len(chunk),
            "task_ids": [task.task_id for task in chunk],
        }
        for rank, chunk in enumerate(chunks)
    ]

