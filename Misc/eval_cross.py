import subprocess, os
R="/run/media/kim/Mantu/sa3_control_runs"
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MIRPY="/home/kim/Projects/mir/mir/bin/python"
AVP="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3"
PROMPTS="aggressive upbeat goa trance||energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine||psytrance, 140 bpm"
ENV={**os.environ,"FLASH_ATTENTION_TRITON_AMD_ENABLE":"FALSE","PYTORCH_TUNABLEOP_ENABLED":"0","PYTORCH_TUNABLEOP_TUNING":"0","MIOPEN_FIND_MODE":"2","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4"}
V=f"{R}/soups_vibe"
for nm in ["cross_10A90F","cross_15A85F","cross_20A80F","cross_30A70F","cross_35A65F","cross40_25A75F"]:
    out=f"{V}/eval_mp/{nm}"; print(f"=== {nm} ===",flush=True)
    subprocess.run([SA3PY,f"{AVP}/sa3_control/multi_eval.py",f"{V}/{nm}.pt","--prompts",PROMPTS,"--seeds","777,1234","--gains","0.5,1,2,3","--densities","3,6,7,8,9,12","--out",out],env=ENV,cwd=AVP)
    subprocess.run([MIRPY,f"{AVP}/sa3_control/pq_score_manifest.py",out],cwd=AVP)
print("CROSS_DONE",flush=True)
