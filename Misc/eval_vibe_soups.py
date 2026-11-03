# Last edited: THE-FINN 2026-11-03 — root-variable paths updated for the __theme sorting
import subprocess, os, time
R="/run/media/kim/Mantu/sa3_control_runs"
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MIRPY="/home/kim/Projects/mir/mir/bin/python"
AVP="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3"
LOG="/tmp/vibe_soups.log"
while not (os.path.exists(LOG) and "VIBE_SOUPS_DONE" in open(LOG).read()):
    if os.path.exists(LOG) and "Traceback" in open(LOG).read(): print("BUILD FAILED",flush=True); raise SystemExit(1)
    time.sleep(30)
print("soups built; starting eval",flush=True)
A20=f"{R}/__onsets/onset_AdamW_lr7.5e-5_randomcrop_20ep"; AC=f"{R}/__onsets/onset_AdamW_lr7.5e-5_continuous"; FR=f"{R}/__onsets/onset_Fusion_lr1e-4_randomcrop"; VIBE=f"{R}/__soups/soups_vibe"
soups=[(f"{A20}/soup_expdecay_9_20.pt",f"{A20}/eval_mp/soup_expdecay_9_20"),
       (f"{AC}/soup_exppeak.pt",f"{AC}/eval_mp/soup_exppeak"),
       (f"{FR}/soup_exppeak.pt",f"{FR}/eval_mp/soup_exppeak")]
for nm in ["AdamW_peak_mix","Fusion_peak_mix","best_of_runs","cross_25A75F","cross_50A50F","cross_75A25F"]:
    soups.append((f"{VIBE}/{nm}.pt",f"{VIBE}/eval_mp/{nm}"))
PROMPTS="aggressive upbeat goa trance||energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine||psytrance, 140 bpm"
ENV={**os.environ,"FLASH_ATTENTION_TRITON_AMD_ENABLE":"FALSE","PYTORCH_TUNABLEOP_ENABLED":"0","PYTORCH_TUNABLEOP_TUNING":"0","MIOPEN_FIND_MODE":"2","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4"}
for ckpt,outdir in soups:
    if not os.path.exists(ckpt): print(f"SKIP missing {ckpt}",flush=True); continue
    print(f"=== eval {os.path.basename(outdir)} ===",flush=True)
    subprocess.run([SA3PY,f"{AVP}/sa3_control/multi_eval.py",ckpt,"--prompts",PROMPTS,"--seeds","777,1234","--gains","0.5,1,2,3","--densities","3,6,7,8,9,12","--out",outdir],env=ENV,cwd=AVP)
    subprocess.run([MIRPY,f"{AVP}/sa3_control/pq_score_manifest.py",outdir],cwd=AVP)
print("SOUP_EVAL_DONE",flush=True)
