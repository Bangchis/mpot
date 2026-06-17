# Communication Strategy Analysis

This analysis is generated from real MPI communication event artifacts.

## Summary

- run_id: `mpi-mini_sweep-N2-P2`
- input_size_n: `2`
- processes: `2`
- topology: `SPMD with rank 0 coordinator, logical star topology`
- strategy: `blocking collectives: bcast, scatter, gather`
- all_events_blocking: `yes`
- observed_collectives: `bcast, gather, scatter`
- has_expected_collectives: `yes`

## Event Groups

| event | collective | root | blocking | rank_rows | max_duration_s | sum_duration_s | max_payload_count |
|---|---|---:|---:|---:|---:|---:|---:|
| bcast_assignment | bcast | 0 | yes | 2 | 3.25008e-06 | 6.25011e-06 | 2 |
| bcast_config | bcast | 0 | yes | 2 | 0.000135792 | 0.000205667 |  |
| bcast_run_id | bcast | 0 | yes | 2 | 4.33403e-06 | 7.29202e-06 |  |
| gather_rank_timings | gather | 0 | yes | 2 | 3.2083e-05 | 3.975e-05 | 1 |
| gather_results | gather | 0 | yes | 2 | 0.000791792 | 0.00133708 | 1 |
| scatter_tasks | scatter | 0 | yes | 2 | 1.38751e-05 | 2.72081e-05 | 1 |

## Per-Rank Communication Totals

| rank | num_events | total_duration_s |
|---:|---:|---:|
| 0 | 6 | 0.000913291 |
| 1 | 6 | 0.000709959 |

Derived only from real comm_events.csv and summary.json artifacts.
