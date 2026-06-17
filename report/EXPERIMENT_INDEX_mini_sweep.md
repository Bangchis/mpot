# Experiment Index

This index is generated from local artifacts. Use it to navigate real
runs and report evidence without guessing filenames.

- created_at: `2026-06-17 06:48:27 +0700`
- label: `mini_sweep`
- results_dir: `results`
- report_dir: `report`

## Counts

| item | count |
|---|---:|
| runs | 3 |
| serial_runs | 1 |
| mpi_runs | 2 |
| correctness_reports | 1 |
| validation_reports | 1 |
| environment_reports | 1 |
| granularity_reports | 1 |
| communication_reports | 1 |
| solution_quality_reports | 1 |
| ownership_reports | 1 |
| defense_guides | 1 |
| report_manifests | 1 |
| table_manifests | 1 |

## Runs

| run_id | mode | N | processes | runtime_with_comm_s | runtime_without_comm_s | rank_timings | comm_events | task_assignment | summary |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| mpi-mini_sweep-N2-P1 | mpi | 2 | 1 | 0.484948 | 0.484671 | yes | yes | yes | `results/mpi-mini_sweep-N2-P1/summary.json` |
| serial-mini_sweep-N2 | serial | 2 | 1 | 0.938341 | 0.938341 | no | no | no | `results/serial-mini_sweep-N2/summary.json` |
| mpi-mini_sweep-N2-P2 | mpi | 2 | 2 | 0.537446 | 0.536736 | yes | yes | yes | `results/mpi-mini_sweep-N2-P2/summary.json` |

## Correctness Reports

| path | run_id | passed |
|---|---|---:|
| `results/compare-mini_sweep-N2-P2/correctness_report.json` | `compare-mini_sweep-N2-P2` | yes |

## Validation Reports

| path | run_id | passed |
|---|---|---:|
| `results/validation-mini_sweep-N2-P2.json` | `results` | yes |

## Environment Reports

| path | run_id | passed |
|---|---|---:|
| `results/environment-mini_sweep.json` | `results` |  |

## Granularity Reports

| path | run_id | passed |
|---|---|---:|
| `results/granularity-mini_sweep-N2-P2.json` | `mpi-mini_sweep-N2-P2` | yes |

## Communication Reports

| path | run_id | passed |
|---|---|---:|
| `results/communication-mini_sweep-N2-P2.json` | `mpi-mini_sweep-N2-P2` | yes |

## Solution Quality Reports

| path | run_id | passed |
|---|---|---:|
| `results/solution-quality-mini_sweep-N2-P2.json` | `mpi-mini_sweep-N2-P2` | yes |

## Team Ownership Reports

| path | run_id | passed |
|---|---|---:|
| `report/TEAM_OWNERSHIP_REPORT.json` | `report` | yes |

## Member Defense Guides

| path | run_id | passed |
|---|---|---:|
| `report/MEMBER_DEFENSE_GUIDE.json` | `report` | yes |

## Report Manifests

| path | run_id | passed |
|---|---|---:|
| `report/artifacts/mini_sweep/manifest.json` | `mini_sweep` |  |

## Table Manifests

| path | run_id | passed |
|---|---|---:|
| `report/tables/tables_manifest_mini_sweep.json` | `tables` |  |
