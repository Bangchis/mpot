# Solution Quality Validation

This validation checks the saved best trajectory against the 2D planning problem.

- run_id: `mpi-mini_sweep-N2-P2`
- mode: `mpi`
- verdict: **PASS**
- best_task_id: `0`
- best_seed: `20260617`
- best_cost: `0.00905869`
- start_error: `3.37175e-08`
- goal_error: `3.37175e-08`
- hard_collision_fraction: `0`
- max_bounds_violation: `0`

## Checks

| status | check | detail |
|---|---|---|
| PASS | trajectory exists | `states=24` |
| PASS | trajectory length matches problem | `observed=24, expected=24` |
| PASS | trajectory values are finite | `finite values required` |
| PASS | best cost is finite | `best_cost=0.009058685973286629` |
| PASS | start state is respected | `start_error=3.371747884011707e-08, tolerance=0.001` |
| PASS | goal state is reached | `goal_error=3.371747884011707e-08, tolerance=0.001` |
| PASS | hard obstacle collision fraction is acceptable | `collision_fraction=0.0, max=0.0` |
| PASS | trajectory stays inside workspace bounds | `max_bounds_violation=0.0, tolerance=1e-06` |

Derived only from saved summary.json and task_results.json artifacts.
