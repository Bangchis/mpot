# Granularity and Load Balance Analysis

This analysis is generated from real MPI timing artifacts.

## Summary

- run_id: `mpi-final_macbook_air_2d-N412-P4`
- input_size_n: `412`
- processes: `4`
- threshold: `0.25`
- idle_fraction: `0.00705028`
- balanced_under_threshold: `yes`
- communication_fraction_of_slowest_rank: `0.0110326`

## Recommendation

Load balance is within the 25% threshold. The current granularity is acceptable for this run, so no adjustment is required before using the result in the report.

## Per-Rank Timing

| rank | num_tasks | compute_time_s | communication_time_s | total_time_s | idle_time_s | idle_fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 103 | 4.87856 | 0.0362787 | 4.91507 | 0 | 0 |
| 1 | 103 | 4.84445 | 0.0359233 | 4.88042 | 0.0346526 | 0.00705028 |
| 2 | 103 | 4.82673 | 0.0542262 | 4.881 | 0.0340763 | 0.00693303 |
| 3 | 103 | 4.85176 | 0.0296996 | 4.8815 | 0.0335723 | 0.00683048 |
