# MPOT Serial and Distributed Algorithm Specification

## Purpose

This file is the compact algorithm document for the Parallel Computing /
Parallel Programming report. It describes:

- the normal/local MPOT algorithm used inside one planning task;
- the serial baseline over many tasks;
- the OpenMPI multi-process and multi-machine version;
- how computation, communication, reduction, timing, and correctness are
  handled.

The explanation is mathematical and algorithmic. It is not implementation code.

## Notation

| Symbol | Meaning |
|---|---|
| `N` | number of independent planning tasks, also the input size for experiments |
| `P` | number of MPI processes/ranks |
| `r` | MPI rank id, `r in {0, ..., P-1}` |
| `i` | task id |
| `s_i` | deterministic seed for task `i` |
| `K` | number of MPOT particles per local task |
| `T` | trajectory length |
| `d` | robot state dimension; here `d = 4` for `[x, y, vx, vy]` |
| `L` | maximum MPOT outer iterations |
| `H` | maximum Sinkhorn inner iterations |
| `X` | one trajectory, `X in R^{T x d}` |
| `X_k` | trajectory particle `k` |
| `J(X)` | full trajectory cost |
| `C` | local probe cost matrix used by the Sinkhorn step |
| `G` | entropic optimal transport plan |
| `D_r` | task subset assigned to rank `r` |
| `Y_i` | result of task `i`: best cost, best trajectory, seed, rank, timing |

The 2D project cost is:

```text
J(X) =
  w_obs * collision_penalty(X)
+ w_bound * boundary_penalty(X)
+ w_smooth * smoothness_penalty(X)
+ w_goal * goal_error(X)
+ w_vel * velocity_penalty(X)
```

The final trajectory of one task is:

```text
X_i^* = argmin_{k in {1,...,K}} J(X_{i,k})
```

The final distributed answer is:

```text
Y^* = argmin_{i in {0,...,N-1}} cost(Y_i)
```

Ties are broken deterministically by smaller task id and then smaller seed.

## Parallel Algorithm Input Parameters

The distributed algorithm is configured by a small set of mathematical and
runtime inputs. The key point is that MPI does not change the local MPOT
optimization rule; MPI only distributes independent MPOT tasks and then reduces
their results.

| Parameter | Meaning | How it is used in parallel execution |
|---|---|---|
| `config` | complete experiment configuration | read by rank 0, then broadcast to all ranks |
| `problem_config` | workspace, start, goal, obstacles, trajectory length `T`, time step `dt`, cost weights | defines the shared 2D motion-planning problem and objective `J(X)` |
| `optimizer_config` | particles `K`, outer iterations `L`, Sinkhorn iterations `H`, probe radius, convergence tolerance | controls the local MPOT task executed independently on each rank |
| `N` | number of independent tasks | main input size for runtime, granularity, and speedup experiments |
| `base_seed` and `s_i` | deterministic seed schedule | creates reproducible exploratory tasks; normally `s_i = base_seed + i` |
| `P` | number of MPI ranks/processes | supplied by OpenMPI at launch time |
| `r` | current MPI rank id | supplied by the MPI communicator to each process |
| `mapping_rule` | assignment formula `owner(i) = i mod P` | implements 1D cyclic mapping from tasks to ranks |
| `D_r` | local task subset for rank `r` | scattered by rank 0; each rank runs only its own subset |
| `timing_fields` | compute time, communication time, idle time, total time | recorded for report figures, not used to change the trajectory |
| `reduction_key` | `(best_cost, task_id, seed)` | gives deterministic selection of the best global result |

Data movement follows the same parameter structure:

```text
rank 0:
  read config
  build task list D = [(0, s_0), ..., (N-1, s_{N-1})]
  compute cyclic subsets D_0, ..., D_{P-1}

all ranks:
  receive config through blocking bcast
  receive own D_r through blocking scatter
  compute local results Y_i for tasks in D_r
  send local results, rank timing, and communication events through blocking gather

rank 0:
  flatten gathered results
  select Y^* by the reduction key
  write result artifacts for correctness, timing, and visualization
```

## Algorithm 1: Local MPOT Task

This is the normal MPOT-style algorithm used for one seed. It corresponds to one
complete planning attempt. In the repository, the MPOT core is in
`mpot/planner.py`, while the project-specific 2D task wrapper is in
`mpot/benchmarks/local_runner.py`.

```text
Algorithm 1: LOCAL_MPOT_TASK(config, task_id, seed)

Input:
  config: 2D planning and optimizer parameters
  task_id: integer task id
  seed: deterministic random seed

Output:
  Y_i = (task_id, seed, best_cost, best_trajectory, opt_iters, runtime)

01  Start local timer.
02  Fix the random generator with seed.
03  Build the 2D planning problem:
      start state x_start, goal state x_goal, obstacles, workspace, cost J.
04  Construct the MPOT objective for local probe costs and full trajectory cost.
05  Construct the Sinkhorn solver with maximum H inner iterations.
06  Sample K initial trajectory particles from the Gaussian-process prior:
      {X_1^0, X_2^0, ..., X_K^0}.
07  Fix the first waypoint of every particle to x_start.
08  Fix the last waypoint of every particle to x_goal when fixed-goal mode is on.
09  Set outer iteration ell = 0.
10  While ell < L and the displacement has not converged:
11      Normalize position and velocity coordinates.
12      For each particle k and each waypoint t:
13          Generate local polytope probe candidates around X_k^ell[t].
14          Evaluate local objective values for the probe candidates.
15      Build the local cost matrix C from all probe costs.
16      Solve the entropic optimal transport problem:
            G^ell = argmin_G <C, G> + epsilon * sum(G * (log G - 1))
            subject to G has the required source and target marginals.
17      Apply barycentric projection:
            X^{ell+1} = BarycentricProjection(G^ell, probe_candidates).
18      Denormalize the updated states.
19      Re-apply fixed start and fixed goal constraints.
20      Record displacement ||X^{ell+1} - X^ell||^2.
21      ell = ell + 1.
22  For every final particle X_k, compute full trajectory cost J(X_k).
23  Select k^* = argmin_k J(X_k).
24  Stop local timer.
25  Return Y_i with best_trajectory = X_{k^*}, best_cost = J(X_{k^*}).
```

Main local computation cost is approximately:

```text
T_task = O(L * (K * T * probe_cost + H * sinkhorn_cost))
```

For the course project, this computation is local to one process. MPI does not
communicate inside lines 10-21.

## Algorithm 2: Serial MPOT Baseline

The serial baseline uses the same local task algorithm, but runs all tasks one
after another on a single process. It is the correctness reference for MPI.

```text
Algorithm 2: SERIAL_MPOT(config, N)

Input:
  config: experiment configuration
  N: number of independent tasks

Output:
  Y^*: best result among all N tasks
  results: list of all task results

01  Build task list D = [(0, s_0), (1, s_1), ..., (N-1, s_{N-1})].
02  Initialize results = empty list.
03  Start serial wall-clock timer.
04  For each task (i, s_i) in D:
05      Y_i = LOCAL_MPOT_TASK(config, i, s_i).
06      Append Y_i to results.
07  Y^* = argmin_{Y_i in results} (Y_i.best_cost, Y_i.task_id, Y_i.seed).
08  Stop serial wall-clock timer.
09  Write serial CSV/JSON/PNG artifacts.
10  Return Y^* and results.
```

The serial wall time is approximately:

```text
T_1 ~= sum_{i=0}^{N-1} T_task(i)
```

## Algorithm 3: Distributed MPOT with OpenMPI

This is the parallel version for one machine or multiple Ubuntu VMs connected
through LAN/Wi-Fi. OpenMPI starts `P` ranks. The algorithm is SPMD: every rank
runs the same program, but rank 0 acts as the coordinator.

The decomposition is exploratory task decomposition. The mapping is 1D cyclic:

```text
owner(i) = i mod P
D_r = {(i, s_i) | owner(i) = r}
```

```text
Algorithm 3: DISTRIBUTED_MPOT_OPENMPI(config, N, P)

Input:
  config on rank 0
  N: number of independent planning tasks
  P: number of MPI ranks launched by OpenMPI

Output on rank 0:
  Y^*: global best result
  all_results: all task results
  timing and communication artifacts

01  OpenMPI launches ranks r = 0, 1, ..., P-1.
02  Every rank reads its rank id r, process count P, and hostname.
03  Every rank starts a wall-clock timer.

04  If r == 0:
05      Build task list D = [(0, s_0), ..., (N-1, s_{N-1})].
06      For each rank q in {0, ..., P-1}:
07          D_q = [(i, s_i) in D such that i mod P = q].
08      Validate that every task appears in exactly one D_q.
09      Prepare assignment metadata for the report.
10  Else:
11      D = null, D_q = null, assignment = null.

12  Blocking BCAST from rank 0 to all ranks:
13      send config.
14  Blocking BCAST from rank 0 to all ranks:
15      send run id.
16  Blocking BCAST from rank 0 to all ranks:
17      send assignment metadata.
18  Blocking SCATTER from rank 0:
19      rank r receives its local task subset D_r.

20  Every rank starts compute timer.
21  local_results_r = empty list.
22  For each task (i, s_i) in D_r:
23      Y_i = LOCAL_MPOT_TASK(config, i, s_i).
24      Set Y_i.rank = r.
25      Append Y_i to local_results_r.
26  local_best_r = argmin_{Y_i in local_results_r}
        (Y_i.best_cost, Y_i.task_id, Y_i.seed).
27  Every rank stops compute timer.

28  Every rank records:
        compute_time_r, communication_time_r, total_time_r, hostname, |D_r|.
29  Blocking GATHER to rank 0:
        send local_results_r.
30  Blocking GATHER to rank 0:
        send rank timing record.
31  Blocking GATHER to rank 0:
        send communication event records.

32  If r != 0:
33      Return no final summary.

34  If r == 0:
35      Flatten all gathered local result lists into all_results.
36      Compute global best:
            Y^* = argmin_{Y_i in all_results}
                  (Y_i.best_cost, Y_i.task_id, Y_i.seed).
37      Compute parallel wall time:
            T_P_with_comm = max_r(total_time_r).
38      Compute compute-only time:
            T_P_no_comm = max_r(compute_time_r).
39      Compute load-balance statistics from all compute_time_r.
40      Write summary.json, task_results.csv, rank_timings.csv,
        comm_events.csv, task_assignment.csv, and plots.
41      Return Y^* and summary.
```

## Why Parallelization Is Added At The Task Level

### Dependency Analysis

The serial many-task algorithm can be viewed as:

```text
Y_i = F(config, s_i), for i = 0, 1, ..., N-1
Y^* = REDUCE_MIN(Y_0, Y_1, ..., Y_{N-1})
```

where `F` is one complete local MPOT run and `s_i` is the seed for task `i`.
For two different tasks `i` and `j`:

```text
Y_i does not read Y_j
Y_j does not read Y_i
F(config, s_i) and F(config, s_j) share only read-only config data
```

Therefore, all `F(config, s_i)` calls are independent. This creates an
embarrassingly parallel stage followed by one deterministic reduction. The
parallel insertion point is between serial Algorithm 2 line 01 and line 04:

```text
Serial:
  build all tasks -> run task 0 -> run task 1 -> ... -> run task N-1 -> reduce

Parallel:
  build all tasks -> distribute task subsets -> each rank runs its subset -> gather -> reduce
```

This is why the project counts as task-level parallelism. The computation done
by rank `r` is:

```text
Work_r = {F(config, s_i) | i mod P = r}
```

and rank 0 computes:

```text
Y^* = min_by_cost( union_r WorkResults_r )
```

### Why This Matches MPOT

The original MPOT idea benefits from many trajectory samples because different
samples may discover different motion modes around obstacles. The distributed
version preserves that idea at a coarser level:

- MPOT particles explore alternatives inside one task.
- MPI tasks explore alternatives across different random seeds.
- Rank 0 chooses the best trajectory from all explored alternatives.

So the MPI layer does not replace MPOT. It expands the exploration budget by
running many complete MPOT attempts concurrently.

## Why Other MPOT Steps Are Not Split Across MPI Ranks

The original MPOT optimizer has several possible parallelization levels. The
project intentionally chooses only the outer task level for OpenMPI.

| Candidate level | Could be parallel? | Chosen for OpenMPI? | Reason |
|---|---:|---:|---|
| Independent seed/task `F(config, s_i)` | yes | yes | No data dependency between tasks; coarse enough for LAN/VM communication. |
| Particle batch inside one MPOT task | yes in shared memory/GPU | no | Particles interact through batch objective/Sinkhorn state; splitting them across MPI ranks would require frequent synchronization. |
| Waypoints inside one trajectory | partly | no | Smoothness and trajectory constraints couple neighboring waypoints, so communication would be fine-grained. |
| Probe cost evaluation | yes in vectorized PyTorch | no MPI split | It is already local tensor work; distributing small probe matrices over LAN would cost more than it saves. |
| Sinkhorn inner iterations | mathematically possible | no | Each iteration depends on current dual variables and transport state; MPI would need repeated synchronization inside every MPOT iteration. |
| Final best-result reduction | yes | yes, small gather/reduce | Results are compact, so gathering them at rank 0 is cheap and easy to verify. |

The main tradeoff is communication granularity:

```text
Task-level MPI:
  few messages, large local compute per rank, good for LAN/VM.

Sinkhorn-level MPI:
  many messages inside every outer iteration, small synchronized updates,
  poor fit for LAN/VM and harder to defend.
```

For this course project, the goal is not to build a distributed optimal
transport solver. The goal is to parallelize an MPOT-based motion planning
workload in a way that is correct, measurable, and explainable.

## How Result Aggregation Works

Each rank returns a list:

```text
local_results_r = [Y_i for i in D_r]
```

Rank 0 gathers:

```text
all_results = local_results_0 ++ local_results_1 ++ ... ++ local_results_{P-1}
```

Then rank 0 applies the deterministic reduction:

```text
Y^* = argmin_{Y_i in all_results} (Y_i.best_cost, Y_i.task_id, Y_i.seed)
```

The tuple ordering matters:

1. Lowest cost wins.
2. If costs are equal, smaller task id wins.
3. If task ids are equal, smaller seed wins.

This makes serial and MPI comparable. MPI may finish tasks in a different
order, but the final reduction is order-independent because all task results are
collected and sorted by the same rule.

## Why This Is Valid Parallel Computing

The parallel program has all required components of a parallel algorithm:

- **Decomposition:** split `N` independent MPOT attempts into `P` task subsets.
- **Mapping:** assign task `i` to rank `i mod P`.
- **Communication:** use blocking `bcast`, `scatter`, and `gather`.
- **Synchronization:** collectives synchronize ranks at setup and result
  collection boundaries.
- **Reduction:** rank 0 computes the global best trajectory from all task
  results.
- **Timing:** measure compute time, communication time, and total wall time per
  rank.
- **Load balancing:** compare per-rank timing and check the 25 percent threshold.

The mathematical result is unchanged from serial execution because the same set
of deterministic tasks is evaluated and the same reduction rule is applied.
Only the execution schedule changes.

## Communication Model

The communication topology is a logical star centered at rank 0.

| Step | MPI collective | Blocking? | Main data |
|---|---|---|---|
| Setup | `bcast` | yes | config |
| Setup | `bcast` | yes | run id |
| Setup | `bcast` | yes | assignment metadata |
| Distribution | `scatter` | yes | task subsets `D_r` |
| Collection | `gather` | yes | task results |
| Collection | `gather` | yes | per-rank timing |
| Collection | `gather` | yes | communication event logs |

Approximate communication volume:

```text
V_comm = O(P * |config| + N * |task_result| + P * |rank_timing|)
```

There is no repeated communication during the MPOT optimization loop. Therefore
the communication frequency is low:

```text
number_of_collective_phases = constant
```

This is why the implementation is suitable for multiple physical machines over
LAN/Wi-Fi.

## Parallel Time, Speedup, and Efficiency

Per-rank time is recorded as:

```text
T_total(r) = T_compute(r) + T_comm(r) + T_idle_or_wait(r)
```

The measured parallel runtime with communication is:

```text
T_P_with_comm = max_r T_total(r)
```

The measured compute-only runtime is:

```text
T_P_no_comm = max_r T_compute(r)
```

Speedup and efficiency are:

```text
S_P = T_1 / T_P
E_P = S_P / P
```

The report plots both:

```text
S_P_with_comm    = T_1 / T_P_with_comm
S_P_without_comm = T_1 / T_P_no_comm
```

## Load Balancing and Granularity

Each task is coarse-grained: it contains a full MPOT run. This gives good
computation per communication event.

Cyclic mapping helps balance random seed variability:

```text
D_0 = {0, P, 2P, ...}
D_1 = {1, P+1, 2P+1, ...}
...
D_{P-1} = {P-1, 2P-1, 3P-1, ...}
```

Let:

```text
C_max = max_r T_compute(r)
C_min = min_r T_compute(r)
imbalance = (C_max - C_min) / C_max
```

The course threshold is:

```text
imbalance <= 0.25
```

If imbalance is larger than 25 percent, the project should adjust granularity:

- increase `N` so every rank receives more tasks;
- keep cyclic mapping instead of block mapping;
- avoid tasks that are too small, because communication overhead becomes large;
- avoid tasks that are too large, because one slow seed can dominate a rank.

## Correctness of the Parallel Algorithm

The MPI algorithm is correct with respect to the serial baseline because:

1. Serial and MPI use the same `LOCAL_MPOT_TASK`.
2. Each task seed `s_i` is deterministic.
3. Cyclic mapping is a partition:
   - every task appears in one and only one `D_r`;
   - no task is dropped;
   - no task is duplicated.
4. MPI changes execution order, not task mathematics.
5. Rank 0 applies the same deterministic reduction rule as serial:

```text
Y^* = argmin_i (Y_i.best_cost, Y_i.task_id, Y_i.seed)
```

The correctness comparison checks matching task ids, seeds, costs, and selected
best task between serial and MPI artifacts.

## What To Say in the Report

Use this concise statement:

```text
The original MPOT optimizer is kept as the local planning kernel. We parallelize
outside the Sinkhorn loop by launching many independent MPOT tasks with different
random seeds. OpenMPI assigns tasks to ranks using 1D cyclic mapping. Each rank
computes its tasks independently, then rank 0 gathers task results, timing data,
and communication logs. Rank 0 reduces all task results to the global best
trajectory by minimum cost. This is task-level parallelism with exploratory
decomposition and a logical star communication topology.
```

## File Traceability

| Algorithm concept | Repository path |
|---|---|
| MPOT local optimizer core | `mpot/planner.py` |
| Sinkhorn and Sinkhorn Step | `mpot/ot/sinkhorn.py`, `mpot/ot/sinkhorn_step.py` |
| 2D cost and problem definition | `mpot/benchmarks/problem_2d.py` |
| One local MPOT task | `mpot/benchmarks/local_runner.py` |
| Serial baseline | `scripts/run_serial.py` |
| Task construction and cyclic mapping | `mpot/benchmarks/mpi_scheduler.py` |
| Distributed MPI orchestration | `mpot/benchmarks/mpi_runner.py` |
| MPI entrypoint | `scripts/run_mpi.py` |
| Correctness comparison | `scripts/compare_serial_mpi.py`, `mpot/benchmarks/correctness.py` |
| Communication analysis | `scripts/analyze_communication.py`, `mpot/benchmarks/communication.py` |
