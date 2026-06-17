# Results Summary

This summary is generated from real benchmark artifacts. It can be used
as a report-writing helper, but it does not create new measurements.

- label: `final_macbook_air_2d`
- verdict: **PASS**
- generated_at: `2026-06-17 07:24:05 +0700`

## Correctness

- serial run: `serial-final_macbook_air_2d-N824`
- MPI run: `mpi-final_macbook_air_2d-N824-P4`
- same best task: `yes`
- same best seed: `yes`
- best cost difference: `0`
- compared tasks: `824`

## Solution Quality

- MPI best task: `184`
- MPI best seed: `20260801`
- MPI best cost: `0.00520871`
- goal error: `3.37175e-08`
- hard collision fraction: `0`
- max bounds violation: `0`

## Communication and Load Balance

- topology: `SPMD with rank 0 coordinator, logical star topology`
- strategy: `blocking collectives: bcast, scatter, gather`
- observed collectives: `bcast, gather, scatter`
- all events blocking: `yes`
- idle fraction: `0.00705028`
- balanced under threshold: `yes`
- recommendation: Load balance is within the 25% threshold. The current granularity is acceptable for this run, so no adjustment is required before using the result in the report.

## Generated Tables

- runtime rows: `12`
- speedup rows: `3`
- load-balance rows: `4`

## Checks

| status | check | detail |
|---|---|---|
| PASS | serial summary exists | `results/serial-final_macbook_air_2d-N824/summary.json` |
| PASS | MPI summary exists | `results/mpi-final_macbook_air_2d-N824-P4/summary.json` |
| PASS | correctness passed | `passed=True` |
| PASS | task-level correctness passed | `tasks_passed=True` |
| PASS | solution quality passed | `passed=True` |
| PASS | communication analysis passed | `collectives=['bcast', 'gather', 'scatter'], blocking=True` |
| PASS | granularity under threshold | `idle_fraction=0.007050277842431597` |
| PASS | result tables have rows | `runtime=12, speedup=3, load_balance=4` |
| PASS | figure exists | `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` |
| PASS | figure exists | `report/figures/speedup_final_macbook_air_2d.png` |
| PASS | figure exists | `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png` |
| PASS | figure exists | `report/figures/trajectory_final_macbook_air_2d.gif` |
| PASS | figure exists | `report/figures/algorithm_trace_final_macbook_air_2d.gif` |

## Sources

| artifact | path |
|---|---|
| serial_summary | `results/serial-final_macbook_air_2d-N824/summary.json` |
| mpi_summary | `results/mpi-final_macbook_air_2d-N824-P4/summary.json` |
| correctness_report | `results/compare-final_macbook_air_2d-N824-P4/correctness_report.json` |
| tables_manifest | `report/tables/tables_manifest_final_macbook_air_2d.json` |
| runtime_csv | `report/tables/runtime_table_final_macbook_air_2d.csv` |
| speedup_csv | `report/tables/speedup_table_final_macbook_air_2d.csv` |
| load_balance_csv | `report/tables/load_balance_table_final_macbook_air_2d.csv` |
| granularity_report | `results/granularity-final_macbook_air_2d-N412-P4.json` |
| communication_report | `results/communication-final_macbook_air_2d-N824-P4.json` |
| solution_quality_report | `results/solution-quality-final_macbook_air_2d-N824-P4.json` |
| benchmark_budget | `report/BENCHMARK_BUDGET_final_macbook_air_2d.json` |
| figure | `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` |
| figure | `report/figures/speedup_final_macbook_air_2d.png` |
| figure | `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png` |
| figure | `report/figures/trajectory_final_macbook_air_2d.gif` |
| figure | `report/figures/algorithm_trace_final_macbook_air_2d.gif` |

Generated only from existing benchmark artifacts. Do not use this file to invent missing results.
