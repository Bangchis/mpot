"""Local MPOT-style task runner and serial baseline helpers."""

from __future__ import annotations

from time import perf_counter
import random

from mpot.benchmarks.config import ExperimentConfig
from mpot.benchmarks.mpi_scheduler import TaskSpec
from mpot.benchmarks.problem_2d import MPOTObjective2D, PlanningProblem2D, require_torch
from mpot.benchmarks.reduction import TaskResult, choose_best


def _fix_local_seed(seed: int) -> None:
    """Seed Python and PyTorch for repeatable task-level experiments."""

    torch = require_torch()
    random.seed(int(seed))
    torch.manual_seed(int(seed))


def _make_tensor_args(config: ExperimentConfig):
    torch = require_torch()
    dtype = torch.float64 if config.dtype == "float64" else torch.float32
    return {"device": config.device, "dtype": dtype}


def build_planner(config: ExperimentConfig, problem: PlanningProblem2D, seed: int, *, store_history: bool = False):
    """Construct the original MPOT planner for one local task."""

    torch = require_torch()
    from mpot.ot.problem import EpsilonScheduler
    from mpot.ot.sinkhorn import Sinkhorn
    from mpot.planner import MPOT

    objective = MPOTObjective2D(problem)
    opt = config.optimizer

    linear_ot_solver = Sinkhorn(
        threshold=opt.sinkhorn_threshold,
        inner_iterations=1,
        max_iterations=opt.max_inner_iters,
    )

    ss_params = {
        "epsilon": EpsilonScheduler(target=opt.epsilon_target, init=1.0, decay=1.0),
        "ent_epsilon": EpsilonScheduler(target=opt.ent_epsilon_target, init=1.0, decay=1.0),
        "polytope_type": opt.polytope,
        "step_radius": opt.step_radius,
        "probe_radius": opt.probe_radius,
        "num_probe": opt.num_probe,
        "min_iterations": opt.min_outer_iters,
        "max_iterations": opt.max_outer_iters,
        "threshold": opt.outer_threshold,
        "store_history": bool(store_history),
        "tensor_args": _make_tensor_args(config),
    }

    return MPOT(
        dim=2,
        objective_fn=objective,
        linear_ot_solver=linear_ot_solver,
        ss_params=ss_params,
        traj_len=config.problem.traj_len,
        num_particles_per_goal=config.optimizer.num_particles,
        dt=config.problem.dt,
        start_state=problem.start_tensor(),
        multi_goal_states=problem.goal_tensor().view(1, 4),
        pos_limits=config.problem.pos_limits,
        vel_limits=config.problem.vel_limits,
        polytope=config.optimizer.polytope,
        fixed_start=True,
        fixed_goal=True,
        sigma_start_init=config.optimizer.sigma_start_init,
        sigma_goal_init=config.optimizer.sigma_goal_init,
        sigma_gp_init=config.optimizer.sigma_gp_init,
        seed=int(seed),
        tensor_args=_make_tensor_args(config),
    )


def run_task(config: ExperimentConfig, task: TaskSpec, rank: int = 0) -> TaskResult:
    """Run one task/seed and return its best trajectory.

    This function is shared by serial and MPI. Keeping it shared is important:
    it means correctness comparisons focus on parallel scheduling, not on two
    different optimization implementations.
    """

    start_time = perf_counter()
    torch = require_torch()
    if config.torch_num_threads > 0:
        torch.set_num_threads(int(config.torch_num_threads))
    _fix_local_seed(task.seed)

    problem = PlanningProblem2D.from_config(config)
    planner = build_planner(config, problem, task.seed)
    trajs, _, opt_iters = planner.optimize()
    runtime_s = perf_counter() - start_time

    flat_trajs = trajs.reshape(-1, config.problem.traj_len, 4)
    costs = problem.full_trajectory_cost(flat_trajs)
    best_idx = int(torch.argmin(costs).item())
    best_traj = flat_trajs[best_idx].detach().cpu()
    best_cost = float(costs[best_idx].detach().cpu().item())
    collision_fraction = problem.collision_fraction(best_traj)

    return TaskResult(
        task_id=int(task.task_id),
        seed=int(task.seed),
        rank=int(rank),
        best_cost=best_cost,
        opt_iters=int(opt_iters),
        runtime_s=float(runtime_s),
        num_particles=int(config.optimizer.num_particles),
        traj_len=int(config.problem.traj_len),
        collision_fraction=float(collision_fraction),
        trajectory=[[float(v) for v in state] for state in best_traj.tolist()],
    )


def _fix_trace_endpoints(flat_trajs, config: ExperimentConfig):
    """Fix start/goal in trace frames before scoring or plotting."""

    torch = require_torch()
    out = flat_trajs.clone()
    start = torch.tensor(config.problem.start, device=out.device, dtype=out.dtype)
    goal = torch.tensor(config.problem.goal, device=out.device, dtype=out.dtype)
    out[:, 0, :] = start
    out[:, -1, :] = goal
    return out


def _trace_frame(problem: PlanningProblem2D, config: ExperimentConfig, flat_trajs, iteration: int) -> dict:
    """Build one JSON-friendly algorithm trace frame."""

    torch = require_torch()
    fixed = _fix_trace_endpoints(flat_trajs, config)
    costs = problem.full_trajectory_cost(fixed)
    best_idx = int(torch.argmin(costs).item())
    return {
        "iteration": int(iteration),
        "best_index": best_idx,
        "best_cost": float(costs[best_idx].detach().cpu().item()),
        "costs": [float(v) for v in costs.detach().cpu().tolist()],
        "trajectories": [
            [[float(value) for value in state] for state in traj]
            for traj in fixed.detach().cpu().tolist()
        ],
    }


def run_task_trace(config: ExperimentConfig, task: TaskSpec, rank: int = 0) -> dict:
    """Rerun one task with MPOT history enabled for algorithm visualization."""

    start_time = perf_counter()
    torch = require_torch()
    if config.torch_num_threads > 0:
        torch.set_num_threads(int(config.torch_num_threads))
    _fix_local_seed(task.seed)

    problem = PlanningProblem2D.from_config(config)
    planner = build_planner(config, problem, task.seed, store_history=True)
    initial = planner.flatten_trajs.view(planner.traj_dim).reshape(-1, config.problem.traj_len, 4)
    trajs, state, opt_iters = planner.optimize()

    frames = [_trace_frame(problem, config, initial, iteration=0)]
    history = state.X_history[: int(opt_iters)]
    for index in range(int(opt_iters)):
        frame_trajs = history[index].view(planner.traj_dim).reshape(-1, config.problem.traj_len, 4)
        frames.append(_trace_frame(problem, config, frame_trajs, iteration=index + 1))

    flat_final = trajs.reshape(-1, config.problem.traj_len, 4)
    final_costs = problem.full_trajectory_cost(_fix_trace_endpoints(flat_final, config))
    final_best_idx = int(torch.argmin(final_costs).item())
    runtime_s = perf_counter() - start_time
    return {
        "task_id": int(task.task_id),
        "seed": int(task.seed),
        "rank": int(rank),
        "opt_iters": int(opt_iters),
        "runtime_s": float(runtime_s),
        "num_particles": int(config.optimizer.num_particles),
        "traj_len": int(config.problem.traj_len),
        "final_best_index": final_best_idx,
        "final_best_cost": float(final_costs[final_best_idx].detach().cpu().item()),
        "frames": frames,
    }


def run_tasks_serial(config: ExperimentConfig, tasks: list[TaskSpec]) -> tuple[list[TaskResult], TaskResult, float]:
    """Run all tasks sequentially and return all results, best result, total time."""

    started = perf_counter()
    results = [run_task(config, task, rank=0) for task in tasks]
    total_time_s = perf_counter() - started
    return results, choose_best(results), total_time_s
