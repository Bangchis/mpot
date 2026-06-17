# 2D Problem Variants

The final speedup/load-balance benchmark should stay on one main config so the
results are easy to compare. The extra variants below are for report discussion,
figures, GIF demos, and showing that the same parallel planner handles multiple
2D environments.

## Variant Summary

| Config | Role | Obstacles | Difficulty | Recommended use |
|---|---|---:|---|---|
| `configs/local_smoke.json` | Fast sanity check | 2 | very small | quick local pipeline/debug |
| `configs/variant_open_2d.json` | Easy visual baseline | 1 | easy | show straight-ish path with one obstacle |
| `configs/local_benchmark.json` | Main final benchmark | 3 | medium | runtime, speedup, load balance, correctness |
| `configs/variant_narrow_passage_2d.json` | Harder qualitative demo | 4 | medium-hard | show path squeezed through a passage |
| `configs/variant_cluttered_2d.json` | Hardest qualitative demo | 6 | hard | show many-obstacle planning behavior |
| `configs/variant_dense_sampling_2d.json` | Dense GIF demo | 10 | hard visual demo | show many obstacles with more particles and probe samples |

## How To Use These Variants

Do not mix every variant into the main speedup experiment. For the course
report, use:

- `configs/local_benchmark.json` for the required quantitative plots.
- One or two variant figures/GIFs for qualitative discussion.
- The same MPI code path for every variant, so the topic remains parallel
  programming rather than changing the problem.

## Quick Variant Commands

Run one serial visualization for each variant:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/variant_open_2d.json \
  --run-id variant-open-serial-N8 \
  --experiment-name variant_open_N8 \
  --total-tasks 8

.venv/bin/python scripts/run_serial.py \
  --config configs/variant_narrow_passage_2d.json \
  --run-id variant-narrow-serial-N12 \
  --experiment-name variant_narrow_N12 \
  --total-tasks 12

.venv/bin/python scripts/run_serial.py \
  --config configs/variant_cluttered_2d.json \
  --run-id variant-cluttered-serial-N16 \
  --experiment-name variant_cluttered_N16 \
  --total-tasks 16

.venv/bin/python scripts/run_serial.py \
  --config configs/variant_dense_sampling_2d.json \
  --run-id variant-dense-serial-N20 \
  --experiment-name variant_dense_N20 \
  --total-tasks 20
```

Run a small MPI smoke for a variant:

```bash
.venv/bin/python scripts/run_sweep.py \
  --config configs/variant_narrow_passage_2d.json \
  --input-sizes 12 \
  --process-counts 1,2,4 \
  --label variant_narrow \
  --output-dir results \
  --skip-existing
```

Generate qualitative figures/GIFs after a run:

```bash
.venv/bin/python scripts/animate_trajectory.py \
  --run-dir results/mpi-variant_narrow-N12-P4 \
  --output report/figures/trajectory_variant_narrow.gif

.venv/bin/python scripts/animate_algorithm_trace.py \
  --run-dir results/mpi-variant_narrow-N12-P4 \
  --output report/figures/algorithm_trace_variant_narrow.gif \
  --trace-output report/ALGORITHM_TRACE_variant_narrow.json
```

For the clearest algorithm-trace demo, use the dense variant:

```bash
.venv/bin/python scripts/run_sweep.py \
  --config configs/variant_dense_sampling_2d.json \
  --input-sizes 12 \
  --process-counts 4 \
  --label variant_dense \
  --output-dir results \
  --skip-serial \
  --skip-existing

.venv/bin/python scripts/animate_algorithm_trace.py \
  --run-dir results/mpi-variant_dense-N12-P4 \
  --output report/figures/algorithm_trace_variant_dense.gif \
  --trace-output report/ALGORITHM_TRACE_variant_dense.json \
  --fps 3 \
  --max-particles 24
```

If you shrink a variant for a very fast smoke test, keep
`max_outer_iters > min_outer_iters`. The config validator rejects invalid
iteration windows before the planner starts so teammates get a clear error
instead of a low-level tensor index failure.

## Report Placement

Suggested report use:

- Introduction / Problem Definition: mention all environments are 2D point
  robot problems with circular obstacles.
- Implementation: say variants are JSON-only problem definitions, not different
  algorithms.
- Results: keep runtime/speedup tables on `configs/local_benchmark.json`.
- Discussion: include one figure/GIF from `variant_narrow_passage_2d`,
  `variant_cluttered_2d`, or `variant_dense_sampling_2d` to discuss how
  exploratory seed-level parallelism helps search multiple path candidates.

## Why This Helps The Parallel Programming Story

The variants make it visible that the parallel unit is not an obstacle or a
waypoint. The parallel unit is still a complete independent planning task
created from one random seed. More obstacles make some seeds find poor paths and
some seeds find better paths, which makes exploratory decomposition easier to
explain.
