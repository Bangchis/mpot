"""Helpers for deciding whether an existing benchmark run is reusable."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any
import json

from mpot.benchmarks.cli import add_config_override_args, apply_config_overrides
from mpot.benchmarks.config import config_hash, config_hash_from_dict, load_config


def extra_override_args(extra: list[str]):
    """Parse config override flags from an arbitrary extra-argument list."""

    parser = ArgumentParser(add_help=False)
    add_config_override_args(parser)
    args, _ = parser.parse_known_args(extra)
    return args


def expected_config_hash(
    *,
    config_path: str | Path,
    experiment_name: str,
    output_dir: str,
    total_tasks: int,
    extra: list[str] | None = None,
) -> str:
    """Return the config hash that a runner should write for one planned run."""

    config = load_config(config_path)
    overrides = extra_override_args(extra or [])
    overrides.experiment_name = experiment_name
    overrides.output_dir = output_dir
    overrides.total_tasks = total_tasks
    config = apply_config_overrides(config, overrides)
    return config_hash(config)


def expected_run_metadata(
    *,
    config_path: str | Path,
    output_dir: str,
    label: str,
    input_size_n: int,
    mode: str,
    processes: int,
    extra: list[str] | None = None,
) -> dict[str, Any]:
    """Return the metadata expected in summary.json for one planned run."""

    if mode not in {"serial", "mpi"}:
        raise ValueError("mode must be 'serial' or 'mpi'.")
    run_id = f"serial-{label}-N{input_size_n}" if mode == "serial" else f"mpi-{label}-N{input_size_n}-P{processes}"
    experiment_name = f"{label}_N{input_size_n}"
    return {
        "run_id": run_id,
        "mode": mode,
        "total_tasks": int(input_size_n),
        "size": int(processes),
        "experiment_name": experiment_name,
        "config_hash": expected_config_hash(
            config_path=config_path,
            experiment_name=experiment_name,
            output_dir=output_dir,
            total_tasks=input_size_n,
            extra=extra or [],
        ),
    }


def summary_config_hash(summary: dict[str, Any]) -> str | None:
    """Return config_hash from a summary, computing it from embedded config if needed."""

    if summary.get("config_hash"):
        return str(summary["config_hash"])
    config_payload = summary.get("config")
    if isinstance(config_payload, dict):
        return config_hash_from_dict(config_payload)
    return None


def existing_run_status(
    output_dir: str | Path,
    run_id: str,
    *,
    expected: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Return whether an existing run can be reused and a human-readable reason."""

    summary_path = Path(output_dir) / run_id / "summary.json"
    if not summary_path.exists():
        return False, f"missing {summary_path}"

    if expected is None:
        return True, str(summary_path)

    try:
        with summary_path.open("r", encoding="utf-8") as f:
            summary = json.load(f)
    except Exception as exc:
        return False, f"cannot read {summary_path}: {exc}"

    checks = [
        ("run_id", summary.get("run_id"), expected.get("run_id")),
        ("mode", summary.get("mode"), expected.get("mode")),
        ("total_tasks", int(summary.get("total_tasks", -1)), int(expected.get("total_tasks", -2))),
        ("size", int(summary.get("size", -1)), int(expected.get("size", -2))),
    ]
    summary_config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    checks.append(
        (
            "experiment_name",
            summary.get("experiment_name") or summary_config.get("experiment_name"),
            expected.get("experiment_name"),
        )
    )
    observed_hash = summary_config_hash(summary)
    if expected.get("config_hash"):
        if not observed_hash:
            return False, f"{summary_path} does not contain config_hash or embedded config"
        checks.append(("config_hash", observed_hash, expected.get("config_hash")))

    for name, observed, wanted in checks:
        if observed != wanted:
            return False, f"{summary_path} has {name}={observed!r}, expected {wanted!r}"
    return True, str(summary_path)


def run_is_complete(output_dir: str | Path, run_id: str, expected: dict[str, Any] | None = None) -> bool:
    """Return True when a run exists and matches optional expected metadata."""

    reusable, _ = existing_run_status(output_dir, run_id, expected=expected)
    return reusable
