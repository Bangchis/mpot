# Setup Doctor

This file checks whether one teammate machine is ready to run the
local-first MPOT/MPI benchmark.

- created_at: `2026-06-17 12:23:14 +0000`
- label: `ubuntu_vm_single`
- verdict: **PASS**
- repo_root: `/home/mpot/mpot`
- OS: `Linux 7.0.0-22-generic`
- Python: `3.14.4`
- Python executable: `/home/mpot/mpot/.venv/bin/python`

## Checks

| status | check | detail |
|---|---|---|
| PASS | repo root exists | `/home/mpot/mpot` |
| PASS | python version is supported | `observed=3.14.4, required>=3.9` |
| PASS | repo import works: mpot | `import ok` |
| PASS | package installed: torch | `2.12.0+cpu` |
| PASS | package installed: numpy | `2.4.6` |
| PASS | package installed: matplotlib | `3.11.0` |
| PASS | package installed: pillow | `12.2.0` |
| PASS | package installed: mpi4py | `4.1.2` |
| PASS | mpirun executable exists | `/usr/bin/mpirun` |
| PASS | mpi runtime probe passed | `returncode=0, output=[mpot-a][[54545,1],1][../../../../../../opal/mca/btl/tcp/btl_tcp_proc.c:266:mca_btl_tcp_proc_create_interface_graph] Unable to find reachable pairing between local and remote interfaces | [mpot-a][[54545,1],0][../../../../../../opal/mca/btl/tcp/btl_tcp_proc.c:266:mca_btl_tcp_proc_create_interface_graph] Unable to find reachable pairing between local and remote interfaces | rank=0 size=2 | rank=1 size=2` |

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
