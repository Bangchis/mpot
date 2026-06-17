"""Plan final benchmark sizes and commands from measured sample artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import math
import os

from mpot.benchmarks.artifacts import read_json, write_json


@dataclass
class BenchmarkPlan:
    """Report-friendly benchmark plan derived from a measured sample run."""

    label: str
    config: str
    sample_summary: str | None
    sample_tasks: int | None
    sample_time_s: float | None
    seconds_per_task: float
    target_seconds: float
    target_processes: int
    assumed_parallel_efficiency: float
    chosen_n: int
    speedup_n: int
    input_sizes: list[int]
    process_counts: list[int]
    pipeline_command: list[str]
    note: str

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "config": self.config,
            "sample_summary": self.sample_summary,
            "sample_tasks": self.sample_tasks,
            "sample_time_s": self.sample_time_s,
            "seconds_per_task": self.seconds_per_task,
            "target_seconds": self.target_seconds,
            "target_processes": self.target_processes,
            "assumed_parallel_efficiency": self.assumed_parallel_efficiency,
            "chosen_n": self.chosen_n,
            "speedup_n": self.speedup_n,
            "input_sizes": self.input_sizes,
            "process_counts": self.process_counts,
            "pipeline_command": self.pipeline_command,
            "note": self.note,
        }


def round_up_to_multiple(value: float, multiple: int) -> int:
    """Round a positive value up to a positive multiple."""

    if multiple <= 0:
        raise ValueError("multiple must be positive.")
    return max(multiple, int(math.ceil(value / multiple) * multiple))


def process_counts_for_max(max_processes: int, include_max: bool = True) -> list[int]:
    """Return 1, 2, 4, ... up to max_processes, optionally including max."""

    if max_processes <= 0:
        raise ValueError("max_processes must be positive.")
    counts = []
    value = 1
    while value <= max_processes:
        counts.append(value)
        value *= 2
    if include_max and counts[-1] != max_processes:
        counts.append(max_processes)
    return sorted(set(counts))


def parse_float_list(value: str) -> list[float]:
    """Parse a comma-separated list of positive floats."""

    out = []
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        number = float(item)
        if number <= 0:
            raise ValueError("factors must be positive.")
        out.append(number)
    if not out:
        raise ValueError("At least one factor is required.")
    return out


def seconds_per_task_from_summary(summary_path: str | Path) -> tuple[int, float, float]:
    """Return sample_tasks, sample_time_s, seconds_per_task from summary.json."""

    payload = read_json(summary_path)
    tasks = int(payload["total_tasks"])
    total_time = float(payload.get("total_time_s", payload["runtime_with_communication_s"]))
    if tasks <= 0 or total_time <= 0:
        raise ValueError("sample summary must contain positive total_tasks and runtime.")
    return tasks, total_time, total_time / tasks


def estimate_n_for_parallel_runtime(
    *,
    seconds_per_task: float,
    target_seconds: float,
    target_processes: int,
    assumed_parallel_efficiency: float,
) -> int:
    """Estimate N for target runtime under a simple efficiency assumption."""

    if seconds_per_task <= 0:
        raise ValueError("seconds_per_task must be positive.")
    if target_seconds <= 0:
        raise ValueError("target_seconds must be positive.")
    if target_processes <= 0:
        raise ValueError("target_processes must be positive.")
    if not (0 < assumed_parallel_efficiency <= 1.0):
        raise ValueError("assumed_parallel_efficiency must be in (0, 1].")
    estimated = target_seconds * target_processes * assumed_parallel_efficiency / seconds_per_task
    return round_up_to_multiple(estimated, target_processes)


def input_sizes_from_n(chosen_n: int, speedup_n: int, factors: list[float], multiple: int) -> list[int]:
    """Build unique input sizes for runtime-vs-N and speedup runs."""

    values = {round_up_to_multiple(chosen_n * factor, multiple) for factor in factors}
    values.add(chosen_n)
    values.add(speedup_n)
    return sorted(values)


def build_pipeline_command(
    *,
    config: str,
    input_sizes: list[int],
    process_counts: list[int],
    label: str,
    speedup_n: int,
    load_balance_n: int,
    final_processes: int,
) -> list[str]:
    """Build the final local pipeline command for the generated plan."""

    return [
        "python",
        "scripts/run_local_pipeline.py",
        "--config",
        config,
        "--input-sizes",
        ",".join(str(n) for n in input_sizes),
        "--process-counts",
        ",".join(str(p) for p in process_counts),
        "--label",
        label,
        "--final-n",
        str(speedup_n),
        "--load-balance-n",
        str(load_balance_n),
        "--final-processes",
        str(final_processes),
    ]


def create_benchmark_plan(
    *,
    config: str,
    label: str,
    target_seconds: float,
    target_processes: int | None = None,
    assumed_parallel_efficiency: float = 0.8,
    sample_summary: str | Path | None = None,
    seconds_per_task: float | None = None,
    runtime_factors: list[float] | None = None,
    include_max_processes: bool = True,
) -> BenchmarkPlan:
    """Create a benchmark plan without running experiments."""

    target_processes = target_processes or max(1, os.cpu_count() or 1)
    runtime_factors = runtime_factors or [0.5, 1.0, 2.0]

    sample_tasks = None
    sample_time_s = None
    sample_summary_text = None
    if sample_summary is not None:
        sample_summary_text = str(sample_summary)
        sample_tasks, sample_time_s, measured_seconds_per_task = seconds_per_task_from_summary(sample_summary)
        if seconds_per_task is None:
            seconds_per_task = measured_seconds_per_task

    if seconds_per_task is None:
        raise ValueError("Provide either sample_summary or seconds_per_task.")

    chosen_n = estimate_n_for_parallel_runtime(
        seconds_per_task=float(seconds_per_task),
        target_seconds=target_seconds,
        target_processes=target_processes,
        assumed_parallel_efficiency=assumed_parallel_efficiency,
    )
    speedup_n = round_up_to_multiple(2 * chosen_n, target_processes)
    input_sizes = input_sizes_from_n(chosen_n, speedup_n, runtime_factors, target_processes)
    process_counts = process_counts_for_max(target_processes, include_max=include_max_processes)
    command = build_pipeline_command(
        config=config,
        input_sizes=input_sizes,
        process_counts=process_counts,
        label=label,
        speedup_n=speedup_n,
        load_balance_n=chosen_n,
        final_processes=target_processes,
    )
    return BenchmarkPlan(
        label=label,
        config=config,
        sample_summary=sample_summary_text,
        sample_tasks=sample_tasks,
        sample_time_s=sample_time_s,
        seconds_per_task=float(seconds_per_task),
        target_seconds=target_seconds,
        target_processes=target_processes,
        assumed_parallel_efficiency=assumed_parallel_efficiency,
        chosen_n=chosen_n,
        speedup_n=speedup_n,
        input_sizes=input_sizes,
        process_counts=process_counts,
        pipeline_command=command,
        note=(
            "This is a planning estimate, not final report data. Run the generated "
            "pipeline command and use only resulting CSV/JSON/PNG artifacts for Results."
        ),
    )


def plan_markdown(plan: BenchmarkPlan) -> str:
    """Render a benchmark plan as Markdown for teammates."""

    data = plan.to_json()
    command = " ".join(plan.pipeline_command)
    lines = [
        "# Benchmark Plan",
        "",
        "This plan is generated from measured sample timing or an explicit",
        "seconds-per-task estimate. It does not contain final benchmark results.",
        "",
        "## Inputs",
        "",
        f"- label: `{plan.label}`",
        f"- config: `{plan.config}`",
        f"- sample_summary: `{plan.sample_summary or ''}`",
        f"- sample_tasks: `{plan.sample_tasks or ''}`",
        f"- sample_time_s: `{'' if plan.sample_time_s is None else plan.sample_time_s}`",
        f"- seconds_per_task: `{plan.seconds_per_task}`",
        f"- target_seconds: `{plan.target_seconds}`",
        f"- target_processes: `{plan.target_processes}`",
        f"- assumed_parallel_efficiency: `{plan.assumed_parallel_efficiency}`",
        "",
        "## Planned Experiment Sizes",
        "",
        f"- N for runtime/load-balance experiment: `{plan.chosen_n}`",
        f"- 2N for speedup experiment: `{plan.speedup_n}`",
        f"- input_sizes: `{','.join(str(n) for n in plan.input_sizes)}`",
        f"- process_counts: `{','.join(str(p) for p in plan.process_counts)}`",
        "",
        "## Pipeline Command",
        "",
        "```bash",
        command,
        "```",
        "",
        "## JSON",
        "",
        "```json",
        json.dumps(data, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def write_benchmark_plan(plan: BenchmarkPlan, json_path: str | Path, markdown_path: str | Path) -> tuple[Path, Path]:
    """Write JSON and Markdown benchmark plan artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, plan.to_json())
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(plan_markdown(plan), encoding="utf-8")
    return json_out, markdown_out
