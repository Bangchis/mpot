"""Validate that a saved trajectory is a valid 2D planning solution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math

from mpot.benchmarks.artifacts import read_json, write_json


@dataclass
class SolutionCheck:
    """One pass/fail check for a saved best trajectory."""

    name: str
    passed: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _dist2(a: list[float], b: list[float]) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def _finite_trajectory(trajectory: list[list[float]]) -> bool:
    return all(math.isfinite(float(value)) for state in trajectory for value in state)


def _hard_collision_fraction(trajectory: list[list[float]], obstacles: list[dict[str, Any]]) -> float:
    if not obstacles or not trajectory:
        return 0.0
    colliding = 0
    for state in trajectory:
        px, py = float(state[0]), float(state[1])
        hit = False
        for obstacle in obstacles:
            cx, cy = obstacle["center"]
            radius = float(obstacle["radius"])
            if math.sqrt((px - float(cx)) ** 2 + (py - float(cy)) ** 2) <= radius:
                hit = True
                break
        if hit:
            colliding += 1
    return colliding / len(trajectory)


def _max_bounds_violation(
    trajectory: list[list[float]],
    workspace_min: list[float],
    workspace_max: list[float],
) -> float:
    max_violation = 0.0
    xmin, ymin = float(workspace_min[0]), float(workspace_min[1])
    xmax, ymax = float(workspace_max[0]), float(workspace_max[1])
    for state in trajectory:
        x, y = float(state[0]), float(state[1])
        violations = [xmin - x, ymin - y, x - xmax, y - ymax, 0.0]
        max_violation = max(max_violation, max(violations))
    return max_violation


def _best_task_row(summary: dict[str, Any], task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    best_task_id = int(summary["best_task_id"])
    best_seed = int(summary["best_seed"])
    for row in task_rows:
        if int(row["task_id"]) == best_task_id and int(row["seed"]) == best_seed:
            return row
    raise ValueError(f"Best task id/seed not found in task_results.json: task={best_task_id}, seed={best_seed}")


def validate_solution_quality(
    run_dir: str | Path,
    *,
    start_tolerance: float = 1.0e-3,
    goal_tolerance: float = 1.0e-3,
    max_collision_fraction: float = 0.0,
    bounds_tolerance: float = 1.0e-6,
) -> dict[str, Any]:
    """Validate the best trajectory saved by one serial or MPI run."""

    root = Path(run_dir)
    summary = read_json(root / "summary.json")
    task_rows = read_json(root / "task_results.json")
    best = _best_task_row(summary, task_rows)
    trajectory = best.get("trajectory", [])
    problem = summary["problem"]

    start = problem["start"]
    goal = problem["goal"]
    expected_len = int(problem["traj_len"])
    start_error = _dist2(trajectory[0], start) if trajectory else math.inf
    goal_error = _dist2(trajectory[-1], goal) if trajectory else math.inf
    collision_fraction = _hard_collision_fraction(trajectory, problem.get("obstacles", []))
    max_bounds_violation = _max_bounds_violation(
        trajectory,
        problem["workspace_min"],
        problem["workspace_max"],
    )
    best_cost = float(best["best_cost"])

    checks = [
        SolutionCheck("trajectory exists", bool(trajectory), f"states={len(trajectory)}"),
        SolutionCheck(
            "trajectory length matches problem",
            len(trajectory) == expected_len,
            f"observed={len(trajectory)}, expected={expected_len}",
        ),
        SolutionCheck("trajectory values are finite", _finite_trajectory(trajectory), "finite values required"),
        SolutionCheck("best cost is finite", math.isfinite(best_cost), f"best_cost={best_cost}"),
        SolutionCheck(
            "start state is respected",
            start_error <= start_tolerance,
            f"start_error={start_error}, tolerance={start_tolerance}",
        ),
        SolutionCheck(
            "goal state is reached",
            goal_error <= goal_tolerance,
            f"goal_error={goal_error}, tolerance={goal_tolerance}",
        ),
        SolutionCheck(
            "hard obstacle collision fraction is acceptable",
            collision_fraction <= max_collision_fraction,
            f"collision_fraction={collision_fraction}, max={max_collision_fraction}",
        ),
        SolutionCheck(
            "trajectory stays inside workspace bounds",
            max_bounds_violation <= bounds_tolerance,
            f"max_bounds_violation={max_bounds_violation}, tolerance={bounds_tolerance}",
        ),
    ]
    failed = [item for item in checks if not item.passed]
    return {
        "run_dir": str(root),
        "run_id": summary.get("run_id", root.name),
        "mode": summary.get("mode", ""),
        "input_size_n": int(summary["total_tasks"]),
        "processes": int(summary["size"]),
        "best_task_id": int(summary["best_task_id"]),
        "best_seed": int(summary["best_seed"]),
        "best_cost": best_cost,
        "trajectory_len": len(trajectory),
        "expected_traj_len": expected_len,
        "start_error": start_error,
        "goal_error": goal_error,
        "hard_collision_fraction": collision_fraction,
        "summary_collision_fraction": float(summary.get("best_collision_fraction", collision_fraction)),
        "max_bounds_violation": max_bounds_violation,
        "passed": not failed,
        "num_checks": len(checks),
        "num_failed": len(failed),
        "checks": [item.to_json() for item in checks],
        "note": "Derived only from saved summary.json and task_results.json artifacts.",
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def solution_quality_markdown(payload: dict[str, Any]) -> str:
    """Render solution quality validation as Markdown."""

    verdict = "PASS" if payload.get("passed") else "FAIL"
    lines = [
        "# Solution Quality Validation",
        "",
        "This validation checks the saved best trajectory against the 2D planning problem.",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- mode: `{payload['mode']}`",
        f"- verdict: **{verdict}**",
        f"- best_task_id: `{payload['best_task_id']}`",
        f"- best_seed: `{payload['best_seed']}`",
        f"- best_cost: `{_fmt(payload['best_cost'])}`",
        f"- start_error: `{_fmt(payload['start_error'])}`",
        f"- goal_error: `{_fmt(payload['goal_error'])}`",
        f"- hard_collision_fraction: `{_fmt(payload['hard_collision_fraction'])}`",
        f"- max_bounds_violation: `{_fmt(payload['max_bounds_violation'])}`",
        "",
        "## Checks",
        "",
        "| status | check | detail |",
        "|---|---|---|",
    ]
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"| {status} | {check['name']} | `{check['detail']}` |")
    lines.extend(["", payload["note"], ""])
    return "\n".join(lines)


def write_solution_quality(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write solution quality JSON and Markdown artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(solution_quality_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
