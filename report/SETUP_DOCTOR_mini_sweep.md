# Setup Doctor

This file checks whether one teammate machine is ready to run the
local-first MPOT/MPI benchmark.

- created_at: `2026-06-17 04:29:41 +0700`
- label: `mini_sweep`
- verdict: **PASS**
- repo_root: `/Users/bangbang/Desktop/code python/mpot`
- OS: `Darwin 25.2.0`
- Python: `3.11.15`
- Python executable: `/Users/bangbang/Desktop/code python/mpot/.venv/bin/python`

## Checks

| status | check | detail |
|---|---|---|
| PASS | repo root exists | `/Users/bangbang/Desktop/code python/mpot` |
| PASS | python version is supported | `observed=3.11.15, required>=3.9` |
| PASS | repo import works: mpot | `import ok` |
| PASS | package installed: torch | `2.12.0` |
| PASS | package installed: numpy | `2.4.6` |
| PASS | package installed: matplotlib | `3.11.0` |
| PASS | package installed: mpi4py | `4.1.2` |
| PASS | mpirun executable exists | `/opt/homebrew/bin/mpirun` |
| PASS | mpi runtime probe passed | `returncode=0, output=rank=1 size=2 | rank=0 size=2` |

## Recommended Install Commands

```bash
python -m pip install -r requirements-local.txt
```
```bash
python -m pip install -e . --no-deps
```

## Recommended Smoke Command

```bash
python scripts/run_local_pipeline.py --config configs/local_smoke.json --input-sizes 2 --process-counts 1,2 --label teammate_smoke --final-n 2 --load-balance-n 2 --final-processes 2
```
