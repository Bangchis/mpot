# Optional W&B Logging Runbook

W&B is a convenience layer for comparing experiments. It is not required for
grading. The local `results/` and `report/` artifacts are still the source of
truth.

## Naming Convention

Use the same naming structure for every machine:

```text
project: distributed-mpot-course
group:   <experiment_label>
name:    <run_id>
tags:    mode:<serial|mpi>, N:<tasks>, P:<processes>, backend:<backend>, mapping:<mapping>, config:<hash>
```

Examples:

```text
group: final_macbook_air_2d
name:  mpi-final_macbook_air_2d-N824-P4

group: ubuntu_vm_single
name:  mpi-ubuntu-single-N8-P4

group: lan_cluster
name:  mpi-lan-cluster-N824-P12
```

This makes W&B easy to filter:

- Compare speedup: filter by `group=final_macbook_air_2d`, then compare `P`.
- Compare problem size: filter by `group=<label>`, then compare `N`.
- Compare serial vs MPI: filter by `group=<label>`, then compare `mode`.
- Compare machines: add a custom tag such as `macbook-air`, `ubuntu-vm`, or `lan`.

## What Gets Logged

For each run directory, the logger uploads:

| W&B area | Content |
|---|---|
| Config | run id, experiment name, config hash, `N`, `P`, device, optimizer settings |
| Scalars | best cost, runtime with/without communication, communication overhead, load-balance metrics |
| Media panels | `best_path.png`, `cost_by_task.png`, `rank_time_breakdown.png` if present |
| Tables | `task_results.csv`, `rank_timings.csv`, `comm_events.csv`, `task_assignment.csv` |
| Artifact bundle | `summary.json`, `config.json`, CSV files, `best_trajectory.npy`, PNG/GIF files |
| Local manifest | `results/<run_id>/wandb_manifest.json` |

Large tables are capped by `--wandb-max-table-rows` so W&B remains usable.

## Log A New MPI Run

```bash
mpirun -np 4 --bind-to none \
  .venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --run-id mpi-wandb-smoke-N4-P4 \
  --experiment-name wandb_smoke_N4 \
  --total-tasks 4 \
  --use-wandb \
  --wandb-project distributed-mpot-course \
  --wandb-group wandb_smoke \
  --wandb-tag local \
  --wandb-tag smoke
```

Only rank 0 creates the W&B run. Worker ranks never initialize W&B.

## Log A New Sweep

`scripts/run_sweep.py` forwards unknown arguments to each serial/MPI runner, so
W&B flags can be placed at the end:

```bash
.venv/bin/python scripts/run_sweep.py \
  --config configs/local_smoke.json \
  --input-sizes 4,8 \
  --process-counts 1,2,4 \
  --label wandb_sweep \
  --output-dir results \
  --use-wandb \
  --wandb-project distributed-mpot-course \
  --wandb-group wandb_sweep \
  --wandb-tag local-sweep
```

## Upload An Existing Run

Use this when an experiment has already finished and you do not want to rerun
it:

```bash
.venv/bin/python scripts/log_run_to_wandb.py \
  --run-dir results/mpi-final_macbook_air_2d-N824-P4 \
  --use-wandb \
  --wandb-project distributed-mpot-course \
  --wandb-group final_macbook_air_2d \
  --wandb-tag final-local
```

Extra report figures or GIFs can be attached:

```bash
.venv/bin/python scripts/log_run_to_wandb.py \
  --run-dir results/mpi-final_macbook_air_2d-N824-P4 \
  --extra-path report/figures/trajectory_final_macbook_air_2d.gif \
  --extra-path report/figures/algorithm_trace_final_macbook_air_2d.gif \
  --use-wandb \
  --wandb-project distributed-mpot-course \
  --wandb-group final_macbook_air_2d
```

## Upload A Whole Experiment Label

Use this when a label already has many run directories, for example serial and
MPI runs for `N=208,412,824` and `P=1,2,4`. This is the recommended workflow
for final-result dashboards because it keeps every run comparable under one
W&B group.

First inspect the matches:

```bash
.venv/bin/python scripts/log_experiment_to_wandb.py \
  --label final_macbook_air_2d \
  --results-dir results \
  --dry-run
```

Then upload the matched runs and create one report-level index run containing
summary figures:

```bash
.venv/bin/python scripts/log_experiment_to_wandb.py \
  --label final_macbook_air_2d \
  --results-dir results \
  --report-path report/figures/runtime_vs_input_size_final_macbook_air_2d.png \
  --report-path report/figures/speedup_final_macbook_air_2d.png \
  --report-path report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png \
  --report-path report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N824-P4_best_path.png \
  --use-wandb \
  --wandb-project distributed-mpot-course \
  --wandb-group final_macbook_air_2d \
  --wandb-tag final-local
```

The batch uploader writes:

| File | Meaning |
|---|---|
| `results/<run_id>/wandb_manifest.json` | Per-run W&B logging manifest |
| `report/WANDB_EXPERIMENT_<label>.json` | Machine-readable batch upload manifest |
| `report/WANDB_EXPERIMENT_<label>.md` | Human-readable list of matched/logged runs |

Useful filters:

```bash
# Only upload MPI runs from the label.
.venv/bin/python scripts/log_experiment_to_wandb.py \
  --label final_macbook_air_2d \
  --include-mode mpi \
  --dry-run

# Upload one run only for a W&B smoke test.
.venv/bin/python scripts/log_experiment_to_wandb.py \
  --label final_macbook_air_2d \
  --limit 1 \
  --use-wandb \
  --wandb-mode offline
```

## Offline Mode

For Ubuntu VM or weak Wi-Fi, log offline first:

```bash
WANDB_MODE=offline mpirun -np 4 --bind-to none \
  .venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --total-tasks 4 \
  --use-wandb \
  --wandb-mode offline
```

After the network is stable:

```bash
wandb sync wandb/offline-run-*
```

## Rule For The Report

Do not copy numbers from W&B by hand unless they match local `summary.json` or
generated CSV tables. W&B is for browsing and comparison; the report should
still cite local artifacts generated by the benchmark pipeline.
