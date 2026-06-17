# Member Defense Guide

This generated guide is meant for studying, not for inflating the report.
Each member should focus on their primary defense files and demo commands.

- created_at: `2026-06-17 15:22:46 +0700`
- verdict: **PASS**
- members: `4`

## Member A: 2D planning problem and configuration

- meaningful_lines: `663`

### Files

| file | meaningful lines | key symbols / config keys |
|---|---:|---|
| `mpot/benchmarks/problem_2d.py` | 272 | require_torch:17, torch_dtype:30, CircleObstacle:40, PlanningProblem2D:49, MPOTObjective2D:184, summarize_problem:296, straight_line_reference:318, euclidean_path_length:332 |
| `mpot/benchmarks/config.py` | 150 | ObstacleConfig:19, ProblemConfig:28, CostConfig:48, OptimizerConfig:59, ExperimentConfig:80, _coerce_obstacle:111, _coerce_problem:119, config_from_dict:125, config_to_dict:144, config_hash_from_dict:150, config_hash:157, load_config:163 |
| `configs/local_smoke.json` | 47 | keys: experiment_name, output_dir, base_seed, total_tasks, torch_num_threads, device, dtype, problem, cost, optimizer |
| `configs/local_benchmark.json` | 48 | keys: experiment_name, output_dir, base_seed, total_tasks, torch_num_threads, device, dtype, problem, cost, optimizer |
| `configs/variant_open_2d.json` | 46 | keys: experiment_name, output_dir, base_seed, total_tasks, torch_num_threads, device, dtype, problem, cost, optimizer |
| `configs/variant_narrow_passage_2d.json` | 49 | keys: experiment_name, output_dir, base_seed, total_tasks, torch_num_threads, device, dtype, problem, cost, optimizer |
| `configs/variant_cluttered_2d.json` | 51 | keys: experiment_name, output_dir, base_seed, total_tasks, torch_num_threads, device, dtype, problem, cost, optimizer |

### Demo Commands

```bash
python scripts/run_serial.py --config configs/local_smoke.json
```

### Practice Questions

1. What is the robot state in this benchmark?
2. How are circular obstacles represented?
3. Which terms are included in the trajectory cost?
4. Why is a 2D point robot acceptable for this parallel-programming demo?

## Member B: Local optimizer, serial baseline, and correctness

- meaningful_lines: `519`

### Files

| file | meaningful lines | key symbols / config keys |
|---|---:|---|
| `mpot/benchmarks/local_runner.py` | 160 | _fix_local_seed:14, _make_tensor_args:22, build_planner:28, run_task:82, _fix_trace_endpoints:122, _trace_frame:134, run_task_trace:153, run_tasks_serial:191 |
| `mpot/benchmarks/reduction.py` | 96 | TaskResult:11, RankTiming:46, result_key:72, choose_best:86, flatten_result_groups:95, task_results_from_json:104 |
| `mpot/benchmarks/correctness.py` | 177 | TaskComparison:21, _close:73, _task_index:77, compare_task_results:89, load_run_task_results:160, compare_run_directories:166 |
| `scripts/run_serial.py` | 51 | parse_args:24, main:33 |
| `scripts/compare_serial_mpi.py` | 35 | parse_args:21, main:31 |

### Demo Commands

```bash
python scripts/run_serial.py --config configs/local_smoke.json
```

```bash
python scripts/compare_serial_mpi.py --serial results/serial-mini_sweep-N2 --mpi results/mpi-mini_sweep-N2-P2
```

### Practice Questions

1. What is one planning task?
2. Why do we need a serial baseline?
3. How does deterministic best-result reduction work?
4. What does task_comparison.csv prove?

## Member C: MPI parallelization, mapping, rank behavior, and communication trace

- meaningful_lines: `496`

### Files

| file | meaningful lines | key symbols / config keys |
|---|---:|---|
| `mpot/benchmarks/mpi_scheduler.py` | 47 | TaskSpec:13, build_tasks:20, cyclic_owner:28, cyclic_chunks:38, validate_assignment:49, describe_chunks:58 |
| `mpot/benchmarks/mpi_runner.py` | 230 | require_mpi4py:18, _record_comm_event:26, run_mpi_benchmark:58 |
| `mpot/benchmarks/communication.py` | 152 | _read_comm_events:15, _as_bool:20, _as_float:24, _as_int_or_none:29, analyze_communication:34, _fmt:105, communication_markdown:115, write_communication_analysis:168 |
| `scripts/run_mpi.py` | 28 | parse_args:20, main:29 |
| `scripts/analyze_communication.py` | 39 | parse_args:18, main:27 |

### Demo Commands

```bash
mpirun -np 4 python scripts/run_mpi.py --config configs/local_smoke.json
```

```bash
python scripts/analyze_communication.py --run-dir results/mpi-mini_sweep-N2-P2 --output results/communication-mini_sweep-N2-P2.json --markdown report/COMMUNICATION_mini_sweep.md --label mini_sweep
```

### Practice Questions

1. What level of parallelism does the project use?
2. How does task i -> rank i mod P work?
3. Which blocking MPI collectives are used?
4. What do comm_events.csv and task_assignment.csv prove?

## Member D: Metrics, plots, result tables, and load-balance evidence

- meaningful_lines: `665`

### Files

| file | meaningful lines | key symbols / config keys |
|---|---:|---|
| `mpot/benchmarks/metrics.py` | 59 | LoadBalanceSummary:13, runtime_with_communication:30, runtime_without_communication:39, compute_speedup:48, compute_efficiency:56, summarize_load_balance:64, rank_timing_records:81 |
| `mpot/benchmarks/plots.py` | 192 | _require_matplotlib:16, _read_csv:24, _best_trajectory_and_problem:29, plot_best_path:41, plot_rank_time_breakdown:83, plot_cost_by_task:107, collect_summaries:128, plot_runtime_vs_input_size:150, plot_speedup:188 |
| `mpot/benchmarks/result_tables.py` | 330 | ResultTablePaths:64, _finite_or_blank:83, _fmt:87, _read_rank_timing_rows:101, _summary_source:106, build_runtime_rows:111, _select_speedup_summaries:149, build_speedup_rows:168, choose_default_load_balance_run:205, build_load_balance_rows:222, _markdown_table:256, build_results_markdown:273 |
| `scripts/analyze_granularity.py` | 40 | parse_args:18, main:28 |
| `scripts/plot_results.py` | 44 | parse_args:18, main:28 |

### Demo Commands

```bash
python scripts/generate_ownership_report.py
```

```bash
python scripts/analyze_granularity.py --run-dir results/mpi-mini_sweep-N2-P2 --output results/granularity-mini_sweep-N2-P2.json --markdown report/GRANULARITY_mini_sweep.md --label mini_sweep
```

```bash
python scripts/plot_results.py --results results --output report/figures --label mini_sweep --input-size 2
```

### Practice Questions

1. How is speedup calculated?
2. How do we separate runtime with and without communication?
3. How is the 25 percent load-imbalance threshold checked?
4. Which tables and figures are generated from real artifacts?

Generated from the compact primary defense set. Shared support modules are intentionally summarized elsewhere.
