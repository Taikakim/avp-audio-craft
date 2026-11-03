# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
import subprocess, os
ROOT="/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_AdamW_lr7.5e-5_randomcrop_20ep"
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MIRPY="/home/kim/Projects/mir/mir/bin/python"
AVP="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3"
PROMPTS="aggressive upbeat goa trance||energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine||psytrance, 140 bpm"
ENV={**os.environ,"FLASH_ATTENTION_TRITON_AMD_ENABLE":"FALSE","PYTORCH_TUNABLEOP_ENABLED":"0","PYTORCH_TUNABLEOP_TUNING":"0","MIOPEN_FIND_MODE":"2","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4"}
for ep,st in [(2,10800),(10,54000),(20,108000)]:
    out=f"{ROOT}/eval_mp/ep{ep}_hi"
    print(f"=== ep{ep}_hi (gains 4,6,8) ===",flush=True)
    subprocess.run([SA3PY,f"{AVP}/sa3_control/multi_eval.py",f"{ROOT}/riffer_step{st}.pt","--prompts",PROMPTS,
        "--seeds","777,1234","--gains","4,6,8","--densities","3,6,7,8,9,12","--out",out],env=ENV,cwd=AVP)
    subprocess.run([MIRPY,f"{AVP}/sa3_control/pq_score_manifest.py",out],cwd=AVP)
print("HIGHGAIN_DONE",flush=True)
