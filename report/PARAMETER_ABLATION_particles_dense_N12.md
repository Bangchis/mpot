# Particle-Count Ablation for Dense 2D Variant

This small auxiliary ablation is generated from real MPI summaries. It is not part of the core speedup claim; it is used only to explain the trade-off between local MPOT exploration and runtime.

- config: `configs/variant_dense_sampling_2d.json`
- process count: `P=4`
- input size: `N=12` tasks
- varied parameter: `optimizer.num_particles`

| num_particles | runtime_with_comm_s | runtime_without_comm_s | comm_overhead_s | best_cost | best_task_id | best_seed | source |
|---:|---:|---:|---:|---:|---:|---:|---|
| 8 | 1.502928 | 1.501591 | 0.001337 | 0.00395729 | 0 | 20260617 | `report/artifacts/particle_ablation_dense_N12/mpi-ablation_particles8_dense-N12-P4/summary.json` |
| 16 | 1.069814 | 1.069011 | 0.000803 | 0.00383398 | 8 | 20260625 | `report/artifacts/particle_ablation_dense_N12/mpi-ablation_particles16_dense-N12-P4/summary.json` |
| 24 | 1.185440 | 1.184960 | 0.000480 | 0.00370045 | 10 | 20260627 | `report/artifacts/particle_ablation_dense_N12/mpi-ablation_particles24_dense-N12-P4/summary.json` |

Interpretation: increasing particles makes each local task more expensive but may improve the best discovered trajectory. This is a local MPOT quality/runtime trade-off, not a different parallelization strategy.
