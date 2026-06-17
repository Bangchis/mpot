# Final Experiment Audit

This file is generated from real local artifacts. Use it as a checklist
before copying experiment claims into the final report.

- created_at: `2026-06-17 07:24:05 +0700`
- label: `final_macbook_air_2d`
- verdict: **PASS**
- N for runtime/load-balance: `412`
- 2N for speedup/correctness: `824`
- final_processes: `4`
- failed_checks: `0`

## Checks

| status | check | detail |
|---|---|---|
| PASS | serial summaries exist | `count=3` |
| PASS | MPI summaries exist | `count=9` |
| PASS | runtime-vs-N input sizes are present at final process count | `expected=[208, 412, 824], found_for_P4=[208, 412, 824]` |
| PASS | serial baselines are present for expected input sizes | `expected=[208, 412, 824]` |
| PASS | speedup input size has requested process counts | `N=824, expected=[1, 2, 4], found=[1, 2, 4]` |
| PASS | speedup has P=1 MPI baseline | `N=824, found=[1, 2, 4]` |
| PASS | correctness serial run exists | `N=824` |
| PASS | correctness MPI run exists | `N=824, P=4` |
| PASS | serial/MPI correctness passed | `passed=True, task_level=True` |
| PASS | solution quality passed | `passed=True, num_failed=0, goal_error=3.371747884011707e-08, hard_collision_fraction=0.0` |
| PASS | MPI communication events CSV exists | `results/mpi-final_macbook_air_2d-N824-P4/comm_events.csv` |
| PASS | communication analysis passed | `has_expected_collectives=True, all_events_blocking=True, observed=['bcast', 'gather', 'scatter']` |
| PASS | MPI task assignment CSV exists | `results/mpi-final_macbook_air_2d-N824-P4/task_assignment.csv` |
| PASS | granularity under 25 percent threshold | `idle_fraction=0.007050277842431597, threshold=0.25` |
| PASS | runtime-vs-N figure exists | `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` |
| PASS | speedup figure exists | `report/figures/speedup_final_macbook_air_2d.png` |
| PASS | rank time breakdown figure exists | `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png` |
| PASS | report artifact bundle manifest exists | `report/artifacts/final_macbook_air_2d/manifest.json` |
| PASS | result tables have rows | `{'num_runtime_rows': 12, 'num_speedup_rows': 3, 'num_load_balance_rows': 4}` |
| PASS | results summary exists | `report/RESULTS_SUMMARY_final_macbook_air_2d.json` |
| PASS | environment capture exists | `results/environment-final_macbook_air_2d.json` |
| PASS | team ownership report passed | `passed=True, num_members=4, minimum=250, recommended_max=700, member_lines={'Member A': 663, 'Member B': 519, 'Member C': 496, 'Member D': 665}` |
| PASS | member defense guide passed | `passed=True, num_members=4, member_files=[7, 5, 5, 5]` |
| PASS | experiment index exists | `report/EXPERIMENT_INDEX_final_macbook_air_2d.json` |
| PASS | pipeline validation passed | `passed=True, num_failed=0` |
| PASS | benchmark plan exists | `report/BENCHMARK_PLAN.json` |

## Important Artifacts

| artifact | path |
|---|---|
| correctness_report | `results/compare-final_macbook_air_2d-N824-P4/correctness_report.json` |
| solution_quality_report | `results/solution-quality-final_macbook_air_2d-N824-P4.json` |
| communication_report | `results/communication-final_macbook_air_2d-N824-P4.json` |
| granularity_report | `results/granularity-final_macbook_air_2d-N412-P4.json` |
| validation_report | `results/validation-final_macbook_air_2d-N824-P4.json` |
| bundle_manifest | `report/artifacts/final_macbook_air_2d/manifest.json` |
| tables_manifest | `report/tables/tables_manifest_final_macbook_air_2d.json` |
| results_summary | `report/RESULTS_SUMMARY_final_macbook_air_2d.json` |
| environment_json | `results/environment-final_macbook_air_2d.json` |
| ownership_report | `report/TEAM_OWNERSHIP_REPORT.json` |
| defense_guide | `report/MEMBER_DEFENSE_GUIDE.json` |
| experiment_index | `report/EXPERIMENT_INDEX_final_macbook_air_2d.json` |
| runtime_figure | `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` |
| speedup_figure | `report/figures/speedup_final_macbook_air_2d.png` |
| comm_events_csv | `results/mpi-final_macbook_air_2d-N824-P4/comm_events.csv` |
| task_assignment_csv | `results/mpi-final_macbook_air_2d-N824-P4/task_assignment.csv` |
| rank_time_breakdown_figure | `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png` |
| benchmark_plan | `report/BENCHMARK_PLAN.json` |

## Discovered Runs

| run_id | mode | N | processes | summary |
|---|---|---:|---:|---|
| mpi-final_macbook_air_2d-N208-P1 | mpi | 208 | 1 | `results/mpi-final_macbook_air_2d-N208-P1/summary.json` |
| serial-final_macbook_air_2d-N208 | serial | 208 | 1 | `results/serial-final_macbook_air_2d-N208/summary.json` |
| mpi-final_macbook_air_2d-N208-P2 | mpi | 208 | 2 | `results/mpi-final_macbook_air_2d-N208-P2/summary.json` |
| mpi-final_macbook_air_2d-N208-P4 | mpi | 208 | 4 | `results/mpi-final_macbook_air_2d-N208-P4/summary.json` |
| mpi-final_macbook_air_2d-N412-P1 | mpi | 412 | 1 | `results/mpi-final_macbook_air_2d-N412-P1/summary.json` |
| serial-final_macbook_air_2d-N412 | serial | 412 | 1 | `results/serial-final_macbook_air_2d-N412/summary.json` |
| mpi-final_macbook_air_2d-N412-P2 | mpi | 412 | 2 | `results/mpi-final_macbook_air_2d-N412-P2/summary.json` |
| mpi-final_macbook_air_2d-N412-P4 | mpi | 412 | 4 | `results/mpi-final_macbook_air_2d-N412-P4/summary.json` |
| mpi-final_macbook_air_2d-N824-P1 | mpi | 824 | 1 | `results/mpi-final_macbook_air_2d-N824-P1/summary.json` |
| serial-final_macbook_air_2d-N824 | serial | 824 | 1 | `results/serial-final_macbook_air_2d-N824/summary.json` |
| mpi-final_macbook_air_2d-N824-P2 | mpi | 824 | 2 | `results/mpi-final_macbook_air_2d-N824-P2/summary.json` |
| mpi-final_macbook_air_2d-N824-P4 | mpi | 824 | 4 | `results/mpi-final_macbook_air_2d-N824-P4/summary.json` |

Final-ready means required artifact structure exists and checks pass. It does not invent or modify results.
