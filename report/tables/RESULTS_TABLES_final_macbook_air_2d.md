# Generated Results Tables

These tables are generated from existing CSV/JSON artifacts. Do not edit
numbers by hand; regenerate the tables after running new experiments.

## Filters

- label: `final_macbook_air_2d`
- input_size: `824`
- fixed_size: ``

## Runtime vs Input Size N

| run_id | mode | input_size_n | processes | runtime_with_communication_s | runtime_without_communication_s | communication_overhead_s | best_cost | balanced_under_25_percent | source_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mpi-final_macbook_air_2d-N208-P1 | mpi | 208 | 1 | 7.71512 | 7.69082 | 0.0242942 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N208-P1/summary.json |
| serial-final_macbook_air_2d-N208 | serial | 208 | 1 | 7.79078 | 7.79078 | 0 | 0.00520871 |  | results/serial-final_macbook_air_2d-N208/summary.json |
| mpi-final_macbook_air_2d-N208-P2 | mpi | 208 | 2 | 4.32045 | 4.31759 | 0.00285871 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N208-P2/summary.json |
| mpi-final_macbook_air_2d-N208-P4 | mpi | 208 | 4 | 2.8627 | 2.85861 | 0.00408896 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N208-P4/summary.json |
| mpi-final_macbook_air_2d-N412-P1 | mpi | 412 | 1 | 14.4607 | 14.4577 | 0.00306808 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N412-P1/summary.json |
| serial-final_macbook_air_2d-N412 | serial | 412 | 1 | 14.6431 | 14.6431 | 0 | 0.00520871 |  | results/serial-final_macbook_air_2d-N412/summary.json |
| mpi-final_macbook_air_2d-N412-P2 | mpi | 412 | 2 | 7.83052 | 7.80361 | 0.0269048 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N412-P2/summary.json |
| mpi-final_macbook_air_2d-N412-P4 | mpi | 412 | 4 | 4.91507 | 4.87856 | 0.0365121 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N412-P4/summary.json |
| mpi-final_macbook_air_2d-N824-P1 | mpi | 824 | 1 | 27.9028 | 27.8966 | 0.00621529 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N824-P1/summary.json |
| serial-final_macbook_air_2d-N824 | serial | 824 | 1 | 27.8693 | 27.8693 | 0 | 0.00520871 |  | results/serial-final_macbook_air_2d-N824/summary.json |
| mpi-final_macbook_air_2d-N824-P2 | mpi | 824 | 2 | 14.7543 | 14.7472 | 0.00707342 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N824-P2/summary.json |
| mpi-final_macbook_air_2d-N824-P4 | mpi | 824 | 4 | 9.31508 | 9.27704 | 0.0380422 | 0.00520871 | yes | results/mpi-final_macbook_air_2d-N824-P4/summary.json |

## Speedup

| run_id | input_size_n | processes | runtime_with_communication_s | runtime_without_communication_s | speedup_with_communication | speedup_without_communication | efficiency_with_communication | efficiency_without_communication | source_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mpi-final_macbook_air_2d-N824-P1 | 824 | 1 | 27.9028 | 27.8966 | 1 | 1 | 1 | 1 | results/mpi-final_macbook_air_2d-N824-P1/summary.json |
| mpi-final_macbook_air_2d-N824-P2 | 824 | 2 | 14.7543 | 14.7472 | 1.89117 | 1.89165 | 0.945584 | 0.945827 | results/mpi-final_macbook_air_2d-N824-P2/summary.json |
| mpi-final_macbook_air_2d-N824-P4 | 824 | 4 | 9.31508 | 9.27704 | 2.99545 | 3.00706 | 0.748862 | 0.751766 | results/mpi-final_macbook_air_2d-N824-P4/summary.json |

## Granularity and Load Balance

| run_id | rank | processes | hostname | num_tasks | compute_time_s | communication_time_s | total_time_s | idle_time_s | idle_fraction_of_slowest_rank | best_cost | source_rank_timings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mpi-final_macbook_air_2d-N412-P4 | 0 | 4 | Phams-MacBook-Air.local | 103 | 4.87856 | 0.0362787 | 4.91507 | 0 | 0 | 0.00520871 | results/mpi-final_macbook_air_2d-N412-P4/rank_timings.csv |
| mpi-final_macbook_air_2d-N412-P4 | 1 | 4 | Phams-MacBook-Air.local | 103 | 4.84445 | 0.0359233 | 4.88042 | 0.0346526 | 0.00705028 | 0.00530434 | results/mpi-final_macbook_air_2d-N412-P4/rank_timings.csv |
| mpi-final_macbook_air_2d-N412-P4 | 2 | 4 | Phams-MacBook-Air.local | 103 | 4.82673 | 0.0542262 | 4.881 | 0.0340763 | 0.00693303 | 0.00521898 | results/mpi-final_macbook_air_2d-N412-P4/rank_timings.csv |
| mpi-final_macbook_air_2d-N412-P4 | 3 | 4 | Phams-MacBook-Air.local | 103 | 4.85176 | 0.0296996 | 4.8815 | 0.0335723 | 0.00683048 | 0.00526064 | results/mpi-final_macbook_air_2d-N412-P4/rank_timings.csv |
