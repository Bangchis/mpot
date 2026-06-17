# Generated Results Tables

These tables are generated from existing CSV/JSON artifacts. Do not edit
numbers by hand; regenerate the tables after running new experiments.

## Filters

- label: `mini_sweep`
- input_size: `2`
- fixed_size: ``

## Runtime vs Input Size N

| run_id | mode | input_size_n | processes | runtime_with_communication_s | runtime_without_communication_s | communication_overhead_s | best_cost | balanced_under_25_percent | source_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mpi-mini_sweep-N2-P1 | mpi | 2 | 1 | 0.484948 | 0.484671 | 0.000276833 | 0.00905869 | yes | results/mpi-mini_sweep-N2-P1/summary.json |
| serial-mini_sweep-N2 | serial | 2 | 1 | 0.938341 | 0.938341 | 0 | 0.00905869 |  | results/serial-mini_sweep-N2/summary.json |
| mpi-mini_sweep-N2-P2 | mpi | 2 | 2 | 0.537446 | 0.536736 | 0.000709708 | 0.00905869 | yes | results/mpi-mini_sweep-N2-P2/summary.json |

## Speedup

| run_id | input_size_n | processes | runtime_with_communication_s | runtime_without_communication_s | speedup_with_communication | speedup_without_communication | efficiency_with_communication | efficiency_without_communication | source_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mpi-mini_sweep-N2-P1 | 2 | 1 | 0.484948 | 0.484671 | 1 | 1 | 1 | 1 | results/mpi-mini_sweep-N2-P1/summary.json |
| mpi-mini_sweep-N2-P2 | 2 | 2 | 0.537446 | 0.536736 | 0.90232 | 0.902997 | 0.45116 | 0.451498 | results/mpi-mini_sweep-N2-P2/summary.json |

## Granularity and Load Balance

| run_id | rank | processes | hostname | num_tasks | compute_time_s | communication_time_s | total_time_s | idle_time_s | idle_fraction_of_slowest_rank | best_cost | source_rank_timings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mpi-mini_sweep-N2-P2 | 0 | 2 | Phams-MacBook-Air.local | 1 | 0.536508 | 0.000881208 | 0.537405 | 4.0875e-05 | 7.60542e-05 | 0.00905869 | results/mpi-mini_sweep-N2-P2/rank_timings.csv |
| mpi-mini_sweep-N2-P2 | 1 | 2 | Phams-MacBook-Air.local | 1 | 0.536736 | 0.000702292 | 0.537446 | 0 | 0 | 0.00914001 | results/mpi-mini_sweep-N2-P2/rank_timings.csv |
