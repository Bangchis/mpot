"""Utilities for Ubuntu VM LAN cluster hostfiles and commands.

The final demo uses one Ubuntu VM per physical laptop. This module keeps the
host list, OpenMPI hostfile, and smoke commands reproducible instead of relying
on handwritten terminal notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import time

from mpot.benchmarks.artifacts import write_json


@dataclass
class ClusterHost:
    """One Ubuntu VM that can run MPI ranks over SSH."""

    name: str
    address: str
    slots: int
    user: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "slots": self.slots,
            "user": self.user,
        }


def load_cluster_inventory(path: str | Path) -> dict[str, Any]:
    """Load a cluster inventory JSON file."""

    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload


def parse_hosts(payload: dict[str, Any]) -> list[ClusterHost]:
    """Parse and validate host rows from an inventory payload."""

    default_user = str(payload.get("default_user") or "")
    hosts = []
    for index, row in enumerate(payload.get("hosts", [])):
        name = str(row.get("name") or f"node{index + 1}")
        address = str(row.get("address") or "")
        user = str(row.get("user") or default_user)
        slots = int(row.get("slots", 0))
        if not address:
            raise ValueError(f"host {name} has no address.")
        if not user:
            raise ValueError(f"host {name} has no user and no default_user.")
        if slots <= 0:
            raise ValueError(f"host {name} must have positive slots.")
        hosts.append(ClusterHost(name=name, address=address, slots=slots, user=user))
    if not hosts:
        raise ValueError("inventory must contain at least one host.")
    return hosts


def hostfile_text(hosts: list[ClusterHost]) -> str:
    """Return OpenMPI hostfile text."""

    lines = [
        "# Generated OpenMPI hostfile.",
        "# Use IPs or hostnames reachable through SSH from rank 0.",
    ]
    for host in hosts:
        lines.append(f"{host.address} slots={host.slots} # {host.name}")
    return "\n".join(lines) + "\n"


def total_slots(hosts: list[ClusterHost]) -> int:
    """Return the total number of MPI slots in the inventory."""

    return sum(host.slots for host in hosts)


def build_cluster_commands(
    *,
    hostfile_path: str,
    repo_dir: str,
    venv_python: str,
    total_processes: int,
    smoke_tasks: int,
) -> dict[str, Any]:
    """Build copy-paste commands for SSH and MPI smoke checks."""

    mpi_probe = (
        "mpirun --hostfile {hostfile} -np {processes} --map-by slot --bind-to none "
        "{python} -c \"from mpi4py import MPI; import socket; "
        "comm=MPI.COMM_WORLD; print(f'host={{socket.gethostname()}} "
        "rank={{comm.Get_rank()}} size={{comm.Get_size()}}', flush=True)\""
    ).format(hostfile=hostfile_path, processes=total_processes, python=venv_python)

    mpi_smoke = (
        "mpirun --hostfile {hostfile} -np {processes} --map-by slot --bind-to none "
        "{python} scripts/run_mpi.py --config configs/local_smoke.json "
        "--run-id mpi-cluster-smoke-N{tasks}-P{processes} "
        "--experiment-name cluster_smoke_N{tasks} --output-dir results "
        "--total-tasks {tasks}"
    ).format(hostfile=hostfile_path, processes=total_processes, python=venv_python, tasks=smoke_tasks)

    sweep_smoke = (
        "{python} scripts/run_sweep.py --config configs/local_smoke.json "
        "--input-sizes {tasks} --process-counts {processes} --label cluster_smoke "
        "--output-dir results --hostfile {hostfile} --map-by slot --bind-to none --skip-existing"
    ).format(hostfile=hostfile_path, processes=total_processes, python=venv_python, tasks=smoke_tasks)

    final_template = (
        "{python} scripts/run_local_pipeline.py --config configs/local_benchmark.json "
        "--input-sizes 208,412,824 --process-counts 1,2,4,{processes} "
        "--label final_ubuntu_lan_2d --final-n 824 --load-balance-n 412 "
        "--final-processes {processes} --benchmark-plan report/BENCHMARK_PLAN.json "
        "--skip-existing-runs --hostfile {hostfile} --map-by slot --bind-to none"
    ).format(hostfile=hostfile_path, processes=total_processes, python=venv_python)

    return {
        "ssh_probe_template": "ssh <user>@<vm-ip> hostname",
        "working_directory": f"cd {repo_dir}",
        "mpi_probe": mpi_probe,
        "mpi_smoke": mpi_smoke,
        "sweep_smoke": sweep_smoke,
        "final_pipeline_template": final_template,
    }


def build_cluster_plan(
    inventory_path: str | Path,
    *,
    hostfile_path: str | Path,
    total_processes: int | None = None,
    smoke_tasks: int | None = None,
) -> dict[str, Any]:
    """Build hostfile text and cluster commands from an inventory JSON."""

    payload = load_cluster_inventory(inventory_path)
    hosts = parse_hosts(payload)
    slots = total_slots(hosts)
    process_count = int(total_processes or slots)
    if process_count <= 0:
        raise ValueError("total_processes must be positive.")
    repo_dir = str(payload.get("default_repo_dir") or "~/mpot")
    venv_python = str(payload.get("default_venv_python") or ".venv/bin/python")
    smoke_count = int(smoke_tasks or max(process_count, 2))
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "inventory_path": str(inventory_path),
        "cluster_name": str(payload.get("cluster_name") or "mpot_ubuntu_vm_lan"),
        "hostfile_path": str(hostfile_path),
        "hosts": [host.to_json() for host in hosts],
        "total_slots": slots,
        "total_processes": process_count,
        "smoke_tasks": smoke_count,
        "repo_dir": repo_dir,
        "venv_python": venv_python,
        "hostfile_text": hostfile_text(hosts),
        "commands": build_cluster_commands(
            hostfile_path=str(hostfile_path),
            repo_dir=repo_dir,
            venv_python=venv_python,
            total_processes=process_count,
            smoke_tasks=smoke_count,
        ),
        "note": (
            "All Ubuntu VMs should have the repo at the same path and passwordless SSH "
            "from the rank-0 VM before running OpenMPI across the LAN."
        ),
    }


def cluster_plan_markdown(payload: dict[str, Any]) -> str:
    """Render cluster setup commands as Markdown."""

    commands = payload.get("commands", {})
    lines = [
        "# Ubuntu VM Cluster Plan",
        "",
        "This file is generated from a cluster inventory JSON. It does not run MPI by itself.",
        "",
        "## Cluster",
        "",
        f"- cluster_name: `{payload.get('cluster_name')}`",
        f"- inventory_path: `{payload.get('inventory_path')}`",
        f"- hostfile_path: `{payload.get('hostfile_path')}`",
        f"- total_slots: `{payload.get('total_slots')}`",
        f"- total_processes: `{payload.get('total_processes')}`",
        f"- smoke_tasks: `{payload.get('smoke_tasks')}`",
        f"- repo_dir: `{payload.get('repo_dir')}`",
        f"- venv_python: `{payload.get('venv_python')}`",
        "",
        "## Hosts",
        "",
        "| name | address | user | slots |",
        "|---|---|---|---:|",
    ]
    for host in payload.get("hosts", []):
        lines.append(f"| {host['name']} | `{host['address']}` | `{host['user']}` | {host['slots']} |")

    lines.extend(
        [
            "",
            "## Hostfile",
            "",
            "```text",
            str(payload.get("hostfile_text", "")).rstrip(),
            "```",
            "",
            "## Commands",
            "",
            "Run these from the rank-0 Ubuntu VM after all VMs have the same repo path and venv.",
            "",
            "### SSH probe",
            "",
            "```bash",
            str(commands.get("ssh_probe_template", "")),
            "```",
            "",
            "### Working directory",
            "",
            "```bash",
            str(commands.get("working_directory", "")),
            "```",
            "",
            "### MPI probe",
            "",
            "```bash",
            str(commands.get("mpi_probe", "")),
            "```",
            "",
            "### MPI smoke run",
            "",
            "```bash",
            str(commands.get("mpi_smoke", "")),
            "```",
            "",
            "### Sweep smoke run",
            "",
            "```bash",
            str(commands.get("sweep_smoke", "")),
            "```",
            "",
            "### Final pipeline template",
            "",
            "```bash",
            str(commands.get("final_pipeline_template", "")),
            "```",
            "",
            "## Note",
            "",
            str(payload.get("note", "")),
            "",
        ]
    )
    return "\n".join(lines)


def write_cluster_plan(
    payload: dict[str, Any],
    *,
    hostfile_path: str | Path,
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path, Path]:
    """Write hostfile, JSON, and Markdown cluster plan artifacts."""

    hostfile_out = Path(hostfile_path)
    json_out = Path(json_path)
    markdown_out = Path(markdown_path)
    hostfile_out.parent.mkdir(parents=True, exist_ok=True)
    hostfile_out.write_text(str(payload["hostfile_text"]), encoding="utf-8")
    write_json(json_out, payload)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(cluster_plan_markdown(payload), encoding="utf-8")
    return hostfile_out, json_out, markdown_out
