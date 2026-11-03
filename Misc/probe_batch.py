# Last edited: THE-FINN 2026-11-03 — root-variable paths updated for the __theme sorting
import subprocess, time, os, re
SA3PY="/home/kim/Projects/SAO/sa3-rocm7.13-test/.venv/bin/python"
AVP="/home/kim/Projects/SAO/stable-audio-tools/avp_sa3"
ROOT="/run/media/kim/Lehto/sa3_control_runs"
EVAL_LOG=f"{ROOT}/__onsets/onset_AdamW_lr7.5e-5_randomcrop/eval_listen/soup_fine.log"
ENV={**os.environ,"FLASH_ATTENTION_TRITON_AMD_ENABLE":"FALSE","PYTORCH_TUNABLEOP_ENABLED":"0",
     "PYTORCH_TUNABLEOP_TUNING":"0","MIOPEN_FIND_MODE":"2","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4","OPENBLAS_NUM_THREADS":"4"}
COMMON=["--encoded_dir","/run/media/kim/Kosmos/latents/latents_sa3","--model","medium-base","--precision","bf16",
  "--crop-frames","512","--lr","7.5e-5","--optimizer","adamw","--warmup-steps","300","--no-preencode-text",
  "--control-mode","scalar","--scalar-field","onset_density","--control-dim","768","--n-tokens","256",
  "--cfg-dropout","0.1","--num-workers","4","--seed","42","--random-crop","--no-checkpoint","--save-cooldown","0"]
def mem():
    try:
        o=subprocess.run(["rocm-smi","--showmeminfo","vram"],capture_output=True,text=True,timeout=10).stdout
        t=re.search(r"Total Memory \(B\): (\d+)",o); u=re.search(r"Used Memory \(B\): (\d+)",o)
        return (int(t.group(1)) if t else 0, int(u.group(1)) if u else 0)
    except: return (0,0)
def log(s): print(s,flush=True)
TOTAL=mem()[0] or 17179869184
log(f"[probe] total VRAM {TOTAL/1e9:.1f} GB; waiting for soup+fine eval chain...")
for _ in range(220):
    try:
        if "ALL_DONE" in open(EVAL_LOG).read(): break
    except: pass
    time.sleep(30)
log("[probe] eval chain done; sweeping batch sizes"); time.sleep(12)
best=1; best_free=TOTAL/1e9
for B in [2,4,6,8]:
    pd=f"{ROOT}/_probe_b{B}"; os.makedirs(pd,exist_ok=True)
    with open(f"{pd}/probe.log","w") as lg:
        p=subprocess.Popen([SA3PY,f"{AVP}/sa3_control/train.py",*COMMON,"--batch",str(B),"--steps","200",
            "--save-every","999999","--save-dir",pd],cwd=AVP,env=ENV,stdout=lg,stderr=subprocess.STDOUT)
        peak=0
        while p.poll() is None:
            peak=max(peak,mem()[1]); time.sleep(4)
    txt=open(f"{pd}/probe.log").read().lower()
    if p.returncode!=0 or "out of memory" in txt or "hip error" in txt:
        log(f"[probe] batch {B}: OOM/fail (rc={p.returncode}) -> stop"); break
    free=(TOTAL-peak)/1e9
    log(f"[probe] batch {B}: peak {peak/1e9:.2f} GB used, {free:.2f} GB free")
    if free>=1.0: best,best_free=B,free
    else: log(f"[probe] batch {B} leaves <1 GB free -> stop"); break
log(f"[probe] >>> CHOSEN batch={best} ({best_free:.2f} GB free)")
name=f"onset_AdamW_lr7.5e-5_randomcrop_b{best}"
log(f"[probe] launching real run {name}")
subprocess.run(["bash",f"{AVP}/run_control_train.sh",name,"7.5e-5","adamw","--random-crop"],
               cwd=AVP,env={**os.environ,"BATCH":str(best)})
log("[probe] DONE — real run launched")
