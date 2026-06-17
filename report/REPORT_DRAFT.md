# Distributed MPOT on CPU with MPI

**Living report draft for the Parallel Computing / Parallel Programming course**

**Current draft date:** 2026-06-17  
**Submission deadline:** 2026-06-24  
**Status:** Design and implementation draft with measured local-final artifacts
and owner Ubuntu single-VM smoke artifacts. Multi-machine Ubuntu/LAN results are
still a later deployment phase.

> Important rule for this report: do not invent numerical results. The Results
> section is intentionally left without numbers until the experiment scripts
> produce real output files.

## 1. Introduction

Motion planning asks a robot to move from a start state to a goal state while
avoiding obstacles and keeping the trajectory smooth. In robotics, this problem
is difficult because the search space can contain many local minima. A direct
optimization method may find one feasible route, but it can also get stuck when
obstacles block the simple straight-line path.

The original MPOT project, "Accelerating Motion Planning via Optimal
Transport", uses many trajectory samples and optimal-transport-inspired updates
to search for good motion plans in parallel. The original repository is designed
for PyTorch and GPU acceleration. Our course project adapts this idea to a
parallel programming setting that can run on CPU with MPI.

The goal of this project is not to reproduce the full GPU performance of the
paper. Instead, the goal is to build a clear distributed benchmark that shows
how the MPOT-style search can be parallelized across multiple processes. During
the first stage, the program runs locally on one machine with multiple MPI
processes. Later, the same design can be moved to physical group machines.

The project focuses on:

- A simple 2D point-robot motion planning problem.
- A serial baseline that runs the same set of planning tasks sequentially.
- An MPI version that distributes independent trajectory-search tasks across
  ranks.
- Local CSV, JSON, and PNG artifacts for correctness and performance analysis.
- A report workflow that is updated as the code evolves.

The standalone algorithm explanation is maintained in
`docs/mpot_algorithm_overview.md`. That document describes the original MPOT
optimizer, the simplified 2D course variant, and the OpenMPI task-parallel
extension used by this project.
The line-by-line mathematical pseudocode is maintained in
`docs/mpot_parallel_algorithm_spec.md` and should be used when polishing the
final Algorithm and Parallelization sections.

## 2. Problem Definition

### 2.1 Robot and State Space

The benchmark uses a point robot in a 2D workspace. A robot state contains:

```text
state = [x, y, vx, vy]
```

where `(x, y)` is position and `(vx, vy)` is velocity. A trajectory is a sequence
of states:

```text
trajectory = [state_0, state_1, ..., state_T]
```

The first state is fixed to the start state, and the final state is encouraged
or fixed to reach the goal state depending on the selected configuration.

### 2.2 Obstacles

The local benchmark uses simple circular obstacles. A waypoint is in collision
if its 2D position lies inside any obstacle. The obstacle model is intentionally
simple so every team member can explain it and so the CPU benchmark can run
without heavyweight robotics visualization dependencies.

Implementation link:

- `mpot/benchmarks/problem_2d.py` defines the 2D workspace, obstacle list,
  start state, goal state, and cost functions.

### 2.3 Cost Function

Each trajectory receives a scalar cost. Lower cost means a better trajectory.
The planned cost contains:

- Obstacle cost: penalizes waypoints inside or near obstacles.
- Smoothness cost: penalizes large changes in position or velocity.
- Goal cost: penalizes ending far from the target.
- Boundary cost: penalizes leaving the workspace.

The exact weights will be stored in JSON config files so the same experiment can
be repeated by every group member.

## 3. Serial Algorithm

The serial algorithm is the correctness reference. It receives the full list of
task IDs and deterministic random seeds, then runs one local planning task after
another. Each task samples or initializes candidate trajectories, runs the local
MPOT-style optimizer, evaluates the resulting trajectories, and returns the best
candidate from that task.

Implementation links:

- `scripts/run_serial.py` runs the serial baseline.
- `mpot/benchmarks/local_runner.py` runs one local MPOT-style task.
- `mpot/benchmarks/reduction.py` chooses the deterministic global best
  result.

### 3.1 Serial Pseudocode

```text
Input:
    config
    total_tasks
    seed_list
    start_state
    goal_state
    obstacles

best_result = None
all_task_results = []

for task_id in 0 .. total_tasks - 1:
    seed = seed_list[task_id]

    task_result = run_local_planning_task(
        task_id,
        seed,
        config,
        start_state,
        goal_state,
        obstacles
    )

    all_task_results.append(task_result)

    if task_result is better than best_result:
        best_result = task_result

write summary.json
write task_results.csv
write best_trajectory.npy
write local figures

return best_result
```

### 3.2 Deterministic Best Selection

The serial and MPI versions must use the same rule to choose the best result.
The planned tie-break rule is:

```text
min(best_cost, then task_id, then seed)
```

This makes correctness checking easier because the serial and parallel versions
should choose the same task when they evaluate the same deterministic seed list.

## 4. Parallelization Strategy

### 4.1 Parallel Level

The project uses **task-level parallelism**.

Each planning task is an independent search over a random seed or candidate
trajectory batch. Different tasks can be computed at the same time because a
task does not need intermediate results from other tasks.

### 4.2 Decomposition Technique

The decomposition technique is **exploratory decomposition**.

Each process explores a different part of the solution space by running a
different subset of random seeds. This matches the MPOT philosophy: more samples
can discover more and better motion-planning modes.

The detailed reason for placing the MPI layer outside the MPOT Sinkhorn loop is
documented in `docs/mpot_parallel_algorithm_spec.md`. In short, each seeded
MPOT task is independent, while particle, waypoint, and Sinkhorn-level splits
would introduce fine-grained synchronization that is a poor fit for LAN/VM MPI.

### 4.3 Mapping Technique

Tasks are assigned to MPI ranks with 1D cyclic mapping:

```text
task i -> rank (i mod P)
```

where `P` is the number of MPI processes.

This mapping is simple, deterministic, and useful for load balancing. If some
seeds are more expensive than others, cyclic mapping spreads expensive and cheap
tasks more evenly than one large contiguous block per rank.

Implementation link:

- `mpot/benchmarks/mpi_scheduler.py` implements cyclic task assignment.
- MPI runs write `task_assignment.csv`, where each row records
  `task_id -> rank` under the rule `task_id mod process_count`.

### 4.4 Communication Strategy and Topology

The MPI program follows an SPMD style. All ranks run the same Python program,
but their behavior depends on the rank ID.

The logical topology is a star with rank 0 as coordinator:

```text
          rank 1
            |
rank 2 -- rank 0 -- rank 3
            |
          rank ...
```

The planned communication primitives are blocking collectives:

- `bcast`: rank 0 broadcasts the experiment config.
- `scatter`: rank 0 distributes the task chunks.
- `gather`: every rank sends local results and timing data back to rank 0.

Blocking communication is acceptable for the first implementation because each
rank performs relatively large local computation before returning a compact
result.

Implementation link:

- `scripts/run_mpi.py` starts the MPI run.
- `mpot/benchmarks/mpi_runner.py` implements the rank behavior and timing.
- MPI runs write `comm_events.csv`, where each row records one blocking
  collective communication event such as `bcast_config`, `scatter_tasks`, or
  `gather_results`.

### 4.5 Load Balancing Considerations

Load balancing is evaluated by measuring per-rank compute time and communication
time. The report checks whether two ranks have idle-time difference greater than
25%. If the imbalance is too high, the task granularity should be adjusted.

The first implementation uses cyclic mapping as the default balancing technique.
If the result is still imbalanced, the next options are:

- Increase the number of smaller tasks.
- Reduce task size per seed.
- Use dynamic work scheduling in a later version.

### 4.6 Design Rationale Against Course Rubric

This project chooses a coarse-grained MPI design because the original MPOT
optimizer already contains many independent exploration attempts. The MPI layer
does not replace MPOT. It runs multiple complete MPOT attempts at the same time
and then reduces all attempts to the best trajectory.

| Rubric item | Project choice | Reasoning |
|---|---|---|
| Parallel level | Task-level parallelism | One task is one complete MPOT run with one deterministic seed. Different seeds do not depend on each other, so tasks can run concurrently without changing the mathematical result. |
| Decomposition technique | Exploratory decomposition | MPOT searches through many trajectory particles and random initializations to avoid local minima. Distributing seeds across ranks naturally lets different processes explore different motion-planning modes around obstacles. |
| Mapping technique | 1D cyclic mapping, `task i -> rank i mod P` | Runtime can vary by seed. Cyclic mapping spreads early/late and easy/hard seeds across ranks better than a single contiguous block per rank, while remaining deterministic and easy to audit. |
| Communication strategy | SPMD with rank 0 coordinator | All ranks run the same program. Rank 0 owns setup, artifact writing, and final reduction, which avoids duplicate files and keeps the distributed workflow easy to explain. |
| Topology | Logical star centered at rank 0 | The only required global data movement is setup and result collection. A tree/ring topology would add complexity without benefit for this small-result workload. |
| Blocking vs non-blocking | Blocking `bcast`, `scatter`, and `gather` | Communication happens at a few coarse boundaries. Each rank then spends most of its time computing local MPOT tasks, so blocking collectives are simple, measurable, and sufficient. |
| Load balancing | Per-rank timing plus 25% idle threshold | The report measures compute, communication, and idle time per rank. If idle fraction exceeds 25%, the task granularity should be changed before using the result. |
| Why not split Sinkhorn | Keep Sinkhorn local inside each task | Sinkhorn iterations have repeated dependencies on the current transport state. Splitting them across LAN/VM MPI ranks would create fine-grained synchronization and high communication overhead. |

The detailed dependency analysis is in `docs/mpot_parallel_algorithm_spec.md`.
In short:

```text
Y_i = LOCAL_MPOT_TASK(config, seed_i)
Y^* = min_by_cost(Y_0, Y_1, ..., Y_{N-1})
```

Since `Y_i` does not read `Y_j` for `i != j`, the task evaluations are
independent. MPI only changes the execution schedule; the final reduction rule
remains the same as the serial baseline.

## 5. Parallel Algorithm

### 5.1 Parallel Pseudocode

```text
Input:
    config
    total_tasks
    seed_list

MPI_Init()

rank = MPI_Comm_rank()
size = MPI_Comm_size()

if rank == 0:
    load config
    create deterministic seed_list
    create task chunks using cyclic mapping
else:
    config = None
    task_chunks = None

comm_timer_start()
config = bcast(config, root=0)
local_tasks = scatter(task_chunks, root=0)
comm_time += comm_timer_stop()

compute_timer_start()
local_results = []
local_best = None

for task in local_tasks:
    task_result = run_local_planning_task(task)
    local_results.append(task_result)

    if task_result is better than local_best:
        local_best = task_result

compute_time = compute_timer_stop()

rank_record = {
    rank,
    hostname,
    num_tasks,
    compute_time,
    communication_time,
    local_best
}

comm_timer_start()
all_rank_records = gather(rank_record, root=0)
all_task_results = gather(local_results, root=0)
comm_time += comm_timer_stop()

if rank == 0:
    global_best = deterministic_reduce(all local_best values)
    write summary.json
    write rank_timings.csv
    write task_results.csv
    write best_trajectory.npy
    write figures

MPI_Finalize()
```

### 5.2 Timing Measurement

The benchmark measures:

- Total wall-clock time.
- Compute time per rank.
- Communication time per rank.
- Per-task runtime.

The final plots will show runtime both with and without communication time.

Implementation links:

- `mpot/benchmarks/metrics.py` calculates speedup, efficiency, and load
  imbalance.
- `mpot/benchmarks/artifacts.py` writes CSV/JSON outputs.
- `mpot/benchmarks/plots.py` generates report figures.

## 6. Implementation Plan and Code Organization

This section must be kept synchronized with the codebase. When a planned file is
implemented or renamed, update this section and the report checklist.

### 6.1 Implemented Code Modules

```text
configs/local_smoke.json
configs/local_benchmark.json
configs/variant_open_2d.json
configs/variant_narrow_passage_2d.json
configs/variant_cluttered_2d.json
configs/variant_dense_sampling_2d.json
requirements-local.txt
scripts/check_local_env.py
scripts/doctor_local_setup.py
scripts/generate_ownership_report.py
scripts/generate_defense_guide.py
scripts/capture_environment.py
scripts/check_report_sync.py
scripts/animate_trajectory.py
scripts/animate_algorithm_trace.py
scripts/estimate_benchmark_budget.py
scripts/analyze_granularity.py
scripts/analyze_communication.py
scripts/plan_benchmark.py
scripts/run_serial.py
scripts/run_mpi.py
scripts/compare_serial_mpi.py
scripts/plot_results.py
scripts/run_sweep.py
scripts/run_local_pipeline.py
scripts/estimate_input_size.py
scripts/validate_solution_quality.py
scripts/validate_results.py
scripts/export_report_bundle.py
scripts/export_result_tables.py
scripts/export_results_summary.py
scripts/export_submission_package.py
scripts/index_results.py
scripts/audit_final_results.py
mpot/benchmarks/problem_2d.py
mpot/benchmarks/animation.py
mpot/benchmarks/local_runner.py
mpot/benchmarks/benchmark_budget.py
mpot/benchmarks/benchmark_plan.py
mpot/benchmarks/communication.py
mpot/benchmarks/defense_pack.py
mpot/benchmarks/correctness.py
mpot/benchmarks/doctor.py
mpot/benchmarks/environment.py
mpot/benchmarks/experiment_index.py
mpot/benchmarks/final_audit.py
mpot/benchmarks/granularity.py
mpot/benchmarks/mpi_scheduler.py
mpot/benchmarks/mpi_runner.py
mpot/benchmarks/reduction.py
mpot/benchmarks/metrics.py
mpot/benchmarks/ownership.py
mpot/benchmarks/artifacts.py
mpot/benchmarks/plots.py
mpot/benchmarks/validation.py
mpot/benchmarks/pipeline.py
mpot/benchmarks/report_sync.py
mpot/benchmarks/report_bundle.py
mpot/benchmarks/result_tables.py
mpot/benchmarks/results_summary.py
mpot/benchmarks/solution_quality.py
mpot/benchmarks/submission_package.py
mpot/wandb_logger.py
tests/test_benchmark_core.py
```

The current implementation includes the benchmark core, serial and MPI
entrypoints, artifact writers, plotting helpers, optional W&B support, and
dependency-light tests for scheduler, reduction, metrics, config logic,
solution-quality validation, and report artifact bundling/indexing.

### 6.2 Local-First Workflow

The first working target is local execution on one machine:

```bash
python scripts/doctor_local_setup.py --label teammate --run-mpi-probe --mpi-processes 2
python scripts/run_serial.py --config configs/local_smoke.json
mpirun -np 4 python scripts/run_mpi.py --config configs/local_smoke.json
python scripts/compare_serial_mpi.py --serial results/<serial_run> --mpi results/<mpi_run>
```

The setup doctor writes:

```text
results/setup_doctor_<label>.json
report/SETUP_DOCTOR_<label>.md
```

Each teammate should run it once after installing the Python environment and
MPI. It checks Python version, required packages, repo import, `mpirun`, and an
optional tiny `mpi4py` runtime probe.

The benchmark target is:

```bash
python scripts/run_serial.py --config configs/local_benchmark.json
mpirun -np 1 python scripts/run_mpi.py --config configs/local_benchmark.json
mpirun -np 2 python scripts/run_mpi.py --config configs/local_benchmark.json
mpirun -np 4 python scripts/run_mpi.py --config configs/local_benchmark.json
python scripts/plot_results.py --results results/
```

For repeated experiments, `scripts/run_sweep.py` can run several input sizes and
process counts with one command. For input-size selection, `scripts/estimate_input_size.py`
runs a small serial sample and estimates a starting value of `N` for the target
runtime.

Long final sweeps can be resumed safely. `scripts/run_sweep.py` supports
`--skip-existing`, and `scripts/run_local_pipeline.py` exposes this as
`--skip-existing-runs`. A run is considered complete only when its
`summary.json` exists and the recorded run metadata matches the expected
run id, mode, input size `N`, process count, experiment name, and config hash.
The reusable-run check is implemented in `mpot/benchmarks/run_reuse.py` so the
sweep runner and benchmark budget use the same rule.

The recommended local workflow is `scripts/run_local_pipeline.py`. It can run
the sweep and then execute the post-processing chain automatically:

```text
environment capture -> ownership report -> member defense guide -> benchmark budget -> sweep -> plots -> correctness comparison -> trajectory animation -> result tables -> solution quality validation -> granularity analysis -> communication analysis -> artifact bundle -> experiment index -> report sync check -> results summary -> validation -> final audit -> submission package
```

Example dry-run command:

```bash
python scripts/run_local_pipeline.py \
  --config configs/local_smoke.json \
  --input-sizes 2 \
  --process-counts 1,2 \
  --label mini_sweep \
  --final-n 2 \
  --load-balance-n 2 \
  --final-processes 2 \
  --skip-sweep \
  --dry-run
```

For the final benchmark, remove `--skip-sweep` and use
`configs/local_benchmark.json` with the selected input sizes and process counts.
If a previous final sweep was interrupted, keep the same label and add
`--skip-existing-runs` so completed runs are reused while missing runs are
executed.

The helper `scripts/plan_benchmark.py` creates a report-visible benchmark plan
from measured sample timing. It writes:

```text
report/BENCHMARK_PLAN.json
report/BENCHMARK_PLAN.md
```

The current plan follows the rubric convention that `N` is used for
runtime/load-balance and `2*N` is used for speedup. It is still a plan, not a
result; final numerical claims must come from the pipeline artifacts generated
after the plan is executed.

The helper `scripts/estimate_benchmark_budget.py` reads the generated plan and
estimates the total local sweep time before the expensive run starts. It writes:

```text
report/BENCHMARK_BUDGET_<label>.json
report/BENCHMARK_BUDGET_<label>.md
```

This file protects the local-first workflow from two mistakes: choosing an
input size so small that the run looks like a toy, or choosing an input size so
large that a MacBook Air must run for too long. When `--reuse-existing` is
used, it also reports estimated remaining time after subtracting existing runs
whose `summary.json` metadata and config hash match the planned run. It is not
measured Results data. Measured runtime and speedup must still come from the
CSV/JSON artifacts produced by real runs.

For team code ownership, `scripts/generate_ownership_report.py` counts the
compact primary defense file set assigned to each member. The report requires
at least 250 meaningful lines per member, not 1000 lines per person. It uses
700 primary-defense lines as the recommended maximum so no member has to
memorize an oversized code chunk.
It writes:

```text
report/TEAM_OWNERSHIP_REPORT.json
report/TEAM_OWNERSHIP_REPORT.md
```

This artifact supports the course requirement that all four members participate
while keeping each member's defense scope readable.

For oral defense preparation, `scripts/generate_defense_guide.py` reads the same
primary defense file split and extracts top-level Python functions/classes or
JSON config keys for each member. It also records compact demo commands and
practice questions. It writes:

```text
report/MEMBER_DEFENSE_GUIDE.json
report/MEMBER_DEFENSE_GUIDE.md
```

This file is a study guide. It should help the team explain the code, but it is
not counted as experiment data.

Before copying any result claim into the report, `scripts/validate_results.py`
checks that the serial run, MPI run, correctness report, required figures, and
optional artifact bundle manifest exist.

For living-report consistency, `scripts/check_report_sync.py` scans the report
and project docs for concrete path references and writes:

```text
report/REPORT_SYNC_<label>.json
report/REPORT_SYNC_<label>.md
```

This prevents stale file names from staying in the report after code or
artifact paths change. Template paths such as `results/<run_id>/summary.json`
are ignored.

After validation, `scripts/export_report_bundle.py` can copy the real artifacts
into `report/artifacts/<bundle_name>/`, copy selected PNG figures into
`report/figures/`, and write `report/ARTIFACT_MANIFEST.md`. This manifest is
the bridge between code and report: each result claim should be traceable to a
listed CSV, JSON, or PNG file.

For demo visualization, `scripts/animate_trajectory.py` reads one completed
run and creates an optional short final-path GIF:

```text
report/figures/trajectory_<label>.gif
```

For algorithm visualization, `scripts/animate_algorithm_trace.py` reads the
best task metadata from a completed run, reruns only that seed with MPOT history
enabled, and creates:

```text
report/figures/algorithm_trace_<label>.gif
report/ALGORITHM_TRACE_<label>.json
```

This second GIF shows multiple sampled trajectory particles across optimizer
iterations, which is closer to the Monte Carlo / MPOT behavior shown in demo
animations. The GIFs help slides and live explanation, but they are not a
replacement for the required CSV/JSON/PNG report artifacts.

For report tables, `scripts/export_result_tables.py` reads existing
`summary.json` and `rank_timings.csv` artifacts and writes:

```text
report/tables/runtime_table_<label>.csv
report/tables/speedup_table_<label>.csv
report/tables/load_balance_table_<label>.csv
report/tables/RESULTS_TABLES_<label>.md
report/tables/tables_manifest_<label>.json
```

These tables are generated from real artifacts only and should be regenerated
after each final benchmark sweep.

For report-writing support, `scripts/export_results_summary.py` reads the real
correctness, solution-quality, communication, granularity, table, and figure
artifacts and writes:

```text
report/RESULTS_SUMMARY_<label>.json
report/RESULTS_SUMMARY_<label>.md
```

This summary is generated from existing artifacts only. It helps the team copy
numbers into the final Results section without manually editing CSV values or
inventing missing results.

For planning-solution correctness, `scripts/validate_solution_quality.py`
checks the saved best trajectory from one serial or MPI run against the 2D
problem definition. It verifies that the best trajectory exists, has the
expected length, contains finite values, starts at the configured start state,
reaches the goal, avoids hard obstacle collisions, and stays inside workspace
bounds. It writes:

```text
results/solution-quality-<label>-N<N>-P<P>.json
report/SOLUTION_QUALITY_<label>.md
```

This is separate from the serial-vs-MPI comparison. The comparison proves that
parallel execution returns the same deterministic task/cost as the serial
baseline, while the solution-quality check proves that the saved trajectory is
a valid solution for the planning problem.

For the granularity requirement, `scripts/analyze_granularity.py` reads an MPI
run's `rank_timings.csv` and writes:

```text
results/granularity-<label>-N<N>-P<P>.json
report/GRANULARITY_<label>.md
```

The analysis checks the 25% idle-time threshold and writes a short
recommendation about whether task granularity should be adjusted.

For the mapping requirement, each MPI run writes:

```text
results/<mpi_run>/task_assignment.csv
```

This CSV is generated from the same cyclic assignment used by the scheduler.
It is the easiest artifact to show when explaining processor/process
assignment during the demo.

For the communication requirement, each MPI run writes:

```text
results/<mpi_run>/comm_events.csv
```

This CSV lists the blocking collective operations used by the implementation:
`bcast`, `scatter`, and `gather`, along with per-rank durations and payload
counts.

The report-ready communication analysis is generated by
`scripts/analyze_communication.py` and writes:

```text
results/communication-<label>-N<N>-P<P>.json
report/COMMUNICATION_<label>.md
```

For report navigation, `scripts/index_results.py` scans existing result and
report artifacts and writes:

```text
report/EXPERIMENT_INDEX_<label>.json
report/EXPERIMENT_INDEX_<label>.md
```

The index is not a benchmark result. It is a traceability helper that lists
available serial runs, MPI runs, correctness reports, validation reports,
environment captures, granularity analyses, communication analyses,
solution-quality checks, table manifests, and artifact bundles.

Finally, `scripts/audit_final_results.py` checks whether one benchmark label is
ready for final-report use. It verifies the rubric-level shape of the
experiment: all expected input sizes are present, `2*N` has the requested MPI
process counts including `P=1`, correctness passed, solution quality passed,
communication analysis passed, granularity is under the 25% threshold, report
figures/tables/manifests exist, team ownership is balanced, and the pipeline
has a member defense guide, and the pipeline validation passed. It writes:

```text
report/FINAL_AUDIT_<label>.json
report/FINAL_AUDIT_<label>.md
```

After the final audit is available, `scripts/export_submission_package.py`
copies the living report draft, checklist, ownership/defense guide, audit,
experiment index, tables, and figures into `submission/<label>/`. The package
manifest is only a file checklist; it does not generate result data or create
new benchmark claims. It writes:

```text
submission/<label>/SUBMISSION_MANIFEST.json
submission/<label>/SUBMISSION_MANIFEST.md
```

This audit does not create or modify measurements. It only decides whether the
existing artifacts are sufficient to support report claims.

Example mini-sweep table command:

```bash
python scripts/export_result_tables.py \
  --results results \
  --output report/tables \
  --label mini_sweep \
  --input-size 2
```

Example experiment index command:

```bash
python scripts/index_results.py \
  --results results \
  --report-dir report \
  --label mini_sweep \
  --output report/EXPERIMENT_INDEX_mini_sweep.json \
  --markdown report/EXPERIMENT_INDEX_mini_sweep.md
```

Example results-summary command:

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
  --figure report/figures/runtime_vs_input_size_mini_sweep.png \
  --figure report/figures/speedup_mini_sweep.png \
  --figure report/figures/mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png \
  --figure report/figures/trajectory_mini_sweep.gif \
  --output report/RESULTS_SUMMARY_mini_sweep.json \
  --markdown report/RESULTS_SUMMARY_mini_sweep.md
```

Example final-audit command:

```bash
python scripts/audit_final_results.py \
  --results results \
  --report-dir report \
  --label mini_sweep \
  --input-sizes 2 \
  --process-counts 1,2 \
  --n 2 \
  --speedup-n 2 \
  --final-processes 2 \
  --bundle-name mini_sweep \
  --validation results/validation-mini_sweep-N2-P2.json \
  --communication results/communication-mini_sweep-N2-P2.json \
  --solution-quality results/solution-quality-mini_sweep-N2-P2.json \
  --ownership report/TEAM_OWNERSHIP_REPORT.json \
  --defense-guide report/MEMBER_DEFENSE_GUIDE.json \
  --output report/FINAL_AUDIT_mini_sweep.json \
  --markdown report/FINAL_AUDIT_mini_sweep.md
```

Example smoke bundle command:

```bash
python scripts/export_report_bundle.py \
  --bundle-name mini_sweep \
  --clean \
  --serial-run results/serial-mini_sweep-N2 \
  --mpi-run results/mpi-mini_sweep-N2-P2 \
  --correctness results/compare-mini_sweep-N2-P2/correctness_report.json \
  --label mini_sweep \
  --input-size 2
```

The bundle can then be validated together with the other smoke outputs:

```bash
python scripts/validate_results.py \
  --serial-run results/serial-mini_sweep-N2 \
  --mpi-run results/mpi-mini_sweep-N2-P2 \
  --correctness results/compare-mini_sweep-N2-P2/correctness_report.json \
  --figures report/figures \
  --required-figure runtime_vs_input_size_mini_sweep.png \
  --required-figure speedup_mini_sweep.png \
  --required-figure mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png \
  --bundle-manifest report/artifacts/mini_sweep/manifest.json \
  --tables-manifest report/tables/tables_manifest_mini_sweep.json \
  --results-summary report/RESULTS_SUMMARY_mini_sweep.json \
  --environment results/environment-mini_sweep.json \
  --granularity results/granularity-mini_sweep-N2-P2.json \
  --communication results/communication-mini_sweep-N2-P2.json \
  --solution-quality results/solution-quality-mini_sweep-N2-P2.json \
  --ownership report/TEAM_OWNERSHIP_REPORT.json \
  --defense-guide report/MEMBER_DEFENSE_GUIDE.json \
  --experiment-index report/EXPERIMENT_INDEX_mini_sweep.json \
  --benchmark-plan report/BENCHMARK_PLAN.json \
  --sweep-label mini_sweep \
  --results results \
  --output results/validation-mini_sweep-N2-P2.json
```

### 6.3 Optional W&B Logging

W&B is optional and must never be required for grading. The program must save
local CSV, JSON, NumPy, and PNG artifacts whether W&B works or not.

The optional command will be:

```bash
mpirun -np 4 python scripts/run_mpi.py --config configs/local_benchmark.json --use-wandb
```

If W&B is not installed, the user is not logged in, or the network is
unavailable, the logger should print a warning and continue in no-op mode.

## 7. Experimental Setup

The initial experiments run on one local machine with multiple MPI processes.
The later cluster experiments will run on physical group machines after the
local implementation is stable.

Planned local setup:

- Python 3.9 or newer.
- PyTorch 2.0 or newer.
- OpenMPI.
- mpi4py.
- CPU-only execution.
- `torch.set_num_threads(1)` inside each MPI rank to avoid CPU oversubscription.

The current machine setup is captured by:

```text
results/environment-mini_sweep.json
report/ENVIRONMENT_mini_sweep.md
```

These files are generated by `scripts/capture_environment.py` and should be
regenerated on every final local/Ubuntu machine used for reported experiments.

The first Ubuntu ARM64 VM deployment smoke has also been completed on the
owner's VM `mpot-a`. This smoke is not the final LAN benchmark; it proves that
the code, Python environment, OpenMPI, and artifact pipeline run inside Ubuntu
before the group connects multiple machines. The copied evidence is:

```text
results/ubuntu_vm_single/setup_doctor_ubuntu_vm_single.json
report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md
results/ubuntu_vm_single/compare-ubuntu-single-N4-P2/correctness_report.json
results/ubuntu_vm_single/compare-ubuntu-single-N8-P4/correctness_report.json
```

The owner VM status is:

```text
doctor: ready: True
N=4, P=2: serial/MPI comparison passed, best cost difference 0.0
N=8, P=4: serial/MPI comparison passed, best cost difference 0.0
```

The input size `N` is the total number of independent planning tasks. The final
report must choose an `N` such that the full run takes approximately 2-3 minutes
on the target experiment hardware.

The helper command for estimating an initial `N` is:

```bash
python scripts/estimate_input_size.py --config configs/local_benchmark.json --sample-tasks 8 --target-seconds 150
```

The estimate is not final report data. It only gives a starting point; the final
`N` must be measured again with the selected process count.

The current planning artifacts are:

```text
report/BENCHMARK_PLAN.json
report/BENCHMARK_PLAN.md
report/BENCHMARK_BUDGET_<label>.json
report/BENCHMARK_BUDGET_<label>.md
```

The generated plan proposes:

```text
N = 412 for runtime/load-balance
2*N = 824 for speedup
process counts = 1, 2, 4
```

These values are based on `results/estimate-local-benchmark-N4/summary.json`,
which measured about `0.4385 s/task` on the current MacBook Air class local
machine. The plan is deliberately conservative: large enough to avoid toy
sub-second runs, but small enough to keep the full local sweep under one hour.
The values must still be validated by running the generated pipeline command
before they are used as final Results.

### 7.4 Qualitative 2D Problem Variants

The quantitative runtime, load-balance, and speedup experiments should stay on
`configs/local_benchmark.json`. That keeps the required plots comparable across
different values of `N` and different process counts.

For qualitative report figures and demo GIFs, the project also includes four
2D-only problem variants:

- `configs/variant_open_2d.json`: easy visual baseline with one obstacle.
- `configs/variant_narrow_passage_2d.json`: medium-hard environment with a
  narrow passage.
- `configs/variant_cluttered_2d.json`: harder environment with six obstacles.
- `configs/variant_dense_sampling_2d.json`: dense visual demo with ten
  obstacles, more particles, and more probe samples per direction.

These variants are JSON problem definitions only. They do not change the serial
or MPI algorithm. The same task-level exploratory decomposition still applies:
each random seed creates one independent planning task, and MPI distributes
those tasks with the same 1D cyclic mapping.

Commands and suggested report placement are documented in
`docs/problem_variants_2d.md`. Variant figures and GIFs should be used in the
Problem Definition, demo, or Discussion sections; they should not replace the
main quantitative speedup/load-balance results.

Generated qualitative local artifacts:

- `results/mpi-variant_narrow-N12-P4/summary.json`
- `report/figures/trajectory_variant_narrow.gif`
- `report/figures/algorithm_trace_variant_narrow.gif`
- `results/mpi-variant_cluttered-N16-P4/summary.json`
- `report/figures/trajectory_variant_cluttered.gif`
- `report/figures/algorithm_trace_variant_cluttered.gif`
- `results/mpi-variant_dense-N12-P4/summary.json`
- `report/figures/algorithm_trace_variant_dense.gif`

These artifacts are useful for visualization and presentation. They are not used
as the main runtime/speedup experiment, because the quantitative tables should
stay on one consistent benchmark config.

The generated final-local pipeline command is:

```bash
python scripts/estimate_benchmark_budget.py \
  --plan report/BENCHMARK_PLAN.json \
  --output report/BENCHMARK_BUDGET_final_macbook_air_2d.json \
  --markdown report/BENCHMARK_BUDGET_final_macbook_air_2d.md \
  --label final_macbook_air_2d \
  --run-label final_macbook_air_2d \
  --results-dir results \
  --reuse-existing

python scripts/run_local_pipeline.py \
  --config configs/local_benchmark.json \
  --input-sizes 208,412,824 \
  --process-counts 1,2,4 \
  --label final_macbook_air_2d \
  --final-n 824 \
  --load-balance-n 412 \
  --final-processes 4 \
  --benchmark-plan report/BENCHMARK_PLAN.json \
  --skip-existing-runs
```

## 8. Results

This section contains only numbers produced by real runs. The current
local-final label is `final_macbook_air_2d`.

Important caveat: this local run produced valid serial/MPI/plot artifacts, but
the measured runtimes are shorter than the professor's suggested 2-3 minute
target. If the final report must strictly demonstrate a 2-3 minute run, repeat
the same pipeline later with a larger `N` or on the Ubuntu/LAN setup. Do not
claim that the current `N=824` local run satisfies the 2-3 minute target.

The Ubuntu single-VM smoke confirms deployment readiness only. It should not be
reported as the final multi-machine LAN speedup experiment, because teammate VM
hostfile execution has not been measured yet.

### 8.1 Correctness Check

Status: final local correctness check passed.

```text
serial_run = results/serial-final_macbook_air_2d-N824
mpi_run = results/mpi-final_macbook_air_2d-N824-P4
same_best_task = yes
same_best_seed = yes
best_cost_difference = 0.0
compared_tasks = 824
```

The solution-quality check also passed:

```text
run_id = mpi-final_macbook_air_2d-N824-P4
best_task_id = 184
best_seed = 20260801
best_cost = 0.00520871
goal_error = 3.371747884011707e-08
hard_collision_fraction = 0.0
```

Source artifacts:

- `results/compare-final_macbook_air_2d-N824-P4/correctness_report.json`
- `results/compare-final_macbook_air_2d-N824-P4/task_comparison.csv`
- `results/solution-quality-final_macbook_air_2d-N824-P4.json`
- `report/SOLUTION_QUALITY_final_macbook_air_2d.md`

### 8.2 Runtime vs Input Size N

Status: final local runtime table and figure generated from real artifacts.

At final local process count `P=4`:

| N | runtime with communication (s) | runtime without communication (s) |
|---:|---:|---:|
| 208 | 2.86270 | 2.85861 |
| 412 | 4.91507 | 4.87856 |
| 824 | 9.31508 | 9.27704 |

Source artifacts:

- `report/tables/runtime_table_final_macbook_air_2d.csv`
- `report/figures/runtime_vs_input_size_final_macbook_air_2d.png`
- `report/RESULTS_SUMMARY_final_macbook_air_2d.md`

### 8.3 Granularity and Load Balancing

Status: final local granularity check passed for `N=412`, `P=4`.

```text
idle_fraction = 0.00705028
threshold = 0.25
balanced_under_threshold = yes
communication_fraction_of_slowest_rank = 0.0110326
```

Each of the four ranks received 103 tasks under the 1D cyclic mapping.

Source artifacts:

- `results/granularity-final_macbook_air_2d-N412-P4.json`
- `report/GRANULARITY_final_macbook_air_2d.md`
- `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png`

### 8.4 Speedup

Status: final local speedup table and figure generated from real artifacts.

For `N=824`:

| processes | runtime with communication (s) | speedup with communication | efficiency with communication |
|---:|---:|---:|---:|
| 1 | 27.9028 | 1.00000 | 1.00000 |
| 2 | 14.7543 | 1.89117 | 0.945584 |
| 4 | 9.31508 | 2.99545 | 0.748862 |

Source artifacts:

- `report/tables/speedup_table_final_macbook_air_2d.csv`
- `report/figures/speedup_final_macbook_air_2d.png`
- `results/communication-final_macbook_air_2d-N824-P4.json`

The communication analysis observed blocking `bcast`, `scatter`, and `gather`
collectives under an SPMD program with a rank 0 coordinator and logical star
topology.

## 9. Discussion

The local-final experiment supports the main design decision: task-level
parallelism is a suitable MPI layer for this MPOT-inspired benchmark. For
`N=824`, increasing the process count from `P=1` to `P=4` reduced the measured
runtime with communication from `27.9028 s` to `9.31508 s`. The corresponding
speedup was `2.99545x`, with efficiency `0.748862`. This is not perfect linear
speedup, but it is strong enough to show useful parallel execution on one local
machine.

Correctness was verified against the serial baseline. The serial and MPI runs
used the same config, task ids, deterministic seeds, and local MPOT task
implementation. The comparison for `N=824`, `P=4` checked all `824` tasks and
found the same best task, same best seed, and best-cost difference `0.0`.
Therefore, MPI scheduling changed when tasks ran, but it did not change the
computed planning result.

Communication overhead was small relative to computation. The final MPI run
used blocking `bcast`, `scatter`, and `gather` collectives under an SPMD program
with rank 0 as coordinator. This matches the intended logical star topology.
The design works because communication happens at coarse boundaries: setup,
task distribution, result collection, timing collection, and communication-log
collection. There is no MPI communication inside the MPOT Sinkhorn loop.

The load-balance result is also good for the selected local setting. For the
granularity check at `N=412`, `P=4`, every rank received `103` tasks under 1D
cyclic mapping. The measured idle fraction was `0.00705028`, much lower than
the required `0.25` threshold. This means the current task granularity is
acceptable for the local run. If a future run has worse imbalance, the first
adjustment should be to increase `N` so each rank receives more tasks, while
keeping cyclic mapping.

The main limitation is input size. The local run is correct and report-ready as
evidence that the code, MPI design, artifacts, plots, and validation pipeline
work. However, it is shorter than the professor's suggested 2-3 minute target.
The report should not claim that `N=824` satisfies that target. To strictly
meet the timing requirement, the same pipeline should be repeated later with a
larger `N` or on the Ubuntu/LAN setup after the group machines are available.

Compared with the original MPOT paper, this project intentionally focuses on a
smaller CPU-only 2D benchmark. The purpose is not to reproduce GPU performance.
The purpose is to show a correct and measurable parallel-programming design:
decompose independent MPOT planning attempts, map them to MPI ranks, collect
timing and communication data, and reduce all results to the best trajectory.

## 10. Conclusion

This project implements a local-first distributed MPOT benchmark for a 2D
point-robot motion-planning problem. The program uses task-level parallelism:
each MPI rank receives a subset of independent MPOT tasks, runs complete local
trajectory optimizations, and returns compact results to rank 0. The
decomposition is exploratory, the mapping is 1D cyclic, and communication uses
blocking `bcast`, `scatter`, and `gather` collectives in a logical star
topology.

The measured local-final results show that the MPI version is correct relative
to the serial baseline and that parallel execution improves runtime. For
`N=824`, the `P=4` MPI run achieved about `2.995x` speedup with communication
included. The load-balance experiment satisfied the 25% threshold with idle
fraction about `0.00705`, and the saved best trajectory reached the goal without
hard obstacle collision.

The remaining work before final submission is report polishing and, if strict
2-3 minute timing is required, one larger-N or Ubuntu/LAN benchmark run. The
current local artifacts should be used honestly: they demonstrate a working
parallel algorithm and validation pipeline, but they should not be described as
the final 2-3 minute experiment unless a later run produces that timing.

## References

- An T. Le, Georgia Chalvatzaki, Armin Biess, and Jan Peters. "Accelerating
  Motion Planning via Optimal Transport." NeurIPS 2023.
- MPOT repository README and source code in this project.
