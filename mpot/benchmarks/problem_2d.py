"""Simple 2D motion-planning problem for the local-first benchmark.

This module is intentionally independent from ``torch_robotics``. It defines a
small point-robot world that is easy to run on CPU and easy for the group to
explain during the final demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from mpot.benchmarks.config import CostConfig, ExperimentConfig


def require_torch():
    """Import torch lazily so docs/check scripts can run before deps are installed."""

    try:
        import torch
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyTorch is required for the MPOT benchmark. Install it in the project "
            "environment before running serial or MPI experiments."
        ) from exc
    return torch


def torch_dtype(dtype_name: str):
    torch = require_torch()
    if dtype_name == "float64":
        return torch.float64
    if dtype_name == "float32":
        return torch.float32
    raise ValueError("Only float32 and float64 are supported.")


@dataclass(frozen=True)
class CircleObstacle:
    """Circular obstacle in the 2D workspace."""

    center: tuple[float, float]
    radius: float
    safety_margin: float = 0.05


@dataclass
class PlanningProblem2D:
    """Complete 2D point-robot problem used by one experiment config."""

    workspace_min: tuple[float, float]
    workspace_max: tuple[float, float]
    start: tuple[float, float, float, float]
    goal: tuple[float, float, float, float]
    obstacles: list[CircleObstacle]
    traj_len: int
    dt: float
    cost: CostConfig
    tensor_args: dict[str, Any]

    @classmethod
    def from_config(cls, config: ExperimentConfig) -> "PlanningProblem2D":
        """Build a problem from the shared experiment config."""

        tensor_args = {
            "device": config.device,
            "dtype": torch_dtype(config.dtype),
        }
        obstacles = [
            CircleObstacle(
                center=(float(ob.center[0]), float(ob.center[1])),
                radius=float(ob.radius),
                safety_margin=float(ob.safety_margin),
            )
            for ob in config.problem.obstacles
        ]
        return cls(
            workspace_min=(float(config.problem.workspace_min[0]), float(config.problem.workspace_min[1])),
            workspace_max=(float(config.problem.workspace_max[0]), float(config.problem.workspace_max[1])),
            start=tuple(float(v) for v in config.problem.start),
            goal=tuple(float(v) for v in config.problem.goal),
            obstacles=obstacles,
            traj_len=int(config.problem.traj_len),
            dt=float(config.problem.dt),
            cost=config.cost,
            tensor_args=tensor_args,
        )

    def start_tensor(self):
        torch = require_torch()
        return torch.tensor(self.start, **self.tensor_args)

    def goal_tensor(self):
        torch = require_torch()
        return torch.tensor(self.goal, **self.tensor_args)

    def workspace_min_tensor(self):
        torch = require_torch()
        return torch.tensor(self.workspace_min, **self.tensor_args)

    def workspace_max_tensor(self):
        torch = require_torch()
        return torch.tensor(self.workspace_max, **self.tensor_args)

    def obstacle_tensors(self):
        """Return center, radius, and margin tensors for vectorized cost code."""

        torch = require_torch()
        if not self.obstacles:
            empty_centers = torch.zeros((0, 2), **self.tensor_args)
            empty_values = torch.zeros((0,), **self.tensor_args)
            return empty_centers, empty_values, empty_values
        centers = torch.tensor([ob.center for ob in self.obstacles], **self.tensor_args)
        radii = torch.tensor([ob.radius for ob in self.obstacles], **self.tensor_args)
        margins = torch.tensor([ob.safety_margin for ob in self.obstacles], **self.tensor_args)
        return centers, radii, margins

    def full_trajectory_cost(self, trajs):
        """Score complete trajectories.

        Args:
            trajs: tensor with shape ``(..., T, 4)``.

        Returns:
            Tensor with shape ``(...)`` containing one scalar cost per trajectory.
        """

        torch = require_torch()
        pos = trajs[..., :2]
        vel = trajs[..., 2:]
        centers, radii, margins = self.obstacle_tensors()

        if centers.numel() == 0:
            obstacle_cost = torch.zeros(pos.shape[:-2], **self.tensor_args)
        else:
            deltas = pos.unsqueeze(-2) - centers.view(*([1] * (pos.ndim - 1)), -1, 2)
            distances = torch.linalg.norm(deltas, dim=-1)
            safe_distance = radii + margins
            penetration = torch.relu(safe_distance - distances)
            obstacle_cost = (penetration * penetration).sum(dim=-1).mean(dim=-1)

        w_min = self.workspace_min_tensor()
        w_max = self.workspace_max_tensor()
        below = torch.relu(w_min - pos)
        above = torch.relu(pos - w_max)
        boundary_cost = ((below + above) ** 2).sum(dim=-1).mean(dim=-1)

        steps = pos[..., 1:, :] - pos[..., :-1, :]
        step_cost = (steps * steps).sum(dim=-1).mean(dim=-1)
        if self.traj_len > 2:
            curvature = steps[..., 1:, :] - steps[..., :-1, :]
            curve_cost = (curvature * curvature).sum(dim=-1).mean(dim=-1)
        else:
            curve_cost = torch.zeros_like(step_cost)

        goal = self.goal_tensor()
        end_delta = trajs[..., -1, :] - goal
        goal_cost = (end_delta * end_delta).sum(dim=-1)
        velocity_cost = (vel * vel).sum(dim=-1).mean(dim=-1)

        return (
            self.cost.obstacle_weight * obstacle_cost
            + self.cost.boundary_weight * boundary_cost
            + self.cost.smoothness_weight * (step_cost + curve_cost)
            + self.cost.goal_weight * goal_cost
            + self.cost.velocity_weight * velocity_cost
        )

    def collision_fraction(self, traj):
        """Return the fraction of waypoints that collide with hard obstacles."""

        torch = require_torch()
        pos = traj[..., :2]
        centers, radii, _ = self.obstacle_tensors()
        if centers.numel() == 0:
            return 0.0
        deltas = pos.unsqueeze(-2) - centers.view(*([1] * (pos.ndim - 1)), -1, 2)
        distances = torch.linalg.norm(deltas, dim=-1)
        colliding = (distances <= radii).any(dim=-1)
        return float(colliding.to(torch.float32).mean().item())


class MPOTObjective2D:
    """Objective function called by ``SinkhornStep`` during local optimization."""

    def __init__(self, problem: PlanningProblem2D):
        self.problem = problem
        self.tensor_args = problem.tensor_args
        self._last_traj_dim = None

    def __call__(self, probes, current_trajs=None, optim_dim=None, traj_dim=None, **kwargs):
        """Evaluate probe points and return a cost matrix for Sinkhorn Step.

        ``probes`` has shape ``(num_waypoints, num_vertices, num_probe, 4)``.
        The return value must have shape ``(num_waypoints, num_vertices)``.
        """

        if traj_dim is None:
            traj_dim = kwargs.get("traj_dim")
        if traj_dim is None:
            raise ValueError("traj_dim is required to evaluate the 2D objective.")
        self._last_traj_dim = traj_dim

        torch = require_torch()
        pos = probes[..., :2]
        centers, radii, margins = self.problem.obstacle_tensors()

        if centers.numel() == 0:
            obstacle_cost = torch.zeros(probes.shape[:-1], **self.tensor_args)
        else:
            deltas = pos.unsqueeze(-2) - centers.view(1, 1, 1, -1, 2)
            distances = torch.linalg.norm(deltas, dim=-1)
            penetration = torch.relu((radii + margins).view(1, 1, 1, -1) - distances)
            obstacle_cost = (penetration * penetration).sum(dim=-1)

        w_min = self.problem.workspace_min_tensor()
        w_max = self.problem.workspace_max_tensor()
        boundary = torch.relu(w_min - pos) + torch.relu(pos - w_max)
        boundary_cost = (boundary * boundary).sum(dim=-1)

        local_smooth = self._local_smoothness_cost(probes, current_trajs, traj_dim)
        endpoint = self._endpoint_cost(probes, traj_dim)

        per_probe_cost = (
            self.problem.cost.obstacle_weight * obstacle_cost
            + self.problem.cost.boundary_weight * boundary_cost
            + self.problem.cost.smoothness_weight * local_smooth
            + self.problem.cost.goal_weight * endpoint
        )
        return per_probe_cost.mean(dim=-1)

    def cost(self, trajs, traj_dim=None, **kwargs):
        """Score complete trajectories for optional outer-cost logging."""

        if traj_dim is None:
            traj_dim = kwargs.get("traj_dim") or self._last_traj_dim
        if traj_dim is None:
            raise ValueError("traj_dim is required to score complete trajectories.")
        return self.problem.full_trajectory_cost(trajs.view(traj_dim))

    def _local_smoothness_cost(self, probes, current_trajs, traj_dim):
        torch = require_torch()
        if current_trajs is None:
            return torch.zeros(probes.shape[:-1], **self.tensor_args)

        num_rows = probes.shape[0]
        traj_len = int(traj_dim[-2])
        current = current_trajs.view(-1, traj_len, traj_dim[-1])

        row_ids = torch.arange(num_rows, device=probes.device)
        traj_ids = torch.div(row_ids, traj_len, rounding_mode="floor")
        time_ids = row_ids % traj_len

        candidate_pos = probes[..., :2]
        smooth = torch.zeros(probes.shape[:-1], **self.tensor_args)

        has_prev = time_ids > 0
        if bool(has_prev.any()):
            prev_pos = current[traj_ids[has_prev], time_ids[has_prev] - 1, :2]
            diff_prev = candidate_pos[has_prev] - prev_pos[:, None, None, :]
            smooth[has_prev] += (diff_prev * diff_prev).sum(dim=-1)

        has_next = time_ids < (traj_len - 1)
        if bool(has_next.any()):
            next_pos = current[traj_ids[has_next], time_ids[has_next] + 1, :2]
            diff_next = next_pos[:, None, None, :] - candidate_pos[has_next]
            smooth[has_next] += (diff_next * diff_next).sum(dim=-1)

        return smooth

    def _endpoint_cost(self, probes, traj_dim):
        torch = require_torch()
        num_rows = probes.shape[0]
        traj_len = int(traj_dim[-2])
        row_ids = torch.arange(num_rows, device=probes.device)
        time_ids = row_ids % traj_len

        start = self.problem.start_tensor()
        goal = self.problem.goal_tensor()
        endpoint_cost = torch.zeros(probes.shape[:-1], **self.tensor_args)

        is_start = time_ids == 0
        if bool(is_start.any()):
            delta = probes[is_start] - start.view(1, 1, 1, 4)
            endpoint_cost[is_start] += (delta * delta).sum(dim=-1)

        is_goal = time_ids == (traj_len - 1)
        if bool(is_goal.any()):
            delta = probes[is_goal] - goal.view(1, 1, 1, 4)
            endpoint_cost[is_goal] += (delta * delta).sum(dim=-1)

        return endpoint_cost


def summarize_problem(problem: PlanningProblem2D) -> dict[str, Any]:
    """Return a JSON-friendly problem summary for run artifacts."""

    return {
        "workspace_min": list(problem.workspace_min),
        "workspace_max": list(problem.workspace_max),
        "start": list(problem.start),
        "goal": list(problem.goal),
        "traj_len": problem.traj_len,
        "dt": problem.dt,
        "num_obstacles": len(problem.obstacles),
        "obstacles": [
            {
                "center": list(ob.center),
                "radius": ob.radius,
                "safety_margin": ob.safety_margin,
            }
            for ob in problem.obstacles
        ],
    }


def straight_line_reference(problem: PlanningProblem2D) -> list[list[float]]:
    """Return a simple start-to-goal trajectory useful for explanations."""

    start = problem.start
    goal = problem.goal
    out: list[list[float]] = []
    denom = max(problem.traj_len - 1, 1)
    for i in range(problem.traj_len):
        alpha = i / denom
        state = [(1.0 - alpha) * start[j] + alpha * goal[j] for j in range(4)]
        out.append(state)
    return out


def euclidean_path_length(trajectory: list[list[float]]) -> float:
    """Compute geometric path length from a trajectory list."""

    total = 0.0
    for a, b in zip(trajectory[:-1], trajectory[1:]):
        dx = float(b[0]) - float(a[0])
        dy = float(b[1]) - float(a[1])
        total += math.sqrt(dx * dx + dy * dy)
    return total

