# Local To Ubuntu Phase Plan

This document is the project execution plan. It is intentionally a planning
guide, not a script. Use it to decide what must be finished locally before the
group spends time setting up Ubuntu VMs and LAN MPI.

## Current Truth

As of 2026-06-17:

- Local code is runnable.
- Serial baseline works.
- MPI works on one macOS machine with multiple local processes.
- The `mini_sweep` pipeline passed correctness, communication, granularity,
  plotting, report sync, validation, final audit, and submission-package checks.
- The local final run `final_macbook_air_2d` has now been executed on one
  macOS machine.
- `report/FINAL_AUDIT_final_macbook_air_2d.md` says PASS.
- The local final run is valid for local-first development evidence, but its
  measured runtime is shorter than the professor's suggested 2-3 minute target.
  If the final report must strictly satisfy that target, run a larger-N local or
  Ubuntu/LAN benchmark later.
- The owner's Ubuntu ARM64 VM `mpot-a` is installed and has passed the
  single-VM OpenMPI smoke tests:
  - `doctor_local_setup.py --label ubuntu_vm_single` reports `ready: True`.
  - `serial-ubuntu-single-N4` vs `mpi-ubuntu-single-N4-P2` passed correctness
    with best cost difference `0.0`.
  - `serial-ubuntu-single-N8` vs `mpi-ubuntu-single-N8-P4` passed correctness
    with best cost difference `0.0`.
  - Artifacts were copied back to `results/ubuntu_vm_single/` and
    `report/ubuntu_vm_single/`.

Ubuntu VM/LAN setup is now in the teammate replication phase. The next gate is
for every teammate VM to pass the same single-VM smoke before attempting LAN
hostfile MPI.

## Phase 0: Freeze The 2D Scope

Decision:

```text
Only solve the 2D point-robot benchmark for this project.
Do not switch to 3D/Panda.
Do not add GPU/CUDA/MPS requirements.
```

Reason:

- The professor grades parallelization, demo, report, and member
  understanding.
- 2D is enough to explain trajectory, obstacles, cost, and MPI task-level
  parallelism.
- The group has about one week left from 2026-06-17 to the 2026-06-24
  deadline, so the risk should stay low.

## Phase 1: Finish Local Code Readiness

Goal:

```text
The code must be understandable, testable, and runnable on one machine before
moving to Ubuntu.
```

Current status:

```text
Status: done for current local-first implementation
Evidence: mini_sweep and final_macbook_air_2d pipelines passed
Remaining: optional larger-N run if strict 2-3 minute timing is required
```

Must-pass checks:

```bash
.venv/bin/python -m unittest tests/test_benchmark_core.py

.venv/bin/python scripts/run_local_pipeline.py \
  --config configs/local_smoke.json \
  --input-sizes 2 \
  --process-counts 1,2 \
  --label mini_sweep \
  --final-n 2 \
  --load-balance-n 2 \
  --final-processes 2 \
  --skip-sweep \
  --benchmark-plan report/BENCHMARK_PLAN.json \
  --skip-existing-runs
```

Exit gate:

- Tests pass.
- `report/FINAL_AUDIT_mini_sweep.md` says PASS.
- `report/REPORT_SYNC_mini_sweep.md` says missing references = 0.
- All four member ownership counts remain over 250 meaningful lines and under
  the readable-size limit.

## Phase 2: Run Final Local Benchmark On MacBook Air

Goal:

```text
Generate real local final benchmark data before Ubuntu.
```

This stage is complete for the current safe local setting.

Recommended safe local setting:

```text
label: final_macbook_air_2d
config: configs/local_benchmark.json
input sizes: 208,412,824
process counts: 1,2,4
load-balance N: 412
speedup/correctness 2N: 824
estimated full sweep: about 32 minutes
```

Command:

```bash
.venv/bin/python scripts/run_local_pipeline.py \
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

Why `--skip-existing-runs`:

- If the laptop sleeps or the run is interrupted, rerun the same command.
- Completed runs are reused only if `summary.json` metadata and config hash
  match.

Exit gate:

- `results/serial-final_macbook_air_2d-N208/summary.json` exists.
- `results/serial-final_macbook_air_2d-N412/summary.json` exists.
- `results/serial-final_macbook_air_2d-N824/summary.json` exists.
- `results/mpi-final_macbook_air_2d-N824-P4/summary.json` exists.
- `report/FINAL_AUDIT_final_macbook_air_2d.md` says PASS.
- `report/RESULTS_SUMMARY_final_macbook_air_2d.md` exists and is generated
  from real artifacts.
- `report/figures/runtime_vs_input_size_final_macbook_air_2d.png` exists.
- `report/figures/speedup_final_macbook_air_2d.png` exists.
- `report/figures/trajectory_final_macbook_air_2d.gif` exists.

The Results section can now use the `final_macbook_air_2d` local artifacts.
However, do not claim that this local run satisfies the 2-3 minute target unless
a later larger-N run produces that timing.

## Phase 3: Prepare Ubuntu VM Setup Plan

Goal:

```text
Install one Ubuntu VM on the owner's MacBook, run the repo inside that VM, and
prove single-VM OpenMPI works before connecting teammate machines.
```

This phase is complete for the owner's first VM. It is still pending for the
teammate VMs.

First VM on the owner's MacBook:

```text
Install one Ubuntu ARM64/aarch64 VM.
Use Shared Networking for the first single-VM smoke test, or Bridged if it
works immediately.
Use CPU only.
Install OpenMPI, mpi4py, Python venv, and the project repo.
```

Recommended VM resources:

```text
CPU: 4 virtual cores
RAM: 6-8 GB
Disk: 40 GB or more
Network for first VM test: Shared or Bridged
Network for later LAN: Bridged or another reachable LAN IP setup
```

Per-VM setup commands are documented in:

```text
docs/ubuntu_vm_cluster_setup.md
docs/teammate_vm_quickstart.md
```

Exit gate for each VM:

```bash
cd /home/mpot/mpot
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

The doctor command must print `ready: True`, and
`results/serial-ubuntu-single-N4/summary.json`,
`results/mpi-ubuntu-single-N4-P2/summary.json`, and
`results/compare-ubuntu-single-N4-P2/correctness_report.json` must exist.

After the owner's VM passes, every teammate repeats the same VM setup on their
own MacBook. Only then move to Phase 4.

Owner VM evidence:

```text
results/ubuntu_vm_single/setup_doctor_ubuntu_vm_single.json
results/ubuntu_vm_single/serial-ubuntu-single-N4/summary.json
results/ubuntu_vm_single/mpi-ubuntu-single-N4-P2/summary.json
results/ubuntu_vm_single/compare-ubuntu-single-N4-P2/correctness_report.json
results/ubuntu_vm_single/serial-ubuntu-single-N8/summary.json
results/ubuntu_vm_single/mpi-ubuntu-single-N8-P4/summary.json
results/ubuntu_vm_single/compare-ubuntu-single-N8-P4/correctness_report.json
report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md
```

## Phase 4: Connect VMs On One Wi-Fi/LAN

Goal:

```text
Rank 0 VM can SSH into every other VM without a password.
OpenMPI can launch ranks on all VMs.
```

Network rules:

- All VMs must be on the same Wi-Fi/LAN.
- Bridged Adapter must be enabled.
- Every VM must report a LAN-reachable IP from `hostname -I`.
- If an address is still only `192.168.64.x`, the VM is probably still on UTM
  Shared Networking and should not be used for LAN MPI yet.
- Use one VM per physical laptop.
- Do not use cloud servers.
- If Wi-Fi blocks peer-to-peer traffic, switch to another router or wired LAN.

Rank 0 ping checks:

```bash
ping <vm-b-ip>
ping <vm-c-ip>
ping <vm-d-ip>
```

Rank 0 SSH checks:

```bash
ssh mpot@<vm-a-ip> hostname
ssh mpot@<vm-b-ip> hostname
ssh mpot@<vm-c-ip> hostname
ssh mpot@<vm-d-ip> hostname
```

Hostfile example:

```text
192.168.1.101 slots=4 # mpot-a
192.168.1.102 slots=4 # mpot-b
192.168.1.103 slots=4 # mpot-c
192.168.1.104 slots=4 # mpot-d
```

MPI probe:

```bash
mpirun --hostfile configs/hostfile_ubuntu.txt \
  -np 12 \
  --map-by slot \
  --bind-to none \
  /home/mpot/mpot/.venv/bin/python -c "from mpi4py import MPI; import socket; comm=MPI.COMM_WORLD; print(f'host={socket.gethostname()} rank={comm.Get_rank()} size={comm.Get_size()}', flush=True)"
```

Use `-np 12` for three 4-slot VMs, or `-np 16` for four 4-slot VMs.

Exit gate:

- The MPI probe prints ranks from more than one hostname.
- The printed `size` equals the requested `-np`.
- No rank asks for an SSH password.

## Phase 5: Run Ubuntu Cluster Smoke

Goal:

```text
Prove the project code runs across multiple Ubuntu VMs before running the heavy
benchmark.
```

Command shape:

```bash
mpirun --hostfile configs/hostfile_ubuntu.txt \
  -np 12 \
  --map-by slot \
  --bind-to none \
  /home/mpot/mpot/.venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --run-id mpi-cluster-smoke-N12-P12 \
  --experiment-name cluster_smoke_N12 \
  --output-dir results \
  --total-tasks 12
```

Exit gate:

- `results/mpi-cluster-smoke-N12-P12/summary.json` exists.
- `rank_timings.csv` contains rows from multiple hostnames.
- `comm_events.csv` records `bcast`, `scatter`, and `gather`.
- `task_assignment.csv` proves cyclic mapping.

## Phase 6: Plan Ubuntu Final Benchmark From Ubuntu Timing

Goal:

```text
Choose Ubuntu/LAN N using Ubuntu timing, not macOS timing.
```

Run a small Ubuntu sample first:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/local_benchmark.json \
  --run-id estimate-ubuntu-N4 \
  --experiment-name estimate_ubuntu_N4 \
  --output-dir results \
  --total-tasks 4
```

Then generate an Ubuntu benchmark plan:

```bash
.venv/bin/python scripts/plan_benchmark.py \
  --config configs/local_benchmark.json \
  --label final_ubuntu_lan_2d \
  --sample-summary results/estimate-ubuntu-N4/summary.json \
  --target-seconds 120 \
  --target-processes 12 \
  --parallel-efficiency 0.75 \
  --output report/BENCHMARK_PLAN_ubuntu.json \
  --markdown report/BENCHMARK_PLAN_ubuntu.md
```

Use `--target-processes 16` if there are four 4-slot VMs.

Exit gate:

- `report/BENCHMARK_PLAN_ubuntu.md` exists.
- `report/BENCHMARK_BUDGET_ubuntu.md` estimates the sweep within available
  time.
- The planned `N` and `2N` are recorded in the report checklist.

## Phase 7: Run Ubuntu Final Benchmark

Goal:

```text
Produce final multi-machine MPI artifacts for the report if time allows.
```

Command shape:

```bash
.venv/bin/python scripts/run_local_pipeline.py \
  --config configs/local_benchmark.json \
  --input-sizes <from-plan> \
  --process-counts <from-plan> \
  --label final_ubuntu_lan_2d \
  --final-n <2N-from-plan> \
  --load-balance-n <N-from-plan> \
  --final-processes 12 \
  --benchmark-plan report/BENCHMARK_PLAN_ubuntu.json \
  --skip-existing-runs \
  --hostfile configs/hostfile_ubuntu.txt \
  --map-by slot \
  --bind-to none
```

Exit gate:

- `report/FINAL_AUDIT_final_ubuntu_lan_2d.md` says PASS.
- `report/RESULTS_SUMMARY_final_ubuntu_lan_2d.md` exists.
- Runtime, speedup, granularity, communication, correctness, and solution
  quality artifacts exist.

If this phase is too risky near the deadline, submit with the final local
MacBook Air results and explain Ubuntu/LAN as deployment extension. If Ubuntu
cluster results are available and pass audit, use them as the stronger final
Results.

## Decision Rule

Use this order:

```text
1. Mini local pass proves code path works.
2. Final local pass gives safe reportable data.
3. Ubuntu VM single-node doctor proves each teammate machine is ready.
4. Ubuntu LAN MPI smoke proves multi-machine launch works.
5. Ubuntu final benchmark gives strongest final result if time allows.
```

Do not skip Phase 2. Without final local artifacts, the project has runnable
code but not final measured Results.
