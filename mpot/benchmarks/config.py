"""Configuration helpers for the local-first MPOT/MPI benchmark.

The benchmark uses JSON config files instead of hard-coded constants so that
serial and MPI runs can be repeated with exactly the same problem size, seed
list, and cost weights.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json
import time


@dataclass
class ObstacleConfig:
    """Circle obstacle used by the 2D point-robot benchmark."""

    center: list[float]
    radius: float
    safety_margin: float = 0.05


@dataclass
class ProblemConfig:
    """Geometry and trajectory settings for the benchmark problem."""

    workspace_min: list[float] = field(default_factory=lambda: [-1.0, -1.0])
    workspace_max: list[float] = field(default_factory=lambda: [1.0, 1.0])
    start: list[float] = field(default_factory=lambda: [-0.85, -0.85, 0.0, 0.0])
    goal: list[float] = field(default_factory=lambda: [0.85, 0.85, 0.0, 0.0])
    obstacles: list[ObstacleConfig] = field(
        default_factory=lambda: [
            ObstacleConfig(center=[-0.2, -0.05], radius=0.22, safety_margin=0.05),
            ObstacleConfig(center=[0.28, 0.18], radius=0.20, safety_margin=0.05),
        ]
    )
    traj_len: int = 32
    dt: float = 0.05
    pos_limits: list[float] = field(default_factory=lambda: [-1.0, 1.0])
    vel_limits: list[float] = field(default_factory=lambda: [-3.0, 3.0])


@dataclass
class CostConfig:
    """Weights used to score complete trajectories and local probes."""

    obstacle_weight: float = 25.0
    smoothness_weight: float = 0.03
    goal_weight: float = 8.0
    boundary_weight: float = 20.0
    velocity_weight: float = 0.002


@dataclass
class OptimizerConfig:
    """MPOT/Sinkhorn parameters for each local planning task."""

    num_particles: int = 12
    step_radius: float = 0.10
    probe_radius: float = 0.14
    num_probe: int = 3
    polytope: str = "orthoplex"
    max_outer_iters: int = 18
    min_outer_iters: int = 4
    max_inner_iters: int = 40
    sinkhorn_threshold: float = 1.0e-5
    outer_threshold: float = 1.0e-4
    epsilon_target: float = 1.0e-2
    ent_epsilon_target: float = 2.0e-2
    sigma_start_init: float = 0.001
    sigma_goal_init: float = 0.001
    sigma_gp_init: float = 0.8


@dataclass
class ExperimentConfig:
    """Top-level config loaded by serial and MPI entrypoints."""

    experiment_name: str = "mpot_local_smoke"
    output_dir: str = "results"
    base_seed: int = 20260617
    total_tasks: int = 8
    torch_num_threads: int = 1
    device: str = "cpu"
    dtype: str = "float32"
    problem: ProblemConfig = field(default_factory=ProblemConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

    def make_run_id(self, prefix: str) -> str:
        """Return a filesystem-friendly run id with a timestamp."""

        stamp = time.strftime("%Y%m%d-%H%M%S")
        return f"{prefix}-{self.experiment_name}-{stamp}"

    def seed_for_task(self, task_id: int) -> int:
        """Return the deterministic seed for one task id."""

        return int(self.base_seed) + int(task_id)

    def seed_list(self) -> list[int]:
        """Return all deterministic task seeds in task-id order."""

        return [self.seed_for_task(i) for i in range(self.total_tasks)]


def _coerce_obstacle(value: dict[str, Any]) -> ObstacleConfig:
    return ObstacleConfig(
        center=[float(value["center"][0]), float(value["center"][1])],
        radius=float(value["radius"]),
        safety_margin=float(value.get("safety_margin", 0.05)),
    )


def _coerce_problem(value: dict[str, Any]) -> ProblemConfig:
    data = dict(value)
    data["obstacles"] = [_coerce_obstacle(v) for v in data.get("obstacles", [])]
    return ProblemConfig(**data)


def config_from_dict(value: dict[str, Any]) -> ExperimentConfig:
    """Build an ExperimentConfig from a nested dictionary.

    The conversion is intentionally explicit so config mistakes fail close to
    the load point instead of surfacing halfway through an MPI run.
    """

    data = dict(value)
    if "problem" in data:
        data["problem"] = _coerce_problem(data["problem"])
    if "cost" in data:
        data["cost"] = CostConfig(**data["cost"])
    if "optimizer" in data:
        data["optimizer"] = OptimizerConfig(**data["optimizer"])
    cfg = ExperimentConfig(**data)
    validate_config(cfg)
    return cfg


def config_to_dict(config: ExperimentConfig) -> dict[str, Any]:
    """Convert a config dataclass tree into plain JSON data."""

    return asdict(config)


def config_hash_from_dict(payload: dict[str, Any]) -> str:
    """Return a stable short hash for a plain config dictionary."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def config_hash(config: ExperimentConfig) -> str:
    """Return a stable short hash for an ExperimentConfig."""

    return config_hash_from_dict(config_to_dict(config))


def load_config(path: str | Path) -> ExperimentConfig:
    """Load and validate a JSON experiment config."""

    with Path(path).open("r", encoding="utf-8") as f:
        return config_from_dict(json.load(f))


def save_config(config: ExperimentConfig, path: str | Path) -> None:
    """Write the effective config next to a run's output artifacts."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(config_to_dict(config), f, indent=2, sort_keys=True)
        f.write("\n")


def validate_config(config: ExperimentConfig) -> None:
    """Raise ValueError for settings that make the benchmark meaningless."""

    if config.device != "cpu":
        raise ValueError("The local-first benchmark only supports device='cpu'.")
    if config.total_tasks <= 0:
        raise ValueError("total_tasks must be positive.")
    if config.problem.traj_len < 4:
        raise ValueError("traj_len must be at least 4 waypoints.")
    if len(config.problem.start) != 4 or len(config.problem.goal) != 4:
        raise ValueError("start and goal must have four entries: x, y, vx, vy.")
    if config.optimizer.num_particles <= 0:
        raise ValueError("optimizer.num_particles must be positive.")
    if config.optimizer.num_probe <= 0:
        raise ValueError("optimizer.num_probe must be positive.")
    if config.optimizer.max_outer_iters <= config.optimizer.min_outer_iters:
        raise ValueError("optimizer.max_outer_iters must be greater than optimizer.min_outer_iters.")
    if config.optimizer.max_inner_iters <= 0:
        raise ValueError("optimizer.max_inner_iters must be positive.")
    if config.optimizer.polytope not in {"orthoplex", "cube", "simplex"}:
        raise ValueError("polytope must be one of: orthoplex, cube, simplex.")
