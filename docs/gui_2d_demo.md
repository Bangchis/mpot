# 2D GUI Demo Runbook

This document explains the drag-and-drop GUI for the 2D MPOT/OpenMPI demo. The
GUI is meant for local demonstration and teaching: it lets the group edit a
2D motion-planning scene, choose MPOT/MPI parameters, run the existing parallel
algorithm, and generate GIFs that explain both the robot trajectory and the
parallel execution.

## What The GUI Does

- Draws the 2D workspace on a canvas.
- Lets the user drag the start marker, goal marker, and circular obstacles.
- Lets the user double-click or use "Add obstacle" to create new obstacles.
- Lets the user choose MPOT probe type: `orthoplex`, `cube`, or `simplex`.
- Lets the user edit practical demo parameters:
  - input size `N` / total tasks;
  - MPI process count `P`;
  - number of particles per task;
  - trajectory length;
  - probe samples and probe radius;
  - outer MPOT iterations and Sinkhorn inner iterations;
  - cost weights for obstacle, boundary, smoothness, goal, and velocity terms.
- Writes a normal JSON config into `results/gui_configs/`.
- Runs the existing OpenMPI path through `scripts/run_mpi.py`.
- Generates three GIF outputs after the run:
  - `best_path.gif`: point robot replay along the selected best path;
  - `algorithm_trace.gif`: MPOT particles/candidate trajectories over optimizer iterations;
  - `parallel_schedule.gif`: schematic MPI `bcast -> scatter -> compute -> gather -> reduce` workflow.

The GUI does not implement a separate planner. It calls the same benchmark
modules used by the command-line experiments, so the demo remains consistent
with the report.

## Start The GUI

From the repo root:

```bash
.venv/bin/python scripts/mpot_gui.py --self-check
.venv/bin/python scripts/mpot_gui.py
```

Use the GUI mainly on macOS or a Linux desktop environment. A plain Ubuntu
Server VM does not normally have a graphical display, so teammates should use
the command-line smoke tests there unless they install a desktop or use X
forwarding.

## Recommended Demo Flow

1. Press **Fast defaults** for a quick demonstration.
2. Drag the green `START` marker to choose the source.
3. Drag the red `GOAL` marker to choose the destination.
4. Double-click inside the workspace to add obstacles.
5. Click an obstacle and edit its radius or safety margin if needed.
6. Choose the probe type:
   - `orthoplex`: good default, few directions, clear demo;
   - `cube`: more axis-aligned corners, useful for comparison;
   - `simplex`: compact probe shape, also easy to explain.
7. Set `N tasks` and `MPI ranks P`.
8. Press **Run MPI + GIFs**.
9. Wait until the log prints the output GIF paths.
10. Press **Open output folder** to inspect the generated artifacts.

For a richer but slower demo, press **Detailed defaults** before running.

## Output Files

For a run id such as `gui-mpot-20260619-120000`, the GUI writes:

```text
results/gui_configs/gui-mpot-20260619-120000.json
results/gui-mpot-20260619-120000/summary.json
results/gui-mpot-20260619-120000/task_results.csv
results/gui-mpot-20260619-120000/task_assignment.csv
results/gui-mpot-20260619-120000/rank_timings.csv
results/gui-mpot-20260619-120000/comm_events.csv
results/gui-mpot-20260619-120000/best_path.gif
results/gui-mpot-20260619-120000/algorithm_trace.gif
results/gui-mpot-20260619-120000/algorithm_trace.json
results/gui-mpot-20260619-120000/parallel_schedule.gif
```

The GIFs are demo artifacts. Quantitative report claims should still come from
CSV/JSON files and report figures generated from real experiment runs.

## Command-Line Equivalents

The GUI internally runs the same style of command:

```bash
mpirun -np 4 --bind-to none \
  .venv/bin/python scripts/run_mpi.py \
  --config results/gui_configs/<run_id>.json \
  --run-id <run_id>
```

The GIFs can also be regenerated manually:

```bash
.venv/bin/python scripts/animate_trajectory.py \
  --run-dir results/<run_id> \
  --output results/<run_id>/best_path.gif

.venv/bin/python scripts/animate_algorithm_trace.py \
  --run-dir results/<run_id> \
  --output results/<run_id>/algorithm_trace.gif \
  --trace-output results/<run_id>/algorithm_trace.json

.venv/bin/python scripts/animate_parallel_schedule.py \
  --run-dir results/<run_id> \
  --output results/<run_id>/parallel_schedule.gif
```

## Troubleshooting

- If the GUI cannot open, check whether Tkinter is installed:

```bash
.venv/bin/python - <<'PY'
import tkinter
print("tkinter ok")
PY
```

- If `mpirun` is not found, install OpenMPI and `mpi4py`.
- If the run is too slow, use **Fast defaults**, reduce `N`, reduce particles,
  or reduce outer iterations.
- If the GIF is too cluttered, reduce **Particles shown**.
- If the path goes through obstacles, increase obstacle cost, increase particles,
  add more tasks `N`, or use a less difficult obstacle layout.
