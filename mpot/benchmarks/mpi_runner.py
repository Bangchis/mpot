"""MPI orchestration for the distributed MPOT benchmark."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
import socket

from mpot.benchmarks.artifacts import make_run_dir, write_run_artifacts
from mpot.benchmarks.config import ExperimentConfig
from mpot.benchmarks.local_runner import run_task
from mpot.benchmarks.mpi_scheduler import build_tasks, cyclic_chunks, describe_chunks, validate_assignment
from mpot.benchmarks.plots import plot_best_path, plot_cost_by_task, plot_rank_time_breakdown
from mpot.benchmarks.problem_2d import PlanningProblem2D, summarize_problem
from mpot.benchmarks.reduction import RankTiming, choose_best, flatten_result_groups
from mpot.wandb_logger import WandbSettings, log_run_directory_to_wandb


def require_mpi4py():
    try:
        from mpi4py import MPI
    except ModuleNotFoundError as exc:
        raise RuntimeError("mpi4py is required for MPI runs. Install mpi4py in the active environment.") from exc
    return MPI


def _record_comm_event(
    events: list[dict],
    *,
    rank: int,
    size: int,
    hostname: str,
    event: str,
    collective: str,
    root: int,
    started: float,
    payload_count: int | None = None,
) -> float:
    """Record one blocking MPI communication event and return its duration."""

    duration = perf_counter() - started
    events.append(
        {
            "event_index": len(events),
            "rank": int(rank),
            "size": int(size),
            "hostname": hostname,
            "event": event,
            "collective": collective,
            "root": int(root),
            "blocking": True,
            "duration_s": float(duration),
            "payload_count": "" if payload_count is None else int(payload_count),
        }
    )
    return duration


def run_mpi_benchmark(
    *,
    comm,
    config: ExperimentConfig | None,
    run_id: str | None,
    use_wandb: bool = False,
    wandb_settings: WandbSettings | None = None,
) -> dict | None:
    """Run the MPI benchmark.

    Rank 0 receives the config from the script. Other ranks receive it through
    broadcast. Rank 0 writes artifacts and returns the summary; other ranks
    return None.
    """

    rank = comm.Get_rank()
    size = comm.Get_size()
    hostname = socket.gethostname()
    rank_started = perf_counter()
    comm_events: list[dict] = []

    if rank == 0:
        if config is None:
            raise ValueError("Rank 0 must receive a config object.")
        if run_id is None:
            run_id = config.make_run_id("mpi")
        tasks = build_tasks(config.total_tasks, config.base_seed)
        chunks = cyclic_chunks(tasks, size)
        validate_assignment(tasks, chunks)
        assignment = describe_chunks(chunks)
    else:
        tasks = None
        chunks = None
        assignment = None

    comm_time = 0.0
    comm_started = perf_counter()
    config = comm.bcast(config, root=0)
    comm_time += _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="bcast_config",
        collective="bcast",
        root=0,
        started=comm_started,
    )
    comm_started = perf_counter()
    run_id = comm.bcast(run_id, root=0)
    comm_time += _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="bcast_run_id",
        collective="bcast",
        root=0,
        started=comm_started,
    )
    comm_started = perf_counter()
    assignment = comm.bcast(assignment, root=0)
    comm_time += _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="bcast_assignment",
        collective="bcast",
        root=0,
        started=comm_started,
        payload_count=0 if assignment is None else len(assignment),
    )
    comm_started = perf_counter()
    local_tasks = comm.scatter(chunks, root=0)
    comm_time += _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="scatter_tasks",
        collective="scatter",
        root=0,
        started=comm_started,
        payload_count=len(local_tasks),
    )

    compute_started = perf_counter()
    local_results = [run_task(config, task, rank=rank) for task in local_tasks]
    compute_time = perf_counter() - compute_started
    local_best = choose_best(local_results) if local_results else None

    comm_started = perf_counter()
    result_groups = comm.gather(local_results, root=0)
    comm_time += _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="gather_results",
        collective="gather",
        root=0,
        started=comm_started,
        payload_count=len(local_results),
    )

    best_cost = local_best.best_cost if local_best is not None else float("inf")
    total_time_so_far = perf_counter() - rank_started
    rank_timing = RankTiming(
        rank=rank,
        size=size,
        hostname=hostname,
        num_tasks=len(local_tasks),
        compute_time_s=compute_time,
        communication_time_s=comm_time,
        total_time_s=total_time_so_far,
        best_cost=best_cost,
    )

    comm_started = perf_counter()
    rank_timings = comm.gather(rank_timing, root=0)
    comm_time += _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="gather_rank_timings",
        collective="gather",
        root=0,
        started=comm_started,
        payload_count=1,
    )

    comm_started = perf_counter()
    comm_event_groups = comm.gather(comm_events, root=0)
    _record_comm_event(
        comm_events,
        rank=rank,
        size=size,
        hostname=hostname,
        event="gather_comm_events",
        collective="gather",
        root=0,
        started=comm_started,
        payload_count=len(comm_events),
    )

    if rank != 0:
        return None

    all_comm_events = [event for group in comm_event_groups for event in group]
    all_results = flatten_result_groups(result_groups)
    best = choose_best(all_results)
    run_dir = make_run_dir(config, run_id)
    problem = PlanningProblem2D.from_config(config)
    total_time_s = max(t.total_time_s for t in rank_timings) if rank_timings else 0.0
    summary = write_run_artifacts(
        run_dir=run_dir,
        run_id=run_id,
        mode="mpi",
        config=config,
        best=best,
        results=all_results,
        rank_timings=rank_timings,
        total_time_s=total_time_s,
        problem_summary=summarize_problem(problem),
        task_assignment=assignment,
        comm_events=all_comm_events,
    )

    for plotter in (plot_best_path, plot_cost_by_task, plot_rank_time_breakdown):
        try:
            plotter(run_dir)
        except RuntimeError as exc:
            print(f"[rank 0] plotting skipped: {exc}")

    if wandb_settings is None:
        wandb_settings = WandbSettings(enabled=use_wandb)
    if wandb_settings.enabled:
        outcome = log_run_directory_to_wandb(run_dir, settings=wandb_settings)
        print(f"[rank 0] wandb status: {outcome['status']}  manifest: {outcome['manifest']}")

    print(f"[rank 0] MPI run written to {Path(run_dir).resolve()}")
    return summary
