# Team Code Ownership Report

This report is generated from the current repository state. It supports
the course requirement that each member owns at least 250 lines of
meaningful project code or configuration.

- created_at: `2026-06-17 15:22:46 +0700`
- verdict: **PASS**
- minimum_lines_per_member: `250`
- recommended_max_lines_per_member: `700`
- minimum_total_lines: `1000`
- total_meaningful_lines: `2343`
- failed_members: `0`

## Member Summary

| status | member | area | files | meaningful lines | minimum | recommended max |
|---|---|---|---:|---:|---:|---:|
| PASS | Member A | 2D planning problem and configuration | 7 | 663 | 250 | 700 |
| PASS | Member B | Local optimizer, serial baseline, and correctness | 5 | 519 | 250 | 700 |
| PASS | Member C | MPI parallelization, mapping, rank behavior, and communication trace | 5 | 496 | 250 | 700 |
| PASS | Member D | Metrics, plots, result tables, and load-balance evidence | 5 | 665 | 250 | 700 |

## File Details

| member | file | counted | meaningful | total | note |
|---|---|---:|---:|---:|---|
| Member A | `mpot/benchmarks/problem_2d.py` | yes | 272 | 341 | python nonblank noncomment lines |
| Member A | `mpot/benchmarks/config.py` | yes | 150 | 200 | python nonblank noncomment lines |
| Member A | `configs/local_smoke.json` | yes | 47 | 48 | json nonblank config lines |
| Member A | `configs/local_benchmark.json` | yes | 48 | 49 | json nonblank config lines |
| Member A | `configs/variant_open_2d.json` | yes | 46 | 46 | json nonblank config lines |
| Member A | `configs/variant_narrow_passage_2d.json` | yes | 49 | 49 | json nonblank config lines |
| Member A | `configs/variant_cluttered_2d.json` | yes | 51 | 51 | json nonblank config lines |
| Member B | `mpot/benchmarks/local_runner.py` | yes | 160 | 197 | python nonblank noncomment lines |
| Member B | `mpot/benchmarks/reduction.py` | yes | 96 | 122 | python nonblank noncomment lines |
| Member B | `mpot/benchmarks/correctness.py` | yes | 177 | 205 | python nonblank noncomment lines |
| Member B | `scripts/run_serial.py` | yes | 51 | 66 | python nonblank noncomment lines |
| Member B | `scripts/compare_serial_mpi.py` | yes | 35 | 48 | python nonblank noncomment lines |
| Member C | `mpot/benchmarks/mpi_scheduler.py` | yes | 47 | 69 | python nonblank noncomment lines |
| Member C | `mpot/benchmarks/mpi_runner.py` | yes | 230 | 255 | python nonblank noncomment lines |
| Member C | `mpot/benchmarks/communication.py` | yes | 152 | 181 | python nonblank noncomment lines |
| Member C | `scripts/run_mpi.py` | yes | 28 | 40 | python nonblank noncomment lines |
| Member C | `scripts/analyze_communication.py` | yes | 39 | 52 | python nonblank noncomment lines |
| Member D | `mpot/benchmarks/metrics.py` | yes | 59 | 85 | python nonblank noncomment lines |
| Member D | `mpot/benchmarks/plots.py` | yes | 192 | 228 | python nonblank noncomment lines |
| Member D | `mpot/benchmarks/result_tables.py` | yes | 330 | 381 | python nonblank noncomment lines |
| Member D | `scripts/analyze_granularity.py` | yes | 40 | 53 | python nonblank noncomment lines |
| Member D | `scripts/plot_results.py` | yes | 44 | 57 | python nonblank noncomment lines |

## Duplicate Ownership

No counted source/config file is assigned to more than one member.

Counts cover the compact primary defense set for each member. They exclude blank Python lines, Python comment-only lines, docs, slides, results, report text, and shared support modules that no single member has to defend in full.
