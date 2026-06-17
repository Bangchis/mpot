# Communication Strategy Analysis

This analysis is generated from real MPI communication event artifacts.

## Summary

- run_id: `mpi-final_macbook_air_2d-N824-P4`
- input_size_n: `824`
- processes: `4`
- topology: `SPMD with rank 0 coordinator, logical star topology`
- strategy: `blocking collectives: bcast, scatter, gather`
- all_events_blocking: `yes`
- observed_collectives: `bcast, gather, scatter`
- has_expected_collectives: `yes`

## Event Groups

| event | collective | root | blocking | rank_rows | max_duration_s | sum_duration_s | max_payload_count |
|---|---|---:|---:|---:|---:|---:|---:|
| bcast_assignment | bcast | 0 | yes | 4 | 2.24171e-05 | 6.87931e-05 | 4 |
| bcast_config | bcast | 0 | yes | 4 | 0.000497625 | 0.00142617 |  |
| bcast_run_id | bcast | 0 | yes | 4 | 3.24997e-06 | 1.15409e-05 |  |
| gather_rank_timings | gather | 0 | yes | 4 | 0.000661083 | 0.000762666 | 1 |
| gather_results | gather | 0 | yes | 4 | 0.0850515 | 0.151778 | 206 |
| scatter_tasks | scatter | 0 | yes | 4 | 0.000568333 | 0.00215958 | 206 |

## Per-Rank Communication Totals

| rank | num_events | total_duration_s |
|---:|---:|---:|
| 0 | 6 | 0.0857382 |
| 1 | 6 | 0.00166521 |
| 2 | 6 | 0.0170573 |
| 3 | 6 | 0.0517457 |

Derived only from real comm_events.csv and summary.json artifacts.
