# Report Checklist and Requirement Map

This checklist maps each professor requirement to the living report, planned
code, and required real artifacts. Do not mark an experiment item as `Measured`
until the corresponding CSV/JSON/PNG files exist.

Allowed status values:

```text
Not started
Drafted
Implemented
Measured
Final
```

## Professor Requirement Map

| Requirement | Report section | Planned code/module | Required artifact | Status |
|---|---|---|---|---|
| 10-20 page report, maximum 20 pages | Entire report | `report/REPORT_POLISHED_DRAFT.md`, `report/REPORT_DRAFT.md` | Final exported PDF from Markdown/Overleaf | Drafted |
| Parallel level: task or data | Section 4.1 | `mpot/benchmarks/mpi_runner.py` | Explanation in report | Implemented |
| Decomposition technique | Section 4.2 | `mpot/benchmarks/mpi_scheduler.py` | Explanation in report | Implemented |
| Process assignment / mapping | Section 4.3 | `mpot/benchmarks/mpi_scheduler.py`, `mpot/benchmarks/artifacts.py` | Unit test for cyclic mapping and `results/<mpi_run>/task_assignment.csv` | Measured |
| Communication strategy and topology | Section 4.4 | `mpot/benchmarks/mpi_runner.py`, `mpot/benchmarks/communication.py`, `scripts/run_mpi.py`, `scripts/analyze_communication.py` | MPI run logs, `rank_timings.csv`, `comm_events.csv`, and `report/COMMUNICATION_<label>.md` | Measured |
| Blocking or non-blocking communication | Section 4.4 | `mpot/benchmarks/mpi_runner.py`, `mpot/benchmarks/communication.py` | `comm_events.csv` records blocking collectives and communication analysis validates them | Measured |
| Master-slave / coordinator topology | Section 4.4 | `mpot/benchmarks/mpi_runner.py` | Explanation in report | Implemented |
| Load balancing considerations | Section 4.5 and 8.3 | `mpot/benchmarks/metrics.py` | `rank_time_breakdown.png` | Implemented |
| Parallel algorithm pseudocode | Section 5.1 | `scripts/run_mpi.py` | Pseudocode in report | Implemented |
| Parallel algorithm input parameters | Section 2.4 and `docs/mpot_parallel_algorithm_spec.md` | `mpot/benchmarks/config.py`, `mpot/benchmarks/mpi_scheduler.py`, `mpot/benchmarks/mpi_runner.py` | Report section explains problem parameters, MPOT optimizer parameters, MPI parameters, measurement fields, and reduction key | Implemented |
| Serial algorithm pseudocode | Section 3.1 | `scripts/run_serial.py` | Pseudocode in report | Implemented |
| Professional MPOT algorithm explanation | Sections 1, 3, 4, and 5 | `docs/mpot_algorithm_overview.md`, `mpot/planner.py`, `mpot/benchmarks/local_runner.py`, `mpot/benchmarks/mpi_runner.py` | Report-ready explanation of original MPOT and OpenMPI task-level parallelization | Implemented |
| Mathematical serial and parallel algorithm spec | Sections 3, 4, and 5 | `docs/mpot_parallel_algorithm_spec.md`, `mpot/planner.py`, `mpot/benchmarks/mpi_runner.py`, `mpot/benchmarks/mpi_scheduler.py` | Line-by-line algorithms for local MPOT, serial baseline, and distributed OpenMPI MPOT | Implemented |
| Rubric design rationale | Section 4.6 and Discussion | `report/REPORT_DRAFT.md`, `docs/mpot_parallel_algorithm_spec.md` | Explains why task-level exploratory MPI is chosen, why other MPOT levels are not split, and how communication/load-balance choices match the course rubric | Implemented |
| Correctness of parallel result | Section 8.1 | `scripts/compare_serial_mpi.py`, `mpot/benchmarks/correctness.py` | `results/compare-final_macbook_air_2d-N824-P4/correctness_report.json`, `results/compare-final_macbook_air_2d-N824-P4/task_comparison.csv` | Measured |
| Feasibility of saved planning solution | Section 8.1 | `scripts/validate_solution_quality.py`, `mpot/benchmarks/solution_quality.py` | `results/solution-quality-final_macbook_air_2d-N824-P4.json`, `report/SOLUTION_QUALITY_final_macbook_air_2d.md` | Measured |
| Define input size N | Section 7 and 8.2 | `configs/local_smoke.json`, `configs/local_benchmark.json` | Benchmark config showing selected N | Implemented |
| 2D qualitative problem variants | Section 7.4 and Discussion | `configs/variant_open_2d.json`, `configs/variant_narrow_passage_2d.json`, `configs/variant_cluttered_2d.json`, `configs/variant_dense_sampling_2d.json`, `docs/problem_variants_2d.md` | `report/figures/trajectory_variant_narrow.gif`, `report/figures/algorithm_trace_variant_narrow.gif`, `report/figures/trajectory_variant_cluttered.gif`, `report/figures/algorithm_trace_variant_cluttered.gif`, `report/figures/trajectory_variant_dense.gif`, `report/figures/algorithm_trace_variant_dense.gif`; demo artifacts only, not main speedup data | Measured |
| Runtime vs input size N, with communication | Section 8.2 | `mpot/benchmarks/plots.py` | `report/tables/runtime_table_final_macbook_air_2d.csv`, `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` | Measured |
| Runtime vs input size N, without communication | Section 8.2 | `mpot/benchmarks/plots.py` | `report/tables/runtime_table_final_macbook_air_2d.csv`, `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` | Measured |
| Choose N so runtime is about 2-3 minutes | Section 7 and 8.2 | `scripts/estimate_input_size.py`, `scripts/plan_benchmark.py`, `mpot/benchmarks/benchmark_plan.py`, `configs/local_benchmark.json` | Current local `final_macbook_air_2d` artifacts exist but are shorter than 2-3 minutes; run larger `N` later if strict target is required | Implemented |
| Estimate final sweep time before running | Section 7 and 8.2 | `scripts/estimate_benchmark_budget.py`, `mpot/benchmarks/benchmark_budget.py`, `mpot/benchmarks/run_reuse.py`, `mpot/benchmarks/pipeline.py` | `report/BENCHMARK_BUDGET_<label>.json`, `report/BENCHMARK_BUDGET_<label>.md`; estimate only, not Results data; with `--reuse-existing` also reports remaining time after reusable runs | Implemented |
| Granularity / per-rank timing stacked bar | Section 8.3 | `mpot/benchmarks/metrics.py`, `mpot/benchmarks/plots.py` | `report/figures/final_macbook_air_2d_mpi_mpi-final_macbook_air_2d-N412-P4_rank_time_breakdown.png` | Measured |
| Check load imbalance threshold of 25% | Section 4.5 and 8.3 | `mpot/benchmarks/metrics.py`, `mpot/benchmarks/granularity.py`, `scripts/analyze_granularity.py` | `results/granularity-final_macbook_air_2d-N412-P4.json`, `report/GRANULARITY_final_macbook_air_2d.md` | Measured |
| Speedup with process counts 1, 2, 4, 8, ... | Section 8.4 | `mpot/benchmarks/metrics.py`, `mpot/benchmarks/plots.py` | `report/tables/speedup_table_final_macbook_air_2d.csv`, `report/figures/speedup_final_macbook_air_2d.png` | Measured |
| Report must not invent numerical results | Section 8 | `scripts/validate_results.py` and report workflow | No dummy numerical tables in Results | Implemented |
| Trace report claims to real artifacts | Section 6.2 and 8 | `mpot/benchmarks/report_bundle.py`, `mpot/benchmarks/experiment_index.py`, `scripts/export_report_bundle.py`, `scripts/index_results.py`, `scripts/validate_results.py` | `report/ARTIFACT_MANIFEST.md`, `report/artifacts/<bundle>/manifest.json`, `report/EXPERIMENT_INDEX_<label>.md` | Implemented |
| Check living report file references | Section 6.2 and living report rules | `mpot/benchmarks/report_sync.py`, `scripts/check_report_sync.py`, `mpot/benchmarks/pipeline.py` | `report/REPORT_SYNC_<label>.json`, `report/REPORT_SYNC_<label>.md`; concrete paths in report/docs must exist | Measured |
| Generate report tables from real artifacts | Section 6.2 and 8 | `mpot/benchmarks/result_tables.py`, `scripts/export_result_tables.py` | `report/tables/RESULTS_TABLES_<label>.md`, CSV tables, tables manifest | Implemented |
| Generate report-ready Results summary from real artifacts | Section 6.2 and 8 | `mpot/benchmarks/results_summary.py`, `scripts/export_results_summary.py`, `mpot/benchmarks/pipeline.py` | `report/RESULTS_SUMMARY_<label>.json`, `report/RESULTS_SUMMARY_<label>.md`; generated from existing artifacts only | Implemented |
| Optional trajectory replay animation for demo | Section 6.2 and visualization notes | `mpot/benchmarks/animation.py`, `scripts/animate_trajectory.py`, `mpot/benchmarks/pipeline.py` | `report/figures/trajectory_<label>.gif`; demo artifact only, not a substitute for required CSV/JSON/PNG | Measured |
| Optional MPOT algorithm trace animation for demo | Section 6.2 and visualization notes | `mpot/benchmarks/animation.py`, `scripts/animate_algorithm_trace.py`, `mpot/benchmarks/local_runner.py`, `mpot/benchmarks/pipeline.py` | `report/figures/algorithm_trace_<label>.gif`, `report/ALGORITHM_TRACE_<label>.json`; shows particles/candidate trajectories over optimizer iterations | Measured |
| One-command local benchmark workflow | Section 6.2 | `mpot/benchmarks/pipeline.py`, `scripts/run_local_pipeline.py` | Dry-run command and final validation report | Implemented |
| Resume interrupted local sweeps without rerunning completed runs | Section 6.2 | `scripts/run_sweep.py`, `scripts/run_local_pipeline.py`, `mpot/benchmarks/pipeline.py`, `mpot/benchmarks/config.py`, `mpot/benchmarks/run_reuse.py` | `--skip-existing-runs` passes `--skip-existing` to sweep; reusable run must have matching `summary.json` metadata and config hash | Implemented |
| Experimental setup is reproducible | Section 7 | `mpot/benchmarks/environment.py`, `scripts/capture_environment.py`, `scripts/run_local_pipeline.py` | `results/environment-<label>.json`, `report/ENVIRONMENT_<label>.md` | Implemented |
| Local-to-Ubuntu phase plan is documented | Section 7 | `docs/local_to_ubuntu_phase_plan.md`, `docs/ubuntu_vm_cluster_setup.md` | Stage gates for local final run, first single-VM Ubuntu smoke, teammate VM setup, LAN MPI smoke, and Ubuntu final benchmark | Implemented |
| Owner Ubuntu single-VM smoke | Section 7 | `scripts/check_local_env.py`, `scripts/doctor_local_setup.py`, `scripts/run_serial.py`, `scripts/run_mpi.py`, `scripts/compare_serial_mpi.py` | `results/ubuntu_vm_single/setup_doctor_ubuntu_vm_single.json`, `results/ubuntu_vm_single/compare-ubuntu-single-N4-P2/correctness_report.json`, `results/ubuntu_vm_single/compare-ubuntu-single-N8-P4/correctness_report.json`, and `report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md` | Measured |
| Ubuntu/LAN cluster connection plan | Section 7 | `docs/ubuntu_vm_cluster_setup.md`, `docs/teammate_vm_quickstart.md`, `configs/cluster_hosts.example.json`, `scripts/prepare_cluster_hostfile.py` | Teammate single-VM proof, Bridged IP list, ping/SSH checks, generated hostfile after real IPs are known, and LAN MPI smoke artifacts after teammates are available | Drafted |
| Four members have readable code ownership | Section 6.2 and `docs/team_ownership.md` | `mpot/benchmarks/ownership.py`, `scripts/generate_ownership_report.py`, `docs/team_ownership.md` | `report/TEAM_OWNERSHIP_REPORT.json`, `report/TEAM_OWNERSHIP_REPORT.md`; each member 250+ meaningful lines and <=700 primary-defense lines | Measured |
| Four members have a compact defense guide | Section 6.2 and `docs/team_ownership.md` | `mpot/benchmarks/defense_pack.py`, `scripts/generate_defense_guide.py`, `docs/team_ownership.md` | `report/MEMBER_DEFENSE_GUIDE.json`, `report/MEMBER_DEFENSE_GUIDE.md`; each member has primary files, key symbols, demo commands, and practice questions | Measured |
| Teammate local/Ubuntu setup check | Section 6.2 and 7 | `mpot/benchmarks/doctor.py`, `scripts/doctor_local_setup.py` | `results/setup_doctor_<label>.json`, `report/SETUP_DOCTOR_<label>.md` | Measured |
| Index available experiment artifacts | Section 6.2 and 8 | `mpot/benchmarks/experiment_index.py`, `scripts/index_results.py` | `report/EXPERIMENT_INDEX_mini_sweep.json`, `report/EXPERIMENT_INDEX_mini_sweep.md` | Measured |
| Audit final-report readiness | Section 6.2 and 8 | `mpot/benchmarks/final_audit.py`, `scripts/audit_final_results.py`, `mpot/benchmarks/pipeline.py` | `report/FINAL_AUDIT_<label>.json`, `report/FINAL_AUDIT_<label>.md`; audit reads correctness, communication, solution-quality, ownership, defense guide, granularity, tables, figures, and validation payloads | Measured |
| Prepare soft copy submission package | Submission step | `mpot/benchmarks/submission_package.py`, `scripts/export_submission_package.py`, `mpot/benchmarks/pipeline.py` | `submission/<label>/SUBMISSION_MANIFEST.json`, `submission/<label>/SUBMISSION_MANIFEST.md`; copies only existing report/checklist/table/figure/audit artifacts | Implemented |
| Soft copy submission through Teams General | Submission step | Final report export after Markdown/Overleaf polishing | Final PDF/LaTeX source and generated submission folder | Not started |

## Required Result Artifacts

These files must come from real runs before the Results section is finalized:

```text
results/<serial_run>/summary.json
results/<serial_run>/task_results.csv
results/<mpi_run>/summary.json
results/<mpi_run>/rank_timings.csv
results/<mpi_run>/comm_events.csv
results/<mpi_run>/task_assignment.csv
results/<mpi_run>/task_results.csv
results/communication-<label>-N<N>-P<P>.json
report/COMMUNICATION_<label>.md
results/solution-quality-<label>-N<N>-P<P>.json
report/SOLUTION_QUALITY_<label>.md
report/figures/runtime_vs_input_size.png
report/figures/rank_time_breakdown.png
report/figures/speedup.png
report/figures/trajectory_<label>.gif
report/figures/algorithm_trace_<label>.gif
report/ALGORITHM_TRACE_<label>.json
report/ARTIFACT_MANIFEST.md
report/artifacts/<bundle_name>/manifest.json
report/tables/runtime_table_<label>.csv
report/tables/speedup_table_<label>.csv
report/tables/load_balance_table_<label>.csv
report/tables/tables_manifest_<label>.json
report/RESULTS_SUMMARY_<label>.json
report/RESULTS_SUMMARY_<label>.md
results/environment-<label>.json
report/ENVIRONMENT_<label>.md
report/TEAM_OWNERSHIP_REPORT.json
report/TEAM_OWNERSHIP_REPORT.md
report/MEMBER_DEFENSE_GUIDE.json
report/MEMBER_DEFENSE_GUIDE.md
results/setup_doctor_<label>.json
report/SETUP_DOCTOR_<label>.md
report/BENCHMARK_PLAN.json
report/BENCHMARK_PLAN.md
report/BENCHMARK_BUDGET_<label>.json
report/BENCHMARK_BUDGET_<label>.md
results/granularity-<label>-N<N>-P<P>.json
report/GRANULARITY_<label>.md
report/EXPERIMENT_INDEX_<label>.json
report/EXPERIMENT_INDEX_<label>.md
report/REPORT_SYNC_<label>.json
report/REPORT_SYNC_<label>.md
report/FINAL_AUDIT_<label>.json
report/FINAL_AUDIT_<label>.md
submission/<label>/SUBMISSION_MANIFEST.json
submission/<label>/SUBMISSION_MANIFEST.md
```

## Current Ubuntu VM Artifacts

These artifacts prove that the owner's Ubuntu ARM64 VM can run the same project
pipeline with OpenMPI on one machine. They are deployment-readiness evidence,
not the final multi-machine LAN benchmark:

```text
results/ubuntu_vm_single/setup_doctor_ubuntu_vm_single.json
report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md
results/ubuntu_vm_single/serial-ubuntu-single-N4/summary.json
results/ubuntu_vm_single/mpi-ubuntu-single-N4-P2/summary.json
results/ubuntu_vm_single/mpi-ubuntu-single-N4-P2/rank_timings.csv
results/ubuntu_vm_single/mpi-ubuntu-single-N4-P2/comm_events.csv
results/ubuntu_vm_single/compare-ubuntu-single-N4-P2/correctness_report.json
results/ubuntu_vm_single/compare-ubuntu-single-N4-P2/task_comparison.csv
results/ubuntu_vm_single/serial-ubuntu-single-N8/summary.json
results/ubuntu_vm_single/mpi-ubuntu-single-N8-P4/summary.json
results/ubuntu_vm_single/mpi-ubuntu-single-N8-P4/rank_timings.csv
results/ubuntu_vm_single/mpi-ubuntu-single-N8-P4/comm_events.csv
results/ubuntu_vm_single/compare-ubuntu-single-N8-P4/correctness_report.json
results/ubuntu_vm_single/compare-ubuntu-single-N8-P4/task_comparison.csv
```

The current verified results are:

```text
doctor: ready: True
N=4, P=2: serial/MPI correctness passed, best cost difference 0.0
N=8, P=4: serial/MPI correctness passed, best cost difference 0.0
```

## Current Smoke Artifacts

These artifacts prove that the local serial/MPI pipeline runs, but they are not
the final benchmark results for the 2-3 minute experiment:

```text
results/serial-smoke-local-v2/summary.json
results/serial-smoke-local-v2/task_results.csv
results/mpi-smoke-local-np4/summary.json
results/mpi-smoke-local-np4/rank_timings.csv
results/mpi-smoke-local-np4/task_results.csv
results/compare-20260617-032727/correctness_report.json
results/compare-20260617-032727/task_comparison.csv
report/figures/best_path_smoke.png
report/figures/runtime_vs_input_size.png
report/figures/rank_time_breakdown.png
report/figures/speedup.png
report/figures/runtime_vs_input_size_mini_sweep.png
report/figures/speedup_mini_sweep.png
report/figures/trajectory_mini_sweep.gif
report/ARTIFACT_MANIFEST.md
report/artifacts/mini_sweep/manifest.json
results/mpi-mini_sweep-N2-P2/comm_events.csv
report/artifacts/mini_sweep/mpi/mpi-mini_sweep-N2-P2/comm_events.csv
results/communication-mini_sweep-N2-P2.json
report/COMMUNICATION_mini_sweep.md
results/solution-quality-mini_sweep-N2-P2.json
report/SOLUTION_QUALITY_mini_sweep.md
results/mpi-mini_sweep-N2-P2/task_assignment.csv
report/artifacts/mini_sweep/mpi/mpi-mini_sweep-N2-P2/task_assignment.csv
results/compare-mini_sweep-N2-P2/correctness_report.json
results/compare-mini_sweep-N2-P2/task_comparison.csv
report/tables/runtime_table_mini_sweep.csv
report/tables/speedup_table_mini_sweep.csv
report/tables/load_balance_table_mini_sweep.csv
report/tables/RESULTS_TABLES_mini_sweep.md
report/tables/tables_manifest_mini_sweep.json
report/RESULTS_SUMMARY_mini_sweep.json
report/RESULTS_SUMMARY_mini_sweep.md
results/environment-mini_sweep.json
report/ENVIRONMENT_mini_sweep.md
report/TEAM_OWNERSHIP_REPORT.json
report/TEAM_OWNERSHIP_REPORT.md
report/MEMBER_DEFENSE_GUIDE.json
report/MEMBER_DEFENSE_GUIDE.md
results/setup_doctor_mini_sweep.json
report/SETUP_DOCTOR_mini_sweep.md
report/BENCHMARK_PLAN.json
report/BENCHMARK_PLAN.md
report/BENCHMARK_BUDGET_mini_sweep.json
report/BENCHMARK_BUDGET_mini_sweep.md
results/granularity-mini_sweep-N2-P2.json
report/GRANULARITY_mini_sweep.md
report/EXPERIMENT_INDEX_mini_sweep.json
report/EXPERIMENT_INDEX_mini_sweep.md
report/REPORT_SYNC_mini_sweep.json
report/REPORT_SYNC_mini_sweep.md
report/FINAL_AUDIT_mini_sweep.json
report/FINAL_AUDIT_mini_sweep.md
submission/mini_sweep/SUBMISSION_MANIFEST.json
submission/mini_sweep/SUBMISSION_MANIFEST.md
results/smoke_validation_report.json
results/smoke_bundle_validation_report.json
results/validation-mini_sweep-N2-P2.json
results/estimate-local-benchmark-N4/summary.json
results/estimate-local-benchmark-N4/input_size_estimate.json
```

The smoke artifacts can be copied into a traceable bundle with:

```bash
python scripts/export_report_bundle.py \
  --bundle-name mini_sweep \
  --clean \
  --serial-run results/serial-mini_sweep-N2 \
  --mpi-run results/mpi-mini_sweep-N2-P2 \
  --correctness results/compare-mini_sweep-N2-P2/correctness_report.json \
  --label mini_sweep \
  --input-size 2
```

The mini-sweep report tables can be regenerated with:

```bash
python scripts/export_result_tables.py \
  --results results \
  --output report/tables \
  --label mini_sweep \
  --input-size 2
```

The mini-sweep report-ready Results summary can be regenerated with:

```bash
python scripts/export_results_summary.py \
  --label mini_sweep \
  --serial-run results/serial-mini_sweep-N2 \
  --mpi-run results/mpi-mini_sweep-N2-P2 \
  --correctness results/compare-mini_sweep-N2-P2/correctness_report.json \
  --tables-manifest report/tables/tables_manifest_mini_sweep.json \
  --granularity results/granularity-mini_sweep-N2-P2.json \
  --communication results/communication-mini_sweep-N2-P2.json \
  --solution-quality results/solution-quality-mini_sweep-N2-P2.json \
  --benchmark-budget report/BENCHMARK_BUDGET_mini_sweep.json \
  --figure report/figures/runtime_vs_input_size_mini_sweep.png \
  --figure report/figures/speedup_mini_sweep.png \
  --figure report/figures/mini_sweep_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png \
  --figure report/figures/trajectory_mini_sweep.gif \
  --output report/RESULTS_SUMMARY_mini_sweep.json \
  --markdown report/RESULTS_SUMMARY_mini_sweep.md
```

The current experiment index can be regenerated with:

```bash
python scripts/index_results.py \
  --results results \
  --report-dir report \
  --label mini_sweep \
  --output report/EXPERIMENT_INDEX_mini_sweep.json \
  --markdown report/EXPERIMENT_INDEX_mini_sweep.md
```

The current final-readiness audit can be regenerated with:

```bash
python scripts/audit_final_results.py \
  --results results \
  --report-dir report \
  --label mini_sweep \
  --input-sizes 2 \
  --process-counts 1,2 \
  --n 2 \
  --speedup-n 2 \
  --final-processes 2 \
  --bundle-name mini_sweep \
  --validation results/validation-mini_sweep-N2-P2.json \
  --communication results/communication-mini_sweep-N2-P2.json \
  --solution-quality results/solution-quality-mini_sweep-N2-P2.json \
  --ownership report/TEAM_OWNERSHIP_REPORT.json \
  --defense-guide report/MEMBER_DEFENSE_GUIDE.json \
  --benchmark-plan report/BENCHMARK_PLAN.json \
  --output report/FINAL_AUDIT_mini_sweep.json \
  --markdown report/FINAL_AUDIT_mini_sweep.md
```

The full local post-processing pipeline can be checked without rerunning the
sweep with:

```bash
python scripts/run_local_pipeline.py \
  --config configs/local_smoke.json \
  --input-sizes 2 \
  --process-counts 1,2 \
  --label mini_sweep \
  --final-n 2 \
  --load-balance-n 2 \
  --final-processes 2 \
  --skip-sweep \
  --dry-run
```

The optional GIF demo artifact can be regenerated with:

```bash
python scripts/animate_trajectory.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output report/figures/trajectory_mini_sweep.gif

python scripts/animate_algorithm_trace.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output report/figures/algorithm_trace_mini_sweep.gif \
  --trace-output report/ALGORITHM_TRACE_mini_sweep.json
```

After the final audit exists, the soft-submission package can be regenerated
without inventing any new result data:

```bash
python scripts/export_submission_package.py \
  --label mini_sweep \
  --report-dir report \
  --docs-dir docs \
  --output-dir submission \
  --clean
```

The environment artifact can also be regenerated alone with:

```bash
python scripts/capture_environment.py \
  --label mini_sweep \
  --output results/environment-mini_sweep.json \
  --markdown report/ENVIRONMENT_mini_sweep.md
```

The current team ownership report can be regenerated with:

```bash
python scripts/generate_ownership_report.py \
  --output report/TEAM_OWNERSHIP_REPORT.json \
  --markdown report/TEAM_OWNERSHIP_REPORT.md
```

The current member defense guide can be regenerated with:

```bash
python scripts/generate_defense_guide.py \
  --output report/MEMBER_DEFENSE_GUIDE.json \
  --markdown report/MEMBER_DEFENSE_GUIDE.md
```

The living report path-sync check can be regenerated with:

```bash
python scripts/check_report_sync.py \
  --label mini_sweep \
  --output report/REPORT_SYNC_mini_sweep.json \
  --markdown report/REPORT_SYNC_mini_sweep.md
```

Each teammate can check their Ubuntu VM setup with:

```bash
.venv/bin/python scripts/check_local_env.py
.venv/bin/python scripts/doctor_local_setup.py \
  --label ubuntu_vm_single \
  --run-mpi-probe \
  --mpi-processes 2

.venv/bin/python scripts/run_serial.py \
  --config configs/local_smoke.json \
  --run-id serial-ubuntu-single-N4 \
  --experiment-name ubuntu_single_N4 \
  --output-dir results \
  --total-tasks 4

mpirun -np 2 --bind-to none \
  /home/mpot/mpot/.venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --run-id mpi-ubuntu-single-N4-P2 \
  --experiment-name ubuntu_single_N4 \
  --output-dir results \
  --total-tasks 4

.venv/bin/python scripts/compare_serial_mpi.py \
  --serial results/serial-ubuntu-single-N4 \
  --mpi results/mpi-ubuntu-single-N4-P2 \
  --output-dir results \
  --run-id compare-ubuntu-single-N4-P2
```

Do not mark the Ubuntu/LAN cluster items as `Measured` until multiple teammate
VMs have real Bridged IPs, ping/SSH checks pass, and `mpirun --hostfile`
produces real CSV/JSON artifacts.

The current mini-sweep granularity analysis can be regenerated with:

```bash
python scripts/analyze_granularity.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output results/granularity-mini_sweep-N2-P2.json \
  --markdown report/GRANULARITY_mini_sweep.md \
  --label mini_sweep
```

The current mini-sweep communication analysis can be regenerated with:

```bash
python scripts/analyze_communication.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output results/communication-mini_sweep-N2-P2.json \
  --markdown report/COMMUNICATION_mini_sweep.md \
  --label mini_sweep
```

The current mini-sweep solution-quality check can be regenerated with:

```bash
python scripts/validate_solution_quality.py \
  --run-dir results/mpi-mini_sweep-N2-P2 \
  --output results/solution-quality-mini_sweep-N2-P2.json \
  --markdown report/SOLUTION_QUALITY_mini_sweep.md \
  --label mini_sweep
```

The current final-local benchmark plan can be regenerated with:

```bash
python scripts/plan_benchmark.py \
  --config configs/local_benchmark.json \
  --label final_macbook_air_2d \
  --sample-summary results/estimate-local-benchmark-N4/summary.json \
  --target-seconds 60 \
  --target-processes 4 \
  --parallel-efficiency 0.75 \
  --output report/BENCHMARK_PLAN.json \
  --markdown report/BENCHMARK_PLAN.md
```

The generated final-local pipeline command is currently:

```bash
python scripts/estimate_benchmark_budget.py \
  --plan report/BENCHMARK_PLAN.json \
  --output report/BENCHMARK_BUDGET_final_macbook_air_2d.json \
  --markdown report/BENCHMARK_BUDGET_final_macbook_air_2d.md \
  --label final_macbook_air_2d \
  --run-label final_macbook_air_2d \
  --results-dir results \
  --reuse-existing

python scripts/run_local_pipeline.py \
  --config configs/local_benchmark.json \
  --input-sizes 208,412,824 \
  --process-counts 1,2,4 \
  --label final_macbook_air_2d \
  --final-n 824 \
  --load-balance-n 412 \
  --final-processes 4 \
  --benchmark-plan report/BENCHMARK_PLAN.json \
  --skip-existing-runs
```

## Member Defense Checklist

Each member must understand the module they are assigned to in
`docs/team_ownership.md`.

| Member | Must explain | Must demo | Status |
|---|---|---|---|
| Member A | 2D problem, trajectory, obstacles, cost function, config | `python scripts/run_serial.py --config configs/local_smoke.json` | Implemented |
| Member B | Local MPOT-style task, serial baseline, deterministic best selection | `python scripts/run_serial.py --config configs/local_smoke.json`, `python scripts/compare_serial_mpi.py --serial results/serial-mini_sweep-N2 --mpi results/mpi-mini_sweep-N2-P2` | Implemented |
| Member C | MPI ranks, cyclic mapping, blocking communication, timing | `mpirun -np 4 python scripts/run_mpi.py --config configs/local_smoke.json`, `python scripts/analyze_communication.py --run-dir results/mpi-mini_sweep-N2-P2 --output results/communication-mini_sweep-N2-P2.json --markdown report/COMMUNICATION_mini_sweep.md --label mini_sweep` | Implemented |
| Member D | Metrics, plots, result tables, load-balance evidence, balanced ownership | `python scripts/generate_ownership_report.py`, `python scripts/generate_defense_guide.py`, `python scripts/analyze_granularity.py --run-dir results/mpi-mini_sweep-N2-P2 --output results/granularity-mini_sweep-N2-P2.json --markdown report/GRANULARITY_mini_sweep.md --label mini_sweep`, `python scripts/plot_results.py --results results --output report/figures --label mini_sweep --input-size 2` | Implemented |

## Living Report Rules

- Update `REPORT_DRAFT.md` when important file names or implementation behavior
  change.
- Update this checklist when a requirement moves from design to code to
  measured artifact.
- Keep Results empty of numerical claims until real experiment artifacts exist.
- Copy final report figures into `report/figures/`.
- Use `scripts/export_report_bundle.py` to create a manifest before writing
  measured claims in Results.
- Use `scripts/export_submission_package.py` only after validation/final audit,
  so the package contains real checklist, audit, figure, and table artifacts.
- If a planned module is renamed, update both this checklist and the
  Implementation section of the draft.
