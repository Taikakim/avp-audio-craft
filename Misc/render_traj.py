import subprocess, os
R="/run/media/kim/Mantu/sa3_control_runs"
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MIRPY="/home/kim/Projects/mir/mir/bin/python"
AVP="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3"
PROMPTS="aggressive upbeat goa trance||energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine||psytrance, 140 bpm||finger picked steel string folk music solo"
ENV={**os.environ,"FLASH_ATTENTION_TRITON_AMD_ENABLE":"FALSE","PYTORCH_TUNABLEOP_ENABLED":"0","PYTORCH_TUNABLEOP_TUNING":"0","MIOPEN_FIND_MODE":"2","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4"}
runs=[("onset_AdamW_lr7.5e-5_randomcrop_20ep",range(2,21,2)),("onset_FUSION_lr2e5_40epoch",range(10,31,2))]
tot=sum(len(list(e)) for _,e in runs); print(f"PLAN: {tot} ckpts x 72 = {tot*72} clips (4 prompts, 1 seed, every-2nd)",flush=True)
i=0
for run,eps in runs:
    for ep in eps:
        i+=1; ckpt=f"{R}/{run}/riffer_step{5400*ep}.pt"
        if not os.path.exists(ckpt): print(f"SKIP {run} ep{ep}",flush=True); continue
        out=f"{R}/{run}/eval_traj/ep{ep}"
        print(f"=== {i}/{tot} {run.split('_')[1]}-ep{ep} ===",flush=True)
        subprocess.run([SA3PY,f"{AVP}/sa3_control/multi_eval.py",ckpt,"--prompts",PROMPTS,"--seeds","777",
            "--gains","1.75,2,2.25","--densities","2,6,7,8,9,12","--out",out],env=ENV,cwd=AVP)
        subprocess.run([MIRPY,f"{AVP}/sa3_control/pq_score_manifest.py",out],cwd=AVP)
print("TRAJ_DONE",flush=True)
