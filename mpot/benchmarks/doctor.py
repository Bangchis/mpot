"""Setup doctor for local and Ubuntu teammate machines.

Each teammate should be able to run one command and see whether Python,
packages, repo imports, and MPI are ready before attempting the benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import importlib
import subprocess
import sys
import time

from mpot.benchmarks.artifacts import write_json
from mpot.benchmarks.environment import DEFAULT_PACKAGES, capture_environment


@dataclass
class DoctorItem:
    """One setup check with a pass/fail result."""

    name: str
    passed: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }


def _python_version_tuple(version_text: str) -> tuple[int, int, int]:
    parts = version_text.split(".")
    values = [int(part) for part in parts[:3]]
    while len(values) < 3:
        values.append(0)
    return values[0], values[1], values[2]


def _check_python_version(env: dict[str, Any], minimum: tuple[int, int]) -> DoctorItem:
    version_text = str(env.get("python", {}).get("version", "0.0.0"))
    observed = _python_version_tuple(version_text)
    passed = observed >= (minimum[0], minimum[1], 0)
    return DoctorItem(
        name="python version is supported",
        passed=passed,
        detail=f"observed={version_text}, required>={minimum[0]}.{minimum[1]}",
    )


def _check_packages(env: dict[str, Any]) -> list[DoctorItem]:
    items = []
    for package in env.get("packages", []):
        name = str(package.get("name", ""))
        items.append(
            DoctorItem(
                name=f"package installed: {name}",
                passed=bool(package.get("installed")),
                detail=str(package.get("version") or package.get("error") or ""),
            )
        )
    return items


def _check_repo_import(module_name: str = "mpot") -> DoctorItem:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return DoctorItem(
            name=f"repo import works: {module_name}",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
    return DoctorItem(name=f"repo import works: {module_name}", passed=True, detail="import ok")


def _check_mpirun(env: dict[str, Any], required: bool) -> DoctorItem:
    mpirun = env.get("mpi", {}).get("mpirun", {})
    executable = str(mpirun.get("executable") or "")
    if not required:
        return DoctorItem(
            name="mpirun check skipped",
            passed=True,
            detail=f"detected={executable or 'missing'}",
        )
    return DoctorItem(
        name="mpirun executable exists",
        passed=bool(executable),
        detail=executable or "missing",
    )


def run_mpi_probe(*, repo_root: str | Path, processes: int, timeout_s: float = 20.0) -> dict[str, Any]:
    """Run a tiny mpi4py program and return raw command status."""

    code = (
        "from mpi4py import MPI\n"
        "comm=MPI.COMM_WORLD\n"
        "print(f'rank={comm.Get_rank()} size={comm.Get_size()}', flush=True)\n"
    )
    command = ["mpirun", "-np", str(processes), sys.executable, "-c", code]
    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
        output = result.stdout.strip()
        passed = result.returncode == 0 and f"size={processes}" in output
        return {
            "command": command,
            "returncode": result.returncode,
            "output": output,
            "passed": passed,
        }
    except Exception as exc:
        return {
            "command": command,
            "returncode": None,
            "output": f"{type(exc).__name__}: {exc}",
            "passed": False,
        }


def _check_mpi_probe(probe: dict[str, Any] | None) -> DoctorItem:
    if probe is None:
        return DoctorItem("mpi runtime probe skipped", True, "not requested")
    output = str(probe.get("output", ""))
    first_lines = " | ".join(output.splitlines()[:4])
    return DoctorItem(
        name="mpi runtime probe passed",
        passed=bool(probe.get("passed")),
        detail=f"returncode={probe.get('returncode')}, output={first_lines}",
    )


def build_setup_doctor(
    *,
    repo_root: str | Path,
    label: str | None = None,
    packages: list[str] | None = None,
    min_python: tuple[int, int] = (3, 9),
    require_mpirun: bool = True,
    run_probe: bool = False,
    probe_processes: int = 2,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    """Build a setup doctor payload for one machine."""

    root = Path(repo_root).resolve()
    env = capture_environment(repo_root=root, label=label, packages=packages or DEFAULT_PACKAGES)
    probe = None
    if run_probe:
        probe = run_mpi_probe(repo_root=root, processes=probe_processes, timeout_s=timeout_s)

    items = [
        DoctorItem("repo root exists", root.exists(), str(root)),
        _check_python_version(env, min_python),
        _check_repo_import("mpot"),
        *_check_packages(env),
        _check_mpirun(env, require_mpirun),
        _check_mpi_probe(probe),
    ]
    failed = [item for item in items if not item.passed]
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "label": label or "",
        "repo_root": str(root),
        "ready": not failed,
        "num_items": len(items),
        "num_failed": len(failed),
        "items": [item.to_json() for item in items],
        "environment": env,
        "mpi_probe": probe,
        "recommended_install": [
            "python -m pip install -r requirements-local.txt",
            "python -m pip install -e . --no-deps",
        ],
        "recommended_smoke": (
            "python scripts/run_local_pipeline.py --config configs/local_smoke.json "
            "--input-sizes 2 --process-counts 1,2 --label teammate_smoke "
            "--final-n 2 --load-balance-n 2 --final-processes 2"
        ),
    }


def setup_doctor_markdown(payload: dict[str, Any]) -> str:
    """Render a setup doctor payload as Markdown."""

    verdict = "PASS" if payload.get("ready") else "FAIL"
    env = payload.get("environment", {})
    python = env.get("python", {})
    platform = env.get("platform", {})
    lines = [
        "# Setup Doctor",
        "",
        "This file checks whether one teammate machine is ready to run the",
        "local-first MPOT/MPI benchmark.",
        "",
        f"- created_at: `{payload.get('created_at', '')}`",
        f"- label: `{payload.get('label', '')}`",
        f"- verdict: **{verdict}**",
        f"- repo_root: `{payload.get('repo_root', '')}`",
        f"- OS: `{platform.get('system', '')} {platform.get('release', '')}`",
        f"- Python: `{python.get('version', '')}`",
        f"- Python executable: `{python.get('executable', '')}`",
        "",
        "## Checks",
        "",
        "| status | check | detail |",
        "|---|---|---|",
    ]
    for item in payload.get("items", []):
        status = "PASS" if item.get("passed") else "FAIL"
        lines.append(f"| {status} | {item.get('name', '')} | `{item.get('detail', '')}` |")

    lines.extend(["", "## Recommended Install Commands", ""])
    for command in payload.get("recommended_install", []):
        lines.append(f"```bash\n{command}\n```")

    lines.extend(
        [
            "",
            "## Recommended Smoke Command",
            "",
            "```bash",
            str(payload.get("recommended_smoke", "")),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_setup_doctor(payload: dict[str, Any], json_path: str | Path, markdown_path: str | Path) -> tuple[Path, Path]:
    """Write setup doctor JSON and Markdown files."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(setup_doctor_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
