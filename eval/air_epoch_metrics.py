#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""air_epoch_metrics.py -- DSP + Audiobox metrics for the per-epoch air-head sweep clips (eval/air_epoch_sweep.py).
Kim 2026-10-15: "calculate PQ, zero crossings, spectral centroid and flux, crest, RMS and whitening for the clips". Whitening = spectral flatness (clip_metrics 'flatness').
Measured on the LEVEL-MATCHED wavs (original and bass+body unmatched), so loudness is not a confound for PQ / flux / crest. Writes <sweep>/metrics.json {clip_name: {...}}.
    SAO/.venv/bin/python eval/air_epoch_metrics.py dsp        # zcr, centroid, flux, crest, rms, flatness, hf_ratio, onset_p95
    mir/mir/bin/python  eval/air_epoch_metrics.py audiobox    # CE, CU, PC, PQ (CPU)
    SAO/.venv/bin/python eval/air_epoch_metrics.py merge
Audit note: PQ comes from a model that has not been validated against Kim's ratings here; treat as a screen.
"""
import json, os, sys, glob
SW = os.environ.get("SWEEP_DIR", "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_overnight/epoch_sweep")  # override for other sweeps
def files():
    out = {}
    for p in sorted(glob.glob(f"{SW}/clips/*.wav")):
        n = os.path.basename(p)[:-4]
        if n.endswith("_matched"): out[n[:-8]] = p
    for n in ("base", "bass_body"): out[n] = f"{SW}/clips/{n}.wav"
    return out
def dsp():
    sys.path.append("/home/kim/Projects/SAO")
    from control.sa3_control.clip_metrics import clip_metrics
    cols = ["dur", "rms", "crest", "zcr", "onset_p95", "centroid", "flatness", "flux", "hf_ratio", "bpm_librosa"]
    res = {}
    for k, p in files().items():
        v = clip_metrics(p)[1]; res[k] = dict(zip(cols, [float(x) for x in v])) if v else None
    json.dump(res, open(f"{SW}/m_dsp.json", "w")); print("DSP_DONE", len(res))
def audiobox():
    import warnings; warnings.filterwarnings("ignore")
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as ab
    f = f"{SW}/m_audiobox.json"; res = json.load(open(f)) if os.path.exists(f) else {}
    for i, (k, p) in enumerate(files().items()):
        if k in res: continue
        try: res[k] = {a: float(b) for a, b in ab(p).items()}
        except Exception as e: print("AB fail", k, str(e)[:80], flush=True)
        if i % 8 == 0: json.dump(res, open(f, "w"))
    json.dump(res, open(f, "w")); print("AUDIOBOX_DONE", len(res))
def merge():
    d = json.load(open(f"{SW}/m_dsp.json")); a = json.load(open(f"{SW}/m_audiobox.json")) if os.path.exists(f"{SW}/m_audiobox.json") else {}
    out = {k: {**(d.get(k) or {}), **{"ab_" + x: y for x, y in (a.get(k) or {}).items()}} for k in files()}
    json.dump(out, open(f"{SW}/metrics.json", "w")); print("MERGE_DONE", len(out))
if __name__ == "__main__":
    {"dsp": dsp, "audiobox": audiobox, "merge": merge}[sys.argv[1]]()
