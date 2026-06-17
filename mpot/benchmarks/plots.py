"""Plot helpers for benchmark artifacts.

The plotting functions are deliberately simple. They read the same CSV/JSON
files used by the report, which keeps the figures tied to real experiment data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import csv

from mpot.benchmarks.artifacts import read_json


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate PNG report figures.") from exc
    return plt


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _best_trajectory_and_problem(run_dir: Path) -> tuple[list[list[float]], dict[str, Any]]:
    """Load the best trajectory and 2D problem summary for one run."""

    summary = read_json(run_dir / "summary.json")
    tasks = read_json(run_dir / "task_results.json")
    best_id = int(summary["best_task_id"])
    best_rows = [row for row in tasks if int(row["task_id"]) == best_id]
    if not best_rows:
        raise ValueError(f"Best task {best_id} not found in task_results.json.")
    return best_rows[0]["trajectory"], summary["problem"]


def plot_best_path(run_dir: str | Path) -> Path:
    """Draw the best trajectory and circular obstacles for one run."""

    plt = _require_matplotlib()
    run_dir = Path(run_dir)
    traj, problem = _best_trajectory_and_problem(run_dir)
    xs = [state[0] for state in traj]
    ys = [state[1] for state in traj]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(xs, ys, marker="o", linewidth=2, markersize=3, label="best trajectory")
    ax.scatter([problem["start"][0]], [problem["start"][1]], c="green", label="start")
    ax.scatter([problem["goal"][0]], [problem["goal"][1]], c="red", label="goal")
    for obstacle in problem["obstacles"]:
        circle = plt.Circle(
            obstacle["center"],
            obstacle["radius"],
            color="black",
            alpha=0.25,
        )
        safety = plt.Circle(
            obstacle["center"],
            obstacle["radius"] + obstacle["safety_margin"],
            color="orange",
            alpha=0.12,
        )
        ax.add_patch(safety)
        ax.add_patch(circle)
    ax.set_xlim(problem["workspace_min"][0], problem["workspace_max"][0])
    ax.set_ylim(problem["workspace_min"][1], problem["workspace_max"][1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("Best trajectory")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(loc="best")
    fig.tight_layout()
    out = run_dir / "best_path.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def plot_rank_time_breakdown(run_dir: str | Path) -> Path:
    """Create the stacked compute/communication bar chart required by the report."""

    plt = _require_matplotlib()
    run_dir = Path(run_dir)
    rows = _read_csv(run_dir / "rank_timings.csv")
    ranks = [int(row["rank"]) for row in rows]
    compute = [float(row["compute_time_s"]) for row in rows]
    comm = [float(row["communication_time_s"]) for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(ranks, compute, label="compute time")
    ax.bar(ranks, comm, bottom=compute, label="communication time")
    ax.set_title("Per-rank time breakdown")
    ax.set_xlabel("MPI rank")
    ax.set_ylabel("seconds")
    ax.legend(loc="best")
    fig.tight_layout()
    out = run_dir / "rank_time_breakdown.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def plot_cost_by_task(run_dir: str | Path) -> Path:
    """Plot task cost to make stochastic search behavior visible."""

    plt = _require_matplotlib()
    run_dir = Path(run_dir)
    rows = _read_csv(run_dir / "task_results.csv")
    task_ids = [int(row["task_id"]) for row in rows]
    costs = [float(row["best_cost"]) for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(task_ids, costs, marker="o", linewidth=1)
    ax.set_title("Best cost per task")
    ax.set_xlabel("task id")
    ax.set_ylabel("best cost")
    fig.tight_layout()
    out = run_dir / "cost_by_task.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def collect_summaries(
    results_dir: str | Path,
    label: str | None = None,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    """Read every summary.json under a results directory."""

    root = Path(results_dir)
    summaries = []
    for path in sorted(root.glob("*/summary.json")):
        payload = read_json(path)
        run_id = str(payload.get("run_id", path.parent.name))
        experiment = str(payload.get("config", {}).get("experiment_name", ""))
        if label and label not in run_id and label not in experiment:
            continue
        if mode and payload.get("mode") != mode:
            continue
        payload["_run_dir"] = str(path.parent)
        summaries.append(payload)
    return summaries


def plot_runtime_vs_input_size(
    results_dir: str | Path,
    output_dir: str | Path,
    label: str | None = None,
    fixed_size: int | None = None,
) -> Path:
    """Plot runtime against total_tasks for all discovered summaries."""

    plt = _require_matplotlib()
    summaries = collect_summaries(results_dir, label=label)
    if not summaries:
        raise ValueError("No summary.json files found.")
    if fixed_size is not None:
        summaries = [s for s in summaries if int(s["size"]) == fixed_size]
    if not summaries:
        raise ValueError("No summaries match the requested filters.")

    summaries = sorted(summaries, key=lambda s: (int(s["total_tasks"]), int(s["size"])))
    x = [int(s["total_tasks"]) for s in summaries]
    with_comm = [float(s["runtime_with_communication_s"]) for s in summaries]
    without_comm = [float(s["runtime_without_communication_s"]) for s in summaries]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, with_comm, marker="o", label="with communication")
    ax.plot(x, without_comm, marker="s", label="without communication")
    ax.set_title("Runtime vs input size N")
    ax.set_xlabel("N = total planning tasks")
    ax.set_ylabel("seconds")
    ax.legend(loc="best")
    fig.tight_layout()
    suffix = f"_{label}" if label else ""
    out = Path(output_dir) / f"runtime_vs_input_size{suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def plot_speedup(
    results_dir: str | Path,
    output_dir: str | Path,
    label: str | None = None,
    input_size: int | None = None,
) -> Path:
    """Plot speedup for summaries that share the largest input size."""

    plt = _require_matplotlib()
    summaries = collect_summaries(results_dir, label=label, mode="mpi")
    if not summaries:
        raise ValueError("No summary.json files found.")

    selected_n = input_size if input_size is not None else max(int(s["total_tasks"]) for s in summaries)
    chosen = sorted(
        [s for s in summaries if int(s["total_tasks"]) == selected_n],
        key=lambda s: int(s["size"]),
    )
    if not chosen:
        raise ValueError("No summaries match the requested input size.")
    serial_candidates = [s for s in chosen if int(s["size"]) == 1]
    if not serial_candidates:
        raise ValueError("Need at least one size=1 run to plot speedup.")
    serial_time = float(serial_candidates[0]["runtime_with_communication_s"])
    sizes = [int(s["size"]) for s in chosen]
    speedups = [serial_time / float(s["runtime_with_communication_s"]) for s in chosen]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sizes, speedups, marker="o", label="measured speedup")
    ax.plot(sizes, sizes, linestyle="--", color="gray", label="ideal")
    ax.set_title(f"Speedup for N={selected_n}")
    ax.set_xlabel("process count")
    ax.set_ylabel("speedup")
    ax.legend(loc="best")
    fig.tight_layout()
    suffix = f"_{label}" if label else ""
    out = Path(output_dir) / f"speedup{suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out
