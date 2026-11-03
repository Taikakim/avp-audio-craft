import subprocess, math, os
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MAKE="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3/sa3_control/make_soup.py"
R="/run/media/kim/Mantu/sa3_control_runs"
A20=f"{R}/onset_AdamW_lr7.5e-5_randomcrop_20ep"; F40=f"{R}/onset_FUSION_lr2e5_40epoch"
AC=f"{R}/onset_AdamW_lr7.5e-5_continuous"; AR=f"{R}/onset_AdamW_lr7.5e-5_randomcrop"; FR=f"{R}/onset_Fusion_lr1e-4_randomcrop"
VIBE=f"{R}/soups_vibe"; os.makedirs(VIBE,exist_ok=True)
def ck(run,ep): return f"{run}/riffer_step{5400*ep}.pt"
def soup(out,pairs):
    print(f"=== {os.path.basename(out)} ({len(pairs)} parts) ===",flush=True)
    subprocess.run([SA3PY,MAKE,out,*pairs])
# 1. exp-decay ep9->20 (AdamW-20ep) — favors the good early range, tapers the narrowed late
soup(f"{A20}/soup_expdecay_9_20.pt",[f"{ck(A20,i)}:{math.exp(-0.2*(i-9)):.4f}" for i in range(9,21)])
# 2. peak soups for the runs missing one (peak@ep7 over ep1-10)
for run in [AC,FR]:
    soup(f"{run}/soup_exppeak.pt",[f"{ck(run,i)}:{math.exp(-0.2*(i-7)**2):.4f}" for i in range(1,11)])
# 3-4. same-optimizer peak mixes
soup(f"{VIBE}/AdamW_peak_mix.pt",[f"{A20}/soup_exppeak.pt:1",f"{AR}/soup_exppeak.pt:1",f"{AC}/soup_exppeak.pt:1"])
soup(f"{VIBE}/Fusion_peak_mix.pt",[f"{F40}/soup_exppeak.pt:1",f"{FR}/soup_exppeak.pt:1"])
# 5. best checkpoint of every run (AdamW-20ep ep10, Fusion-40ep ep20-centroid, the three 10ep at ep10)
soup(f"{VIBE}/best_of_runs.pt",[f"{ck(A20,10)}:1",f"{ck(F40,20)}:1",f"{ck(FR,10)}:1",f"{ck(AR,10)}:1",f"{ck(AC,10)}:1"])
# 6. cross-optimizer: best AdamW (AR ep10) x best Fusion (FR ep10) at 3 ratios
soup(f"{VIBE}/cross_25A75F.pt",[f"{ck(AR,10)}:0.25",f"{ck(FR,10)}:0.75"])
soup(f"{VIBE}/cross_50A50F.pt",[f"{ck(AR,10)}:0.5",f"{ck(FR,10)}:0.5"])
soup(f"{VIBE}/cross_75A25F.pt",[f"{ck(AR,10)}:0.75",f"{ck(FR,10)}:0.25"])
print("VIBE_SOUPS_DONE",flush=True)
