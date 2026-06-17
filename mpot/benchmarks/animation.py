"""Small GIF animation helper for 2D trajectory demos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mpot.benchmarks.artifacts import read_json, write_json
from mpot.benchmarks.config import config_from_dict
from mpot.benchmarks.local_runner import run_task_trace
from mpot.benchmarks.mpi_scheduler import TaskSpec


TRACE_COLORS = [
    "#4e79a7",
    "#f28e2b",
    "#59a14f",
    "#e15759",
    "#76b7b2",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#2f4b7c",
    "#665191",
    "#a05195",
]


def _require_animation_tools():
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation, PillowWriter
    except Exception as exc:
        raise RuntimeError("matplotlib and Pillow are required to generate GIF files.") from exc
    return plt, FuncAnimation, PillowWriter


def _load_best_trajectory(run_dir: Path) -> tuple[list[list[float]], dict[str, Any]]:
    summary = read_json(run_dir / "summary.json")
    tasks = read_json(run_dir / "task_results.json")
    best_id = int(summary["best_task_id"])
    rows = [row for row in tasks if int(row["task_id"]) == best_id]
    if not rows:
        raise ValueError(f"Best task {best_id} not found in task_results.json.")
    return rows[0]["trajectory"], summary["problem"]


def animate_best_path(run_dir: str | Path, output: str | Path | None = None, fps: int = 8) -> Path:
    """Create a short GIF showing the point robot moving along the best path."""

    plt, FuncAnimation, PillowWriter = _require_animation_tools()
    run_dir = Path(run_dir)
    traj, problem = _load_best_trajectory(run_dir)
    xs = [state[0] for state in traj]
    ys = [state[1] for state in traj]

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(xs, ys, color="#4472c4", linewidth=1.5, alpha=0.35, label="best path")
    robot, = ax.plot([], [], marker="o", color="#d62728", markersize=7, label="robot")
    trace, = ax.plot([], [], color="#d62728", linewidth=2, alpha=0.75)
    ax.scatter([problem["start"][0]], [problem["start"][1]], c="green", label="start")
    ax.scatter([problem["goal"][0]], [problem["goal"][1]], c="red", marker="*", label="goal")

    for obstacle in problem["obstacles"]:
        safety = plt.Circle(
            obstacle["center"],
            obstacle["radius"] + obstacle["safety_margin"],
            color="orange",
            alpha=0.12,
        )
        circle = plt.Circle(obstacle["center"], obstacle["radius"], color="black", alpha=0.25)
        ax.add_patch(safety)
        ax.add_patch(circle)

    ax.set_xlim(problem["workspace_min"][0], problem["workspace_max"][0])
    ax.set_ylim(problem["workspace_min"][1], problem["workspace_max"][1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("Best trajectory animation")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(loc="best")

    def update(frame: int):
        robot.set_data([xs[frame]], [ys[frame]])
        trace.set_data(xs[: frame + 1], ys[: frame + 1])
        return robot, trace

    animation = FuncAnimation(fig, update, frames=len(xs), interval=1000 / max(1, fps), blit=True)
    out = Path(output) if output else run_dir / "best_path.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    animation.save(out, writer=PillowWriter(fps=max(1, fps)))
    plt.close(fig)
    return out


def _load_trace_source(run_dir: Path):
    """Load config and best task metadata from one completed run."""

    summary = read_json(run_dir / "summary.json")
    if "config" not in summary:
        raise ValueError("summary.json must contain embedded config to regenerate an algorithm trace.")
    config = config_from_dict(summary["config"])
    task = TaskSpec(task_id=int(summary["best_task_id"]), seed=int(summary["best_seed"]))
    return config, task, summary["problem"]


def _draw_problem(ax, plt, problem: dict[str, Any]) -> None:
    """Draw workspace, start/goal, and circular obstacles."""

    ax.scatter(
        [problem["start"][0]],
        [problem["start"][1]],
        c="#2ca02c",
        marker="o",
        s=58,
        label="start",
        edgecolors="white",
        linewidths=0.7,
        zorder=6,
    )
    ax.scatter(
        [problem["goal"][0]],
        [problem["goal"][1]],
        c="#d62728",
        marker="*",
        s=95,
        label="goal",
        edgecolors="white",
        linewidths=0.7,
        zorder=6,
    )
    for obstacle in problem["obstacles"]:
        safety = plt.Circle(
            obstacle["center"],
            obstacle["radius"] + obstacle["safety_margin"],
            facecolor="#f28e2b",
            edgecolor="#f28e2b",
            linewidth=1.0,
            alpha=0.20,
        )
        circle = plt.Circle(
            obstacle["center"],
            obstacle["radius"],
            facecolor="#222222",
            edgecolor="#000000",
            linewidth=1.2,
            alpha=0.48,
        )
        ax.add_patch(safety)
        ax.add_patch(circle)
    ax.set_xlim(problem["workspace_min"][0], problem["workspace_max"][0])
    ax.set_ylim(problem["workspace_min"][1], problem["workspace_max"][1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def animate_algorithm_trace(
    run_dir: str | Path,
    output: str | Path | None = None,
    *,
    trace_output: str | Path | None = None,
    fps: int = 3,
    max_particles: int = 24,
) -> Path:
    """Create a GIF showing MPOT particles improving over outer iterations.

    The completed run stores only final task results. To visualize the
    algorithm, this helper reruns the run's best seed with history enabled,
    which is much cheaper than rerunning the whole sweep.
    """

    plt, FuncAnimation, PillowWriter = _require_animation_tools()
    run_dir = Path(run_dir)
    config, task, problem = _load_trace_source(run_dir)
    trace_payload = run_task_trace(config, task)
    if trace_output is not None:
        write_json(trace_output, trace_payload)

    frames = trace_payload["frames"]
    if not frames:
        raise ValueError("No algorithm trace frames were produced.")
    num_particles = min(int(max_particles), len(frames[0]["trajectories"]))
    num_probe = int(config.optimizer.num_probe)
    num_obstacles = len(problem.get("obstacles", []))

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    _draw_problem(ax, plt, problem)
    particle_lines = [
        ax.plot(
            [],
            [],
            color=TRACE_COLORS[index % len(TRACE_COLORS)],
            linewidth=1.35,
            alpha=0.68,
            marker=".",
            markersize=2.2,
            zorder=3,
        )[0]
        for index in range(num_particles)
    ]
    best_line, = ax.plot(
        [],
        [],
        color="#0057b8",
        linewidth=3.0,
        marker="o",
        markersize=3.2,
        label="best current",
        zorder=5,
    )
    best_point, = ax.plot([], [], marker="o", color="#d62728", markersize=6.5, zorder=7)
    text = ax.text(
        0.02,
        0.98,
        "",
        transform=ax.transAxes,
        ha="left",
        va="top",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.8, "edgecolor": "#cccccc"},
    )
    ax.set_title("MPOT particle optimization trace")
    ax.legend(loc="lower right")

    def update(frame_index: int):
        frame = frames[frame_index]
        trajectories = frame["trajectories"][:num_particles]
        for line, traj in zip(particle_lines, trajectories):
            xs = [state[0] for state in traj]
            ys = [state[1] for state in traj]
            line.set_data(xs, ys)

        best = frame["trajectories"][int(frame["best_index"])]
        best_x = [state[0] for state in best]
        best_y = [state[1] for state in best]
        best_line.set_data(best_x, best_y)
        best_point.set_data([best_x[-1]], [best_y[-1]])
        text.set_text(
            "iteration: {iteration}\n"
            "particles shown: {shown}/{particles}\n"
            "probe samples/direction: {num_probe}\n"
            "obstacles: {obstacles}\n"
            "best cost: {cost:.6f}".format(
                iteration=frame["iteration"],
                shown=num_particles,
                particles=len(frame["trajectories"]),
                num_probe=num_probe,
                obstacles=num_obstacles,
                cost=float(frame["best_cost"]),
            )
        )
        return [*particle_lines, best_line, best_point, text]

    animation = FuncAnimation(fig, update, frames=len(frames), interval=1000 / max(1, fps), blit=True)
    out = Path(output) if output else run_dir / "algorithm_trace.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    animation.save(out, writer=PillowWriter(fps=max(1, fps)))
    plt.close(fig)
    return out
