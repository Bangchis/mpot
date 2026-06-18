"""Small GIF animation helper for 2D trajectory demos."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import csv

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
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.animation import FuncAnimation, PillowWriter
    except Exception as exc:
        raise RuntimeError("matplotlib and Pillow are required to generate GIF files.") from exc
    return plt, patches, FuncAnimation, PillowWriter


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

    plt, _, FuncAnimation, PillowWriter = _require_animation_tools()
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

    plt, _, FuncAnimation, PillowWriter = _require_animation_tools()
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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _assignment_from_summary_or_tasks(run_dir: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    assignment = summary.get("task_assignment")
    if assignment:
        return list(assignment)
    rows = read_json(run_dir / "task_results.json")
    grouped: dict[int, list[int]] = {}
    for row in rows:
        grouped.setdefault(int(row["rank"]), []).append(int(row["task_id"]))
    return [
        {"rank": rank, "num_tasks": len(task_ids), "task_ids": sorted(task_ids)}
        for rank, task_ids in sorted(grouped.items())
    ]


def animate_parallel_schedule(run_dir: str | Path, output: str | Path | None = None, fps: int = 1) -> Path:
    """Create a GIF that explains the MPI task-level parallel workflow.

    The animation is intentionally schematic.  It shows the exact task ids
    assigned to each MPI rank, the blocking communication phases, per-rank
    compute/communication time when available, and the final best-task
    reduction.  This is useful for a classroom demo because it visualizes the
    parallel algorithm, not only the robot path.
    """

    plt, patches, FuncAnimation, PillowWriter = _require_animation_tools()
    run_dir = Path(run_dir)
    summary = read_json(run_dir / "summary.json")
    results = read_json(run_dir / "task_results.json")
    assignment = _assignment_from_summary_or_tasks(run_dir, summary)
    rank_rows = _read_csv_rows(run_dir / "rank_timings.csv")
    timings = {int(row["rank"]): row for row in rank_rows if row.get("rank") not in {"", None}}
    result_by_task = {int(row["task_id"]): row for row in results}

    ranks = [int(row["rank"]) for row in assignment]
    if not ranks:
        raise ValueError("No rank assignment is available for the parallel schedule animation.")
    max_tasks = max(len(row.get("task_ids", [])) for row in assignment)
    best_task_id = int(summary.get("best_task_id", -1))
    phases = [
        ("1. broadcast config", "Rank 0 sends shared problem and optimizer settings."),
        ("2. scatter cyclic tasks", "Task i is assigned to rank i mod P."),
        ("3. compute independently", "Each rank runs complete MPOT tasks without inner MPI sync."),
        ("4. gather results", "Workers send compact task results and timings to rank 0."),
        ("5. reduce best trajectory", "Rank 0 selects the minimum-cost trajectory deterministically."),
    ]

    fig_width = max(7.2, 3.2 + 0.65 * max(1, max_tasks))
    fig_height = max(4.2, 1.2 + 0.7 * len(ranks))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    def y_for_rank(rank_index: int) -> float:
        return len(ranks) - rank_index

    def draw_arrow(x0, y0, x1, y1, color="#555555", alpha=0.75):
        ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={"arrowstyle": "->", "color": color, "lw": 1.5, "alpha": alpha},
        )

    def update(frame_index: int):
        phase, detail = phases[frame_index]
        ax.clear()
        ax.set_xlim(0, 3.4 + 0.72 * max(1, max_tasks))
        ax.set_ylim(0.25, len(ranks) + 1.25)
        ax.axis("off")
        ax.set_title(f"OpenMPI task-level MPOT: {phase}", fontsize=13, fontweight="bold")
        ax.text(0.02, 0.04, detail, transform=ax.transAxes, fontsize=9, color="#333333")
        ax.text(
            0.98,
            0.04,
            f"N={summary.get('total_tasks')} tasks, P={summary.get('size')} ranks",
            transform=ax.transAxes,
            ha="right",
            fontsize=9,
            color="#333333",
        )

        rank_positions: dict[int, tuple[float, float]] = {}
        for rank_index, row in enumerate(assignment):
            rank = int(row["rank"])
            y = y_for_rank(rank_index)
            rank_positions[rank] = (0.75, y)
            is_root = rank == 0
            node_color = "#0057b8" if is_root else "#4e79a7"
            ax.add_patch(
                patches.FancyBboxPatch(
                    (0.18, y - 0.20),
                    1.15,
                    0.40,
                    boxstyle="round,pad=0.05",
                    facecolor=node_color,
                    edgecolor="#1f2d3d",
                    alpha=0.92,
                )
            )
            ax.text(0.75, y, f"rank {rank}", ha="center", va="center", color="white", fontsize=9, fontweight="bold")

            if frame_index >= 1:
                for local_index, task_id in enumerate(row.get("task_ids", [])):
                    x = 1.62 + 0.72 * local_index
                    task_result = result_by_task.get(int(task_id), {})
                    is_best = int(task_id) == best_task_id
                    if frame_index == 1:
                        face = "#d8e6f3"
                        edge = "#4e79a7"
                    elif frame_index == 2:
                        face = "#f6c85f" if not is_best else "#59a14f"
                        edge = "#c58a00" if not is_best else "#2d7f35"
                    else:
                        face = "#e8f5e9" if is_best else "#eef2f7"
                        edge = "#2d7f35" if is_best else "#98a2b3"
                    ax.add_patch(
                        patches.Rectangle(
                            (x, y - 0.18),
                            0.52,
                            0.36,
                            facecolor=face,
                            edgecolor=edge,
                            linewidth=2.2 if is_best and frame_index >= 2 else 1.0,
                        )
                    )
                    label = f"T{task_id}"
                    if frame_index >= 2 and "best_cost" in task_result:
                        label += f"\n{float(task_result['best_cost']):.2f}"
                    ax.text(x + 0.26, y, label, ha="center", va="center", fontsize=7)

            if frame_index >= 2 and rank in timings:
                row_timing = timings[rank]
                compute = float(row_timing.get("compute_time_s") or 0.0)
                comm = float(row_timing.get("communication_time_s") or 0.0)
                ax.text(
                    1.44 + 0.72 * max(1, max_tasks),
                    y,
                    f"compute {compute:.3f}s\ncomm {comm:.3f}s",
                    va="center",
                    fontsize=8,
                    color="#333333",
                )

        if frame_index == 0 and 0 in rank_positions:
            root_x, root_y = rank_positions[0]
            for rank, (x, y) in rank_positions.items():
                if rank != 0:
                    draw_arrow(root_x + 0.62, root_y, x - 0.62, y, color="#0057b8")
        if frame_index == 1 and 0 in rank_positions:
            root_x, root_y = rank_positions[0]
            for rank, (x, y) in rank_positions.items():
                if rank != 0:
                    draw_arrow(root_x + 0.58, root_y, x - 0.58, y, color="#4e79a7", alpha=0.40)
        if frame_index == 3 and 0 in rank_positions:
            root_x, root_y = rank_positions[0]
            for rank, (x, y) in rank_positions.items():
                if rank != 0:
                    draw_arrow(x - 0.58, y, root_x + 0.58, root_y, color="#e15759")
        if frame_index == 4:
            best = result_by_task.get(best_task_id, {})
            best_rank = best.get("rank", summary.get("best_rank", "?"))
            best_cost = float(summary.get("best_cost", 0.0))
            ax.text(
                0.50,
                len(ranks) + 0.72,
                f"best task T{best_task_id} from rank {best_rank}, cost={best_cost:.6f}",
                fontsize=10,
                color="#1b5e20",
                fontweight="bold",
            )
        return []

    animation = FuncAnimation(fig, update, frames=len(phases), interval=1000 / max(1, fps), blit=False)
    out = Path(output) if output else run_dir / "parallel_schedule.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    animation.save(out, writer=PillowWriter(fps=max(1, fps)))
    plt.close(fig)
    return out
