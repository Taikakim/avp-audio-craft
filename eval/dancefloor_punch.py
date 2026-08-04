"""dancefloor_punch.py — AudioCommons timbral (depth/hardness/booming/roughness) +
a TRANSIENT-CLARITY composite (crest factor, HPSS percussive ratio, attack slope).
Gauges dance-floor impact / punch, which spectral centroid + Audiobox CE miss
(Kim 2026-07-09: arm G reads 'spectrally healthy' but sounds soft). mir venv.
"""
import sys, glob, re, json, os, warnings
warnings.filterwarnings("ignore")
import numpy as np, soundfile as sf, librosa
import timbral_models as tm

def transient_clarity(y, sr):
    # crest factor (peak/rms, dB)
    peak = np.abs(y).max() + 1e-9; rms = np.sqrt((y**2).mean()) + 1e-9
    crest = 20*np.log10(peak/rms)
    # HPSS percussive energy fraction
    H, P = librosa.effects.hpss(y)
    perc_ratio = float((P**2).sum() / ((H**2).sum() + (P**2).sum() + 1e-9))
    # mean attack slope: rise of onset envelope into detected onsets
    oe = librosa.onset.onset_strength(y=y, sr=sr)
    on = librosa.onset.onset_detect(onset_envelope=oe, sr=sr)
    slopes = [oe[i]-oe[i-1] for i in on if i > 0]
    attack = float(np.mean(slopes)) if slopes else 0.0
    return float(crest), perc_ratio, attack

def measure(f):
    y, sr = sf.read(f, dtype="float32", always_2d=True); y = y.mean(1)
    crest, perc, attack = transient_clarity(y[:sr*30], sr)
    out = {"crest_db": crest, "perc_ratio": perc, "attack_slope": attack}
    for name, fn in [("depth",tm.timbral_depth),("hardness",tm.timbral_hardness),
                     ("booming",tm.timbral_booming),("roughness",tm.timbral_roughness)]:
        try: out[name] = float(fn(f))
        except Exception: out[name] = None
    return out

# representative clip set across the axes that matter for punch
SETS = {
 "cfg_sweep": glob.glob("/run/media/kim/Mantu/sa3_lora_runs/avp_cfg_sweep/*.wav"),
 "orig_ladder": glob.glob("/run/media/kim/Mantu/sa3_lora_runs/avp_board_seeds/r16_originals__*__kimlong__s1234__st10.wav") +
                glob.glob("/run/media/kim/Mantu/sa3_lora_runs/avp_board_seeds/r16_originals__*__kimlong__s1234.wav"),
 "armG": glob.glob("/run/media/kim/Mantu/sa3_lora_runs/avp_board_armG/*__trigdesc__s1234__st10.wav"),
 "r64": glob.glob("/run/media/kim/Mantu/sa3_lora_runs/avp_board_r64/*__kimlong__s1234__st10.wav"),
}
rows = []
for grp, files in SETS.items():
    for f in sorted(files):
        m = measure(f)
        m["group"] = grp; m["file"] = os.path.basename(f)
        me = re.search(r'epoch(\d+)', f); m["epoch"] = int(me.group(1)) if me else None
        mc = re.search(r'cfg(\d+\.\d+)', f); m["cfg"] = float(mc.group(1)) if mc else None
        rows.append(m)
        print(f"[{grp}] {os.path.basename(f)[:45]:45s} depth={m.get('depth')} hard={m.get('hardness')} crest={m['crest_db']:.1f} perc={m['perc_ratio']:.2f}", flush=True)
OUT="/run/media/kim/Mantu/sa3_lora_runs/avp_board_seeds/ANALYSIS/dancefloor_punch.json"
json.dump(rows, open(OUT,"w"), indent=1)
print(f"[done] {len(rows)} clips -> {OUT}", flush=True)
