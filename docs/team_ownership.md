# Team Ownership Plan

This document splits the local-first MPOT/MPI project into four understandable
primary defense parts. The purpose is not only to divide code lines, but also
to make sure every member can read, explain, and demo their assigned part if
the instructor asks.

Use `Member A`, `Member B`, `Member C`, and `Member D` as placeholders until the
group replaces them with real names.

Before studying individual files, every member should read
`docs/mpot_algorithm_overview.md`. It explains the original MPOT algorithm, the
2D course variant, and the OpenMPI task-parallel extension in one place. Docs
help with defense, but they do not count as code lines.

## Ownership Summary

| Member | Primary area | Primary defense files | Main responsibility |
|---|---|---|---|
| Member A | 2D planning problem | `mpot/benchmarks/problem_2d.py`, `mpot/benchmarks/config.py`, `configs/local_smoke.json`, `configs/local_benchmark.json`, `configs/variant_open_2d.json`, `configs/variant_narrow_passage_2d.json`, `configs/variant_cluttered_2d.json` | Define robot state, workspace, obstacles, cost terms, and experiment config variants. |
| Member B | Local optimizer, serial baseline, correctness | `mpot/benchmarks/local_runner.py`, `mpot/benchmarks/reduction.py`, `mpot/benchmarks/correctness.py`, `scripts/run_serial.py`, `scripts/compare_serial_mpi.py` | Run one MPOT-style task, run all tasks sequentially, and compare serial vs MPI outputs. |
| Member C | MPI parallelization and communication trace | `mpot/benchmarks/mpi_scheduler.py`, `mpot/benchmarks/mpi_runner.py`, `mpot/benchmarks/communication.py`, `scripts/run_mpi.py`, `scripts/analyze_communication.py` | Assign tasks to ranks, communicate, gather timings/results, and explain blocking collectives. |
| Member D | Metrics, plots, result tables, load-balance evidence | `mpot/benchmarks/metrics.py`, `mpot/benchmarks/plots.py`, `mpot/benchmarks/result_tables.py`, `scripts/analyze_granularity.py`, `scripts/plot_results.py` | Generate figures/tables and explain runtime, speedup, efficiency, and load-balance evidence. |

The target is at least 1000 lines of meaningful new project code for the group,
not 1000 lines per person. Each member should own at least 250 meaningful lines
in their primary defense set, but the primary set should stay readable. The
generated ownership report uses 700 lines as the recommended maximum per
member. Slides, docs, report text, and experiment outputs do not count as code.

Avoid giving one member a very large support module to memorize. If a support
tool grows too much, keep it in the shared list below and let the member defend
only the small primary files that match their topic.

Generate the current ownership report with:

```bash
python scripts/generate_ownership_report.py
python scripts/generate_defense_guide.py
```

This writes:

```text
report/TEAM_OWNERSHIP_REPORT.json
report/TEAM_OWNERSHIP_REPORT.md
report/MEMBER_DEFENSE_GUIDE.json
report/MEMBER_DEFENSE_GUIDE.md
```

## Shared Support Files

Some workflow modules support the whole project but are not assigned as one
member's primary defense load. Members should know what these files do at a
high level, but they do not need to memorize every line:

```text
mpot/benchmarks/artifacts.py
mpot/benchmarks/animation.py
mpot/benchmarks/benchmark_budget.py
mpot/benchmarks/benchmark_plan.py
mpot/benchmarks/doctor.py
mpot/benchmarks/environment.py
mpot/benchmarks/experiment_index.py
mpot/benchmarks/final_audit.py
mpot/benchmarks/granularity.py
mpot/benchmarks/pipeline.py
mpot/benchmarks/report_sync.py
mpot/benchmarks/report_bundle.py
mpot/benchmarks/run_reuse.py
mpot/benchmarks/results_summary.py
mpot/benchmarks/solution_quality.py
mpot/benchmarks/submission_package.py
mpot/benchmarks/validation.py
mpot/wandb_logger.py
configs/variant_dense_sampling_2d.json
scripts/audit_final_results.py
scripts/animate_trajectory.py
scripts/animate_algorithm_trace.py
scripts/capture_environment.py
scripts/check_report_sync.py
scripts/doctor_local_setup.py
scripts/estimate_benchmark_budget.py
scripts/estimate_input_size.py
scripts/export_report_bundle.py
scripts/export_result_tables.py
scripts/export_results_summary.py
scripts/export_submission_package.py
scripts/generate_defense_guide.py
scripts/generate_ownership_report.py
scripts/index_results.py
scripts/log_run_to_wandb.py
scripts/plan_benchmark.py
scripts/run_local_pipeline.py
scripts/run_sweep.py
scripts/validate_results.py
scripts/validate_solution_quality.py
tests/test_benchmark_core.py
```

## Member A: 2D Problem and Cost Model

### What this member owns

Member A owns the mathematical definition of the benchmark problem.

Expected topics:

- The point robot state `[x, y, vx, vy]`.
- The trajectory as a list of states over time.
- The start state and goal state.
- Circular obstacles.
- Collision, smoothness, goal, and boundary costs.

### Code to understand

Implemented files:

```text
mpot/benchmarks/problem_2d.py
mpot/benchmarks/config.py
configs/local_smoke.json
configs/local_benchmark.json
configs/variant_open_2d.json
configs/variant_narrow_passage_2d.json
configs/variant_cluttered_2d.json
tests/test_benchmark_core.py
```

### Demo command

After implementation, this member should be able to run a small problem example
or explain the generated best path plot:

```bash
python scripts/run_serial.py --config configs/local_smoke.json
```

### Questions this member should answer

1. What is the robot state in the benchmark?
2. How is an obstacle represented?
3. Why do we use a simple 2D point robot instead of the full Panda robot?
4. What terms are included in the trajectory cost?
5. How does the cost encourage a feasible and smooth path?
6. Why do we include open, narrow-passage, cluttered, and dense 2D variants?

## Member B: Local MPOT Task and Serial Baseline

### What this member owns

Member B owns the local computation performed for one planning task and the
serial reference program.

Expected topics:

- A task is one seed or one candidate trajectory batch.
- The serial program loops over all tasks.
- The local runner calls the MPOT-style optimizer.
- The serial result is the correctness reference for the MPI version.
- The best result uses deterministic tie-breaking.

### Code to understand

Implemented files:

```text
mpot/benchmarks/local_runner.py
mpot/benchmarks/reduction.py
mpot/benchmarks/correctness.py
scripts/run_serial.py
scripts/compare_serial_mpi.py
tests/test_benchmark_core.py
```

### Demo command

```bash
python scripts/run_serial.py --config configs/local_smoke.json
```

### Questions this member should answer

1. What is the difference between a task and a trajectory?
2. Why do we need a serial baseline?
3. How does the code choose the best trajectory?
4. What is deterministic tie-breaking?
5. Why should serial and MPI use the same seed list?
6. What does `task_comparison.csv` prove in the correctness check?

## Member C: MPI Parallelization

### What this member owns

Member C owns process-level parallelism.

Expected topics:

- MPI ranks and MPI world size.
- Task-level parallelism.
- Exploratory decomposition over seeds/tasks.
- 1D cyclic mapping: `task i -> rank i mod P`.
- Blocking `bcast`, `scatter`, and `gather`.
- Rank 0 coordinator and logical star topology.
- Compute time vs communication time.
- `comm_events.csv` as the visible communication artifact for `bcast`,
  `scatter`, and `gather`.
- `task_assignment.csv` as the visible mapping artifact for the report/demo.

### Code to understand

Implemented files:

```text
mpot/benchmarks/mpi_scheduler.py
mpot/benchmarks/mpi_runner.py
mpot/benchmarks/communication.py
scripts/run_mpi.py
scripts/analyze_communication.py
tests/test_benchmark_core.py
```

### Demo command

```bash
mpirun -np 4 python scripts/run_mpi.py --config configs/local_smoke.json
```

### Questions this member should answer

1. What level of parallelism does the project use?
2. Why is the decomposition called exploratory decomposition?
3. How does cyclic mapping assign tasks to ranks?
4. What communication operations are used?
5. Why is rank 0 called the coordinator?
6. What does `task_assignment.csv` prove about the mapping?
7. What does `comm_events.csv` prove about the communication strategy?

## Member D: Results, Plots, Report Sync, and Optional W&B

### What this member owns

Member D owns experiment outputs and report synchronization.

Expected topics:

- Runtime table and speedup table formats.
- Per-rank timing and load-balance rows.
- Runtime with and without communication time.
- Load balance and 25% imbalance check.
- Speedup and efficiency.
- Report figures.
- Benchmark budget estimates before launching long final sweeps.
- Report-ready Results summary generated from real artifacts.
- Resume/budget support that reuses only matching `summary.json` metadata and
  config hashes.

### Code and docs to understand

Implemented files:

```text
mpot/benchmarks/metrics.py
mpot/benchmarks/plots.py
mpot/benchmarks/result_tables.py
scripts/analyze_granularity.py
scripts/estimate_benchmark_budget.py
scripts/export_results_summary.py
scripts/plot_results.py
tests/test_benchmark_core.py
```

### Demo command

Generate the balanced ownership evidence:

```bash
python scripts/generate_ownership_report.py
python scripts/generate_defense_guide.py
```

Analyze granularity/load balance:

```bash
python scripts/analyze_granularity.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output results/granularity-mini_sweep-N2-P2.json \
  --markdown report/GRANULARITY_mini_sweep.md \
  --label mini_sweep
```

Generate report-ready tables:

```bash
python scripts/export_result_tables.py \
  --results results \
  --output report/tables \
  --label mini_sweep \
  --input-size 2
```

Generate a report-ready Results summary from real artifacts:

```bash
python scripts/export_results_summary.py \
  --label mini_sweep \
  --serial-run results/serial-mini_sweep-N2 \
  --mpi-run results/mpi-mini_sweep-N2-P2 \
  --correctness results/compare-mini_sweep-N2-P2/correctness_report.json \
  --tables-manifest report/tables/tables_manifest_mini_sweep.json \
  --granularity results/granularity-mini_sweep-N2-P2.json \
  --communication results/communication-mini_sweep-N2-P2.json \
  --solution-quality results/solution-quality-mini_sweep-N2-P2.json \
  --benchmark-budget report/BENCHMARK_BUDGET_mini_sweep.json \
  --output report/RESULTS_SUMMARY_mini_sweep.json \
  --markdown report/RESULTS_SUMMARY_mini_sweep.md
```

Estimate the planned final sweep time before running it:

```bash
python scripts/estimate_benchmark_budget.py \
  --plan report/BENCHMARK_PLAN.json \
  --output report/BENCHMARK_BUDGET_mini_sweep.json \
  --markdown report/BENCHMARK_BUDGET_mini_sweep.md \
  --label mini_sweep \
  --run-label mini_sweep \
  --results-dir results \
  --reuse-existing
```

Regenerate report figures:

```bash
python scripts/plot_results.py \
  --results results \
  --output report/figures \
  --label mini_sweep \
  --input-size 2
```

Generate an optional short GIF for slides/demo:

```bash
python scripts/animate_trajectory.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output report/figures/trajectory_mini_sweep.gif

python scripts/animate_algorithm_trace.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output report/figures/algorithm_trace_mini_sweep.gif \
  --trace-output report/ALGORITHM_TRACE_mini_sweep.json
```

### Questions this member should answer

1. How is speedup calculated?
2. How do we check load imbalance?
3. What does the 25% idle-time threshold mean in `GRANULARITY_<label>.md`?
4. What tables does `export_result_tables.py` generate for the report?
5. Which figures does `plot_results.py` generate?
6. What is the optional trajectory GIF used for?
7. What does the algorithm trace GIF show that the trajectory replay does not?
8. Why must the Results section not contain invented numbers?
9. Why does `TEAM_OWNERSHIP_REPORT.md` keep the primary defense set readable?
10. How does `MEMBER_DEFENSE_GUIDE.md` help each member study only their own primary files?
11. Why is `BENCHMARK_BUDGET_<label>.md` not counted as measured Results data?
12. Why should `RESULTS_SUMMARY_<label>.md` be regenerated instead of edited by hand?
13. Why does resume mode require matching metadata and config hash before reusing a run?

## Group Rules

- Every member must run their demo command at least once before the final demo.
- Every member must read the code and docs for their assigned part.
- If code paths change, update this document and `report/REPORT_CHECKLIST.md`.
- If one member's primary defense set becomes too long, rebalance files instead
  of making that member memorize everything.
- If a member edits a module, they should add or update a short explanation in
  the corresponding doc/report section.
- The final report should use real experiment outputs only.
