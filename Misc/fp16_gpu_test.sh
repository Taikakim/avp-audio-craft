#!/bin/bash
cd /home/kim/Projects/SAO/stable-audio-3 || exit 1
PY=/home/kim/Projects/mir/mir/bin/python
for f in dit_medium-base_L256_ctrl_onset_density_fp16.onnx dit_medium-base_L256_ctrl_onset_density.cond.npz \
         same_decoder_L128_fp16.onnx dit_medium-base_L256_ctrl.cond.npz dit_medium-base_L256_ctrl.uncond.npz; do
  [ -f "$f" ] || { echo "MISSING INPUT: $f"; exit 1; }
done
ARGS="--dit-onnx dit_medium-base_L256_ctrl_onset_density_fp16.onnx --cond-npz dit_medium-base_L256_ctrl_onset_density.cond.npz --decoder-onnx same_decoder_L128_fp16.onnx --cond dit_medium-base_L256_ctrl.cond.npz --uncond dit_medium-base_L256_ctrl.uncond.npz --frames 256"
echo "=== GPU d11 (migraphx) $(date +%H:%M) ==="
$PY scripts/dit_control_onnx_infer.py $ARGS --onset-density 11 --provider migraphx --out /home/kim/fp16_gpu_d11.wav 2>&1
[ -f /home/kim/fp16_gpu_d11.wav ] || { echo "GPU-11 FAILED — aborting"; exit 1; }
echo "=== GPU d3 (migraphx) $(date +%H:%M) ==="
$PY scripts/dit_control_onnx_infer.py $ARGS --onset-density 3 --provider migraphx --out /home/kim/fp16_gpu_d3.wav 2>&1
echo "=== CPU d11 (cos reference) $(date +%H:%M) ==="
$PY scripts/dit_control_onnx_infer.py $ARGS --onset-density 11 --provider cpu --threads 12 --out /home/kim/fp16_cpu_d11.wav 2>&1
echo "=== MEASURE $(date +%H:%M) ==="
$PY - <<'PYEOF'
import numpy as np, librosa
def cos(a,b):
    a,b=np.asarray(a).ravel().astype(np.float64),np.asarray(b).ravel().astype(np.float64)
    return float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)+1e-9))
def od(w):
    y,sr=librosa.load(w,sr=22050,mono=True); on=librosa.onset.onset_detect(y=y,sr=sr,units='time')
    return len(on)/(len(y)/sr)
zg=np.load('/home/kim/fp16_gpu_d11.wav.z0.npy'); zc=np.load('/home/kim/fp16_cpu_d11.wav.z0.npy')
print(f'RESULT cos(GPU,CPU) z0_d11 = {cos(zg,zc):.6f}')
print(f'RESULT onset/sec  GPU_d11={od("/home/kim/fp16_gpu_d11.wav"):.2f}  CPU_d11={od("/home/kim/fp16_cpu_d11.wav"):.2f}  GPU_d3={od("/home/kim/fp16_gpu_d3.wav"):.2f}')
PYEOF
echo "FP16_TEST_DONE"
