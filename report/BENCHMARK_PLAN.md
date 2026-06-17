# Benchmark Plan

This plan is generated from measured sample timing or an explicit
seconds-per-task estimate. It does not contain final benchmark results.

## Inputs

- label: `final_macbook_air_2d`
- config: `configs/local_benchmark.json`
- sample_summary: `results/estimate-local-benchmark-N4/summary.json`
- sample_tasks: `4`
- sample_time_s: `1.7539282909128815`
- seconds_per_task: `0.4384820727282204`
- target_seconds: `60.0`
- target_processes: `4`
- assumed_parallel_efficiency: `0.75`

## Planned Experiment Sizes

- N for runtime/load-balance experiment: `412`
- 2N for speedup experiment: `824`
- input_sizes: `208,412,824`
- process_counts: `1,2,4`

## Pipeline Command

```bash
python scripts/run_local_pipeline.py --config configs/local_benchmark.json --input-sizes 208,412,824 --process-counts 1,2,4 --label final_macbook_air_2d --final-n 824 --load-balance-n 412 --final-processes 4 --benchmark-plan report/BENCHMARK_PLAN.json
```

## JSON

```json
{
  "assumed_parallel_efficiency": 0.75,
  "chosen_n": 412,
  "config": "configs/local_benchmark.json",
  "input_sizes": [
    208,
    412,
    824
  ],
  "label": "final_macbook_air_2d",
  "note": "This is a planning estimate, not final report data. Run the generated pipeline command and use only resulting CSV/JSON/PNG artifacts for Results.",
  "pipeline_command": [
    "python",
    "scripts/run_local_pipeline.py",
    "--config",
    "configs/local_benchmark.json",
    "--input-sizes",
    "208,412,824",
    "--process-counts",
    "1,2,4",
    "--label",
    "final_macbook_air_2d",
    "--final-n",
    "824",
    "--load-balance-n",
    "412",
    "--final-processes",
    "4",
    "--benchmark-plan",
    "report/BENCHMARK_PLAN.json"
  ],
  "process_counts": [
    1,
    2,
    4
  ],
  "sample_summary": "results/estimate-local-benchmark-N4/summary.json",
  "sample_tasks": 4,
  "sample_time_s": 1.7539282909128815,
  "seconds_per_task": 0.4384820727282204,
  "speedup_n": 824,
  "target_processes": 4,
  "target_seconds": 60.0
}
```
