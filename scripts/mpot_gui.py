#!/usr/bin/env python3
"""Launch the drag-and-drop GUI for the 2D MPOT/OpenMPI demo."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpot.benchmarks.config import load_config
from mpot.benchmarks.gui_support import build_config_from_gui, options_from_config, scene_from_config


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-config",
        default=str(ROOT / "configs" / "local_smoke.json"),
        help="Base JSON config used for defaults.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Validate GUI defaults without opening a Tkinter window.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_config = load_config(args.base_config)
    if args.self_check:
        scene = scene_from_config(base_config)
        options = options_from_config(base_config, mpi_processes=2, run_id="gui-self-check")
        config = build_config_from_gui(base_config, scene, options)
        print(
            "gui self-check ok: "
            f"N={config.total_tasks}, P={options.mpi_processes}, "
            f"obstacles={len(config.problem.obstacles)}, polytope={config.optimizer.polytope}"
        )
        return 0

    from mpot.benchmarks.gui_app import launch_gui

    launch_gui(base_config_path=args.base_config, repo_root=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
