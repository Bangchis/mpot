# Final Experiment Audit

This file is generated from real local artifacts. Use it as a checklist
before copying experiment claims into the final report.

- created_at: `2026-06-17 06:48:27 +0700`
- label: `mini_sweep`
- verdict: **PASS**
- N for runtime/load-balance: `2`
- 2N for speedup/correctness: `2`
- final_processes: `2`
- failed_checks: `0`

## Checks

| status | check | detail |
|---|---|---|
| PASS | serial summaries exist | `count=1` |
| PASS | MPI summaries exist | `count=2` |
| PASS | runtime-vs-N input sizes are present at final process count | `expected=[2], found_for_P2=[2]` |
| PASS | serial baselines are present for expected input sizes | `expected=[2]` |
| PASS | speedup input size has requested process counts | `N=2, expected=[1, 2], found=[1, 2]` |
| PASS | speedup has P=1 MPI baseline | `N=2, found=[1, 2]` |
| PASS | correctness serial run exists | `N=2` |
| PASS | correctness MPI run exists | `N=2, P=2` |
| PASS | serial/MPI correctness passed | `passed=True, task_level=True` |
| PASS | solution quality passed | `passed=True, num_failed=0, goal_error=3.371747884011707e-08, hard_collision_fraction=0.0` |
| PASS | MPI communication events CSV exists | `results/mpi-mini_sweep-N2-P2/comm_events.csv` |
| PASS | communication analysis passed | `has_expected_collectives=True, all_events_blocking=True, observed=['bcast', 'gather', 'scatter']` |
| PASS | MPI task assignment CSV exists | `results/mpi-mini_sweep-N2-P2/task_assignment.csv` |
| PASS | granularity under 25 percent threshold | `idle_fraction=7.60542324117304e-05, threshold=0.25` |
| PASS | runtime-vs-N figure exists | `report/figures/runtime_vs_input_size_mini_sweep.png` |
| PASS | speedup figure exists | `report/figures/speedup_mini_sweep.png` |
| PASS | rank time breakdown figure exists | `report/figures/mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png` |
| PASS | report artifact bundle manifest exists | `report/artifacts/mini_sweep/manifest.json` |
| PASS | result tables have rows | `{'num_runtime_rows': 3, 'num_speedup_rows': 2, 'num_load_balance_rows': 2}` |
| PASS | results summary exists | `report/RESULTS_SUMMARY_mini_sweep.json` |
| PASS | environment capture exists | `results/environment-mini_sweep.json` |
| PASS | team ownership report passed | `passed=True, num_members=4, minimum=250, recommended_max=700, member_lines={'Member A': 513, 'Member B': 519, 'Member C': 496, 'Member D': 665}` |
| PASS | member defense guide passed | `passed=True, num_members=4, member_files=[4, 5, 5, 5]` |
| PASS | experiment index exists | `report/EXPERIMENT_INDEX_mini_sweep.json` |
| PASS | pipeline validation passed | `passed=True, num_failed=0` |
| PASS | benchmark plan exists | `report/BENCHMARK_PLAN.json` |

## Important Artifacts

| artifact | path |
|---|---|
| correctness_report | `results/compare-mini_sweep-N2-P2/correctness_report.json` |
| solution_quality_report | `results/solution-quality-mini_sweep-N2-P2.json` |
| communication_report | `results/communication-mini_sweep-N2-P2.json` |
| granularity_report | `results/granularity-mini_sweep-N2-P2.json` |
| validation_report | `results/validation-mini_sweep-N2-P2.json` |
| bundle_manifest | `report/artifacts/mini_sweep/manifest.json` |
| tables_manifest | `report/tables/tables_manifest_mini_sweep.json` |
| results_summary | `report/RESULTS_SUMMARY_mini_sweep.json` |
| environment_json | `results/environment-mini_sweep.json` |
| ownership_report | `report/TEAM_OWNERSHIP_REPORT.json` |
| defense_guide | `report/MEMBER_DEFENSE_GUIDE.json` |
| experiment_index | `report/EXPERIMENT_INDEX_mini_sweep.json` |
| runtime_figure | `report/figures/runtime_vs_input_size_mini_sweep.png` |
| speedup_figure | `report/figures/speedup_mini_sweep.png` |
| comm_events_csv | `results/mpi-mini_sweep-N2-P2/comm_events.csv` |
| task_assignment_csv | `results/mpi-mini_sweep-N2-P2/task_assignment.csv` |
| rank_time_breakdown_figure | `report/figures/mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png` |
| benchmark_plan | `report/BENCHMARK_PLAN.json` |

## Discovered Runs

| run_id | mode | N | processes | summary |
|---|---|---:|---:|---|
| mpi-mini_sweep-N2-P1 | mpi | 2 | 1 | `results/mpi-mini_sweep-N2-P1/summary.json` |
| serial-mini_sweep-N2 | serial | 2 | 1 | `results/serial-mini_sweep-N2/summary.json` |
| mpi-mini_sweep-N2-P2 | mpi | 2 | 2 | `results/mpi-mini_sweep-N2-P2/summary.json` |

Final-ready means required artifact structure exists and checks pass. It does not invent or modify results.
