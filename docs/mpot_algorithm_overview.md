# MPOT Algorithm and MPI Parallelization Overview

## Abstract

Motion Planning via Optimal Transport (MPOT) is a sampling-based trajectory
optimization method that searches for low-cost robot motions by maintaining many
candidate trajectories and improving them through optimal-transport-inspired
updates. The original MPOT project is designed for high-throughput PyTorch/GPU
execution: many samples are optimized in batch so the planner can discover
multiple possible motion modes and avoid being trapped by one poor local
minimum.

This course project keeps the main MPOT idea but changes the execution model for
a Parallel Computing / Parallel Programming project. The local planner solves a
2D point-robot problem on CPU. The distributed planner uses Open MPI through
`mpi4py` to run many independent MPOT planning tasks across processes, and later
across multiple Ubuntu virtual machines on different MacBooks. The
parallelization is outside the inner Sinkhorn update: each MPI rank runs complete
MPOT tasks for different random seeds, then rank 0 gathers results and selects
the best trajectory.

For line-by-line mathematical pseudocode, use
`docs/mpot_parallel_algorithm_spec.md`. This overview explains the ideas; the
algorithm specification is the shorter report-ready reference for serial MPOT
and distributed OpenMPI MPOT.

## 1. What Problem MPOT Solves

The input to motion planning is a robot start state, a goal state, and an
environment containing obstacles. The output is a trajectory, meaning an ordered
sequence of robot states from start to goal.

In this project, the graded benchmark is intentionally 2D:

- Robot type: point robot.
- State: `[x, y, vx, vy]`.
- Obstacles: circles in a bounded 2D workspace.
- Trajectory: `T` states from start to goal.
- Objective: minimize collision, boundary, smoothness, velocity, and goal costs.

The original MPOT repository can target more complex examples, including
occupancy maps, signed distance fields, and robot arms. For the course deadline,
the project uses only the 2D CPU benchmark so every member can understand and
defend the algorithm.

## 2. Original MPOT Algorithm

### 2.1 Core Idea

MPOT treats motion planning as batch trajectory optimization. Instead of
optimizing only one trajectory, it initializes many candidate trajectories, also
called particles. Each particle is a complete possible motion from start to goal.
The planner repeatedly improves the particles using local probes and an
entropic optimal transport solver.

The main intuition is:

- Many particles increase the chance of finding different homotopy classes or
  route shapes around obstacles.
- Local probes ask, for each trajectory state, which nearby candidate direction
  looks cheaper.
- Optimal transport gives a smooth assignment from current states to improved
  local candidate states.
- The best final trajectory is selected by evaluating the full trajectory cost.

### 2.2 Main Components

| Component | Purpose |
|---|---|
| Gaussian-process trajectory prior | Generates smooth initial trajectory particles. |
| Objective function | Scores local probes and full trajectories. |
| Polytope probes | Samples local directions around each current state. |
| Sinkhorn solver | Solves the entropic optimal transport subproblem. |
| Barycentric projection | Converts the transport plan into updated trajectory states. |
| Convergence rule | Stops the outer loop when updates become small or max iterations is reached. |

### 2.3 Conceptual Steps of Original MPOT

1. Define the robot state space, start state, goal state, trajectory length, and
   cost function.
2. Generate many initial trajectory particles from a smooth Gaussian-process
   prior.
3. Fix the start state and, when configured, the goal state.
4. Repeat for several outer optimization iterations:
   - Normalize position and velocity values for stable local search.
   - Around each current trajectory state, generate polytope-based local
     candidate probes.
   - Evaluate the objective cost of those probes.
   - Build an entropic optimal transport problem from the local cost matrix.
   - Solve the transport problem with Sinkhorn iterations.
   - Use barycentric projection to update trajectory states.
   - Restore fixed start and goal constraints.
   - Check convergence.
5. Evaluate all optimized trajectories with the full trajectory cost.
6. Return the trajectory with the lowest cost.

### 2.4 Where Optimal Transport Appears

The optimal transport part does not directly move the robot through the
environment. Instead, it is used inside the optimizer to decide how the current
set of trajectory states should be shifted toward locally better candidate
states. Entropic regularization makes the transport problem smoother and easier
to solve with Sinkhorn iterations.

For defense, a short explanation is:

> MPOT uses optimal transport as an optimizer update rule. The robot path is
> represented by many trajectory particles. At each iteration, the planner
> samples nearby candidate states, scores them, solves a Sinkhorn optimal
> transport problem, and moves the particles toward lower-cost candidates.

## 3. MPOT Variant Used in This Course Project

The project uses the original MPOT planner core with a simplified 2D benchmark
objective. The reason is practical: the course grading focuses on
parallelization, correctness, timing, and explanation, not on reproducing the
full robotics stack of the paper.

### 3.1 Simplifications

| Original repository direction | Course project direction |
|---|---|
| GPU-oriented PyTorch execution | CPU-only execution for local and Ubuntu VM runs. |
| More complex robotics examples | 2D point-robot planning only. |
| Batch planning can exploit GPU parallelism | MPI process-level parallelism across independent tasks. |
| Visualization demos for robotics examples | Report figures, trajectory GIFs, and MPOT iteration trace GIFs. |

### 3.2 One Local Planning Task

One task is one complete MPOT run with one deterministic random seed. A task:

1. Builds the 2D planning problem from a JSON config.
2. Constructs the MPOT planner and the 2D objective.
3. Initializes trajectory particles using the task seed.
4. Runs the MPOT outer optimization loop.
5. Scores all optimized particles.
6. Returns the best trajectory, best cost, collision fraction, iteration count,
   runtime, and seed metadata.

This task is the basic unit used by both serial and MPI execution.

### 3.3 Serial Baseline

The serial baseline runs the same task list sequentially on one process. It is
important because it defines correctness for the MPI version:

- Same config.
- Same task ids.
- Same deterministic seeds.
- Same local MPOT task implementation.
- Same best-selection rule.

The parallel version is considered correct when it produces the same per-task
results as the serial baseline, up to the configured numerical tolerance.

## 4. Why MPOT Is Suitable for MPI Parallelization

MPOT-style planning naturally produces many independent attempts because
different random seeds can explore different trajectory modes. This makes the
algorithm suitable for exploratory decomposition:

- Task 0 may search one set of initial particles.
- Task 1 may search another set of initial particles.
- Tasks do not need to exchange data during MPOT optimization.
- The final result is chosen by reducing all task results to the best cost.

The course project therefore parallelizes across tasks, not inside one
Sinkhorn iteration. This is a conservative and explainable design for multiple
machines because it keeps communication low.

For the full dependency analysis and the reason other MPOT levels are not split
with MPI, see `docs/mpot_parallel_algorithm_spec.md`.

## 5. MPI/OpenMPI Parallel Algorithm

### 5.1 Parallel Level

The project uses task-level parallelism. Each MPI process executes complete
planning tasks. The task granularity is coarse: one task includes the full MPOT
optimization loop for one seed.

### 5.2 Decomposition Technique

The decomposition is exploratory decomposition. The planner launches many
independent searches from different random seeds. Each search may discover a
different route around obstacles. Parallel execution allows several searches to
run at the same time.

### 5.3 Mapping Technique

Tasks are mapped to MPI ranks by 1D cyclic mapping:

| Task id | Assigned rank |
|---:|---:|
| `0` | `0 mod P` |
| `1` | `1 mod P` |
| `2` | `2 mod P` |
| `i` | `i mod P` |

Here `P` is the number of MPI processes. Cyclic mapping is easier to balance
than one large block per rank when individual task runtimes vary by seed.

### 5.4 Communication Strategy

The MPI program follows an SPMD model: every process starts the same program,
but each rank takes a different role based on its rank id.

Rank 0 is the coordinator:

- Reads the config.
- Creates the deterministic task list.
- Computes the cyclic assignment.
- Broadcasts shared metadata.
- Scatters task chunks.
- Gathers results, rank timings, and communication events.
- Selects the global best trajectory.
- Writes report artifacts.

Ranks 1 to `P-1` are workers:

- Receive the config and local task chunk.
- Run MPOT tasks independently.
- Return task results and timing data to rank 0.

The logical communication topology is a star centered at rank 0. The current
implementation uses blocking collectives:

| Phase | Collective | Purpose |
|---|---|---|
| Setup | `bcast` | Send config, run id, and assignment metadata from rank 0. |
| Work distribution | `scatter` | Send each rank its local task list. |
| Result collection | `gather` | Collect task results from all ranks. |
| Timing collection | `gather` | Collect compute and communication timings. |
| Communication audit | `gather` | Collect communication event logs. |

There is no communication inside the MPOT outer iterations. This choice is
intentional: if every Sinkhorn update communicated across machines, network
latency would dominate the small 2D CPU benchmark. Coarse-grained task
parallelism gives better communication-to-computation ratio.

### 5.5 Conceptual Steps of Distributed MPOT

1. OpenMPI launches `P` ranks, possibly across several Ubuntu VMs.
2. Rank 0 loads the experiment config and creates `N` planning tasks.
3. Rank 0 assigns task `i` to rank `i mod P`.
4. Rank 0 broadcasts the shared config and assignment metadata.
5. Rank 0 scatters local task lists to all ranks.
6. Each rank runs the original local MPOT algorithm for every assigned seed.
7. Each rank records compute time, communication time, hostname, and local best
   result.
8. Rank 0 gathers all task results and rank timings.
9. Rank 0 reduces all task results by best cost.
10. Rank 0 writes CSV/JSON/PNG/GIF artifacts for correctness, timing, plots,
    and report synchronization.

## 6. What Is Parallelized and What Is Not

| Part of algorithm | Parallelized by MPI? | Reason |
|---|---|---|
| Different random-seed planning tasks | Yes | Tasks are independent and coarse-grained. |
| Different MPI ranks across machines | Yes | OpenMPI starts ranks on each Ubuntu VM. |
| Best-result reduction | Yes, via gather then rank 0 selection | Results are compact and easy to compare. |
| Individual Sinkhorn iterations inside one task | No | Fine-grained communication would be expensive on LAN/Wi-Fi. |
| Torch tensor operations inside one local task | No MPI-level split | Kept local and simple for course explanation. |
| Report plotting and artifact writing | Only rank 0 | Avoids file conflicts and duplicate outputs. |

This distinction is important for the professor's question "where is the
parallelization applied?" The answer is:

> We parallelize at the outer task level. Each task is a full MPOT planning run
> with one seed. We do not split one Sinkhorn update across MPI ranks. This keeps
> communication low and makes the correctness check straightforward.

## 7. Multi-Machine OpenMPI Execution

On one machine, OpenMPI can launch several ranks locally. On multiple machines,
OpenMPI launches ranks through SSH using a hostfile. The algorithm does not
change between local and multi-machine runs. Only the rank placement changes.

For a multi-machine run:

- Every Ubuntu VM has the same repository path and Python environment.
- Passwordless SSH works between machines.
- OpenMPI receives a hostfile listing each VM and the available slots.
- MPI assigns rank ids across the listed hosts.
- The same 1D cyclic mapping assigns tasks to rank ids.

The important point is that MPI rank ids are logical. A task is assigned to a
rank, and OpenMPI decides which physical VM hosts that rank.

## 8. Correctness Argument

The distributed algorithm should produce the same task-level results as the
serial baseline because the local task implementation is shared.

The correctness check compares:

- Task ids.
- Seeds.
- Best costs.
- Best trajectory metadata.
- Selected global best task.

If the serial and MPI runs use the same config and deterministic seed list, then
MPI scheduling should not change the mathematical result. MPI only changes when
tasks are executed, not what each task computes.

## 9. Performance Argument

Let `N` be the number of independent planning tasks and `P` be the number of MPI
processes.

In the serial baseline, the wall time is approximately the sum of all task
runtimes. In the MPI version, the wall time is approximately the maximum local
rank compute time plus communication overhead:

- More ranks can reduce compute time when `N` is large enough.
- Communication overhead is small because data is exchanged mainly at the start
  and end of the run.
- Load balance depends on how evenly task runtimes are distributed across
  ranks.
- Cyclic mapping helps when different random seeds have different runtimes.

The report measures:

- Runtime versus input size `N`.
- Runtime with communication time.
- Runtime without communication time.
- Per-rank compute and communication time.
- Load imbalance threshold of 25 percent.
- Speedup for process counts `1, 2, 4, 8, ...` where hardware allows.

## 10. How To Explain This in Defense

Short answer:

> MPOT optimizes many trajectory particles using Sinkhorn optimal transport
> updates. Our project keeps that local planner and parallelizes outside it:
> many complete MPOT runs with different random seeds are distributed across MPI
> ranks. Rank 0 sends tasks, ranks compute independently, and rank 0 gathers
> results to select the best trajectory.

If asked "why not parallelize Sinkhorn itself?":

> We chose coarse-grained task parallelism because each planning task is
> independent and has enough computation to justify MPI communication. Splitting
> every Sinkhorn iteration across machines would create frequent small
> communications, which is not suitable for LAN/Wi-Fi and is harder to explain
> correctly within the course deadline.

If asked "what does OpenMPI do here?":

> OpenMPI starts multiple Python processes as MPI ranks, either on one machine
> or across several Ubuntu VMs. The program uses blocking broadcast, scatter,
> and gather collectives so ranks can receive tasks and return results.

If asked "what proves the parallel result is correct?":

> The serial and MPI versions share the same local task runner. We compare runs
> task by task using the same config and seeds. If task ids, seeds, costs, and
> selected best result match within tolerance, the parallel version is correct.

## 11. Implementation Traceability

| Concept | Repository location |
|---|---|
| Original MPOT planner core | `mpot/planner.py` |
| Sinkhorn optimizer | `mpot/ot/sinkhorn.py`, `mpot/ot/sinkhorn_step.py` |
| 2D planning problem and cost | `mpot/benchmarks/problem_2d.py` |
| One local MPOT task | `mpot/benchmarks/local_runner.py` |
| Task list and cyclic mapping | `mpot/benchmarks/mpi_scheduler.py` |
| MPI orchestration | `mpot/benchmarks/mpi_runner.py` |
| Serial entrypoint | `scripts/run_serial.py` |
| MPI entrypoint | `scripts/run_mpi.py` |
| Correctness comparison | `scripts/compare_serial_mpi.py`, `mpot/benchmarks/correctness.py` |
| Communication analysis | `scripts/analyze_communication.py`, `mpot/benchmarks/communication.py` |
| Algorithm trace GIF | `scripts/animate_algorithm_trace.py`, `mpot/benchmarks/animation.py` |
