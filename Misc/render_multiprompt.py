import subprocess, os
ROOT="/run/media/kim/Mantu/sa3_control_runs"
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MIRPY="/home/kim/Projects/mir/mir/bin/python"
AVP="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3"
PROMPTS="aggressive upbeat goa trance||energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine||psytrance, 140 bpm"
SEEDS="777,1234"; GAINS="0.5,1,2,3"; DENS="3,6,7,8,9,12"
ENV={**os.environ,"FLASH_ATTENTION_TRITON_AMD_ENABLE":"FALSE","PYTORCH_TUNABLEOP_ENABLED":"0",
     "PYTORCH_TUNABLEOP_TUNING":"0","MIOPEN_FIND_MODE":"2","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4"}
sets=[]
def add(run,ckpt,name): sets.append((f"{ROOT}/{run}/{ckpt}", f"{ROOT}/{run}/eval_mp/{name}"))
E5=[(2,10800),(5,27000),(10,54000),(15,81000),(20,108000)]; E3=[(2,10800),(5,27000),(10,54000)]
for ep,st in E5: add("onset_AdamW_lr7.5e-5_randomcrop_20ep",f"riffer_step{st}.pt",f"ep{ep}")
for sp in ["expasc","exppeak","fibonacci"]: add("onset_AdamW_lr7.5e-5_randomcrop_20ep",f"soup_{sp}.pt",f"soup_{sp}")
for ep,st in E5: add("onset_FUSION_lr2e5_40epoch",f"riffer_step{st}.pt",f"ep{ep}")
for sp in ["expasc","exppeak"]: add("onset_FUSION_lr2e5_40epoch",f"soup_{sp}.pt",f"soup_{sp}")
for ep,st in E3: add("onset_AdamW_lr7.5e-5_continuous",f"riffer_step{st}.pt",f"ep{ep}")
for ep,st in E3: add("onset_AdamW_lr7.5e-5_randomcrop",f"riffer_step{st}.pt",f"ep{ep}")
for sp in ["exppeak","expasc"]: add("onset_AdamW_lr7.5e-5_randomcrop",f"soup_{sp}.pt",f"soup_{sp}")
for ep,st in E3: add("onset_Fusion_lr1e-4_randomcrop",f"riffer_step{st}.pt",f"ep{ep}")
print(f"PLAN: {len(sets)} sets x 144 = {len(sets)*144} clips",flush=True)
miss=[c for c,o in sets if not os.path.exists(c)]
print("MISSING ckpts:", len(miss), *([] if not miss else ["\n  "+ "\n  ".join(miss)]),flush=True)
for i,(ckpt,outdir) in enumerate(sets):
    if not os.path.exists(ckpt): print(f"SKIP {i+1} missing",flush=True); continue
    print(f"=== {i+1}/{len(sets)} {outdir.split('/')[-2]}/{outdir.split('/')[-1]} ===",flush=True)
    subprocess.run([SA3PY,f"{AVP}/sa3_control/multi_eval.py",ckpt,"--prompts",PROMPTS,"--seeds",SEEDS,"--gains",GAINS,"--densities",DENS,"--out",outdir],env=ENV,cwd=AVP)
    subprocess.run([MIRPY,f"{AVP}/sa3_control/pq_score_manifest.py",outdir],cwd=AVP)
print("ALL_DONE",flush=True)
