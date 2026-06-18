"""Pure helpers shared by the 2D GUI and its tests.

The GUI itself uses Tkinter, but these helpers stay UI-free.  They convert a
drag-and-drop scene into the same JSON config that the existing serial and MPI
runners already understand.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import sys

from mpot.benchmarks.config import (
    ExperimentConfig,
    ObstacleConfig,
    config_from_dict,
    config_to_dict,
    save_config,
)


@dataclass
class GuiObstacle:
    """One circular obstacle edited on the GUI canvas."""

    x: float
    y: float
    radius: float = 0.18
    safety_margin: float = 0.05


@dataclass
class GuiScene:
    """Editable 2D problem scene."""

    workspace_min: list[float] = field(default_factory=lambda: [-1.0, -1.0])
    workspace_max: list[float] = field(default_factory=lambda: [1.0, 1.0])
    start: list[float] = field(default_factory=lambda: [-0.85, -0.85, 0.0, 0.0])
    goal: list[float] = field(default_factory=lambda: [0.85, 0.85, 0.0, 0.0])
    obstacles: list[GuiObstacle] = field(default_factory=list)


@dataclass
class GuiRunOptions:
    """Algorithm and MPI parameters controlled by the GUI."""

    run_id: str = "gui-mpot-demo"
    experiment_name: str = "gui_mpot_demo"
    output_dir: str = "results"
    total_tasks: int = 8
    mpi_processes: int = 4
    base_seed: int = 20260619
    traj_len: int = 28
    num_particles: int = 10
    num_probe: int = 3
    polytope: str = "orthoplex"
    step_radius: float = 0.10
    probe_radius: float = 0.14
    max_outer_iters: int = 10
    min_outer_iters: int = 3
    max_inner_iters: int = 24
    obstacle_weight: float = 25.0
    smoothness_weight: float = 0.03
    goal_weight: float = 8.0
    boundary_weight: float = 20.0
    velocity_weight: float = 0.002
    trace_fps: int = 3
    trace_max_particles: int = 24


def scene_from_config(config: ExperimentConfig) -> GuiScene:
    """Create an editable scene from an experiment config."""

    return GuiScene(
        workspace_min=list(config.problem.workspace_min),
        workspace_max=list(config.problem.workspace_max),
        start=list(config.problem.start),
        goal=list(config.problem.goal),
        obstacles=[
            GuiObstacle(
                x=float(ob.center[0]),
                y=float(ob.center[1]),
                radius=float(ob.radius),
                safety_margin=float(ob.safety_margin),
            )
            for ob in config.problem.obstacles
        ],
    )


def options_from_config(config: ExperimentConfig, *, mpi_processes: int = 4, run_id: str = "gui-mpot-demo") -> GuiRunOptions:
    """Create default GUI run options from an experiment config."""

    return GuiRunOptions(
        run_id=run_id,
        experiment_name=config.experiment_name or "gui_mpot_demo",
        output_dir=config.output_dir,
        total_tasks=int(config.total_tasks),
        mpi_processes=int(mpi_processes),
        base_seed=int(config.base_seed),
        traj_len=int(config.problem.traj_len),
        num_particles=int(config.optimizer.num_particles),
        num_probe=int(config.optimizer.num_probe),
        polytope=str(config.optimizer.polytope),
        step_radius=float(config.optimizer.step_radius),
        probe_radius=float(config.optimizer.probe_radius),
        max_outer_iters=int(config.optimizer.max_outer_iters),
        min_outer_iters=int(config.optimizer.min_outer_iters),
        max_inner_iters=int(config.optimizer.max_inner_iters),
        obstacle_weight=float(config.cost.obstacle_weight),
        smoothness_weight=float(config.cost.smoothness_weight),
        goal_weight=float(config.cost.goal_weight),
        boundary_weight=float(config.cost.boundary_weight),
        velocity_weight=float(config.cost.velocity_weight),
    )


def build_config_from_gui(base_config: ExperimentConfig, scene: GuiScene, options: GuiRunOptions) -> ExperimentConfig:
    """Return a validated experiment config matching the GUI scene/options."""

    payload = deepcopy(config_to_dict(base_config))
    payload["experiment_name"] = options.experiment_name
    payload["output_dir"] = options.output_dir
    payload["base_seed"] = int(options.base_seed)
    payload["total_tasks"] = int(options.total_tasks)
    payload["problem"]["workspace_min"] = [float(v) for v in scene.workspace_min[:2]]
    payload["problem"]["workspace_max"] = [float(v) for v in scene.workspace_max[:2]]
    payload["problem"]["start"] = [float(v) for v in scene.start[:4]]
    payload["problem"]["goal"] = [float(v) for v in scene.goal[:4]]
    payload["problem"]["traj_len"] = int(options.traj_len)
    payload["problem"]["obstacles"] = [
        {
            "center": [float(ob.x), float(ob.y)],
            "radius": float(ob.radius),
            "safety_margin": float(ob.safety_margin),
        }
        for ob in scene.obstacles
    ]
    payload["cost"]["obstacle_weight"] = float(options.obstacle_weight)
    payload["cost"]["smoothness_weight"] = float(options.smoothness_weight)
    payload["cost"]["goal_weight"] = float(options.goal_weight)
    payload["cost"]["boundary_weight"] = float(options.boundary_weight)
    payload["cost"]["velocity_weight"] = float(options.velocity_weight)
    payload["optimizer"]["num_particles"] = int(options.num_particles)
    payload["optimizer"]["num_probe"] = int(options.num_probe)
    payload["optimizer"]["polytope"] = str(options.polytope)
    payload["optimizer"]["step_radius"] = float(options.step_radius)
    payload["optimizer"]["probe_radius"] = float(options.probe_radius)
    payload["optimizer"]["max_outer_iters"] = int(options.max_outer_iters)
    payload["optimizer"]["min_outer_iters"] = int(options.min_outer_iters)
    payload["optimizer"]["max_inner_iters"] = int(options.max_inner_iters)
    return config_from_dict(payload)


def write_gui_config(config: ExperimentConfig, run_id: str, *, config_dir: str | Path = "results/gui_configs") -> Path:
    """Write the effective GUI config and return its path."""

    out = Path(config_dir) / f"{run_id}.json"
    save_config(config, out)
    return out


def build_mpi_command(
    config_path: str | Path,
    run_id: str,
    mpi_processes: int,
    *,
    python_executable: str | None = None,
    mpirun_executable: str = "mpirun",
) -> list[str]:
    """Return the command used by the GUI to launch the existing MPI runner."""

    python_executable = python_executable or sys.executable
    return [
        mpirun_executable,
        "-np",
        str(int(mpi_processes)),
        "--bind-to",
        "none",
        python_executable,
        "scripts/run_mpi.py",
        "--config",
        str(config_path),
        "--run-id",
        str(run_id),
    ]


def expected_run_dir(options: GuiRunOptions) -> Path:
    """Return the run directory produced by the MPI command."""

    return Path(options.output_dir) / options.run_id


def obstacle_config_from_gui(obstacle: GuiObstacle) -> ObstacleConfig:
    """Convert one GUI obstacle to the existing config dataclass."""

    return ObstacleConfig(
        center=[float(obstacle.x), float(obstacle.y)],
        radius=float(obstacle.radius),
        safety_margin=float(obstacle.safety_margin),
    )
