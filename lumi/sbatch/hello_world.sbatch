#!/bin/bash
# hello_world.sbatch — DAY 0: the first job to submit, minutes after first login.
# Needs NOTHING of ours — no container build, no data, no project dirs. Uses LUMI's
# own stock PyTorch image. Proves: account works, queue works, a GCD is visible,
# torch does a matmul on it. Everything else builds on this.
#
#   sbatch --account=project_465003186 hello_world.sbatch
#   squeue --me            # watch it queue/run
#   cat hello-*.out        # the proof
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --job-name=hello
#SBATCH --output=%x-%j.out

set -euo pipefail
echo "node: $(hostname)   date: $(date -Is)"

# newest stock PyTorch image on the system (they version-drift; take what's there)
SIF=$(ls -t /appl/local/containers/sif-images/lumi-pytorch-rocm-*.sif 2>/dev/null | head -1)
echo "container: ${SIF:?no lumi-pytorch image found — ls /appl/local/containers/sif-images/}"

srun singularity exec "${SIF}" python3 - <<'PY'
import torch, platform
print("python :", platform.python_version())
print("torch  :", torch.__version__)
print("gpu ok :", torch.cuda.is_available())
print("device :", torch.cuda.get_device_name(0))
a = torch.randn(4096, 4096, device="cuda")
b = a @ a
torch.cuda.synchronize()
print("matmul :", tuple(b.shape), "on", b.device, "— HELLO LUMI, the stack is alive")
PY
