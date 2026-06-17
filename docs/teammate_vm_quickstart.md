# Teammate VM Quickstart

File này là bản hướng dẫn ngắn cho từng thành viên trong nhóm. Mục tiêu là mỗi
máy tự chạy được project trước, rồi sau đó cả nhóm mới nối LAN/Bridged để chạy
OpenMPI nhiều máy.

## Luồng đúng

```text
1. Mỗi bạn lấy code mới nhất.
2. Mỗi bạn test smoke nhỏ trên máy của mình nếu có thể.
3. Mỗi bạn cài một Ubuntu ARM64 VM.
4. Mỗi Ubuntu VM tự chạy serial + MPI local smoke.
5. Chỉ khi tất cả VM pass, mới đổi network sang Bridged.
6. Sau Bridged, master ping/SSH tới worker.
7. Tạo hostfile.
8. Chạy mpirun --hostfile nhiều máy.
```

Không debug LAN ngay từ đầu. Nếu một VM chưa chạy được local smoke thì cluster
sẽ lỗi rất khó tìm.

## Chuẩn chung cho mọi VM

```text
VM app: UTM
Ubuntu: ARM64/aarch64 Server LTS
Username: mpot
Repo path: /home/mpot/mpot
Python path: /home/mpot/mpot/.venv/bin/python
CPU: 4 cores nếu máy đủ khỏe
RAM: 4-8 GB
Disk: 40 GB hoặc hơn
```

Project dùng CPU-only. Không cài CUDA/NVIDIA.

## Bước 1: Test nhanh trên máy local nếu có thể

Nếu bạn đang ở macOS/Linux và đã có repo:

```bash
cd /path/to/mpot
python3 -m venv .venv
.venv/bin/python -m pip install -U pip wheel setuptools
.venv/bin/python -m pip install numpy matplotlib pillow mpi4py
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e . --no-deps
```

Chạy kiểm tra:

```bash
.venv/bin/python scripts/check_local_env.py
.venv/bin/python scripts/doctor_local_setup.py \
  --label teammate_mac_local \
  --run-mpi-probe \
  --mpi-processes 2
```

Chạy serial/MPI smoke:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/local_smoke.json \
  --run-id serial-teammate-local-N4 \
  --experiment-name teammate_local_N4 \
  --output-dir results \
  --total-tasks 4
```

```bash
mpirun -np 2 --bind-to none \
  .venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --run-id mpi-teammate-local-N4-P2 \
  --experiment-name teammate_local_N4 \
  --output-dir results \
  --total-tasks 4
```

```bash
.venv/bin/python scripts/compare_serial_mpi.py \
  --serial results/serial-teammate-local-N4 \
  --mpi results/mpi-teammate-local-N4-P2 \
  --output-dir results \
  --run-id compare-teammate-local-N4-P2
```

Pass khi compare báo:

```text
passed: true
best_cost_difference: 0.0
```

Nếu máy local khó cài OpenMPI, có thể bỏ qua bước local macOS và chuyển sang
Ubuntu VM. Nhưng trong Ubuntu VM thì bắt buộc phải pass.

## Bước 2: Cài Ubuntu VM

Trong UTM:

```text
Create a new VM
Virtualize
Linux
Attach Ubuntu ARM64 Server ISO
CPU/RAM/Disk theo chuẩn ở trên
Network ban đầu: Shared Network là đủ để test single-VM
Create user: mpot
Hostname: mpot-a, mpot-b, mpot-c, hoặc mpot-d
```

Sau khi vào Ubuntu:

```bash
uname -m
```

Kết quả nên là:

```text
aarch64
```

Cài system packages:

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

## Bước 3: Đưa repo vào VM

Repo trong VM phải nằm ở:

```text
/home/mpot/mpot
```

Nếu dùng GitHub:

```bash
git clone <repo-url> /home/mpot/mpot
cd /home/mpot/mpot
```

Nếu copy từ Mac host:

```bash
rsync -av \
  --exclude .venv \
  --exclude results \
  --exclude submission \
  --exclude __pycache__ \
  ./ mpot@<vm-ip>:/home/mpot/mpot/
```

## Bước 4: Cài Python trong Ubuntu VM

Chạy trong VM:

```bash
cd /home/mpot/mpot
python3 -m venv .venv
.venv/bin/python -m pip install -U pip wheel setuptools
.venv/bin/python -m pip install numpy matplotlib pillow mpi4py
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e . --no-deps
```

Không chạy plain `pip install -r requirements-local.txt` nếu nó kéo các gói
`nvidia_*` hoặc CUDA. VM của nhóm chạy CPU-only.

## Bước 5: Mỗi VM tự chạy smoke

Chạy trong Ubuntu VM:

```bash
cd /home/mpot/mpot
.venv/bin/python scripts/check_local_env.py
.venv/bin/python scripts/doctor_local_setup.py \
  --label ubuntu_vm_single \
  --run-mpi-probe \
  --mpi-processes 2
```

Doctor phải in:

```text
ready: True
```

Chạy serial:

```bash
.venv/bin/python scripts/run_serial.py \
  --config configs/local_smoke.json \
  --run-id serial-ubuntu-single-N4 \
  --experiment-name ubuntu_single_N4 \
  --output-dir results \
  --total-tasks 4
```

Chạy MPI trên chính VM đó:

```bash
mpirun -np 2 --bind-to none \
  /home/mpot/mpot/.venv/bin/python scripts/run_mpi.py \
  --config configs/local_smoke.json \
  --run-id mpi-ubuntu-single-N4-P2 \
  --experiment-name ubuntu_single_N4 \
  --output-dir results \
  --total-tasks 4
```

So sánh correctness:

```bash
.venv/bin/python scripts/compare_serial_mpi.py \
  --serial results/serial-ubuntu-single-N4 \
  --mpi results/mpi-ubuntu-single-N4-P2 \
  --output-dir results \
  --run-id compare-ubuntu-single-N4-P2
```

VM được coi là sẵn sàng khi có đủ:

```text
ready: True
results/serial-ubuntu-single-N4/summary.json
results/mpi-ubuntu-single-N4-P2/summary.json
results/mpi-ubuntu-single-N4-P2/rank_timings.csv
results/mpi-ubuntu-single-N4-P2/comm_events.csv
results/compare-ubuntu-single-N4-P2/correctness_report.json
compare passed: true
best_cost_difference: 0.0
```

## Bước 6: Khi nào mới chuyển sang Bridged

Chỉ chuyển sang Bridged khi:

```text
Tất cả teammate VM đã pass Bước 5.
Cả nhóm ngồi cùng một Wi-Fi/hotspot/router/LAN.
Master cần SSH được vào mọi VM worker.
```

Không cần Bridged cho single-VM smoke. Shared Network đã đủ cho một VM tự chạy
`mpirun -np 2` hoặc `mpirun -np 4`.

## Bước 7: Plan Bridged/LAN

Trên từng VM trong UTM:

```text
Tắt VM.
Mở VM Settings.
Network.
Đổi từ Shared Network sang Bridged.
Chọn Wi-Fi hoặc adapter LAN đang dùng.
Start VM lại.
```

Trong mỗi VM, lấy IP:

```bash
hostname -I
```

IP LAN thường giống:

```text
192.168.1.x
192.168.0.x
10.0.0.x
```

Nếu vẫn chỉ thấy:

```text
192.168.64.x
```

thì nhiều khả năng vẫn là UTM Shared Network, chưa phải Bridged LAN thật.

## Bước 8: Master kiểm tra ping/SSH

Chọn một máy làm master, ví dụ `mpot-a`.

Từ master VM:

```bash
ping <worker-b-ip>
ping <worker-c-ip>
ping <worker-d-ip>
```

Tạo SSH key trên master nếu chưa có:

```bash
ssh-keygen -t ed25519
```

Copy key sang từng worker:

```bash
ssh-copy-id mpot@<worker-b-ip>
ssh-copy-id mpot@<worker-c-ip>
ssh-copy-id mpot@<worker-d-ip>
```

Test SSH:

```bash
ssh mpot@<worker-b-ip> hostname
ssh mpot@<worker-c-ip> hostname
ssh mpot@<worker-d-ip> hostname
```

Chỉ đi tiếp khi SSH không hỏi password.

## Bước 9: Tạo hostfile và chạy MPI nhiều máy

Tạo file config thật từ mẫu:

```bash
cp configs/cluster_hosts.example.json configs/cluster_hosts.local.json
```

Sửa `configs/cluster_hosts.local.json` bằng IP thật.

Tạo hostfile:

```bash
.venv/bin/python scripts/prepare_cluster_hostfile.py \
  --config configs/cluster_hosts.local.json \
  --hostfile configs/hostfile_ubuntu.txt \
  --output report/CLUSTER_PLAN_local.json \
  --markdown report/CLUSTER_PLAN_local.md
```

Test rank distribution:

```bash
mpirun --hostfile configs/hostfile_ubuntu.txt \
  -np 12 \
  --map-by slot \
  --bind-to none \
  /home/mpot/mpot/.venv/bin/python -c "from mpi4py import MPI; import socket; c=MPI.COMM_WORLD; print(socket.gethostname(), c.Get_rank(), c.Get_size(), flush=True)"
```

Chạy project cluster smoke:

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

Nếu nhóm có 4 VM, có thể dùng `-np 16` nếu mỗi VM có 4 slots và máy đủ khỏe.

## Trạng thái hiện tại của owner VM

Owner VM `mpot-a` đã pass:

```text
doctor: ready: True
N=4, P=2: serial/MPI pass, best cost difference 0.0
N=8, P=4: serial/MPI pass, best cost difference 0.0
```

Artifacts trên máy owner:

```text
results/ubuntu_vm_single/
report/ubuntu_vm_single/SETUP_DOCTOR_ubuntu_vm_single.md
```

Vì vậy việc còn lại trước LAN là: từng teammate cài VM và pass cùng smoke.
