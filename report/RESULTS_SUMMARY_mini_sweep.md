# Results Summary

This summary is generated from real benchmark artifacts. It can be used
as a report-writing helper, but it does not create new measurements.

- label: `mini_sweep`
- verdict: **PASS**
- generated_at: `2026-06-17 06:48:27 +0700`

## Correctness

- serial run: `serial-mini_sweep-N2`
- MPI run: `mpi-mini_sweep-N2-P2`
- same best task: `yes`
- same best seed: `yes`
- best cost difference: `0`
- compared tasks: `2`

## Solution Quality

- MPI best task: `0`
- MPI best seed: `20260617`
- MPI best cost: `0.00905869`
- goal error: `3.37175e-08`
- hard collision fraction: `0`
- max bounds violation: `0`

## Communication and Load Balance

- topology: `SPMD with rank 0 coordinator, logical star topology`
- strategy: `blocking collectives: bcast, scatter, gather`
- observed collectives: `bcast, gather, scatter`
- all events blocking: `yes`
- idle fraction: `7.60542e-05`
- balanced under threshold: `yes`
- recommendation: Load balance is within the 25% threshold. The current granularity is acceptable for this run, so no adjustment is required before using the result in the report.

## Generated Tables

- runtime rows: `3`
- speedup rows: `2`
- load-balance rows: `2`

## Checks

| status | check | detail |
|---|---|---|
| PASS | serial summary exists | `results/serial-mini_sweep-N2/summary.json` |
| PASS | MPI summary exists | `results/mpi-mini_sweep-N2-P2/summary.json` |
| PASS | correctness passed | `passed=True` |
| PASS | task-level correctness passed | `tasks_passed=True` |
| PASS | solution quality passed | `passed=True` |
| PASS | communication analysis passed | `collectives=['bcast', 'gather', 'scatter'], blocking=True` |
| PASS | granularity under threshold | `idle_fraction=7.60542324117304e-05` |
| PASS | result tables have rows | `runtime=3, speedup=2, load_balance=2` |
| PASS | figure exists | `report/figures/runtime_vs_input_size_mini_sweep.png` |
| PASS | figure exists | `report/figures/speedup_mini_sweep.png` |
| PASS | figure exists | `report/figures/mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png` |
| PASS | figure exists | `report/figures/trajectory_mini_sweep.gif` |
| PASS | figure exists | `report/figures/algorithm_trace_mini_sweep.gif` |

## Sources

| artifact | path |
|---|---|
| serial_summary | `results/serial-mini_sweep-N2/summary.json` |
| mpi_summary | `results/mpi-mini_sweep-N2-P2/summary.json` |
| correctness_report | `results/compare-mini_sweep-N2-P2/correctness_report.json` |
| tables_manifest | `report/tables/tables_manifest_mini_sweep.json` |
| runtime_csv | `report/tables/runtime_table_mini_sweep.csv` |
| speedup_csv | `report/tables/speedup_table_mini_sweep.csv` |
| load_balance_csv | `report/tables/load_balance_table_mini_sweep.csv` |
| granularity_report | `results/granularity-mini_sweep-N2-P2.json` |
| communication_report | `results/communication-mini_sweep-N2-P2.json` |
| solution_quality_report | `results/solution-quality-mini_sweep-N2-P2.json` |
| benchmark_budget | `report/BENCHMARK_BUDGET_mini_sweep.json` |
| figure | `report/figures/runtime_vs_input_size_mini_sweep.png` |
| figure | `report/figures/speedup_mini_sweep.png` |
| figure | `report/figures/mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png` |
| figure | `report/figures/trajectory_mini_sweep.gif` |
| figure | `report/figures/algorithm_trace_mini_sweep.gif` |

Generated only from existing benchmark artifacts. Do not use this file to invent missing results.
