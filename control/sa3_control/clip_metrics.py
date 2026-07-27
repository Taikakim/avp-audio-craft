#!/usr/bin/env python3
"""Comprehensive per-clip metrics over ALL eval clips (Kim 2026-07-12: "run all of the
metrics we have so far found useful for all of our clips").

CPU metrics (librosa, multiprocess) — the fast, reliable bulk:
  dur, rms, crest, zcr, onset_density_p95 (the honest gated meter), spectral_centroid,
  spectral_flatness, spectral_flux, hf_ratio (>5 kHz energy fraction = harshness/brightness),
  bpm. Writes to one SQLite DB, resumable (skips paths already scored). Audiobox CE/PQ is a
  SEPARATE GPU pass (clip_metrics_audiobox.py) writing the same DB — WavLM is the only
  neural/GPU metric; the rest see no GPU benefit and parallelize across cores instead.

Run (mir venv):
  mir/bin/python control/sa3_control/clip_metrics.py [--workers 12] [--roots model_matrix,control_runs,renders,riffer]
"""
import argparse
import glob
import os
import sqlite3
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STAGE = "/home/kim/evals_aac"
DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"
SR = 22050
HI_HZ = 5000.0
COLS = ["dur", "rms", "crest", "zcr", "onset_p95", "centroid", "flatness", "flux", "hf_ratio", "bpm"]


def clip_metrics(path):
    import librosa
    try:
        y, _ = librosa.load(path, sr=SR, mono=True)
        if len(y) < SR // 2:
            return path, None
        dur = len(y) / SR
        rms = float(np.sqrt(np.mean(y ** 2)))
        peak = float(np.max(np.abs(y)) + 1e-9)
        crest = peak / (rms + 1e-9)
        zcr = float((np.abs(np.diff(np.sign(y))) > 0).mean())
        # p95-gated onset density (the honest meter)
        env = librosa.onset.onset_strength(y=y, sr=SR)
        envn = np.clip(env / max(np.percentile(env, 95), 1e-9), 0, 3)
        peaks = librosa.util.peak_pick(envn, pre_max=3, post_max=3, pre_avg=10, post_avg=10, delta=0.3, wait=2)
        onset_p95 = float(len(peaks) / max(dur, 1e-6))
        S = np.abs(librosa.stft(y, n_fft=2048))
        freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
        centroid = float(librosa.feature.spectral_centroid(S=S, sr=SR).mean())
        flatness = float(librosa.feature.spectral_flatness(S=S).mean())
        flux = float(np.mean(np.sqrt(np.sum(np.diff(S, axis=1) ** 2, axis=0)))) if S.shape[1] > 1 else 0.0
        power = S ** 2
        hf_ratio = float(power[freqs >= HI_HZ].sum() / (power.sum() + 1e-9))
        try:
            bpm = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=SR)[0])[0])
        except Exception:
            bpm = 0.0
        return path, [round(dur, 2), round(rms, 5), round(crest, 3), round(zcr, 5),
                      round(onset_p95, 3), round(centroid, 1), round(flatness, 5),
                      round(flux, 4), round(hf_ratio, 5), round(bpm, 1)]
    except Exception:
        return path, None


def enumerate_clips(roots, base=STAGE, ext="m4a"):
    paths = []
    for r in roots:
        paths += glob.glob(f"{base}/{r}/**/*.{ext}", recursive=True)
        paths += glob.glob(f"{base}/{r}/*.{ext}")
    return sorted(set(paths))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--roots", default="model_matrix,control_runs,renders,riffer")
    ap.add_argument("--base", default=STAGE,
                    help="base dir the roots live under (default the AAC staging dir)")
    ap.add_argument("--ext", default="m4a",
                    help="clip extension to meter — 'wav' to meter the LOSSLESS source "
                         "(no AAC artifacts in flatness/hf_ratio/etc.) instead of staged m4a")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB, timeout=60)          # wait on locks (Audiobox may share the DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(f"CREATE TABLE IF NOT EXISTS metrics (path TEXT PRIMARY KEY, {', '.join(c+' REAL' for c in COLS)})")
    con.commit()
    # "done" = HAS the CPU metrics (dur set), NOT merely present — an Audiobox-only row
    # (ce set, dur NULL) still needs the CPU pass. Named-column upsert preserves ce/pq.
    done = {r[0] for r in con.execute("SELECT path FROM metrics WHERE dur IS NOT NULL")}

    clips = enumerate_clips(args.roots.split(","), args.base, args.ext)
    todo = [c for c in clips if c not in done]
    print(f"clips total {len(clips)}, already done {len(done)}, to do {len(todo)}", flush=True)
    if not todo:
        print("nothing to do"); return

    t0 = time.time(); n = 0
    with Pool(args.workers) as pool:
        batch = []
        for path, vals in pool.imap_unordered(clip_metrics, todo, chunksize=8):
            n += 1
            if vals is not None:
                batch.append([path] + vals)
            if len(batch) >= 200:
                con.executemany(f"INSERT INTO metrics (path,{','.join(COLS)}) VALUES ({','.join('?'*(len(COLS)+1))}) "
                                f"ON CONFLICT(path) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in COLS)}", batch)
                con.commit(); batch = []
            if n % 500 == 0:
                rate = n / (time.time() - t0)
                print(f"  {n}/{len(todo)} ({rate:.1f}/s, ETA {int((len(todo)-n)/max(rate,1e-6)/60)}min)", flush=True)
        if batch:
            con.executemany(f"INSERT INTO metrics (path,{','.join(COLS)}) VALUES ({','.join('?'*(len(COLS)+1))}) "
                            f"ON CONFLICT(path) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in COLS)}", batch)
            con.commit()
    total = con.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    print(f"DONE: {n} scored this run, {total} total in {DB} ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
