# HANOI UNIVERSITY OF SCIENCE AND TECHNOLOGY

**Project Report**

# Distributed MPOT Motion Planning with OpenMPI

| Field | Value |
|---|---|
| School / Faculty | TODO: fill official school or faculty name |
| Course | Parallel Computing and Parallel Programming |
| Group | TODO: fill group number |
| Group members | TODO: fill full names and student IDs |
| Instructor | TODO: fill instructor name |
| Submission deadline | 24 June 2026 |
| Draft date | 17 June 2026 |
| Report status | Local-first report draft. Local macOS MPI results and owner Ubuntu single-VM smoke results are measured. Multi-machine LAN results are TODO until teammate VMs are ready. |

---

## Abstract

Motion planning searches for a collision-free and smooth trajectory from a start state to a goal state. It is difficult because obstacle constraints and nonlinear costs can create local minima. Motion Planning via Optimal Transport (MPOT) addresses this issue by optimizing a batch of trajectory particles using a gradient-free, optimal-transport-inspired update. The original MPOT work is highly parallelizable and was demonstrated mainly as a batch optimization method.

This project adapts the MPOT idea into a course-level CPU/OpenMPI system for a 2D point robot. Instead of splitting the inner Sinkhorn optimization across machines, the project parallelizes independent MPOT planning attempts generated from different deterministic seeds. Each MPI process solves a subset of complete planning tasks, then rank 0 gathers the compact results and selects the lowest-cost trajectory. This design uses task-level parallelism, exploratory decomposition, 1D cyclic mapping, SPMD execution, a logical star communication topology, and blocking `bcast/scatter/gather` collectives.

The current local experiment verifies correctness, communication, load balance, runtime scaling, speedup, and visualization. For `N=824` tasks and `P=4` MPI processes, serial and MPI outputs match on `824/824` tasks, the best-cost difference is `0.0`, and the measured speedup is approximately `2.995x` with communication included. The load-balance idle fraction at `N=412, P=4` is approximately `0.00705`, below the professor's 25% threshold. The current run is shorter than the 2-3 minute target, so larger-N and multi-machine LAN experiments remain TODO until real artifacts are produced.

**Keywords:** motion planning, MPOT, optimal transport, Sinkhorn Step, OpenMPI, task-level parallelism, exploratory decomposition, cyclic mapping, load balancing.

---

## Table of Contents

> TODO: Generate the final table of contents automatically after exporting this Markdown report to PDF or LaTeX/Overleaf.

1. Introduction
2. Related Work and MPOT Background
3. Problem Definition and Input Parameters
4. Serial Baseline
5. Parallel Algorithm Design
6. Complexity Analysis
7. Implementation Overview
8. Experimental Methodology
9. Results
10. Discussion
11. Conclusion
12. References
Appendix A. Requirement Coverage
Appendix B. Remaining TODO Items
Appendix C. Demo Artifacts

---

## 1. Introduction

Motion planning is a fundamental problem in robotics and autonomous systems. Given an initial state, a goal state, and obstacle constraints, the planner must produce a feasible trajectory that is collision-free, smooth, and close to the target. The problem is often non-convex because obstacles divide the free space into different route modes. A single optimization run can become trapped in a poor local minimum.

MPOT, short for Motion Planning via Optimal Transport, is attractive for this project because it naturally uses many trajectory particles and local cost probes. Different particles or seeds can explore different candidate paths around obstacles. This exploration property gives a clear parallel-computing opportunity: many independent planning attempts can run concurrently, and only the final compact results need to be reduced.

The objective of this project is not to reproduce the original GPU MPOT performance. The objective is to build an understandable OpenMPI program that demonstrates the concepts required by the course:

- what level of parallelism is used;
- which decomposition technique is used;
- how tasks are mapped to MPI processes;
- how processes communicate;
- how load balance is measured;
- how correctness and speedup are evaluated with real artifacts.

The project uses only 2D planning settings in the report. This makes the algorithm easier to explain and makes the figures readable for defense. More complicated 2D obstacle variants are included for qualitative visualization, but the main measured benchmark uses one fixed configuration so runtime and speedup comparisons remain fair.

---

## 2. Related Work and MPOT Background

### 2.1 Original MPOT

The original MPOT paper, *Accelerating Motion Planning via Optimal Transport*, presents a gradient-free method for optimizing a batch of smooth trajectories over nonlinear motion-planning costs. The method uses a Gaussian Process dynamics prior for smoothness and introduces the Sinkhorn Step as a zero-order, highly parallelizable update rule. Around each trajectory waypoint, a regular polytope defines local search directions. Costs are evaluated at local probe points, then an entropic optimal transport computation moves trajectory parameters toward lower-cost regions.

The important idea for this project is not that MPOT removes optimization difficulty. Instead, MPOT changes the optimization into repeated batch evaluations. A trajectory particle does not need an analytic gradient of every obstacle or collision function. It samples nearby candidates, scores them, and uses an optimal-transport-style update to shift probability mass toward better candidates. This makes the method attractive for parallel computing because many particles, probes, and seeds can be evaluated independently before their compact scores are combined.

The Sinkhorn Step can be understood at a high level as a regularized matching problem. The local cost values define which candidate directions are cheaper. Sinkhorn iterations then compute a transport plan under an entropy regularizer, so the update is smooth rather than a hard winner-take-all jump. In this report, the mathematical details of entropic optimal transport are kept compact because the course focus is MPI parallelization. What matters for the design is that the Sinkhorn loop is iterative and stateful inside one MPOT task, while different seeded tasks are independent outside that loop.

In simplified terms, one MPOT optimization run performs the following loop:

```text
Algorithm 1: Local MPOT Optimization Kernel

Input:
    problem configuration, optimizer configuration, deterministic seed
Output:
    best trajectory and best cost for this seed

1. Initialize a batch of K trajectory particles.
2. For iteration l = 1 to L:
       2.1 Generate local probe points around current waypoints.
       2.2 Evaluate obstacle, boundary, smoothness, velocity, and goal costs.
       2.3 Build an entropic optimal transport problem from the local costs.
       2.4 Run Sinkhorn iterations to estimate a transport plan.
       2.5 Update trajectory particles by barycentric projection.
       2.6 Decay probe or step radius if configured.
3. Evaluate the final trajectories.
4. Return the lowest-cost trajectory for this seed.
```

This local kernel is still sequential from the MPI point of view in our implementation. Its internal tensor operations may be vectorized by PyTorch, but MPI ranks do not communicate inside the Sinkhorn loop. This boundary is deliberate: MPI is used to distribute complete planning attempts, while PyTorch handles the smaller tensor operations inside one attempt.

### 2.2 Original MPOT vs. This Course Project

**Table 1. Original MPOT and OpenMPI adaptation.**

| Aspect | Original MPOT | This course project |
|---|---|---|
| Main goal | Fast batch motion planning via optimal transport | Parallel-programming demonstration with measurable MPI behavior |
| Main hardware assumption | GPU-friendly batch computation | CPU-only macOS/Ubuntu VM and OpenMPI |
| Planning scope in report | The paper covers low- and high-dimensional tasks | 2D point robot only |
| Parallelism focus | Batch particles/probes inside MPOT | Independent seed-level MPOT tasks across MPI ranks |
| Communication model | Mostly local tensor computation | SPMD MPI with rank 0 coordinator |
| Output emphasis | Planning performance and solution quality | Correctness, runtime, communication, load balance, speedup |

The adaptation is intentional. Splitting the fine-grained Sinkhorn or waypoint updates across virtual machines would introduce frequent synchronization and make the code harder to defend. Parallelizing complete independent tasks gives coarse-grained work units, simple communication, and clear experimental metrics. In one sentence: this project parallelizes the exploration budget of MPOT, not the inner optimizer.

---

## 3. Problem Definition and Input Parameters

The project solves a repeated 2D motion-planning problem. The input is a planning environment and an exploration budget; the output is the best trajectory discovered across that budget.

At a high level, the input is:

```text
I = (Omega, x_start, x_goal, O, W, T, optimizer_config, N, P)
```

where `Omega` is the bounded workspace, `O` is the obstacle set, `W` is the cost-weight set, `T` is the trajectory horizon, `N` is the number of independent planning tasks, and `P` is the number of MPI processes. The output is:

```text
Y* = (task_id*, seed*, X*, J(X*), timing, rank_metadata)
```

where `X*` is the lowest-cost trajectory found by all tasks. The timing and rank metadata are not part of the motion-planning solution itself; they are recorded to evaluate the parallel program.

### 3.1 2D Planning Problem

The robot is a point mass moving in a bounded 2D workspace. A state is:

```text
x_t = [p_x, p_y, v_x, v_y]
```

where `(p_x, p_y)` is position and `(v_x, v_y)` is velocity. A trajectory is a sequence:

```text
X = [x_0, x_1, ..., x_T].
```

The planner receives a fixed start state, a fixed goal state, circular obstacles, workspace bounds, and cost weights. The optimization objective is:

```text
J(X) =
  w_obs    * obstacle_penalty(X)
+ w_bound  * boundary_penalty(X)
+ w_smooth * smoothness_penalty(X)
+ w_goal   * goal_error(X)
+ w_vel    * velocity_penalty(X)
```

A good solution has low cost, zero hard collision fraction, small goal error, no boundary violation, and a smooth path.

The obstacle term is the safety term: it penalizes waypoint positions that enter the soft margin around a circular obstacle. The boundary term keeps the path inside the workspace. The smoothness term discourages sharp turns and unstable waypoint jumps. The goal term pulls the final state toward the target, and the velocity term discourages unnecessarily aggressive motion. These terms make the objective interpretable for a 2D demo and also give the report measurable correctness indicators.

### 3.2 Planning Task

One task is one complete MPOT-inspired local optimization run:

```text
Y_i = F(problem_config, optimizer_config, seed_i)
```

where `Y_i` stores the task id, seed, best cost, best trajectory, rank id, and timing information. Two tasks are independent because task `i` does not read intermediate state from task `j`.

### 3.3 Input Parameters of the Parallel Algorithm

The parallel algorithm input is:

```text
(problem_config, optimizer_config, N, P, mapping_rule)
```

**Table 2. Main parameter groups.**

| Group | Parameters | Role |
|---|---|---|
| Problem parameters | workspace bounds, start, goal, circular obstacles, trajectory length `T`, step `dt`, cost weights | Define the motion-planning objective |
| Local MPOT parameters | particles `K`, iterations `L`, Sinkhorn iterations `H`, probe radius, step radius, seed | Define one planning task |
| Parallel parameters | total task count `N`, process count `P`, rank id `r`, mapping `owner(i)=i mod P` | Define MPI workload distribution |
| Measurement parameters | compute time, communication time, idle time, total runtime, task assignment | Define report evidence |

For the professor's runtime and speedup requirements, `N` is the main input size. Increasing `N` increases the number of independent planning attempts.

---

### 3.4 Mathematical Formulation

Let the 2D workspace be a bounded set:

```text
Omega = [x_min, x_max] x [y_min, y_max].
```

The start and goal states are:

```text
x_start, x_goal in R^4.
```

Each circular obstacle is represented as:

```text
O_m = (c_m, rho_m, delta_m)
```

where `c_m in R^2` is the center, `rho_m` is the hard radius, and `delta_m` is the safety margin. A waypoint position `p_t` is inside the soft unsafe region of obstacle `m` when:

```text
||p_t - c_m||_2 < rho_m + delta_m.
```

For one trajectory `X = [x_0, ..., x_T]`, with `x_t = [p_t, v_t]`, the implemented objective can be written as:

```text
minimize_X J(X)
subject to x_0 = x_start, x_T close to x_goal, p_t in Omega.
```

The full trajectory cost is:

```text
J(X) =
  w_obs    * (1/T) sum_t sum_m max(0, rho_m + delta_m - ||p_t - c_m||_2)^2
+ w_bound  * (1/T) sum_t violation_Omega(p_t)^2
+ w_smooth * (1/T) sum_t (||p_t - p_{t-1}||_2^2 + ||p_{t+1} - 2p_t + p_{t-1}||_2^2)
+ w_goal   * ||x_T - x_goal||_2^2
+ w_vel    * (1/T) sum_t ||v_t||_2^2.
```

The global project objective over `N` independent seeds is:

```text
Y* = argmin_{i in {0, ..., N-1}} J(X_i*)
```

where `X_i*` is the best trajectory returned by local MPOT task `i`. This formulation is important for correctness: the MPI program does not solve a different mathematical problem; it evaluates the same set of `N` tasks in parallel and applies the same final minimum-cost reduction.

### 3.5 Why This Is Still a Motion-Planning Problem

The MPI layer changes only the execution schedule. It does not replace the planning objective with a synthetic workload. Every task still constructs trajectories, evaluates collision and smoothness costs, searches for a feasible route from start to goal, and returns a physical path in the 2D workspace. The final result is not the average runtime or a random numerical score; it is the best candidate trajectory found under the cost function.

This distinction matters for the project topic. The program is interesting for the course because it combines a real optimization problem with measurable parallel behavior. The motion-planning side provides obstacle-rich search, local minima, and trajectory visualization. The parallel-computing side provides task decomposition, process mapping, communication measurement, load-balance analysis, and speedup evaluation.

---

## 4. Serial Baseline

The serial baseline evaluates all `N` tasks one after another using the same local task runner as the MPI version. It is the reference for correctness.

```text
Algorithm 2: Serial MPOT Baseline

Input:
    problem_config, optimizer_config, total tasks N
Output:
    global best result Y*

1. Build deterministic task list:
       D = [(0, seed_0), (1, seed_1), ..., (N-1, seed_{N-1})]
2. Create empty result list R.
3. For each task (i, seed_i) in D:
       3.1 Run Local MPOT Optimization Kernel.
       3.2 Append result Y_i to R.
4. Select:
       Y* = argmin_i (Y_i.best_cost, Y_i.task_id, Y_i.seed_i)
5. Write summary, task results, and best trajectory.
6. Return Y*.
```

The serial runtime is approximately:

```text
T_serial = sum_i T_task(i)
```

Because serial and MPI call the same local task kernel, any result difference should come only from task distribution or result reduction, not from a different optimization algorithm.

---

## 5. Parallel Algorithm Design

### 5.1 Parallel Level

The program uses **task-level parallelism**. Each MPI process solves complete MPOT tasks. A task is coarse-grained enough to run for meaningful compute time before communicating, and it returns only compact results.

This choice is appropriate because:

- different seeds are independent;
- MPOT benefits from exploring multiple route modes;
- task results can be deterministically reduced by minimum cost;
- communication cost is small compared with local computation.

This is also the safest level for a group project defense. A member can explain one task as "one full planning attempt with one seed." The parallel program then becomes a controlled way to run many attempts at once. If the project used data-level parallelism inside one Sinkhorn iteration, the implementation would need to explain distributed tensor slices, repeated synchronization, and numerical equivalence of the transport update. That would be harder to test and less robust on a Wi-Fi/LAN cluster.

### 5.2 Decomposition Technique

The decomposition technique is **exploratory decomposition**. Each task explores the planning problem with a different deterministic seed. In obstacle-rich spaces, different seeds can lead particles around different sides of obstacles. The algorithm therefore parallelizes exploration rather than dividing a single matrix or image.

This is not 2D block decomposition because the work unit is not a spatial grid block. It is also not recursive decomposition because tasks do not recursively create subtasks. It is not speculative execution in the strict sense because every task result is useful for finding the global best candidate.

The decomposition matches the nature of MPOT. Motion planning around obstacles often has several route modes, for example passing above or below an obstacle group. A single local run may converge to one mode. Running multiple seeded tasks increases the chance that at least one task explores a better basin of attraction. Therefore the decomposition is not an artificial trick added only for MPI; it is aligned with the exploratory behavior already present in sampling and particle-based motion planning.

### 5.3 Mapping Technique

Tasks are assigned by **1D cyclic mapping**:

```text
owner(i) = i mod P
D_r = { task i | owner(i) = r }
```

where `P` is the number of MPI processes and `D_r` is the task subset assigned to rank `r`.

Cyclic mapping is chosen over block mapping because seed runtimes may vary. With block mapping, a rank could receive a contiguous region of expensive seeds. Cyclic mapping spreads task ids across ranks and is simple enough for every member to explain during defense.

For example, with `N=12` and `P=4`, rank 0 receives tasks `{0,4,8}`, rank 1 receives `{1,5,9}`, rank 2 receives `{2,6,10}`, and rank 3 receives `{3,7,11}`. This is a 1D mapping because tasks are indexed along one list. A 2D block mapping such as `n/sqrt(P) x n/sqrt(P)` would be suitable for matrix or image blocks, but it does not match a list of independent planning attempts.

### 5.4 Communication Strategy and Topology

The program follows the **SPMD** model: all ranks execute the same script, but each rank behaves according to its MPI rank id. Rank 0 acts as the coordinator. The logical communication topology is a **star** centered at rank 0.

**Table 3. Communication phases.**

| Phase | MPI collective | Blocking? | Purpose |
|---|---|---:|---|
| Setup | `bcast` | yes | Share configuration and run metadata |
| Distribution | `scatter` | yes | Send each rank its cyclic task subset |
| Collection | `gather` | yes | Collect task results, rank timings, and communication logs |
| Reduction | local on rank 0 | not MPI | Select global best result |

Blocking collectives are chosen because communication happens at coarse boundaries only. During local MPOT optimization there is no inter-rank communication. Non-blocking communication would add code complexity but little benefit for the current coarse-grained workload.

The communication design is deliberately conservative. Rank 0 owns run setup, reproducible task construction, artifact writing, and final result selection. Worker ranks only need to receive their assigned tasks and return compact task summaries. This makes the demo easier to reproduce on macOS, on one Ubuntu VM, and later on several Ubuntu VMs connected through Bridged networking. It also makes communication time easy to measure because the code has a small number of clearly named collective phases.

### 5.5 Course-Rubric Decision Summary

**Table 4. Parallel design choices mapped to course terminology.**

| Rubric item | Project choice | Defense rationale |
|---|---|---|
| Parallel level | Task-level | One task is one full MPOT planning attempt, independent from other tasks |
| Decomposition | Exploratory | Different seeds explore different route modes around obstacles |
| Mapping | 1D cyclic, `owner(i)=i mod P` | Spreads seed-level runtime variation more evenly than block mapping |
| Execution model | SPMD | Same script runs on every rank, behavior depends on rank id |
| Coordinator/topology | Rank 0, logical star | Small setup/result messages naturally flow through one coordinator |
| Communication | Blocking `bcast`, `scatter`, `gather` | Few communication phases, simpler timing, no inner-loop synchronization |
| Load balance | Per-rank timing and idle fraction | Directly checks the professor's 25% imbalance threshold |

These choices are consistent with the project constraints. The target platform is CPU-only OpenMPI on local machines and Ubuntu VMs, not a tightly coupled GPU cluster. Therefore the design favors coarse-grained tasks, deterministic assignment, and transparent measurement over aggressive fine-grained parallelization.

### 5.6 Why Parallelization Is Added Outside the Sinkhorn Loop

**Table 5. Candidate parallelization levels.**

| Candidate level | Decision | Reason |
|---|---|---|
| Independent seed/task | Use MPI | Coarse-grained, independent, easy to distribute |
| Particle batch inside one task | Keep local | Particles share batch state and cost context |
| Waypoints inside one trajectory | Keep local | Smoothness couples neighboring waypoints |
| Probe evaluation | Keep local | Fine-grained tensor work; LAN communication would dominate |
| Sinkhorn inner iterations | Keep local | Iterative dual updates would require repeated synchronization |
| Final best-result selection | Use rank 0 reduction | Compact result objects are cheap to gather |

The central design argument is that MPI should be used where communication is rare and computation is independent. In this project, that point is the outer task layer.

### 5.7 Parallel Pseudocode

```text
Algorithm 3: Distributed MPOT with OpenMPI

Input:
    problem_config on rank 0
    optimizer_config on rank 0
    total tasks N
    process count P
Output:
    global best result Y* on rank 0

1. Start MPI ranks r = 0, 1, ..., P-1.
2. If r == 0:
       2.1 Build deterministic task list D.
       2.2 Partition tasks by cyclic mapping:
             D_r = { task i | i mod P = r }
3. Rank 0 broadcasts problem_config and optimizer_config.
4. Rank 0 scatters task subsets so rank r receives D_r.
5. Each rank initializes local timer and result list R_r.
6. For each task (i, seed_i) in D_r:
       6.1 Run Local MPOT Optimization Kernel.
       6.2 Append local result Y_i to R_r.
7. Each rank records compute_time_r and communication_time_r.
8. All ranks gather R_r and rank timing records to rank 0.
9. Rank 0 merges all task results:
       R = union_r R_r
10. Rank 0 selects:
       Y* = argmin_i (Y_i.best_cost, Y_i.task_id, Y_i.seed_i)
11. Rank 0 writes summaries, CSV tables, plots, and validation artifacts.
12. Finalize MPI.
```

### 5.8 Load Balancing Strategy

Load balance is measured using per-rank compute time, communication time, total time, and idle time. The course threshold is:

```text
idle_fraction <= 0.25
```

If the idle fraction exceeds 25%, the planned correction is to adjust task granularity. For task-level parallelism, the simplest correction is to increase `N` so each rank receives more tasks and cyclic mapping can average out seed-level variability.

---

## 6. Complexity Analysis

This section gives an asymptotic view of the algorithm. The exact measured time is still obtained from CSV/JSON artifacts because PyTorch kernels, CPU scheduling, and MPI runtime overhead are machine-dependent.

### 6.1 Symbols

**Table 6. Complexity symbols.**

| Symbol | Meaning |
|---|---|
| `N` | number of independent planning tasks / seeds |
| `P` | number of MPI processes |
| `T` | number of trajectory waypoints |
| `K` | number of particles in one local MPOT task |
| `L` | maximum outer MPOT iterations |
| `H` | maximum Sinkhorn inner iterations |
| `Q` | number of probe candidates per waypoint after polytope/probe expansion |
| `M` | number of circular obstacles |
| `C_task` | average runtime of one local MPOT task |

### 6.2 Local MPOT Task Complexity

In one local task, the dominant cost comes from repeatedly evaluating local probes and running Sinkhorn updates. A simple upper-level model is:

```text
C_task = O(L * (K * T * Q * M + H * K * T * Q)).
```

The first term approximates obstacle and cost evaluation over particles, waypoints, probes, and obstacles. The second term approximates repeated Sinkhorn-style updates over the local candidate costs. Constants are omitted because the implementation uses vectorized PyTorch operations, so the practical cost is measured empirically.

Memory per task is mainly the particle batch and local probe/cost tensors:

```text
M_task = O(K * T * Q)
```

plus the saved final trajectory and small metadata.

### 6.3 Serial Complexity

The serial baseline runs all tasks sequentially:

```text
T_serial = sum_{i=0}^{N-1} C_task(i).
```

If task runtimes are approximately similar:

```text
T_serial = O(N * C_task).
```

The final reduction over `N` task results is:

```text
O(N)
```

which is small compared with local optimization.

The serial baseline is important for two reasons. First, it defines the reference answer for correctness: the MPI version must evaluate the same task ids and seeds. Second, it defines the denominator of the speedup metric. A parallel result is meaningful only if it is compared against the same amount of planning work.

### 6.4 Parallel Computation Complexity

Under 1D cyclic mapping, rank `r` receives:

```text
D_r = { i | i mod P = r }.
```

The compute time on rank `r` is:

```text
T_compute(r) = sum_{i in D_r} C_task(i).
```

The parallel runtime without communication is modeled as:

```text
T_P_no_comm = max_r T_compute(r).
```

If tasks are balanced and have similar cost:

```text
T_P_no_comm ~= O((N / P) * C_task).
```

This is why increasing `P` can reduce runtime: each process handles fewer independent MPOT tasks.

The complete measured model used in the report is:

```text
T_parallel ~= max_r T_compute(r) + T_comm + T_idle.
```

The first term is useful work. `T_comm` includes blocking broadcast, scatter, and gather phases. `T_idle` appears when some ranks finish earlier than the slowest rank. With good granularity, many tasks are distributed to each rank, and cyclic mapping can average out seed-level runtime differences. With poor granularity, one rank may receive too few or unusually expensive tasks, causing others to wait.

### 6.5 Communication Complexity

The MPI program communicates only at coarse boundaries. The approximate communication volume is:

```text
V_comm = O(P * |config| + N * |task_result| + P * |rank_timing|).
```

The number of collective communication phases is constant:

```text
bcast(config), bcast(run_id), bcast(assignment), scatter(tasks), gather(results), gather(timings), gather(comm_events).
```

There is no communication inside the local MPOT/Sinkhorn loop. Therefore the parallel design is coarse-grained and suitable for a LAN/Ubuntu VM cluster.

This communication pattern is closer to an embarrassingly parallel search than to a tightly coupled stencil or matrix multiplication. That is why the project does not need ring, mesh, or hypercube communication. A logical star is enough because the data exchanged between ranks is small relative to the local optimization work.

### 6.6 Parallel Runtime, Speedup, and Efficiency

The measured runtime with communication is:

```text
T_P_with_comm = max_r (T_compute(r) + T_comm(r) + T_wait(r)).
```

The ideal speedup model is:

```text
S_P = T_1 / T_P
E_P = S_P / P.
```

In an ideal embarrassingly parallel system:

```text
S_P ~= P, E_P ~= 1.
```

In practice:

```text
S_P < P
```

because of communication, process launch overhead, serial reduction on rank 0, OS scheduling, and load imbalance. The report therefore plots both runtime with communication and runtime without communication.

The expected behavior is:

```text
large N  -> compute dominates -> better speedup
small N  -> overhead visible  -> weaker speedup
larger P -> less work per rank but more process/runtime overhead
```

This is why the current local result is valid but not the final ideal experiment. It proves that the program is correct and parallel, but the strict 2-3 minute target requires a larger `N` or more machines so the compute phase is large enough to represent the final course benchmark.

### 6.7 Load Balance Model

The idle time of a rank is measured against the slowest rank:

```text
idle_r = max_j T_total(j) - T_total(r).
```

The imbalance indicator used in this project is:

```text
idle_fraction = max_r idle_r / max_j T_total(j).
```

The course threshold is:

```text
idle_fraction <= 0.25.
```

For the measured `N=412, P=4` local run, `idle_fraction ~= 0.00705`, so the task granularity is acceptable for the current setting.

---

## 7. Implementation Overview

The implementation is organized so that the serial and MPI runners share the same local planning task. This keeps correctness checks meaningful.

**Table 7. Main implementation files.**

| File | Responsibility |
|---|---|
| `mpot/benchmarks/problem_2d.py` | 2D workspace, obstacles, trajectory cost, solution-quality checks |
| `mpot/benchmarks/local_runner.py` | One deterministic MPOT-inspired planning task and serial execution loop |
| `mpot/benchmarks/mpi_runner.py` | MPI setup, cyclic mapping, collectives, result gathering |
| `mpot/benchmarks/reduction.py` | Deterministic best-result selection shared by serial and MPI workflows |
| `mpot/benchmarks/metrics.py` | Correctness, speedup, load-balance, timing metrics |
| `mpot/benchmarks/plots.py` | Runtime, speedup, load-balance, path figures |
| `scripts/run_serial.py` | Command-line serial runner |
| `scripts/run_mpi.py` | Command-line MPI runner |
| `scripts/compare_serial_mpi.py` | Serial-vs-MPI correctness comparison |
| `scripts/check_report_sync.py` | Living-report path consistency check |

The original MPOT support modules remain in the repository and are credited. Core algorithm/support files such as `mpot/planner.py`, `mpot/ot`, `mpot/gp`, `mpot/utils`, and `mpot/envs` are not rewritten in this cleanup because changing them would be risky for a late-stage course submission.

---

## 8. Experimental Methodology

### 8.1 Measured Local Experiment

The measured local experiment is labeled `final_macbook_air_2d`. It uses:

- 2D point robot;
- circular obstacles;
- CPU-only execution;
- OpenMPI on one macOS machine;
- input sizes `N = 208, 412, 824`;
- MPI process counts `P = 1, 2, 4`.

The experiment produces runtime tables, speedup tables, rank timing tables, correctness reports, communication logs, and visualization figures.

### 8.2 Correctness Check

Correctness is checked by comparing the serial and MPI outputs for the same task list:

```text
For every task i:
    serial_result_i.best_cost == mpi_result_i.best_cost
    serial_result_i.seed == mpi_result_i.seed
    serial_result_i.task_id == mpi_result_i.task_id
```

The final best trajectory is selected by the same deterministic rule:

```text
argmin_i (best_cost, task_id, seed)
```

### 8.3 Runtime Versus Input Size

The runtime-vs-input-size experiment fixes the process count and varies `N`. It records runtime with communication and runtime without communication.

> TODO (strict runtime target): The current local run is shorter than 2-3 minutes. If strict compliance is required, rerun with larger `N` or with the LAN cluster and replace this section with the new real CSV/PNG artifacts.

### 8.4 Granularity and Load Balance

The granularity experiment fixes `N` and `P`, then plots per-rank compute and communication time in one stacked bar chart per rank. The decision rule is:

```text
balanced if idle_fraction <= 0.25
```

### 8.5 Speedup

The speedup experiment fixes the input size at `2N` and varies process count:

```text
P = 1, 2, 4
```

The course requirement allows extending this to `P = 8, 16, ...` when enough physical cores or teammate VMs are available.

> TODO (process-count extension): Run `P=8` or higher only after a larger local machine or multi-machine Ubuntu LAN setup is available. Do not invent higher-P speedup.

### 8.6 Ubuntu VM and LAN Plan

The owner Ubuntu ARM64 VM has passed smoke tests. The multi-machine LAN stage is not measured yet. The required stage gates are:

1. Owner VM verified.
2. Each teammate VM verified locally.
3. UTM network switched from Shared Network to Bridged.
4. `ping` and `ssh` from master to workers verified.
5. Hostfile MPI rank distribution verified.
6. Project cluster smoke verified.
7. Larger benchmark measured and copied into `report/`.

> TODO (LAN benchmark): Replace this TODO only after teammate VMs produce real `summary.json`, hostfile output, rank timing CSVs, and figures.

### 8.7 Additional Experiments and Ablation Policy

The main report should not become a large robotics hyperparameter study. The course grading focuses on how the problem is parallelized, whether the demo runs, whether the report is clear, and whether members understand the code. Therefore, extra experiments are selected by this rule:

```text
Add an experiment only if it improves one of:
    parallel explanation,
    demo clarity,
    solution-quality interpretation,
    or teammate defense readiness.
```

The selected additions are:

| Candidate | Decision | Reason |
|---|---|---|
| Communication overhead analysis | Keep | Directly supports the MPI communication discussion |
| 2D problem-variant visualization | Keep | Makes the demo more interesting without changing the algorithm |
| Particle-count ablation | Keep as auxiliary | Shows local MPOT quality/runtime trade-off in one small controlled run |
| Mapping comparison: cyclic vs block | TODO only | Useful but not required; would add implementation complexity |
| Large MPOT hyperparameter sweep | Do not include now | Too broad and weakly connected to parallel computing |
| 3D/Panda/CUDA benchmark | Do not include now | Distracts from CPU/OpenMPI and teammate VM setup |

The detailed plan is maintained in `docs/extra_experiments_plan.md`.

---

## 9. Results

All numbers in this section are generated from real artifacts under the label `final_macbook_air_2d`. They should not be edited manually.

The current results should be read as local-first evidence. They demonstrate that the serial runner, MPI runner, task assignment, timing collection, plotting pipeline, and Ubuntu single-VM deployment are working. They do not yet claim a final multi-machine LAN benchmark.

### 9.1 Correctness

For `N=824` and `P=4`, the serial and MPI results match exactly at task level.

**Table 8. Correctness result.**

| Metric | Value |
|---|---:|
| Compared tasks | 824 |
| Same best task | yes |
| Same best seed | yes |
| Best cost difference | 0.0 |
| Task-level comparison | pass |

The best MPI trajectory also passes solution-quality checks.

**Table 9. Best trajectory quality.**

| Metric | Value |
|---|---:|
| Best task id | 184 |
| Best seed | 20260801 |
| Best cost | 0.00520871 |
| Goal error | 3.37175e-08 |
| Hard collision fraction | 0.0 |
| Max bounds violation | 0.0 |

**Figure 1. Best distributed trajectory.**

![Best trajectory](report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N824-P4_best_path.png)

This correctness result is stronger than comparing only the final best cost. The task-level comparison checks that the same deterministic task set is evaluated and that the MPI program does not silently skip, duplicate, or reorder work in a way that changes the selected solution.

### 9.2 Runtime Versus Input Size

At `P=4`, runtime increases with `N`, and the gap between runtime with and without communication remains small.

**Table 10. Runtime vs input size at `P=4`.**

| N | Runtime with communication (s) | Runtime without communication (s) | Communication overhead (s) |
|---:|---:|---:|---:|
| 208 | 2.86270 | 2.85861 | 0.00409 |
| 412 | 4.91507 | 4.87856 | 0.03651 |
| 824 | 9.31508 | 9.27704 | 0.03804 |

**Figure 2. Runtime versus input size.**

![Runtime versus input size](report/figures/runtime_vs_input_size_final_macbook_air_2d.png)

The trend is consistent with the complexity model: increasing `N` increases the number of complete MPOT tasks, so runtime grows with input size. The measured communication overhead is small in these local runs because each rank communicates only compact task lists, results, and timing records. However, the absolute runtime is still much shorter than the professor's 2-3 minute target, so these values should be treated as a verified pipeline result, not the final strict runtime-size experiment.

### 9.3 Granularity and Load Balance

The load-balance experiment uses `N=412`, `P=4`. Each rank receives 103 tasks. The maximum observed idle fraction is approximately `0.00705`, which is far below the 25% threshold.

**Table 11. Load-balance summary.**

| Metric | Value |
|---|---:|
| Tasks per rank | 103 |
| Max idle fraction | 0.00705028 |
| Threshold | 0.25 |
| Balanced under threshold | yes |
| Observed communication collectives | `bcast`, `scatter`, `gather` |

**Figure 3. Per-rank compute and communication time.**

![Rank timing breakdown](report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png)

### 9.4 Speedup

For `N=824`, the measured speedup is:

**Table 12. Speedup at `N=824`.**

| Processes | Runtime with communication (s) | Speedup | Efficiency |
|---:|---:|---:|---:|
| 1 | 27.9028 | 1.00000 | 1.00000 |
| 2 | 14.7543 | 1.89117 | 0.945584 |
| 4 | 9.31508 | 2.99545 | 0.748862 |

**Figure 4. Speedup.**

![Speedup](report/figures/speedup_final_macbook_air_2d.png)

The speedup is meaningful but not ideal. Moving from one to two processes gives most of the expected improvement. Moving to four processes still improves runtime, but efficiency decreases because the local machine shares CPU and memory resources among all ranks. This is normal for a one-machine MPI experiment and is one reason the LAN experiment remains useful.

### 9.5 Algorithm Trace and 2D Variants

The report includes a static key frame from the algorithm-trace GIF because PDF export cannot play GIFs. The GIF shows trajectory particles and candidate paths evolving across optimization iterations, which is more informative than showing only the final path.

**Figure 5. Algorithm trace key frame.**

![Algorithm trace key frame](report/figures/algorithm_trace_final_macbook_air_2d_keyframe.png)

Additional 2D variants were generated for presentation:

**Table 13. Qualitative 2D variants.**

| Variant | Obstacles | Purpose |
|---|---:|---|
| Open | 2 | Simple sanity-check layout |
| Narrow passage | 4 | Demonstrates route selection through a tighter gap |
| Cluttered | 6 | Demonstrates behavior with more obstacles |
| Dense sampling | 10 | Uses more particles/probes to make the trace clearer |

These qualitative variants are not used as the main speedup evidence because the report should compare runtime using a consistent benchmark configuration.

**Figure 6. Dense 2D variant trace key frame.**

![Dense variant trace key frame](report/figures/algorithm_trace_variant_dense_keyframe.png)

### 9.6 Auxiliary Particle-Count Ablation

This ablation is intentionally small. It varies only `optimizer.num_particles` on the dense 2D variant with `N=12` and `P=4`. The purpose is to explain the local MPOT exploration/runtime trade-off, not to replace the main parallel-computing experiments.

The detailed generated table is stored in `report/PARAMETER_ABLATION_particles_dense_N12.md`, with copied source summaries under `report/artifacts/particle_ablation_dense_N12/`.

**Table 14. Particle-count ablation on dense 2D variant.**

| Particles | Runtime with communication (s) | Best cost | Best task | Best seed |
|---:|---:|---:|---:|---:|
| 8 | 1.502928 | 0.00395729 | 0 | 20260617 |
| 16 | 1.069814 | 0.00383398 | 8 | 20260625 |
| 24 | 1.185440 | 0.00370045 | 10 | 20260627 |

**Figure 7. Particle-count ablation.**

![Particle-count ablation](report/figures/particle_ablation_dense_N12_P4.png)

The result suggests that more particles can improve the best discovered cost, but runtime does not change perfectly monotonically in such a small run because task-level seed variability and local machine scheduling are still visible. For this reason, the ablation is treated as qualitative support only.

**Result TODO box.** The following items must stay TODO until real artifacts exist:

| Missing final evidence | Required artifact |
|---|---|
| Larger `N` near 2-3 minutes | Runtime CSV/PNG generated from a real larger run |
| `P=8` or higher | Speedup CSV/PNG from a capable local or LAN setup |
| Multi-machine Ubuntu LAN | Hostfile, rank distribution log, summaries, timing CSVs, figures |
| Replacing local-only claims | Updated tables copied from generated artifacts, not hand-written values |

---

## 10. Discussion

The local results support the chosen parallel design. The correctness result shows that MPI distribution does not change the mathematical answer for the measured task set: all `824` tasks match the serial baseline, and the best-cost difference is `0.0`. This is important because the parallel implementation should only change execution order and process assignment, not the objective function or local optimizer.

The runtime and speedup results show useful parallel benefit on one machine. At `P=4`, speedup is approximately `2.995x` with communication included. Efficiency drops from about `0.946` at `P=2` to about `0.749` at `P=4`, which is expected because process-management overhead and shared local resources become more visible as `P` increases.

Communication overhead is small in the measured runs. This agrees with the design: ranks communicate through blocking collectives only during setup, distribution, and collection. The expensive local MPOT optimization is performed without inter-rank synchronization.

Load balance is acceptable for the current granularity. At `N=412, P=4`, each rank receives the same number of tasks and the maximum idle fraction is about `0.00705`, well below the 25% threshold. This supports the use of 1D cyclic mapping for seed-level exploratory tasks.

The main algorithmic trade-off is between simplicity and fine-grained parallelism. A more aggressive implementation could try to split particles, probes, or Sinkhorn iterations across ranks. That might expose more parallel operations inside one task, but it would also introduce synchronization in every optimizer iteration and make correctness harder to explain. The selected design is conservative but appropriate for the course: it has clear decomposition, clear mapping, small communication, measured load balance, and deterministic serial-versus-MPI validation.

The auxiliary particle-count ablation adds one useful local-optimizer insight: increasing the number of particles can improve the discovered trajectory cost, but it is not the main evaluation criterion for this course. The project should still be judged primarily by its parallelization design, correctness, communication behavior, load balance, and speedup.

The main limitation is experiment scale. The local benchmark currently runs in seconds, not 2-3 minutes. Therefore, the report should not claim full compliance with the strict runtime-size requirement yet. The correct interpretation is:

- local MPI algorithm, correctness, artifact pipeline, plotting, and Ubuntu single-VM deployment are ready;
- larger `N` or multi-machine LAN experiments are still required for strict final timing and higher process counts.

For final submission, the priority is not to add many unrelated MPOT hyperparameter sweeps. The priority is to make the required parallel-computing evidence stronger: one larger `N` run, one granularity/load-balance chart at the chosen `N`, and one speedup chart with as many process counts as the available machines can honestly support.

---

## 11. Conclusion

This project turns MPOT-inspired motion planning into a clear parallel-computing benchmark. The system uses task-level exploratory parallelism, cyclic process assignment, SPMD execution, rank 0 coordination, blocking `bcast/scatter/gather`, and measured load-balance analysis. The local experiment demonstrates correct MPI behavior, low communication overhead, and meaningful speedup up to four processes.

The project is currently ready for local demonstration and Ubuntu single-VM smoke testing. Before final submission, the group should either run a larger local `N` or execute the planned multi-machine Ubuntu/LAN benchmark after teammate VMs pass local smoke tests. Any new results must be copied from real CSV/JSON/PNG artifacts into the report; no runtime or speedup values should be invented.

---

## 12. References

1. An T. Le, Georgia Chalvatzaki, Armin Biess, and Jan Peters. "Accelerating Motion Planning via Optimal Transport." Advances in Neural Information Processing Systems 36, NeurIPS 2023. https://proceedings.neurips.cc/paper_files/paper/2023/hash/f7a94134f1c726796c6f81fb946e489d-Abstract-Conference.html
2. An T. Le, Georgia Chalvatzaki, Armin Biess, and Jan Peters. "Accelerating Motion Planning via Optimal Transport." arXiv:2309.15970. https://arxiv.org/abs/2309.15970
3. Original MPOT source repository. https://github.com/anindex/mpot
4. Hanoi University of Science and Technology thesis/project template references were used as formatting guidance for cover-page style, numbered sections, figures, tables, and concise academic presentation. https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baiviet=35523
5. HUST thesis template on Overleaf, used only as structure guidance for Markdown-to-PDF polishing. https://www.overleaf.com/latex/templates/thesis-template-for-hanoi-university-of-science-and-technology/nfpspdwmgjmz

---

## Appendix A. Requirement Coverage

**Table 15. Course-rubric mapping.**

| Requirement | Project answer | Evidence |
|---|---|---|
| Parallel level | Task-level parallelism | Section 5.1 |
| Decomposition | Exploratory decomposition | Section 5.2 |
| Mapping | 1D cyclic, `task i -> rank i mod P` | Section 5.3 |
| Communication | SPMD, rank 0 coordinator, logical star, blocking `bcast/scatter/gather` | Section 5.4 |
| Complexity analysis | Local task, serial, parallel, communication, speedup, efficiency, and load-balance model | Section 6 |
| Load balancing | Per-rank compute/communication/idle timing, 25% threshold | Sections 5.8, 6.7, and 9.3 |
| Parallel pseudocode | Distributed MPOT with OpenMPI | Section 5.7 |
| Correctness | Serial/MPI task-level comparison | Section 9.1 |
| Runtime vs input size | `N = 208, 412, 824` at `P=4` | Section 9.2 |
| Granularity | Stacked rank timing at `N=412, P=4` | Section 9.3 |
| Speedup | `P = 1, 2, 4` at `N=824` | Section 9.4 |
| Auxiliary ablation | Particle-count trade-off on dense 2D variant | Section 9.6 |
| Final real figures | Runtime, speedup, rank timing, best path, algorithm trace, dense trace, particle ablation | Figures 1-7 |

---

## Appendix B. Remaining TODO Items

> TODO: Fill official cover-page metadata: school/faculty, group number, member names, student IDs, and instructor name.

> TODO: Export this Markdown report to PDF and manually verify the final length is between 10 and 20 pages, figures are readable, and tables do not overflow.

> TODO: If strict 2-3 minute runtime compliance is required, run a larger `N` and regenerate `report/tables/` and `report/figures/` from real artifacts.

> TODO: After teammate VMs pass local smoke tests, switch UTM networking to Bridged, verify LAN `ping`/`ssh`, generate a hostfile, and run the OpenMPI multi-machine benchmark.

> TODO: If LAN artifacts are produced, replace local-only runtime/speedup discussion with the new measured LAN tables and figures while keeping local results as preliminary validation.

---

## Appendix C. Demo Artifacts

Static PNG figures are used in the main report because exported PDF files cannot play GIF animations. The GIFs below are useful for oral presentation:

| Artifact | Path |
|---|---|
| Main trajectory GIF | `report/figures/trajectory_final_macbook_air_2d.gif` |
| Main algorithm trace GIF | `report/figures/algorithm_trace_final_macbook_air_2d.gif` |
| Narrow-passage trajectory GIF | `report/figures/trajectory_variant_narrow.gif` |
| Cluttered trajectory GIF | `report/figures/trajectory_variant_cluttered.gif` |
| Dense-sampling trajectory GIF | `report/figures/trajectory_variant_dense.gif` |
| Narrow-passage algorithm trace GIF | `report/figures/algorithm_trace_variant_narrow.gif` |
| Cluttered algorithm trace GIF | `report/figures/algorithm_trace_variant_cluttered.gif` |
| Dense-sampling algorithm trace GIF | `report/figures/algorithm_trace_variant_dense.gif` |
| Narrow-passage algorithm trace key frame | `report/figures/algorithm_trace_variant_narrow_keyframe.png` |
| Cluttered algorithm trace key frame | `report/figures/algorithm_trace_variant_cluttered_keyframe.png` |
| Dense-sampling algorithm trace key frame | `report/figures/algorithm_trace_variant_dense_keyframe.png` |
| Particle-count ablation table | `report/PARAMETER_ABLATION_particles_dense_N12.md` |
| Particle-count ablation figure | `report/figures/particle_ablation_dense_N12_P4.png` |

Detailed teammate ownership and defense preparation are maintained in `docs/team_ownership.md` and `report/MEMBER_DEFENSE_GUIDE.md`.
