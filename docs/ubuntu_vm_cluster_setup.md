# Ubuntu VM LAN Cluster Setup

This runbook prepares the final multi-machine demo for the MPOT/MPI course
project. The local macOS run remains the first checkpoint. Use this only after
the local `mini_sweep` pipeline passes.

For a shorter teammate-facing checklist, use
`docs/teammate_vm_quickstart.md`. This file is the detailed reference; the
quickstart is the version to send to group members.

## Current Stage

As of 2026-06-17, the macOS local implementation is working and has a passing
`final_macbook_air_2d` result. The owner's first Ubuntu VM (`mpot-a`) has also
passed a single-VM OpenMPI smoke test. The next step is not the full LAN
benchmark yet. The current flow is:

```text
Install one Ubuntu VM on the owner's MacBook -> run the repo inside that VM ->
prove single-VM OpenMPI works -> repeat on teammate VMs -> then prepare
teammate/LAN connection.
```

Do not start by debugging four machines at once. Each teammate VM must pass the
local doctor and MPI smoke test first.

Current owner-VM evidence copied back to macOS:

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

## Goal

Final environment:

- 3 or 4 physical MacBook Air machines.
- Exactly one Ubuntu ARM64 VM per physical MacBook.
- All VMs connected to the same Wi-Fi/LAN using bridged networking.
- OpenMPI + `mpi4py` inside the Ubuntu VMs.
- CPU only. No CUDA, no Apple MPS, no cloud VMs.

The algorithm does not change on Ubuntu. First, one VM uses single-machine
`mpirun -np P`. Later, the LAN run changes the launcher to hostfile-based
`mpirun`.

## Recommended VM Tool And Ubuntu Version

For Apple Silicon MacBooks, use an ARM64/aarch64 Ubuntu image and virtualization
rather than x64 emulation.

Recommended low-risk setup for this project:

```text
VM app: UTM
Ubuntu image: Ubuntu Server ARM64 LTS
Version choice: use the same Ubuntu LTS version on all group VMs
```

Notes:

- UTM uses Apple's Hypervisor virtualization framework for ARM64 guests on
  Apple Silicon, so this is the simplest free option for the group.
- Ubuntu 26.04 LTS is the latest LTS on Ubuntu's official download page as of
  2026-06-17. Ubuntu 24.04 LTS is also fine if the group already installed it
  and package installation works.
- Use Server if you are comfortable with the terminal. Use Desktop only if a
  teammate needs a GUI. The project itself is terminal/CPU-only.

Reference links:

- UTM: `https://mac.getutm.app/`
- Ubuntu Server: `https://ubuntu.com/download/server`
- Ubuntu Server ARM: `https://ubuntu.com/download/server/arm`

## VM Settings

Recommended VM resources per physical MacBook:

```text
CPU: 4 virtual cores
RAM: 6-8 GB
Disk: 40 GB or more
Network for first single-VM test: Shared networking is acceptable
Network for later multi-machine LAN: Bridged networking or any mode that gives
  the VM a reachable LAN IP
```

If the MacBook has only 8 GB RAM, use 2-4 virtual cores and 4 GB RAM. The first
Ubuntu smoke test is small; it does not need the full benchmark resources.

Do not run multiple Ubuntu VMs on one physical machine for the final demo.

## Stage A: Install One Ubuntu VM On Your Mac First

This is the stage to do now.

### A1. Create The VM

In UTM:

```text
Create a new VM
Choose Virtualize
Choose Linux
Attach the Ubuntu ARM64 Server ISO
Set CPU/RAM/Disk using the VM settings above
Use Shared Networking for the first smoke test, or Bridged if it works now
Install Ubuntu normally
Create user: mpot
Hostname suggestion: mpot-a
```

After first boot, check the architecture:

```bash
uname -m
```

Expected:

```text
aarch64
```

If it prints `x86_64` on an Apple Silicon Mac, the VM is emulating x64 and will
be slower than needed. Recreate the VM with the ARM64 image.

### A2. Install System Packages

Run this inside the Ubuntu VM:

```bash
sudo apt update
sudo apt install -y \
  git \
  rsync \
  python3 \
  python3-venv \
  python3-pip \
  build-essential \
  openmpi-bin \
  libopenmpi-dev \
  openssh-server
sudo systemctl enable --now ssh
```

Record the VM's IP address:

```bash
hostname -I
ip addr
```

Optional but useful hostnames:

```bash
sudo hostnamectl set-hostname mpot-a
```

Use `mpot-a`, `mpot-b`, `mpot-c`, `mpot-d` for the four VMs.

### A3. Put The Repo In The VM

Use this path inside every VM, including your first VM:

```text
/home/mpot/mpot
```

If the project is available through Git:

```bash
git clone <your-repo-url> /home/mpot/mpot
cd /home/mpot/mpot
```

If there is no Git remote yet, copy from the Mac host with `rsync` after SSH
from macOS to the VM works:

```bash
rsync -av \
  --exclude .venv \
  --exclude results \
  --exclude submission \
  --exclude __pycache__ \
  ./ mpot@<vm-ip>:/home/mpot/mpot/
```

Run the command from the macOS repo directory:

```bash
cd "/Users/bangbang/Desktop/code python/mpot"
```

Later, repeat the same repo path on every teammate VM.

### A4. Create Python Environment

Run this inside `/home/mpot/mpot` in the VM:

```bash
cd /home/mpot/mpot
python3 -m venv .venv
.venv/bin/python -m pip install -U pip wheel setuptools
.venv/bin/python -m pip install numpy matplotlib pillow mpi4py
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e . --no-deps
```

Use the explicit CPU-only PyTorch install command above inside the Ubuntu VM.
Do not use a plain `pip install -r requirements-local.txt` there if it starts
downloading CUDA/NVIDIA wheels such as `nvidia_nccl_*`; this project is CPU-only
and those packages can fill the VM disk.

### A5. Single-VM Readiness And Project Smoke

Check package and MPI installation first:

```bash
.venv/bin/python scripts/check_local_env.py
.venv/bin/python scripts/doctor_local_setup.py \
  --label ubuntu_vm_single \
  --run-mpi-probe \
  --mpi-processes 2
```

Expected final line:

```text
ready: True
```

Then run the serial baseline, the MPI version, and a correctness comparison
inside the single VM:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/local_smoke.json \
  --run-id serial-ubuntu-single-N4 \
  --experiment-name ubuntu_single_N4 \
  --output-dir results \
  --total-tasks 4
```

```bash
mpirun -np 2 --bind-to none \
  /home/mpot/mpot/.venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --run-id mpi-ubuntu-single-N4-P2 \
  --experiment-name ubuntu_single_N4 \
  --output-dir results \
  --total-tasks 4
```

```bash
.venv/bin/python scripts/compare_serial_mpi.py \
  --serial results/serial-ubuntu-single-N4 \
  --mpi results/mpi-ubuntu-single-N4-P2 \
  --output-dir results \
  --run-id compare-ubuntu-single-N4-P2
```

Exit gate for your first VM:

```text
results/serial-ubuntu-single-N4/summary.json exists
results/mpi-ubuntu-single-N4-P2/summary.json exists
results/mpi-ubuntu-single-N4-P2/rank_timings.csv exists
results/mpi-ubuntu-single-N4-P2/comm_events.csv exists
results/compare-ubuntu-single-N4-P2/correctness_report.json exists
doctor command prints ready: True
```

Owner VM verification status on 2026-06-17:

```text
mpot-a doctor: ready: True
N=4 serial vs MPI P=2: passed, best cost difference 0.0
N=8 serial vs MPI P=4: passed, best cost difference 0.0
Artifacts copied to: results/ubuntu_vm_single/
```

OpenMPI may print a non-fatal TCP interface warning in the UTM Shared Network
mode. For the single-VM smoke, the important condition is that every rank runs
and the serial/MPI comparison passes. For LAN testing, switch to Bridged and
verify ping/SSH before using a hostfile.

Only after this should the group spend time on multi-machine SSH/hostfile.

## Stage B: Repeat On Every Teammate VM

After the first VM works, each teammate should repeat Stage A on their own
MacBook. Keep these values identical across machines:

```text
Ubuntu LTS version
repo path: /home/mpot/mpot
Python venv path: /home/mpot/mpot/.venv/bin/python
package install commands
```

Each teammate should send back:

```text
hostname
hostname -I output
doctor ready: True
summary path from serial-ubuntu-single-N4
summary path from mpi-ubuntu-single-N4-P2
correctness report path from compare-ubuntu-single-N4-P2
```

## Stage C: Connect VMs On LAN

Do not start this stage until every VM has passed Stage A. A cluster run is only
as stable as the least-ready teammate VM.

### C1. LAN Connection Checklist

Put every physical MacBook on the same Wi-Fi, hotspot, or wired router. In UTM,
change each Ubuntu VM network mode to Bridged, or any mode that gives the VM a
LAN-reachable IP.

Each VM records its IP:

```bash
hostname -I
```

The LAN IPs should usually be in the same range, for example
`192.168.1.x` or `192.168.0.x`. If a VM still reports only an address such as
`192.168.64.x`, it is probably still using UTM Shared Networking and may not be
reachable from other physical laptops.

From the rank 0 VM, ping every worker:

```bash
ping 192.168.1.102
ping 192.168.1.103
ping 192.168.1.104
```

Stop and fix networking if ping cannot reach a worker. Common causes are Shared
Networking, router client isolation, or different Wi-Fi networks.

### C2. Enable Passwordless SSH From Rank 0

Choose one VM as rank 0, usually `mpot-a`. From `mpot-a`, generate a key:

```bash
ssh-keygen -t ed25519 -C mpot-cluster
```

Copy it to every VM, including `mpot-a` itself:

```bash
ssh-copy-id mpot@192.168.1.101
ssh-copy-id mpot@192.168.1.102
ssh-copy-id mpot@192.168.1.103
ssh-copy-id mpot@192.168.1.104
```

Test SSH from rank 0:

```bash
ssh mpot@192.168.1.101 hostname
ssh mpot@192.168.1.102 hostname
ssh mpot@192.168.1.103 hostname
ssh mpot@192.168.1.104 hostname
```

OpenMPI uses SSH to launch workers. If SSH asks for a password during `mpirun`,
fix SSH before debugging Python.

### C3. Generate Hostfile

Copy the example inventory and replace IPs, user, and slots:

```bash
cd /home/mpot/mpot
cp configs/cluster_hosts.example.json configs/cluster_hosts.local.json
```

Edit `configs/cluster_hosts.local.json`. Example for three VMs with 4 slots
each:

```json
{
  "cluster_name": "mpot_ubuntu_vm_lan",
  "default_user": "mpot",
  "default_repo_dir": "/home/mpot/mpot",
  "default_venv_python": "/home/mpot/mpot/.venv/bin/python",
  "hosts": [
    {"name": "mpot-a", "address": "192.168.1.101", "slots": 4},
    {"name": "mpot-b", "address": "192.168.1.102", "slots": 4},
    {"name": "mpot-c", "address": "192.168.1.103", "slots": 4}
  ]
}
```

Generate hostfile and command guide:

```bash
.venv/bin/python scripts/prepare_cluster_hostfile.py \
  --inventory configs/cluster_hosts.local.json \
  --hostfile configs/hostfile_ubuntu.txt \
  --output report/CLUSTER_PLAN_local.json \
  --markdown report/CLUSTER_PLAN_local.md
```

The generated hostfile looks like:

```text
192.168.1.101 slots=4 # mpot-a
192.168.1.102 slots=4 # mpot-b
192.168.1.103 slots=4 # mpot-c
```

Do not commit `configs/cluster_hosts.local.json` if it contains private LAN IPs
or personal usernames.

### C4. Hostfile And MPI Cluster Smoke

Run an MPI rank-distribution probe from rank 0:

```bash
cd /home/mpot/mpot
mpirun --hostfile configs/hostfile_ubuntu.txt \
  -np 12 \
  --map-by slot \
  --bind-to none \
  /home/mpot/mpot/.venv/bin/python -c "from mpi4py import MPI; import socket; c=MPI.COMM_WORLD; print(socket.gethostname(), c.Get_rank(), c.Get_size(), flush=True)"
```

For 4 VMs with 4 slots each, use `-np 16`. For 3 VMs, use `-np 12`.

The output must show ranks from more than one hostname. Then run a real project
cluster smoke:

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

Or use the sweep wrapper:

```bash
.venv/bin/python scripts/run_sweep.py \
  --config configs/local_smoke.json \
  --input-sizes 12 \
  --process-counts 12 \
  --label cluster_smoke \
  --output-dir results \
  --hostfile configs/hostfile_ubuntu.txt \
  --map-by slot \
  --bind-to none \
  --skip-existing
```

## Stage D: Plan Final Ubuntu/LAN Benchmark

Do not reuse MacBook macOS timing blindly. Measure a small Ubuntu sample first:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/local_benchmark.json \
  --run-id estimate-ubuntu-N4 \
  --experiment-name estimate_ubuntu_N4 \
  --output-dir results \
  --total-tasks 4
```

For 3 VMs with 4 slots each:

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

For 4 VMs with 4 slots each, use `--target-processes 16`.

Estimate full sweep time:

```bash
.venv/bin/python scripts/estimate_benchmark_budget.py \
  --plan report/BENCHMARK_PLAN_ubuntu.json \
  --output report/BENCHMARK_BUDGET_ubuntu.json \
  --markdown report/BENCHMARK_BUDGET_ubuntu.md \
  --label final_ubuntu_lan_2d \
  --run-label final_ubuntu_lan_2d \
  --results-dir results \
  --reuse-existing
```

Run the generated pipeline command from `BENCHMARK_PLAN_ubuntu.md`, adding the
hostfile flags at the end:

```bash
.venv/bin/python scripts/run_local_pipeline.py \
  --config configs/local_benchmark.json \
  --input-sizes <from-plan> \
  --process-counts <from-plan> \
  --label final_ubuntu_lan_2d \
  --final-n <speedup-2N-from-plan> \
  --load-balance-n <N-from-plan> \
  --final-processes 12 \
  --benchmark-plan report/BENCHMARK_PLAN_ubuntu.json \
  --skip-existing-runs \
  --hostfile configs/hostfile_ubuntu.txt \
  --map-by slot \
  --bind-to none
```

## Common Failure Checklist

| Symptom | Likely cause | Fix |
|---|---|---|
| `ssh mpot@IP hostname` asks for password | SSH key not installed | Run `ssh-copy-id mpot@IP` from rank 0. |
| `ssh: connect to host ...` fails | VM is not bridged or IP is wrong | Check VM network mode, `hostname -I`, router client isolation. |
| VM IP is still `192.168.64.x` | UTM Shared Networking is still active | Switch that VM to Bridged before LAN testing. |
| MPI launches only on rank 0 | Hostfile not used or SSH blocked | Check `--hostfile configs/hostfile_ubuntu.txt` and SSH to every VM. |
| Remote rank cannot find Python | Repo/venv path differs across VMs | Use identical `/home/mpot/mpot/.venv/bin/python` on all VMs. |
| `ModuleNotFoundError: mpi4py` | Venv not installed on one VM | Re-run pip install commands on that VM. |
| `libmpi` build error | Missing OpenMPI development package | `sudo apt install -y openmpi-bin libopenmpi-dev`. |
| Wi-Fi machines cannot see each other | Router AP/client isolation | Use a different router, disable isolation, or use wired LAN. |

## What To Put In The Report

Use these artifacts for the experimental setup section:

```text
report/CLUSTER_PLAN_local.md
configs/hostfile_ubuntu.txt
report/ENVIRONMENT_<label>.md
results/environment-<label>.json
report/BENCHMARK_PLAN_ubuntu.md
report/BENCHMARK_BUDGET_ubuntu.md
```

Use real CSV/JSON/PNG/GIF from the final pipeline for Results. The setup plan
and budget are not measured speedup results.
