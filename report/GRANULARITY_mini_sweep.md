# Granularity and Load Balance Analysis

This analysis is generated from real MPI timing artifacts.

## Summary

- run_id: `mpi-mini_sweep-N2-P2`
- input_size_n: `2`
- processes: `2`
- threshold: `0.25`
- idle_fraction: `7.60542e-05`
- balanced_under_threshold: `yes`
- communication_fraction_of_slowest_rank: `0.00163962`

## Recommendation

Load balance is within the 25% threshold. The current granularity is acceptable for this run, so no adjustment is required before using the result in the report.

## Per-Rank Timing

| rank | num_tasks | compute_time_s | communication_time_s | total_time_s | idle_time_s | idle_fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 0.536508 | 0.000881208 | 0.537405 | 4.0875e-05 | 7.60542e-05 |
| 1 | 1 | 0.536736 | 0.000702292 | 0.537446 | 0 | 0 |
