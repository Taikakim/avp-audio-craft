#!/usr/bin/env python3
"""interval_resolution_ladder.py — "are we even SEEING a small second before we update
the weights?" (Kim, 2026-08-06). The melody machinery was only ever *calibrated* on a
FIFTH (7 semitones); this places every interval 1..12 on the same axis as the SAME/MP3
codec-noise floor, using the SAME latent space + the SAME 15-dim melody subspace the
#59 subspace-loss upweighted (lumi/melody_subspace15_v2.npz).

Source = the CLEAN single-note pitch atlas from the v2 melody study
(stage1_pitch_atlas_v2.npz: [10 timbres, 73 pitches 36..108, 256 latent]). Isolated
monophonic notes = the BEST case for our resolution; if a second is at the floor here,
it is hopeless in a real polyphonic mix.

Per interval k (semitones), over all (timbre, pitch-position) pairs i,i+k:
  d = z(p+k) - z(p)                      the interval's latent displacement
  |d|                                     magnitude (abs, and as fraction of the atlas fifth)
  melFrac = |B15 d|^2 / |d|^2            energy fraction inside the melody subspace
                                          (random baseline = 15/256 = 0.0586)
  dir_cos                                 mean cosine of d to the grand-mean interval dir
                                          (is there a coherent, readable interval direction?)
  detect_acc                             balanced acc of a 1-D readout (project onto the
                                          mean-delta axis) separating low vs high note; 0.5=blind
Overlaid: the codec floor from eval/mp3_latent_sensitivity (SAME-path encode):
  magnitude   frac_of_fifthjump  320k 0.222 / 256k 0.347 / 192k ~0.49 / 128k 0.74
  subspace    melody_frac        codec ~0.073-0.080  vs random 0.0586

Run (any venv w/ numpy):  .venv/bin/python eval/musicology/interval_resolution_ladder.py
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATLAS = np.load(HERE / "latent_melody_analysis_v2/stage1_pitch_atlas_v2.npz", allow_pickle=True)
B15 = np.load(ROOT / "lumi/melody_subspace15_v2.npz")["basis15"].astype(np.float64)  # [15,256]
MP3 = json.loads((Path("/run/media/kim/Mantu/sa3_control_runs/analysis/"
                       "mp3_latent_sensitivity_2026-08-04/results.json")).read_text())
OUT = HERE / "interval_resolution_ladder_2026-08-06"
OUT.mkdir(exist_ok=True)

SLOT = ATLAS["slot_vectors"].astype(np.float64)   # [10 timbre, 73 pitch, 256]
PITCH = ATLAS["pitches"]                            # 36..108
TIMBRES = [str(t) for t in ATLAS["timbres"]]
NT, NP, C = SLOT.shape
RANDOM_FRAC = 15.0 / C                              # 0.0586 — a random dir's melody-subspace share

INTERVALS = {1: "minor 2nd", 2: "major 2nd (whole tone)", 3: "minor 3rd", 4: "major 3rd",
             5: "perfect 4th", 7: "perfect 5th", 12: "octave"}


def mel_energy_frac(d):
    """fraction of ||d||^2 living in the 15-dim melody subspace."""
    proj = B15 @ d
    return float((proj @ proj) / (d @ d + 1e-12))


PIDX = {int(p): i for i, p in enumerate(PITCH)}
BASES = [p for p in range(48, 85, 3) if p in PIDX and (p + 12) in PIDX]   # fixed registers


def _pairwise_offdiag_cos(V):
    """mean cosine between distinct rows of V (the fifth-jump cross-timbre cos was 0.275)."""
    Vn = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)
    G = Vn @ Vn.T
    n = len(V)
    return float((G.sum() - np.trace(G)) / (n * (n - 1)))


def ladder_for(k):
    """CONTROLLED: fix base pitch (register), vary only the interval, aggregate over
    registers. This isolates the interval from the register/timbre variance that pooling
    conflates — the same design as the v2 fifth-jump calibration."""
    norms, mels, coh, accs = [], [], [], []
    for p0 in BASES:
        lo = SLOT[:, PIDX[p0]]           # [10 timbre, 256] low note
        hi = SLOT[:, PIDX[p0 + k]]       # high note (interval k above)
        d = hi - lo                      # [10,256] per-timbre interval displacement
        norms.append(np.linalg.norm(d, axis=1).mean())
        mels.append(np.mean([mel_energy_frac(x) for x in d]))
        coh.append(_pairwise_offdiag_cos(d))                     # cross-timbre direction coherence
        u = d.mean(0); u /= (np.linalg.norm(u) + 1e-12)          # within-register shift axis
        pl, ph = lo @ u, hi @ u
        thr = 0.5 * (pl.mean() + ph.mean())
        accs.append(0.5 * ((ph > thr).mean() + (pl <= thr).mean()))
    return {"k": k, "name": INTERVALS[k], "n_registers": len(BASES),
            "abs_norm": float(np.mean(norms)), "abs_norm_sd": float(np.std(norms)),
            "melFrac": float(np.mean(mels)), "melFrac_sd": float(np.std(mels)),
            "dir_cos": float(np.mean(coh)), "detect_acc": float(np.mean(accs))}


rows = [ladder_for(k) for k in INTERVALS]
fifth = next(r for r in rows if r["k"] == 7)["abs_norm"]
for r in rows:
    r["frac_of_atlas_fifth"] = round(r["abs_norm"] / fifth, 4)

# ---- codec floor, unit-matched ----
bb = MP3["by_bitrate"]
codec = {b: {"frac_of_fifth": bb[b]["frac_of_fifthjump"], "melFrac": bb[b]["melody_frac_mean"]}
         for b in ("320", "256", "192", "128")}
incontext_fifth = MP3["calibration"]["fifthjump_delta_norm_mean"]   # 5.64 (pattern-context ref)

# The finding is NOT a detectability floor — it's magnitude saturation + poor subspace SNR.
codec_mel_strict = codec["320"]["melFrac"]        # 0.080 — strictest codec melody-subspace floor
min2 = next(r for r in rows if r["k"] == 1)
for r in rows:
    r["melody_snr_vs_codec"] = round(r["melFrac"] / codec_mel_strict, 3)   # >1 = melody beats codec hiss
    r["melody_snr_vs_random"] = round(r["melFrac"] / RANDOM_FRAC, 3)
mag_saturation = round(min2["abs_norm"] / fifth, 3)   # minor-2nd |d| as fraction of a fifth's |d|

summary = {"purpose": "interval-resolution ladder vs codec floor (Kim 2026-08-06)",
           "source": "stage1 pitch atlas (clean single notes) — BEST-CASE resolution ceiling",
           "method": ("CONTROLLED: fix register (base pitch), vary only the interval, aggregate "
                      "over %d registers x 10 timbres; dir_cos = cross-timbre coherence "
                      "(fifth-jump in-context ref = 0.275); detect_acc is IN-SAMPLE (upper bound)."
                      % len(BASES)),
           "subspace": "lumi/melody_subspace15_v2.npz basis15 (the #59 loss subspace)",
           "atlas_fifth_abs_norm": round(fifth, 3), "incontext_fifth_norm": round(incontext_fifth, 3),
           "random_melFrac_baseline": round(RANDOM_FRAC, 4),
           "codec_floor": codec, "rows": rows,
           "headline": {
               "magnitude_saturation_min2nd_over_fifth": mag_saturation,
               "melody_snr_vs_codec_min2nd": min2["melFrac"] / codec_mel_strict,
               "melody_snr_vs_codec_range": [round(min(r["melFrac"] for r in rows) / codec_mel_strict, 3),
                                             round(max(r["melFrac"] for r in rows) / codec_mel_strict, 3)],
               "detect_acc_min2nd": min2["detect_acc"]},
           "reading": ("A minor 2nd is NOT below the noise floor: its latent move is ~%.0f%% of a "
                       "fifth's (magnitude SATURATES — displacement can't read interval SIZE), it is "
                       "detectable (in-sample), and its melody-subspace share (%.3f) beats codec hiss "
                       "(%.3f) and random (%.3f). BUT the melody-subspace SNR over codec noise is only "
                       "~%.1fx — the subspace the #59 loss boosts is barely more melodic than noisy, "
                       "so upweighting it amplifies codec hiss almost as much as melody."
                       % (mag_saturation * 100, min2["melFrac"], codec_mel_strict, RANDOM_FRAC,
                          min2["melFrac"] / codec_mel_strict))}
(OUT / "results.json").write_text(json.dumps(summary, indent=2))

# ---- console table ----
print(f"\natlas fifth |d|={fifth:.2f}  (in-context fifth ref={incontext_fifth:.2f})  "
      f"random melFrac={RANDOM_FRAC:.4f}  codec melFrac(320k)={codec_mel_strict:.3f}")
print(f"\n{'interval':<24}{'|d|':>7}{'/fifth':>8}{'melFrac':>9}{'SNRvsCodec':>11}{'dirCos':>8}{'detect':>8}")
for r in rows:
    print(f"{r['name']:<24}{r['abs_norm']:>7.2f}{r['frac_of_atlas_fifth']:>8.2f}"
          f"{r['melFrac']:>9.4f}{r['melody_snr_vs_codec']:>11.2f}{r['dir_cos']:>8.3f}{r['detect_acc']:>8.3f}")
print(f"\nHEADLINE: minor-2nd |d| = {mag_saturation:.0%} of a fifth (magnitude SATURATES — can't read "
      f"interval size).\n  minor-2nd melody-subspace SNR over codec noise = "
      f"{min2['melFrac']/codec_mel_strict:.2f}x (thin) — the #59 subspace is only weakly melody-selective.")

# ---- figure (best-effort) ----
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ks = [r["k"] for r in rows]
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    ax[0].plot(ks, [r["frac_of_atlas_fifth"] for r in rows], "o-", color="#5cf")
    ax[0].axhspan(codec["320"]["frac_of_fifth"], codec["128"]["frac_of_fifth"], color="#f55", alpha=.18)
    ax[0].axhline(codec["128"]["frac_of_fifth"], color="#f55", lw=.8, ls="--")
    ax[0].set_title("magnitude / a fifth\n(red band = codec 320k..128k floor)"); ax[0].set_xlabel("interval (semitones)")
    ax[1].plot(ks, [r["melFrac"] for r in rows], "o-", color="#5cf")
    ax[1].axhline(RANDOM_FRAC, color="#888", ls=":", label="random (0.059)")
    ax[1].axhspan(codec["256"]["melFrac"], codec["320"]["melFrac"], color="#f55", alpha=.18)
    ax[1].set_title("melody-subspace energy frac\n(grey=random, red=codec)"); ax[1].set_xlabel("interval (semitones)"); ax[1].legend()
    ax[2].plot(ks, [r["detect_acc"] for r in rows], "o-", color="#5cf")
    ax[2].axhline(0.5, color="#888", ls=":", label="chance")
    ax[2].set_title("1-D readout detectability (balanced acc)"); ax[2].set_xlabel("interval (semitones)"); ax[2].set_ylim(0.4, 1.02); ax[2].legend()
    for a in ax: a.grid(alpha=.2); a.set_xticks(ks)
    fig.suptitle("Interval-resolution ladder — clean single-note atlas (best case) vs SAME/MP3 codec floor", fontsize=11)
    fig.tight_layout(); fig.savefig(OUT / "ladder.png", dpi=110)
    print(f"[fig] {OUT/'ladder.png'}")
except Exception as e:
    print(f"[fig skipped: {e}]")

print(f"[done] -> {OUT}/results.json")
