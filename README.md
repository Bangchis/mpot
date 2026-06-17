# Distributed MPOT Motion Planning with OpenMPI

Course project repository for **Parallel Computing and Parallel Programming**.
The project adapts the idea of Motion Planning via Optimal Transport (MPOT) into
a CPU-only, OpenMPI-based benchmark for 2D motion planning.

This is not a GPU reproduction of the original MPOT system. The original MPOT
paper uses highly parallel batch trajectory optimization and motivates the
algorithmic kernel. This course project keeps the local MPOT-inspired planner
as the task kernel and studies how independent seed-level planning attempts can
be distributed across MPI processes and, later, Ubuntu VMs on the same LAN.

## Current Status

| Stage | Status | Evidence |
|---|---|---|
| macOS local serial/MPI benchmark | Done | `report/FINAL_AUDIT_final_macbook_air_2d.md` |
| Ubuntu single-VM smoke | Done | `report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md` |
| Teammate VM smoke | TODO | Run each teammate VM before LAN |
| Multi-machine LAN benchmark | TODO | Requires Bridged networking and hostfile |
| Final PDF report | TODO | Export `report/REPORT_POLISHED_DRAFT.md` |

The measured local run is valid for correctness, MPI communication, plotting,
load balance, and speedup evidence. It is shorter than the professor's suggested
2-3 minute runtime target, so the final report marks larger-N and LAN runs as
TODO until real artifacts exist.

## Repository Map

| Path | Purpose |
|---|---|
| `mpot/benchmarks/` | Course benchmark implementation: 2D problem, task runner, metrics, plots, report helpers |
| `scripts/run_serial.py` | Serial baseline runner |
| `scripts/run_mpi.py` | OpenMPI runner |
| `scripts/check_local_env.py` | Local environment check |
| `scripts/doctor_local_setup.py` | Smoke-test doctor for local or Ubuntu VM setup |
| `configs/local_smoke.json` | Small smoke-test configuration |
| `configs/local_benchmark.json` | Main local benchmark configuration |
| `configs/variant_*.json` | 2D visualization variants with harder obstacle layouts |
| `docs/` | Algorithm notes, teammate VM guide, LAN cluster runbook, ownership plan |
| `report/REPORT_POLISHED_DRAFT.md` | Main English report draft for submission |
| `report/REPORT_CHECKLIST.md` | Rubric-to-code/artifact checklist |
| `report/figures/` | Real plots and GIFs generated from experiment artifacts |
| `report/tables/` | Generated CSV/Markdown result tables |

## Local Quickstart

Use this on macOS or Ubuntu after cloning the repo. The default workflow is
CPU-only and does not require CUDA.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip wheel setuptools
.venv/bin/python -m pip install -r requirements-local.txt
.venv/bin/python -m pip install -e . --no-deps
```

Check the environment:

```bash
.venv/bin/python scripts/check_local_env.py
.venv/bin/python scripts/doctor_local_setup.py \
  --label local_single \
  --run-mpi-probe \
  --mpi-processes 2
```

Run a tiny serial/MPI smoke test:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/local_smoke.json \
  --total-tasks 4

mpirun -np 2 --bind-to none \
  .venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --total-tasks 4
```

## Ubuntu VM Quickstart

For teammate machines, use Ubuntu ARM64 VM on Apple Silicon and keep these
conventions:

- username: `mpot`
- repo path: `/home/mpot/mpot`
- Python: `/home/mpot/mpot/.venv/bin/python`
- network: Shared Network for single-VM smoke; Bridged only when testing LAN

Detailed setup is in:

- `docs/teammate_vm_quickstart.md`
- `docs/ubuntu_vm_cluster_setup.md`
- `docs/local_to_ubuntu_phase_plan.md`

Each teammate should pass local smoke first:

```bash
cd /home/mpot/mpot
.venv/bin/python scripts/check_local_env.py
.venv/bin/python scripts/doctor_local_setup.py \
  --label ubuntu_vm_single \
  --run-mpi-probe \
  --mpi-processes 2
.venv/bin/python scripts/run_serial.py \
  --config configs/local_smoke.json \
  --total-tasks 4
mpirun -np 2 --bind-to none \
  .venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --total-tasks 4
```

Only after every VM passes local smoke should the group switch UTM networking to
Bridged, verify `ping`/`ssh`, generate a hostfile, and run multi-machine MPI.

## Reports and Results

Main report:

- `report/REPORT_POLISHED_DRAFT.md`

Supporting report files:

- `report/REPORT_DRAFT.md`
- `report/REPORT_CHECKLIST.md`
- `docs/mpot_algorithm_overview.md`
- `docs/mpot_parallel_algorithm_spec.md`
- `docs/team_ownership.md`

Generated evidence:

- `report/FINAL_AUDIT_final_macbook_air_2d.md`
- `report/RESULTS_SUMMARY_final_macbook_air_2d.md`
- `report/tables/RESULTS_TABLES_final_macbook_air_2d.md`
- `report/figures/runtime_vs_input_size_final_macbook_air_2d.png`
- `report/figures/speedup_final_macbook_air_2d.png`
- `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png`
- `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N824-P4_best_path.png`

## Project Design in One Paragraph

The program uses task-level exploratory parallelism. Each task is one complete
2D MPOT-inspired planning attempt with one deterministic seed. MPI rank 0
creates the task list, broadcasts shared configuration, scatters task subsets
by 1D cyclic mapping `task i -> rank i mod P`, gathers compact results and
timing records, then selects the best trajectory by minimum cost. The local
MPOT optimizer is not split across ranks because its inner trajectory,
waypoint, probe, and Sinkhorn updates are tightly coupled and too fine-grained
for LAN-level MPI communication.

## Original MPOT Credit

This course project is based on and acknowledges:

An T. Le, Georgia Chalvatzaki, Armin Biess, and Jan Peters. "Accelerating Motion
Planning via Optimal Transport." NeurIPS 2023.

Original project page and source:

- Paper: https://arxiv.org/abs/2309.15970
- Original repository: https://github.com/anindex/mpot

The original MPOT code remains credited under the repository license. Course
benchmark files were added around the original implementation to support the
parallel-programming assignment.
