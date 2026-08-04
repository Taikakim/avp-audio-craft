#!/usr/bin/env python
"""decoder_haze_probe.py — Is the SA3 SAME autoencoder decoder a spectral-haze source?

We found SA3 generations carry a mono spectral-haze artifact (spectral flatness ~3x real
music) that is NOT from the sampler (unchanged at 48 vs 24 steps). Remaining suspect: the
SAME autoencoder decoder itself vs. the DiT's latent target.

This probe round-trips REAL DRY goa clips through the autoencoder in isolation
(encode -> latent -> decode) and measures whether spectral flatness *rises* toward the
generation level (~0.016-0.024). If it does, the decoder injects haze that every SA3
output inherits. If output flatness stays near the dry input (~0.008), the decoder is
clean and the haze must live in the DiT latent target (generation/adapter), not the codec.

Flatness + broadband L/R coherence are computed with the SAME method/params as
eval/reverb_table_measure.py (_mono_reverb_metrics) and eval/stereo_phase_meter.py
(broadband coherence), reused verbatim below so numbers are directly comparable.

Run (SA3 venv, GPU):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
  /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python \
  /home/kim/Projects/SAO/eval/decoder_haze_probe.py --n 20
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import soundfile as sf
from scipy.signal import stft, coherence, resample_poly

# ---- shared measurement constants, identical to the eval meters ----
FS = 44100
EPS = 1e-12
NPERSEG = 2048
NOVERLAP = 1536
BROAD_LO, BROAD_HI = 200.0, 8000.0

MANIFEST = "/home/kim/Projects/SAO/eval/reverb_goa.jsonl"


def spectral_flatness_mean(mono):
    """Mean per-frame spectral flatness — verbatim method from reverb_table_measure.py
    (_mono_reverb_metrics, item (a)): geo-mean/arith-mean of STFT power over frequency."""
    _f, _t, Z = stft(mono.astype(np.float64), fs=FS, window="hann",
                     nperseg=NPERSEG, noverlap=NOVERLAP)
    power = np.abs(Z) ** 2 + EPS
    geo = np.exp(np.mean(np.log(power), axis=0))
    arith = np.mean(power, axis=0)
    flat = geo / (arith + EPS)
    return float(np.mean(flat))


def broadband_coherence(l, r):
    """Broadband (200-8000 Hz) magnitude-squared L/R coherence — verbatim method from
    stereo_phase_meter.py (_coherence_bands broadband branch)."""
    f, cxy = coherence(l, r, fs=FS, window="hann", nperseg=NPERSEG, noverlap=NOVERLAP)
    m = (f >= BROAD_LO) & (f < BROAD_HI)
    return float(np.mean(cxy[m])) if m.any() else float("nan")


def load_crop(path, start_s, dur_s):
    """Load [start_s, start_s+dur_s) as stereo float32 @ FS. Uses soundfile frame-accurate
    seek (handles flac + mp3), resamples with scipy resample_poly like the eval pipeline."""
    try:
        info = sf.info(path)
        sr = info.samplerate
        s0 = int(round(start_s * sr))
        n = int(round(dur_s * sr))
        audio, _ = sf.read(path, start=s0, frames=n, dtype="float32", always_2d=True)
    except sf.LibsndfileError:
        # formats libsndfile can't decode (e.g. m4a) -> librosa/ffmpeg fallback
        import librosa
        y, sr = librosa.load(path, sr=None, mono=False, offset=start_s, duration=dur_s)
        audio = np.atleast_2d(y).T  # (frames, channels)
    # -> (frames, channels); force stereo
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]
    if sr != FS:
        from math import gcd
        g = gcd(int(sr), FS)
        audio = resample_poly(audio, FS // g, int(sr) // g, axis=0)
    return audio.astype(np.float32)  # (frames, 2)


def measure(audio_fc):
    """audio_fc: (frames, 2) float32 @ FS -> (flatness_mono, coherence_broadband)."""
    l = audio_fc[:, 0].astype(np.float64)
    r = audio_fc[:, 1].astype(np.float64)
    mono = 0.5 * (l + r)
    return spectral_flatness_mean(mono), broadband_coherence(l, r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="number of driest clips")
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--out", default="/home/kim/Projects/SAO/eval/decoder_haze_probe.json")
    args = ap.parse_args()

    # ---- pick the N driest real clips ----
    recs = []
    with open(MANIFEST) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            sf_mean = (r.get("mono") or {}).get("spectral_flatness_mean")
            if r.get("ok") and sf_mean is not None and os.path.exists(r["path"]):
                recs.append(r)
    recs.sort(key=lambda r: r["mono"]["spectral_flatness_mean"])
    picked = recs[:args.n]
    print(f"[manifest] {len(recs)} usable clips; taking {len(picked)} driest "
          f"(flatness {picked[0]['mono']['spectral_flatness_mean']:.2e} .. "
          f"{picked[-1]['mono']['spectral_flatness_mean']:.2e})", flush=True)

    # ---- load model (SAME-L pretransform of the medium DiT) ----
    os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
    import torch
    from stable_audio_3 import StableAudioModel

    t_load0 = time.time()
    sam = StableAudioModel.from_pretrained(args.model, device="cuda")
    pretransform = sam.model.pretransform
    pt_dtype = next(pretransform.parameters()).dtype
    ds = pretransform.downsampling_ratio
    t_load = time.time() - t_load0
    print(f"[model] {args.model} loaded in {t_load:.1f}s | pretransform dtype={pt_dtype} "
          f"downsample={ds} scale={getattr(pretransform,'scale',None)} sr={sam.model.sample_rate}",
          flush=True)

    rows = []
    for i, rec in enumerate(picked):
        t0 = time.time()
        path = rec["path"]
        cs = float(rec.get("crop_start_s", 0.0))
        cd = float(rec.get("crop_dur_s") or 20.0)
        audio_in = load_crop(path, cs, cd)  # (frames, 2)

        f_in, c_in = measure(audio_in)

        # round-trip through the autoencoder in isolation.
        # pretransform.encode divides by scale, decode multiplies by scale -> cancels,
        # so this is the pure AE reconstruction (no DiT, no sampler).
        x = torch.from_numpy(audio_in.T).unsqueeze(0).to("cuda", pt_dtype)  # (1, 2, N)
        with torch.no_grad():
            lat = pretransform.encode(x)
            y = pretransform.decode(lat.to(pt_dtype), chunked=True)
        audio_out = y[0].float().cpu().numpy().T  # (frames, 2)
        # length can differ by a few samples; trim to min for coherence pairing
        m = min(audio_in.shape[0], audio_out.shape[0])
        audio_out = audio_out[:m]

        f_out, c_out = measure(audio_out)
        dt = time.time() - t0
        row = {
            "path": path,
            "name": os.path.basename(os.path.dirname(path)),
            "flat_in": f_in, "flat_out": f_out, "flat_delta": f_out - f_in,
            "flat_ratio": f_out / (f_in + EPS),
            "coh_in": c_in, "coh_out": c_out, "coh_delta": c_out - c_in,
            "lat_shape": list(lat.shape), "sec": round(dt, 2),
        }
        rows.append(row)
        print(f"[{i+1:2d}/{len(picked)}] flat {f_in:.4e}->{f_out:.4e} "
              f"(x{row['flat_ratio']:.2f})  coh {c_in:.3f}->{c_out:.3f} "
              f"({c_out-c_in:+.3f})  {dt:.2f}s  {row['name'][:40]}", flush=True)

    # ---- aggregate ----
    fin = np.array([r["flat_in"] for r in rows])
    fout = np.array([r["flat_out"] for r in rows])
    cin = np.array([r["coh_in"] for r in rows])
    cout = np.array([r["coh_out"] for r in rows])
    per_clip_sec = np.array([r["sec"] for r in rows])

    agg = {
        "n": len(rows),
        "flat_in_median": float(np.median(fin)),
        "flat_out_median": float(np.median(fout)),
        "flat_delta_median": float(np.median(fout - fin)),
        "flat_ratio_median": float(np.median(fout / (fin + EPS))),
        "flat_in_mean": float(np.mean(fin)),
        "flat_out_mean": float(np.mean(fout)),
        "coh_in_median": float(np.median(cin)),
        "coh_out_median": float(np.median(cout)),
        "coh_delta_median": float(np.median(cout - cin)),
        "model_load_sec": round(t_load, 1),
        "per_clip_sec_median": float(np.median(per_clip_sec)),
        "gen_flatness_reference": [0.016, 0.024],
    }

    print("\n===== AGGREGATE (n=%d driest real goa clips) =====" % agg["n"])
    print(f"  spectral flatness  IN  median = {agg['flat_in_median']:.4e}")
    print(f"  spectral flatness  OUT median = {agg['flat_out_median']:.4e}")
    print(f"  flatness delta     median = {agg['flat_delta_median']:+.4e}  "
          f"(ratio x{agg['flat_ratio_median']:.2f})")
    print(f"  gen-level haze reference      = 0.016 - 0.024")
    print(f"  L/R coherence      IN  median = {agg['coh_in_median']:.3f}")
    print(f"  L/R coherence      OUT median = {agg['coh_out_median']:.3f}  "
          f"(delta {agg['coh_delta_median']:+.3f})")
    print(f"  model load = {agg['model_load_sec']}s | per-clip median = "
          f"{agg['per_clip_sec_median']:.2f}s")

    # verdict
    out_med = agg["flat_out_median"]
    if out_med >= 0.016:
        verdict = ("DECODER IS A HAZE SOURCE: output flatness reaches the gen-level haze "
                   "band (>=0.016). The SAME decoder injects a fixed spectral-haze component "
                   "that every SA3 output inherits.")
    elif out_med >= 2 * agg["flat_in_median"]:
        verdict = ("DECODER ADDS PARTIAL HAZE: output flatness rises well above the dry "
                   "input but does not fully reach gen level — the decoder contributes some "
                   "haze, but the DiT latent target likely adds the rest.")
    else:
        verdict = ("DECODER IS CLEAN: output flatness stays near the dry input and far below "
                   "the gen haze band. The haze must originate in the DiT latent target "
                   "(generation/adapter), NOT the autoencoder decoder.")
    print("\nVERDICT:", verdict)

    with open(args.out, "w") as fh:
        json.dump({"aggregate": agg, "verdict": verdict, "rows": rows}, fh, indent=2)
    print(f"\n[written] {args.out}")


if __name__ == "__main__":
    main()
