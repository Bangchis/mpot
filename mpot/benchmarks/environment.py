"""Environment capture for reproducible local and Ubuntu benchmark runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import importlib
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time


DEFAULT_PACKAGES = ["torch", "numpy", "matplotlib", "pillow", "mpi4py"]


@dataclass
class CommandStatus:
    """Small command probe used for mpirun and git metadata."""

    executable: str | None
    command: list[str]
    returncode: int | None
    output: str

    def to_json(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "command": self.command,
            "returncode": self.returncode,
            "output": self.output,
        }


def probe_command(command: list[str], timeout_s: float = 5.0) -> CommandStatus:
    """Run a short metadata command without raising on failure."""

    executable = shutil.which(command[0])
    if not executable:
        return CommandStatus(None, command, None, "MISSING")
    try:
        result = subprocess.run(
            [executable] + command[1:],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
        output = result.stdout.strip()
        return CommandStatus(executable, command, result.returncode, output)
    except Exception as exc:
        return CommandStatus(executable, command, None, f"{type(exc).__name__}: {exc}")


def package_status(name: str) -> dict[str, Any]:
    """Return installed/missing status for one Python package."""

    try:
        version = importlib.metadata.version(name)
        return {"name": name, "installed": True, "version": version, "error": ""}
    except importlib.metadata.PackageNotFoundError:
        try:
            module = importlib.import_module(name)
            return {
                "name": name,
                "installed": True,
                "version": str(getattr(module, "__version__", "installed")),
                "error": "",
            }
        except Exception as exc:
            return {"name": name, "installed": False, "version": "", "error": f"{type(exc).__name__}: {exc}"}


def _git_info(repo_root: Path) -> dict[str, Any]:
    head = probe_command(["git", "rev-parse", "--short", "HEAD"])
    branch = probe_command(["git", "branch", "--show-current"])
    status = probe_command(["git", "status", "--short"])
    return {
        "head": head.output.splitlines()[0] if head.returncode == 0 and head.output else "",
        "branch": branch.output.splitlines()[0] if branch.returncode == 0 and branch.output else "",
        "dirty": bool(status.output.strip()) if status.returncode == 0 else None,
        "status_short": status.output if status.returncode == 0 else "",
        "git_available": head.executable is not None,
    }


def capture_environment(
    *,
    repo_root: str | Path,
    label: str | None = None,
    packages: list[str] | None = None,
) -> dict[str, Any]:
    """Capture reproducibility metadata for the current machine."""

    root = Path(repo_root).resolve()
    packages = packages or DEFAULT_PACKAGES
    mpirun = probe_command(["mpirun", "--version"])
    payload = {
        "label": label or "",
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "repo_root": str(root),
        "hostname": socket.gethostname(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_implementation": platform.python_implementation(),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "version_full": sys.version,
        },
        "cpu": {
            "logical_count": os.cpu_count(),
        },
        "packages": [package_status(name) for name in packages],
        "mpi": {
            "mpirun": mpirun.to_json(),
            "mpi4py": package_status("mpi4py"),
        },
        "git": _git_info(root),
    }
    return payload


def build_environment_markdown(payload: dict[str, Any]) -> str:
    """Render a compact Markdown environment report."""

    platform_info = payload["platform"]
    python_info = payload["python"]
    lines = [
        "# Environment Report",
        "",
        "This file is generated from the local machine. Use it as evidence for",
        "the Experimental Setup section, and regenerate it on Ubuntu/cluster runs.",
        "",
        f"- label: `{payload.get('label', '')}`",
        f"- captured_at: `{payload.get('captured_at', '')}`",
        f"- hostname: `{payload.get('hostname', '')}`",
        f"- repo_root: `{payload.get('repo_root', '')}`",
        f"- OS: `{platform_info.get('system', '')} {platform_info.get('release', '')}`",
        f"- machine: `{platform_info.get('machine', '')}`",
        f"- logical CPU count: `{payload.get('cpu', {}).get('logical_count', '')}`",
        f"- Python: `{python_info.get('version', '')}`",
        f"- Python executable: `{python_info.get('executable', '')}`",
        "",
        "## Packages",
        "",
        "| package | installed | version | error |",
        "|---|---:|---|---|",
    ]
    for package in payload.get("packages", []):
        installed = "yes" if package.get("installed") else "no"
        lines.append(
            f"| {package.get('name', '')} | {installed} | {package.get('version', '')} | {package.get('error', '')} |"
        )

    mpirun = payload.get("mpi", {}).get("mpirun", {})
    first_mpi_line = str(mpirun.get("output", "")).splitlines()[0] if mpirun.get("output") else ""
    lines.extend(
        [
            "",
            "## MPI",
            "",
            f"- mpirun executable: `{mpirun.get('executable', '')}`",
            f"- mpirun version: `{first_mpi_line}`",
            "",
            "## Git",
            "",
            f"- branch: `{payload.get('git', {}).get('branch', '')}`",
            f"- head: `{payload.get('git', {}).get('head', '')}`",
            f"- dirty worktree: `{payload.get('git', {}).get('dirty', '')}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_environment_artifacts(
    *,
    payload: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown environment artifacts."""

    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    markdown_out.write_text(build_environment_markdown(payload), encoding="utf-8")
    return json_out, markdown_out
