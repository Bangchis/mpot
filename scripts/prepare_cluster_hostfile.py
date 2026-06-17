#!/usr/bin/env python3
"""Generate an OpenMPI hostfile and cluster command guide from JSON inventory."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.cluster import build_cluster_plan, write_cluster_plan


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default="configs/cluster_hosts.example.json", help="Cluster inventory JSON.")
    parser.add_argument("--hostfile", default="configs/hostfile_ubuntu.txt", help="Generated OpenMPI hostfile.")
    parser.add_argument("--output", default="report/CLUSTER_PLAN.json", help="Generated cluster plan JSON.")
    parser.add_argument("--markdown", default="report/CLUSTER_PLAN.md", help="Generated cluster plan Markdown.")
    parser.add_argument("--total-processes", type=int, default=None, help="MPI process count. Defaults to total slots.")
    parser.add_argument("--smoke-tasks", type=int, default=None, help="Task count for cluster smoke commands.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = build_cluster_plan(
            args.inventory,
            hostfile_path=args.hostfile,
            total_processes=args.total_processes,
            smoke_tasks=args.smoke_tasks,
        )
        hostfile_path, json_path, markdown_path = write_cluster_plan(
            payload,
            hostfile_path=args.hostfile,
            json_path=args.output,
            markdown_path=args.markdown,
        )
    except Exception as exc:
        print(f"cluster hostfile generation failed: {exc}", file=sys.stderr)
        return 1

    print(f"hostfile: {hostfile_path}")
    print(f"cluster_plan_json: {json_path}")
    print(f"cluster_plan_markdown: {markdown_path}")
    print(f"total_slots: {payload['total_slots']}")
    print(f"total_processes: {payload['total_processes']}")
    print("mpi_probe: " + payload["commands"]["mpi_probe"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
