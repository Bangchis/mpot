# Distributed MPOT Motion Planning with OpenMPI

**Parallel Computing / Parallel Programming Course Project**

**Draft date:** 2026-06-17  
**Status:** Academic report draft based on real local artifacts and owner
Ubuntu single-VM smoke artifacts. Multi-machine Ubuntu/LAN experiments are not
measured yet.

## Abstract

This project studies how Motion Planning via Optimal Transport (MPOT) can be
adapted into a course-level parallel computing project. The original MPOT
approach optimizes many trajectory particles with an optimal-transport-inspired
Sinkhorn update in order to search for good motion plans around obstacles. Our
project keeps the local MPOT optimizer as the planning kernel and adds an MPI
parallel layer outside the inner Sinkhorn loop.

The benchmark uses a two-dimensional point robot moving from a start state to a
goal state while avoiding circular obstacles. The parallel program uses
task-level parallelism: each MPI rank solves a subset of independent MPOT
planning tasks generated from deterministic random seeds. Tasks are assigned by
1D cyclic mapping, `task i -> rank i mod P`. Rank 0 coordinates setup, gathers
results and timing data, and reduces all task results to the best trajectory.

Local experiments on one machine show that the MPI version matches the serial
baseline exactly at the task level for `N=824`, achieves about `2.995x` speedup
with `P=4`, and satisfies the 25% load-balance threshold with idle fraction
about `0.00705`. The same code has also passed an Ubuntu ARM64 single-VM smoke
test with OpenMPI. The current local run is shorter than the professor's
suggested 2-3 minute target, so a larger-N or multi-machine Ubuntu/LAN run
should be executed later if strict timing compliance is required.

**Keywords:** motion planning, optimal transport, MPOT, MPI, OpenMPI, task-level
parallelism, exploratory decomposition, load balancing.

## 1. Introduction

Motion planning is the problem of finding a trajectory from a start state to a
goal state while avoiding obstacles and keeping the path smooth. It is a
challenging optimization problem because obstacles can create local minima. A
single optimizer run may find a poor route, collide with an obstacle, or fail to
discover an alternative path.

MPOT, short for Motion Planning via Optimal Transport, addresses this by
optimizing many trajectory particles. The method uses local candidate probes and
an entropic optimal transport step to move particles toward lower-cost states.
In the original repository, this batch nature is suitable for GPU acceleration.

The goal of this course project is different from the original MPOT paper. We do
not attempt to reproduce GPU performance. Instead, we build a CPU-only MPI
benchmark that demonstrates a clear parallel programming design. The key idea is
to run many independent MPOT planning attempts with different random seeds in
parallel. Each MPI process solves complete local MPOT tasks, and rank 0 selects
the best result.

The project contributions are:

- a simple 2D point-robot MPOT benchmark that can run on CPU;
- a serial baseline for correctness checking;
- an OpenMPI implementation using task-level exploratory parallelism;
- runtime, communication, load-balance, correctness, and speedup artifacts;
- qualitative trajectory and algorithm-trace GIFs for demonstration.

## 2. Background and Problem Definition

### 2.1 MPOT Background

The MPOT optimizer represents a candidate motion plan as a trajectory particle.
Instead of optimizing one path only, it initializes a batch of particles. Each
outer iteration evaluates local candidate probes around current trajectory
states, solves an entropic optimal transport problem with Sinkhorn iterations,
and updates particles through barycentric projection.

Conceptually, one MPOT run can be summarized as:

```text
initialize K trajectory particles
repeat:
    generate local probes around current particles
    evaluate obstacle, boundary, smoothness, and goal costs
    solve the entropic optimal transport problem
    update particles by barycentric projection
select the particle with the lowest full trajectory cost
```

The important property for this project is that MPOT benefits from exploration.
Different initial particles or random seeds can discover different route modes
around obstacles. This makes MPOT a natural fit for exploratory task-level
parallelism.

### 2.2 2D Planning Problem

The benchmark uses a point robot in a bounded 2D workspace. A state is

```text
x = [px, py, vx, vy]
```

where `(px, py)` is position and `(vx, vy)` is velocity. A trajectory is a
sequence of states:

```text
X = [x_0, x_1, ..., x_T].
```

The start and goal states are fixed by the experiment configuration. Obstacles
are circles. A trajectory is considered good when it reaches the goal, avoids
hard collisions, stays inside the workspace, and remains smooth.

The trajectory cost is:

```text
J(X) =
  w_obs    * obstacle_penalty(X)
+ w_bound  * boundary_penalty(X)
+ w_smooth * smoothness_penalty(X)
+ w_goal   * goal_error(X)
+ w_vel    * velocity_penalty(X)
```

Lower cost means a better trajectory.

### 2.3 One Planning Task

One planning task is one complete MPOT optimization run with one deterministic
seed. The task receives the shared configuration and seed, initializes MPOT
particles, runs the local optimizer, evaluates all final particles, and returns
the best trajectory for that seed.

Mathematically:

```text
Y_i = F(config, seed_i)
```

where `Y_i` contains the best cost, best trajectory, task id, seed, rank, and
timing for task `i`.

### 2.4 Input Parameters of the Parallel Algorithm

The parallel algorithm has four groups of input parameters. Separating them is
important because only some parameters belong to MPI; the rest define the
motion-planning problem and the local MPOT optimizer executed by each task.

**Problem parameters.** These describe the 2D planning instance: workspace
bounds, start state, goal state, circular obstacles, trajectory length `T`, time
step `dt`, and cost weights for obstacle avoidance, boundary violation,
smoothness, goal error, and velocity. These values define the objective
function `J(X)` and are shared by every MPI rank.

**Local MPOT optimizer parameters.** These control how one planning task is
solved: number of particles `K`, maximum outer iterations `L`, maximum Sinkhorn
iterations `H`, local probe radius, polytope/candidate count, convergence
tolerance, and deterministic seed `seed_i`. The seed is different for each task
so that the tasks explore different trajectory modes around obstacles.

**Parallel execution parameters.** These define how the independent tasks are
distributed: total task count `N`, MPI process count `P`, rank id `r`, mapping
rule `owner(i) = i mod P`, and the local task subset `D_r` assigned to each
rank. In the experiments, `N` is the main input size used for runtime and
speedup plots.

**Measurement and reduction parameters.** These do not change the planner
itself, but they are needed for the report: per-rank compute time,
communication time, idle time, total runtime, and communication events. Each
task returns:

```text
Y_i = (task_id, seed_i, best_cost, best_trajectory, runtime, rank)
```

Rank 0 gathers all `Y_i` values and selects the distributed answer:

```text
Y* = argmin_i (Y_i.best_cost, Y_i.task_id, Y_i.seed_i)
```

Therefore, the mathematical input of the parallel experiment is not just
`N` and `P`. It is the tuple:

```text
(problem_config, optimizer_config, N, P, mapping_rule)
```

where `problem_config` and `optimizer_config` are broadcast to all ranks, while
the task subsets `D_r` are scattered according to the mapping rule.

## 3. Serial Algorithm

The serial baseline evaluates all tasks sequentially. It is the correctness
reference for the parallel implementation.

```text
Algorithm 1: Serial MPOT Baseline

Input:
    config, N
Output:
    global best result Y*

1. Create deterministic task list D = [(0, seed_0), ..., (N-1, seed_{N-1})].
2. Initialize results = empty list.
3. For each task (i, seed_i) in D:
       Y_i = LocalMPOTTask(config, i, seed_i)
       Append Y_i to results.
4. Select:
       Y* = argmin_i (Y_i.best_cost, Y_i.task_id, Y_i.seed)
5. Return Y* and all task results.
```

The serial runtime is approximately:

```text
T_1 = sum_i T_task(i)
```

## 4. Parallel Algorithm Design

### 4.1 Parallel Level

The project uses **task-level parallelism**. Each task is one complete MPOT run
with one deterministic seed. Two different tasks do not share intermediate
optimizer state:

```text
Y_i does not read Y_j, for i != j.
```

Therefore, evaluating all tasks is an embarrassingly parallel stage followed by
a deterministic reduction.

### 4.2 Decomposition Technique

The decomposition technique is **exploratory decomposition**. Each process
explores a different subset of random seeds. This matches the MPOT idea because
different seeds may generate different particle initializations and discover
different motion modes around obstacles.

This is not data decomposition over a matrix or image. The input size `N` is the
number of independent planning attempts. The computational work is divided by
planning tasks.

### 4.3 Mapping Technique

Tasks are assigned to ranks by **1D cyclic mapping**:

```text
owner(i) = i mod P
D_r = { task i | owner(i) = r }
```

where `P` is the number of MPI processes and `D_r` is the task subset assigned
to rank `r`.

Cyclic mapping is selected because task runtimes can vary by seed. A contiguous
block assignment may accidentally place several expensive seeds on one rank.
Cyclic mapping spreads tasks more evenly while remaining deterministic and easy
to explain in the report.

### 4.4 Communication Strategy and Topology

The MPI program uses the SPMD model: every rank starts the same program, and the
rank id determines the role. Rank 0 is the coordinator. The logical topology is
a star centered at rank 0.

The program uses blocking collectives:

| Phase | Collective | Purpose |
|---|---|---|
| Setup | `bcast` | Rank 0 sends config, run id, and assignment metadata. |
| Distribution | `scatter` | Rank 0 sends task subset `D_r` to each rank. |
| Collection | `gather` | Ranks return task results, timing data, and communication logs. |

Blocking communication is chosen because communication occurs only at coarse
boundaries. During local MPOT optimization, ranks do not communicate. This keeps
the communication-to-computation ratio favorable and makes the implementation
easy to measure.

### 4.5 Why Not Split The Sinkhorn Loop?

MPOT contains several possible parallelization levels, but not all are suitable
for multi-process OpenMPI over LAN or virtual machines.

| Candidate level | Decision | Reason |
|---|---|---|
| Independent MPOT seed/task | Use MPI | Tasks are independent and coarse-grained. |
| Particle batch inside one task | Keep local | Particles interact through batch objective and Sinkhorn state. |
| Waypoints inside one trajectory | Keep local | Smoothness couples neighboring waypoints. |
| Probe evaluation | Keep local | Vectorized PyTorch work is small compared with LAN communication. |
| Sinkhorn inner iterations | Keep local | Iterations depend on current dual variables and require repeated synchronization. |
| Final best-result reduction | Use MPI gather/reduction | Results are compact and cheap to collect. |

Thus, the MPI layer is added outside the inner MPOT optimizer. This design keeps
the original local MPOT algorithm intact and parallelizes the independent
exploration attempts around it.

### 4.6 Parallel Pseudocode

```text
Algorithm 2: Distributed MPOT with OpenMPI

Input:
    config on rank 0, number of tasks N, number of ranks P
Output:
    global best result Y* on rank 0

1. MPI starts ranks r = 0, 1, ..., P-1.
2. If r == 0:
       create task list D = [(0, seed_0), ..., (N-1, seed_{N-1})]
       create cyclic chunks D_r = {i | i mod P = r}
3. Broadcast config and assignment metadata from rank 0.
4. Scatter task chunks so each rank receives D_r.
5. Each rank runs LocalMPOTTask for every task in D_r.
6. Each rank records compute time, communication time, and local results.
7. Gather local task results and rank timing records to rank 0.
8. Rank 0 computes:
       Y* = argmin_i (Y_i.best_cost, Y_i.task_id, Y_i.seed)
9. Rank 0 writes summaries, plots, timing tables, and validation artifacts.
```

### 4.7 Load Balancing

Load balancing is measured, not assumed. Each MPI run records compute time,
communication time, total time, task count, and idle time per rank.

For the course threshold:

```text
idle_fraction <= 0.25
```

If the idle fraction is larger than 25%, the task granularity should be
adjusted. For task-level parallelism, the first fix is to increase `N` so every
rank receives more tasks. The current local-final experiment satisfies the
threshold.

## 5. Implementation Overview

The implementation is organized around one shared local task runner. The serial
and MPI programs both call the same local MPOT task function. This is important
for correctness: the parallel version is not a different optimizer. It only
changes where tasks are executed.

The main implementation responsibilities are:

- define the 2D problem and trajectory cost;
- run one local MPOT task from a deterministic seed;
- build the serial baseline;
- distribute tasks and gather results with MPI;
- write timing, assignment, correctness, and result artifacts;
- generate plots and GIFs from real output files.

The project also includes qualitative 2D variants with more obstacles. These
variants are useful for demonstration, but the main runtime and speedup tables
use one consistent benchmark configuration. The dense qualitative variant uses
ten obstacles, more trajectory particles, and more probe samples per direction
so the MPOT iteration trace is easier to see in a GIF demo.

## 6. Experimental Setup

The current measured results are from one local macOS machine using multiple MPI
processes. This is the local-first stage of the project. The same MPI design can
later be deployed on multiple Ubuntu virtual machines connected through LAN.

The main benchmark configuration uses:

- 2D point robot;
- circular obstacles;
- CPU-only execution;
- process counts `P = 1, 2, 4`;
- input sizes `N = 208, 412, 824`.

The local experiment is sufficient to verify correctness, artifact generation,
MPI communication, load balance, and speedup behavior. However, it is shorter
than the professor's suggested 2-3 minute runtime target. A larger `N` or
Ubuntu/LAN run should be used later if strict timing compliance is required.

The first Ubuntu deployment smoke was run on the owner's ARM64 VM `mpot-a`.
This is not the final multi-machine LAN benchmark. Its purpose is to prove that
the repo, Python environment, OpenMPI launcher, serial baseline, MPI runner, and
comparison script work inside Ubuntu before teammates connect their machines.
The evidence copied back into the repo is:

```text
results/ubuntu_vm_single/setup_doctor_ubuntu_vm_single.json
report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md
results/ubuntu_vm_single/compare-ubuntu-single-N4-P2/correctness_report.json
results/ubuntu_vm_single/compare-ubuntu-single-N8-P4/correctness_report.json
```

The smoke results were:

| Check | Result |
|---|---:|
| Setup doctor | ready: True |
| N=4, P=2 serial/MPI comparison | pass |
| N=4, P=2 best cost difference | 0.0 |
| N=8, P=4 serial/MPI comparison | pass |
| N=8, P=4 best cost difference | 0.0 |

## 7. Results

All numbers in this section are generated from real local artifacts under the
label `final_macbook_air_2d`.

The Ubuntu single-VM artifacts are used as deployment-readiness evidence only.
They are not claimed as the final multi-machine LAN speedup experiment.

### 7.1 Correctness

For `N=824` and `P=4`, the serial and MPI results matched exactly at the
task-comparison level:

| Metric | Result |
|---|---:|
| Compared tasks | 824 |
| Same best task | yes |
| Same best seed | yes |
| Best cost difference | 0.0 |
| Task-level comparison | pass |

The saved best MPI trajectory also passed the solution-quality check:

| Metric | Result |
|---|---:|
| Best task id | 184 |
| Best seed | 20260801 |
| Best cost | 0.00520871 |
| Goal error | 3.37e-08 |
| Hard collision fraction | 0.0 |

### 7.2 Runtime Versus Input Size

At `P=4`, runtime increased with `N` as expected:

| N | Runtime with communication (s) | Runtime without communication (s) |
|---:|---:|---:|
| 208 | 2.86270 | 2.85861 |
| 412 | 4.91507 | 4.87856 |
| 824 | 9.31508 | 9.27704 |

The corresponding figure is `runtime_vs_input_size_final_macbook_air_2d.png`.

### 7.3 Granularity and Load Balance

The load-balance experiment used `N=412`, `P=4`. Each rank received 103 tasks.

| Metric | Result |
|---|---:|
| Idle fraction | 0.00705028 |
| Threshold | 0.25 |
| Balanced under threshold | yes |
| Communication fraction of slowest rank | 0.0110326 |

This indicates that the current granularity is acceptable for the local run.

### 7.4 Speedup

For `N=824`, the measured speedup was:

| Processes | Runtime with communication (s) | Speedup | Efficiency |
|---:|---:|---:|---:|
| 1 | 27.9028 | 1.00000 | 1.00000 |
| 2 | 14.7543 | 1.89117 | 0.945584 |
| 4 | 9.31508 | 2.99545 | 0.748862 |

The `P=4` run achieved about `2.995x` speedup with communication included.

### 7.5 Qualitative Visualizations

The project generated trajectory replay GIFs and MPOT algorithm-trace GIFs.
The algorithm trace is useful because it shows the trajectory particles changing
over optimization iterations, not only the final path.

Additional 2D variants were run for visualization:

| Variant | Obstacles | Purpose |
|---|---:|---|
| narrow passage | 4 | show planning through a tighter passage |
| cluttered | 6 | show planning behavior with many obstacles |
| dense sampling | 10 | show a clearer MPOT trace with more particles and probe samples |

These visual artifacts are for explanation and presentation. They are not used
as the main speedup data.

## 8. Discussion

The results support the task-level MPI design. The `P=4` run is faster than the
`P=1` run, and the correctness check confirms that distributing tasks does not
change the selected best trajectory. The communication overhead is small because
the program communicates only at setup and collection boundaries.

The load-balance result also supports the choice of cyclic mapping. Since each
rank received the same number of tasks and the idle fraction was far below 25%,
the workload was balanced enough for the measured local run. If future larger
experiments show imbalance, the natural adjustment is to increase the number of
tasks or tune the task granularity.

The largest limitation is that the current local run is shorter than the
suggested 2-3 minute runtime target. The local result is still valuable because
it proves the correctness, timing, communication, plotting, and validation
pipeline. It should be presented honestly as the local-first result. A stricter
final experiment should use larger `N` or the Ubuntu/LAN setup.

## 9. Conclusion

This project adapts MPOT into a clear MPI parallel-programming benchmark. The
local MPOT optimizer remains unchanged as the planning kernel, while OpenMPI
parallelizes independent seed-level planning attempts. The chosen design is
task-level, exploratory, cyclically mapped, and coordinated by rank 0 using
blocking collectives.

The local-final experiment demonstrates correctness against the serial baseline,
useful speedup up to `P=4`, low communication overhead, and good load balance.
The remaining work is to run a larger-N or multi-machine Ubuntu/LAN experiment
if strict 2-3 minute runtime compliance is required, then convert this Markdown
draft into the final LaTeX/Overleaf report.

## References

1. An T. Le, Georgia Chalvatzaki, Armin Biess, and Jan Peters. "Accelerating
   Motion Planning via Optimal Transport." NeurIPS 2023.
2. MPOT repository README and source code in this project.
3. HUST official thesis/project template notice and course report templates
   were used only as formatting guidance for the academic report structure.
