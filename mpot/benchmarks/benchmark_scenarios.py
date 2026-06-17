"""Compare final benchmark size scenarios before running a long sweep.

This module is a planning helper only. It uses the same seconds-per-task sample
as ``benchmark_plan.py`` and estimates candidate local sweeps so the team can
choose a setting without doing the arithmetic by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import time

from mpot.benchmarks.artifacts import write_json
from mpot.benchmarks.benchmark_budget import estimate_run_seconds
from mpot.benchmarks.benchmark_plan import (
    BenchmarkPlan,
    create_benchmark_plan,
    parse_float_list,
    seconds_per_task_from_summary,
)


@dataclass
class BenchmarkScenario:
    """One candidate final benchmark plan and its estimated sweep budget."""

    name: str
    label: str
    target_seconds: float
    chosen_n: int
    speedup_n: int
    input_sizes: list[int]
    process_counts: list[int]
    estimated_total_seconds: float
    estimated_total_minutes: float
    estimated_n_at_max_processes_seconds: float
    estimated_2n_at_max_processes_seconds: float
    max_total_seconds: float
    passed_budget: bool
    recommendation: str
    pipeline_command: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "target_seconds": self.target_seconds,
            "chosen_n": self.chosen_n,
            "speedup_n": self.speedup_n,
            "input_sizes": self.input_sizes,
            "process_counts": self.process_counts,
            "estimated_total_seconds": self.estimated_total_seconds,
            "estimated_total_minutes": self.estimated_total_minutes,
            "estimated_n_at_max_processes_seconds": self.estimated_n_at_max_processes_seconds,
            "estimated_2n_at_max_processes_seconds": self.estimated_2n_at_max_processes_seconds,
            "max_total_seconds": self.max_total_seconds,
            "passed_budget": self.passed_budget,
            "recommendation": self.recommendation,
            "pipeline_command": self.pipeline_command,
        }


def _scenario_name(index: int, target_seconds: float) -> str:
    """Return a readable default name for a scenario target."""

    if index == 0:
        return "safe_local"
    minutes = target_seconds / 60.0
    return f"target_{minutes:.1f}_min_N".replace(".", "p")


def _estimate_sweep_seconds(plan: BenchmarkPlan, *, mpi_startup_seconds: float, mpi_overhead_factor: float) -> float:
    """Estimate total time for all serial and MPI runs in a generated plan."""

    total = 0.0
    for n in plan.input_sizes:
        total += estimate_run_seconds(
            seconds_per_task=plan.seconds_per_task,
            input_size_n=n,
            processes=1,
            assumed_parallel_efficiency=plan.assumed_parallel_efficiency,
            kind="serial",
            mpi_startup_seconds=mpi_startup_seconds,
            mpi_overhead_factor=mpi_overhead_factor,
        )
        for p in plan.process_counts:
            total += estimate_run_seconds(
                seconds_per_task=plan.seconds_per_task,
                input_size_n=n,
                processes=p,
                assumed_parallel_efficiency=plan.assumed_parallel_efficiency,
                kind="mpi",
                mpi_startup_seconds=mpi_startup_seconds,
                mpi_overhead_factor=mpi_overhead_factor,
            )
    return total


def _estimated_mpi_seconds(plan: BenchmarkPlan, n: int, *, mpi_startup_seconds: float, mpi_overhead_factor: float) -> float:
    """Estimate one MPI run at the plan's maximum process count."""

    return estimate_run_seconds(
        seconds_per_task=plan.seconds_per_task,
        input_size_n=n,
        processes=plan.target_processes,
        assumed_parallel_efficiency=plan.assumed_parallel_efficiency,
        kind="mpi",
        mpi_startup_seconds=mpi_startup_seconds,
        mpi_overhead_factor=mpi_overhead_factor,
    )


def build_benchmark_scenarios(
    *,
    config: str,
    label: str,
    target_seconds: list[float],
    target_processes: int,
    assumed_parallel_efficiency: float,
    sample_summary: str | Path | None = None,
    seconds_per_task: float | None = None,
    runtime_factors: list[float] | None = None,
    include_max_processes: bool = True,
    max_total_seconds: float = 3600.0,
    mpi_startup_seconds: float = 1.0,
    mpi_overhead_factor: float = 1.05,
    scenario_names: list[str] | None = None,
) -> dict[str, Any]:
    """Build report-friendly scenario estimates without running benchmarks."""

    if not target_seconds:
        raise ValueError("target_seconds must not be empty.")
    if seconds_per_task is None and sample_summary is None:
        raise ValueError("Provide either sample_summary or seconds_per_task.")

    sample_tasks = None
    sample_time_s = None
    if sample_summary is not None:
        sample_tasks, sample_time_s, measured = seconds_per_task_from_summary(sample_summary)
        if seconds_per_task is None:
            seconds_per_task = measured

    names = scenario_names or [_scenario_name(i, target) for i, target in enumerate(target_seconds)]
    if len(names) != len(target_seconds):
        raise ValueError("scenario_names length must match target_seconds length.")

    scenarios: list[BenchmarkScenario] = []
    for index, target in enumerate(target_seconds):
        scenario_label = f"{label}_{names[index]}"
        plan = create_benchmark_plan(
            config=config,
            label=scenario_label,
            target_seconds=float(target),
            target_processes=target_processes,
            assumed_parallel_efficiency=assumed_parallel_efficiency,
            sample_summary=sample_summary,
            seconds_per_task=seconds_per_task,
            runtime_factors=runtime_factors,
            include_max_processes=include_max_processes,
        )
        plan.pipeline_command.extend(["--benchmark-plan", "report/BENCHMARK_PLAN.json", "--skip-existing-runs"])
        total = _estimate_sweep_seconds(
            plan,
            mpi_startup_seconds=mpi_startup_seconds,
            mpi_overhead_factor=mpi_overhead_factor,
        )
        n_seconds = _estimated_mpi_seconds(
            plan,
            plan.chosen_n,
            mpi_startup_seconds=mpi_startup_seconds,
            mpi_overhead_factor=mpi_overhead_factor,
        )
        speedup_seconds = _estimated_mpi_seconds(
            plan,
            plan.speedup_n,
            mpi_startup_seconds=mpi_startup_seconds,
            mpi_overhead_factor=mpi_overhead_factor,
        )
        passed = total <= max_total_seconds
        recommendation = "safe for local-first run" if passed else "run only unattended or on Ubuntu/LAN machines"
        scenarios.append(
            BenchmarkScenario(
                name=names[index],
                label=scenario_label,
                target_seconds=float(target),
                chosen_n=plan.chosen_n,
                speedup_n=plan.speedup_n,
                input_sizes=plan.input_sizes,
                process_counts=plan.process_counts,
                estimated_total_seconds=total,
                estimated_total_minutes=total / 60.0,
                estimated_n_at_max_processes_seconds=n_seconds,
                estimated_2n_at_max_processes_seconds=speedup_seconds,
                max_total_seconds=max_total_seconds,
                passed_budget=passed,
                recommendation=recommendation,
                pipeline_command=plan.pipeline_command,
            )
        )

    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "label": label,
        "config": config,
        "sample_summary": None if sample_summary is None else str(sample_summary),
        "sample_tasks": sample_tasks,
        "sample_time_s": sample_time_s,
        "seconds_per_task": float(seconds_per_task),
        "target_processes": target_processes,
        "assumed_parallel_efficiency": assumed_parallel_efficiency,
        "max_total_seconds": max_total_seconds,
        "scenarios": [scenario.to_json() for scenario in scenarios],
        "note": (
            "Scenario estimates are planning data only. Use them to choose a run command, "
            "then fill Results from real CSV/JSON/PNG/GIF artifacts."
        ),
    }


def benchmark_scenarios_markdown(payload: dict[str, Any]) -> str:
    """Render benchmark scenarios as a short Markdown decision table."""

    lines = [
        "# Benchmark Scenario Comparison",
        "",
        "This file compares possible final local 2D benchmark settings. It is planning data, not measured Results.",
        "",
        "## Inputs",
        "",
        f"- label: `{payload.get('label')}`",
        f"- config: `{payload.get('config')}`",
        f"- sample_summary: `{payload.get('sample_summary') or ''}`",
        f"- seconds_per_task: `{payload.get('seconds_per_task')}`",
        f"- target_processes: `{payload.get('target_processes')}`",
        f"- assumed_parallel_efficiency: `{payload.get('assumed_parallel_efficiency')}`",
        f"- max_total_seconds: `{payload.get('max_total_seconds')}`",
        "",
        "## Scenarios",
        "",
        "| Name | N | 2N | Process counts | Est. N at max P | Est. 2N at max P | Est. full sweep | Passed | Recommendation |",
        "|---|---:|---:|---|---:|---:|---:|---|---|",
    ]
    for scenario in payload.get("scenarios", []):
        lines.append(
            "| {name} | {n} | {two_n} | `{processes}` | {n_sec:.2f}s | {two_n_sec:.2f}s | {total_min:.2f} min | {passed} | {rec} |".format(
                name=scenario["name"],
                n=scenario["chosen_n"],
                two_n=scenario["speedup_n"],
                processes=",".join(str(p) for p in scenario["process_counts"]),
                n_sec=float(scenario["estimated_n_at_max_processes_seconds"]),
                two_n_sec=float(scenario["estimated_2n_at_max_processes_seconds"]),
                total_min=float(scenario["estimated_total_minutes"]),
                passed=scenario["passed_budget"],
                rec=scenario["recommendation"],
            )
        )

    lines.extend(["", "## Commands", ""])
    for scenario in payload.get("scenarios", []):
        lines.extend(
            [
                f"### {scenario['name']}",
                "",
                "```bash",
                " ".join(str(part) for part in scenario["pipeline_command"]),
                "```",
                "",
            ]
        )

    lines.extend(["## Note", "", str(payload.get("note", "")), ""])
    return "\n".join(lines)


def write_benchmark_scenarios(
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown scenario comparison artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(benchmark_scenarios_markdown(payload), encoding="utf-8")
    return json_out, markdown_out


def parse_scenario_names(value: str | None) -> list[str] | None:
    """Parse optional comma-separated scenario names."""

    if value is None:
        return None
    names = [part.strip() for part in value.split(",") if part.strip()]
    if not names:
        raise ValueError("scenario names must not be empty.")
    return names


def parse_target_seconds(value: str) -> list[float]:
    """Parse comma-separated target seconds for scenario generation."""

    return parse_float_list(value)
