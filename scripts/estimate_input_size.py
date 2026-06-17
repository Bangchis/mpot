#!/usr/bin/env python3
"""Estimate a task count N for a target runtime.

This script runs a small serial sample and extrapolates the number of tasks
needed to reach a target number of seconds. The estimate is only a starting
point; final N must still be measured with the real process count.
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/local_benchmark.json", help="Base config.")
    parser.add_argument("--sample-tasks", type=int, default=8, help="Small N used for measurement.")
    parser.add_argument("--target-seconds", type=float, default=150.0, help="Desired runtime in seconds.")
    parser.add_argument("--run-id", default="estimate-n-sample", help="Run id for the sample serial run.")
    parser.add_argument("--output", default=None, help="Optional output JSON path for the estimate.")
    parser.add_argument("--extra", nargs="*", default=[], help="Extra args appended to run_serial.py.")
    args, unknown = parser.parse_known_args()
    args.extra.extend(unknown)
    return args


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        "scripts/run_serial.py",
        "--config",
        args.config,
        "--run-id",
        args.run_id,
        "--total-tasks",
        str(args.sample_tasks),
        "--no-plots",
    ] + args.extra
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)

    summary_path = ROOT / "results" / args.run_id / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    measured = float(summary["total_time_s"])
    per_task = measured / max(1, int(args.sample_tasks))
    estimated_n = max(1, round(args.target_seconds / per_task))

    payload = {
        "sample_tasks": args.sample_tasks,
        "sample_time_s": measured,
        "seconds_per_task": per_task,
        "target_seconds": args.target_seconds,
        "estimated_total_tasks": estimated_n,
        "sample_summary": str(summary_path.relative_to(ROOT)),
        "command": command,
        "note": "Measure this N again; the estimate is not final report data.",
    }
    output = Path(args.output) if args.output else summary_path.parent / "input_size_estimate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"estimate_json: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
