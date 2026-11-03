import subprocess, os, glob
root="/run/media/kim/Mantu/sa3_control_runs"
stage=os.path.expanduser("~/riffer-evals/clips_mp")
SEED="777"; GAINS=["0.5","1","2","3"]; DENS=["3","7","9","12"]; PIS=[0,1,2]
n=0
for s in sorted(glob.glob(f"{root}/*/eval_mp/*/")):
    p=s.rstrip('/').split('/'); run=p[-3]; name=p[-1]
    outdir=f"{stage}/{run}__{name}"; os.makedirs(outdir,exist_ok=True)
    for pi in PIS:
        for g in GAINS:
            for d in DENS:
                src=f"{s}p{pi}_s{SEED}_g{g}_d{d}.wav"
                if os.path.exists(src):
                    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",src,"-b:a","192k",
                                    f"{outdir}/p{pi}_g{g}_d{d}.mp3"]); n+=1
print(f"DONE {n} mp3", flush=True)
