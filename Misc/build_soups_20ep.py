# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
import subprocess, math
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
MAKE="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3/sa3_control/make_soup.py"
A20="/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_AdamW_lr7.5e-5_randomcrop_20ep"
def ck(ep): return f"{A20}/riffer_step{5400*ep}.pt"
asc =[f"{ck(i)}:{math.exp(0.15*i):.4f}" for i in range(1,21)]
peak=[f"{ck(i)}:{math.exp(-0.04*(i-14)**2):.4f}" for i in range(1,21)]
fib_eps=[20,19,18,17,15,12,7]; fib_w=[7,6,5,4,3,2,1]
fib =[f"{ck(e)}:{w}" for e,w in zip(fib_eps,fib_w)]
for out,a in [("soup_expasc",asc),("soup_exppeak",peak),("soup_fibonacci",fib)]:
    print(f"=== {out} ({len(a)} ckpts) ===", flush=True)
    subprocess.run([SA3PY, MAKE, f"{A20}/{out}.pt", *a])
print("SOUPS_DONE", flush=True)
