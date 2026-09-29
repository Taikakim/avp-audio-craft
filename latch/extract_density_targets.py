#!/usr/bin/env python3
"""extract_density_targets.py — onset-per-beat ("density") targets for a latent store that has none.

WHY (C, 2026-09-30, Kim's ask): bracket LatCH and the FiLM control adapter on the 12.5k-crop goa
bigset (`latents_goa_bigset`, Kosmos) with the density target, i.e. onset density normalised by
tempo — the tempo-invariant form that made the tempo shortcut unexpressible (W's 2026-06-26
finding). The bigset crops carry no targets at all (docs/data.md), so this computes them from the
source audio, with the SAME definitions as the MIR pipeline behind `latents_sa3`:
  - onsets: librosa onset_strength(hop 512) + onset_detect(backtrack=True)  (mir src/rhythm/onsets.py)
  - tempo:  madmom RNNBeatProcessor + TempoEstimationProcessor(fps=100)  (mir src/rhythm/bpm.py), BUT the
            strongest candidate in [95,190) BPM, not the top one: the top one is half-tempo on 45% of goa crops
  - onset_per_beat = onset_density * 60 / bpm                    (latents_sa3 crop .json)

Writes `<stem>.TIMESERIES.npz` next to each crop latent, the companion format
stable-audio-3/scripts/latch/train_latch.py (--target-source npz) and control/sa3_control's
--scalar-from-timeseries already read:
  onset_per_beat_ts (T,)  onsets per beat, Gaussian-weighted over ~one bar (sigma 2 beats), per latent frame
  onset_envelope_ts (T,)  raw librosa onset_strength resampled to the latent grid (parity with latents_sa3)
  valid_ts (T,)           the crop's padding_mask (1 = real audio)
  + scalars bpm_madmom, onset_density, onset_per_beat (whole valid crop)
Resumable: skips crops whose companion exists. Run with the mir venv (madmom lives there).
USAGE  /home/kim/Projects/mir/mir/bin/python latch/extract_density_targets.py \
         --latent-dir /run/media/kim/Kosmos/latents_goa_bigset \
         --audio-root /run/media/kim/Mantu/goa_archive_extracted --workers 12
"""
import argparse
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

SR = 44100
HOP_LATENT = 4096
FPS = SR / HOP_LATENT          # 10.7666 Hz, the SA3 SAME latent rate
TEMPO_EXCERPT_S = 90.0


def onset_per_beat_ts(onset_times, bpm, T, beats=4.0):
    """Onsets per beat, Gaussian-weighted over ~`beats` beats (sigma = beats/2), at every latent frame."""
    if not bpm or bpm <= 0:
        raise ValueError(f"bad bpm {bpm}")
    frames = np.floor(np.asarray(onset_times, dtype=np.float64) * FPS).astype(np.int64)
    frames = frames[(frames >= 0) & (frames < T)]
    imp = np.bincount(frames, minlength=T).astype(np.float64)
    # Gaussian, sigma = beats/2 beats (one bar at beats=4 spans ~ +-1 sigma). A box window
    # aliases against the beat grid: it holds 3 or 4 onsets depending on its phase (+-25%).
    sigma = max(0.5, beats / 2.0 * 60.0 / bpm * FPS)    # in frames
    r = int(np.ceil(4 * sigma))
    x = np.arange(-r, r + 1)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()                                        # mean onsets per frame in the window
    rate = np.convolve(imp, k, mode="same")             # onsets / frame
    return (rate * FPS * 60.0 / bpm).astype(np.float32)  # -> onsets / beat


def pick_tempo(tempos, lo=95.0, hi=190.0):
    """Strongest madmom tempo candidate inside [lo, hi); else the top one octave-folded into it.
    madmom's top candidate is HALF the tempo on 45% of latents_sa3's goa crops (2430/5401 under
    95 BPM, essentia median 142) — that doubled every such crop's onset_per_beat (C, 2026-09-30)."""
    tempos = np.asarray(tempos, dtype=np.float64).reshape(-1, 2) if len(tempos) else np.zeros((0, 2))
    inside = tempos[(tempos[:, 0] >= lo) & (tempos[:, 0] < hi)]
    if len(inside):
        return float(inside[np.argmax(inside[:, 1]), 0])
    if not len(tempos) or tempos[0, 0] <= 0:
        return 0.0
    b = float(tempos[0, 0])
    while b < lo:
        b *= 2.0
    while b >= hi:
        b /= 2.0
    return b


def _fit(x, T):
    x = np.asarray(x, dtype=np.float32)
    if len(x) == T:
        return x
    return np.interp(np.linspace(0, len(x) - 1, T), np.arange(len(x)), x).astype(np.float32)


def process(args):
    npy, audio_root = args
    out = npy.with_suffix(".TIMESERIES.npz")
    if out.exists():
        return npy.name, "skip", 0.0
    t0 = time.time()
    try:
        import librosa
        import madmom
        meta = json.loads(npy.with_suffix(".json").read_text())
        mask = np.asarray(meta.get("padding_mask") or [], dtype=np.float32)
        T = len(mask) if len(mask) else 4096
        valid = int(mask.sum()) if len(mask) else T
        src = Path(audio_root) / meta["relpath"]
        y, _ = librosa.load(str(src), sr=SR, mono=True, offset=float(meta.get("seconds_start", 0)),
                            duration=T * HOP_LATENT / SR)
        env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=512)
        on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=512, backtrack=True)
        times = librosa.frames_to_time(on, sr=SR, hop_length=512)
        # tempo from a TEMPO_EXCERPT_S window at the middle of the valid audio: madmom's RNN ensemble
        # costs ~25 s on a full 380 s crop (the whole budget), and goa tempo is steady within a track
        vlen = min(len(y), int(valid * HOP_LATENT))
        a0 = max(0, vlen // 2 - int(TEMPO_EXCERPT_S * SR / 2))
        seg = y[a0:a0 + int(TEMPO_EXCERPT_S * SR)]
        act = madmom.features.beats.RNNBeatProcessor()(madmom.audio.signal.Signal(seg, sample_rate=SR))
        tempos = madmom.features.tempo.TempoEstimationProcessor(fps=100)(act)
        bpm_raw = float(tempos[0, 0]) if len(tempos) else 0.0
        bpm = pick_tempo(tempos)
        if bpm <= 0:
            return npy.name, "no-bpm", time.time() - t0
        dur = valid / FPS
        dens = float(np.sum(times < dur)) / dur
        env_ts = _fit(env, int(round(len(y) / HOP_LATENT)))
        env_ts = np.pad(env_ts, (0, max(0, T - len(env_ts))))[:T]
        tmp = out.with_suffix(".tmp.npz")
        np.savez(tmp, onset_per_beat_ts=onset_per_beat_ts(times, bpm, T), onset_envelope_ts=env_ts,
                 valid_ts=mask if len(mask) else np.ones(T, np.float32),
                 bpm_madmom=np.float32(bpm), bpm_madmom_raw=np.float32(bpm_raw),
                 onset_density=np.float32(dens),
                 onset_per_beat=np.float32(dens * 60.0 / bpm))
        os.replace(tmp, out)
        return npy.name, "ok", time.time() - t0
    except Exception as e:  # keep going; the log lists failures
        return npy.name, f"err {type(e).__name__}: {e}"[:200], time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latent-dir", required=True)
    ap.add_argument("--audio-root", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    items = sorted(p for p in Path(a.latent_dir).glob("*.npy") if not p.name.endswith(".z0.npy"))
    if a.limit:
        items = items[:a.limit]
    todo = [(p, a.audio_root) for p in items if not p.with_suffix(".TIMESERIES.npz").exists()]
    print(f"[density] {len(items)} crops, {len(todo)} to do, {a.workers} workers", flush=True)
    n = 0
    t0 = time.time()
    with Pool(a.workers, maxtasksperchild=50) as pool:
        for name, status, dt in pool.imap_unordered(process, todo, chunksize=2):
            n += 1
            if status != "ok" or n % 100 == 0:
                el = time.time() - t0
                print(f"[density] {n}/{len(todo)} {name} {status} {dt:.1f}s  "
                      f"(eta {el / n * (len(todo) - n) / 60:.0f} min)", flush=True)
    print("[density] DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
