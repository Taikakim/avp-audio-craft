"""cfg_sweep_analysis.py — CFG-vs-training-stage analysis (Kim's away-run).
Similarity metrics on avp_cfg_sweep: (1) STYLE SIMILARITY to Kim's real catalog
(cosine of a musical feature vector to the real-avp centroid), (2) EMPTY-vs-PROMPTED
convergence (absorption diagnostic), (3) per-(ckpt,cfg) fingerprint. Merges with
dancefloor_punch.json (depth/hardness/crest). mir venv. Robust librosa features (no MERT
dependency)."""
import glob, re, os, json, warnings
warnings.filterwarnings("ignore")
import numpy as np, soundfile as sf, librosa

def fvec(y, sr):
    y = y[:sr*40]
    mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20).mean(1)
    cen = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    bw = librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()
    ro = librosa.feature.spectral_rolloff(y=y, sr=sr).mean()
    fl = librosa.feature.spectral_flatness(y=y).mean()
    ch = librosa.feature.chroma_cqt(y=y, sr=sr).mean(1)
    zcr = librosa.feature.zero_crossing_rate(y)[0].mean()
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr).mean(1)
    return np.concatenate([mf, [cen, bw, ro, fl, zcr], ch, contrast]).astype(float)

def load(f, dur=40):
    y, sr = sf.read(f, dtype="float32", always_2d=True); return y.mean(1), sr

# real catalog reference (random-ish 40s window from each of ~50 tracks)
real_files = sorted(glob.glob("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed/*/full_mix.flac"))[::3][:55]
real_vecs = []
for rf in real_files:
    try:
        info = sf.info(rf); start = int(max(0, info.frames*0.4))  # mid-track
        y, sr = sf.read(rf, dtype="float32", always_2d=True, start=start, frames=44100*40)
        real_vecs.append(fvec(y.mean(1), sr))
    except Exception as e:
        pass
real = np.array(real_vecs)
print(f"[ref] {len(real)} real avp tracks", flush=True)

# CFG-sweep clips
clips = sorted(glob.glob("/run/media/kim/Mantu/sa3_lora_runs/avp_cfg_sweep/*.wav"))
gen = {}
for f in clips:
    y, sr = load(f); gen[os.path.basename(f)] = fvec(y, sr)

# standardize over real+gen jointly
allv = np.vstack([real] + list(gen.values()))
mu, sd = allv.mean(0), allv.std(0) + 1e-9
realz = (real - mu) / sd
real_centroid = realz.mean(0)
def sim_to_real(v):
    vz = (v - mu) / sd
    return float(np.dot(vz, real_centroid) / (np.linalg.norm(vz)*np.linalg.norm(real_centroid) + 1e-9))

rows = []
for name, v in gen.items():
    lbl = name[:-4]
    mck = re.match(r'([a-zA-Z0-9]+_ep\d+)__', name)
    mpl = re.search(r'__(kimlong|empty)__', name)
    mcfg = re.search(r'cfg(\d+\.\d+)', name)
    rows.append({"file": lbl, "ckpt": mck.group(1) if mck else None,
                 "prompt": mpl.group(1) if mpl else None,
                 "cfg": float(mcfg.group(1)) if mcfg else None,
                 "style_sim": sim_to_real(v)})
# empty-vs-kimlong convergence per (ckpt,cfg)
bykey = {}
for name, v in gen.items():
    mck = re.match(r'([a-zA-Z0-9]+_ep\d+)__', name); mpl = re.search(r'__(kimlong|empty)__', name)
    mcfg = re.search(r'cfg(\d+\.\d+)', name)
    if mck and mpl and mcfg:
        bykey.setdefault((mck.group(1), float(mcfg.group(1))), {})[mpl.group(1)] = v
conv = {}
for (ck, cfg), d in bykey.items():
    if "empty" in d and "kimlong" in d:
        a, b = (d["empty"]-mu)/sd, (d["kimlong"]-mu)/sd
        conv[f"{ck}|cfg{cfg}"] = float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-9))
OUT="/run/media/kim/Mantu/sa3_lora_runs/avp_board_seeds/ANALYSIS/cfg_sweep_similarity.json"
json.dump({"rows":rows,"empty_vs_kimlong":conv,"n_real":len(real)}, open(OUT,"w"), indent=1)
print(f"[done] {len(rows)} clips, {len(conv)} convergence pairs -> {OUT}", flush=True)
