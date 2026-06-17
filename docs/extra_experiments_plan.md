# Extra Experiments and Visualization Plan

This document answers a practical question for the final defense: after the
required parallel-computing experiments, what else is worth adding without
making the project too complex?

The short answer is: add only small experiments that help explain the parallel
design or make the MPOT behavior visible. Do not turn the project into a full
robotics hyperparameter study.

## Priority 1: Required Parallel-Computing Evidence

These are already the core of the report and should remain the main story.

| Experiment | Why it matters | Current status |
|---|---|---|
| Correctness: serial vs MPI | Proves the parallel version solves the same task set as the serial baseline | Measured for `final_macbook_air_2d`, `824/824` tasks matched |
| Runtime vs input size `N` | Answers the professor's input-size requirement | Measured for `N=208,412,824`; larger 2-3 minute `N` remains TODO |
| Load balance / granularity | Shows whether work is balanced across ranks | Measured at `N=412, P=4`; idle fraction is below 25% |
| Speedup | Shows parallel benefit as `P` increases | Measured for `P=1,2,4`; `P>=8` remains TODO until LAN or larger machine |
| Communication timing | Shows overhead of blocking `bcast/scatter/gather` | Measured from `comm_events.csv` and runtime with/without communication |

## Priority 2: Useful Additions Already Included

These additions make the demo and report stronger, but they should not replace
the required parallel-computing evidence.

| Addition | Why it is useful | Artifact |
|---|---|---|
| 2D problem variants | Shows the planner on easy, narrow-passage, cluttered, and dense obstacle layouts | `docs/problem_variants_2d.md` |
| Algorithm-trace GIFs | Shows MPOT-style particles changing across iterations, not just the final path | `report/figures/algorithm_trace_variant_dense.gif` |
| Static key frames for PDF | Makes the GIF evidence visible in a static report | `report/figures/algorithm_trace_variant_dense_keyframe.png` |
| Particle-count ablation | Shows the local MPOT quality/runtime trade-off in one small controlled setting | `report/PARAMETER_ABLATION_particles_dense_N12.md` |

## Priority 3: Good TODOs If There Is More Time

These are good extensions, but only after the current report remains clean and
the group can still explain the code.

| TODO experiment | When to run it | Why it helps |
|---|---|---|
| Larger `N` target | If the final report must strictly hit 2-3 minutes | Satisfies the professor's runtime-size target more directly |
| LAN hostfile benchmark | After teammate Ubuntu VMs pass local smoke | Shows true multi-machine MPI execution |
| `P=8` or `P=12/16` speedup | After LAN or a stronger machine is available | Extends the speedup curve beyond one MacBook |
| Mapping comparison: cyclic vs block | Only if implementation time remains | Would justify cyclic mapping empirically, but it is not required by the rubric |

## Experiments Not Recommended For This Course Submission

Avoid these unless the project is already finished and the team has extra time.

| Avoid | Reason |
|---|---|
| Large sweep over many MPOT hyperparameters | Too much robotics tuning; weak connection to parallel programming |
| 3D or Panda robot benchmark | Requires heavier dependencies and distracts from the 2D MPI story |
| GPU/CUDA comparison | The course project is CPU/OpenMPI-focused and teammates use Ubuntu VMs |
| Too many random visual demos | Makes the report noisy and hard to defend |
| Non-blocking MPI rewrite | More complex code for little benefit because communication is already coarse-grained |

## Recommended Defense Message

If asked why the report does not include a large MPOT hyperparameter study:

> The course focuses on parallel computing. We included one small particle-count
> ablation only to show the local optimizer's quality/runtime trade-off. The
> main evaluation remains correctness, runtime vs `N`, communication overhead,
> load balance, and speedup, because those directly evaluate the OpenMPI
> parallelization.

If asked what to run next:

> First run the same pipeline on teammate Ubuntu VMs with Bridged LAN and a
> hostfile. Then increase `N` until the runtime reaches the 2-3 minute target.
> Only after that should we consider optional mapping or MPOT-parameter
> ablations.
