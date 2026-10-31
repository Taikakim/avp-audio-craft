#!/usr/bin/env python3
"""cache_mood_targets.py -- pre-extracts and slices effnet_moodtheme_ts targets
for all 5,401 crops in latents_sa3, saving them to /run/media/kim/Mantu/latents_sa3_mood/.
Total size: ~338 MB. Zero I/O overhead during LatCH training.
"""
import glob, json, os, time, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np

LATENTS_DIR = Path("/run/media/kim/Kosmos/latents/latents_sa3")
TIMESERIES_DIR = Path("/run/media/kim/Kosmos/timeseries")
OUT_DIR = Path("/run/media/kim/Mantu/latents_sa3_mood")
OUT_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FRAMES = 280

def resample_axis0(arr, n):
    arr = np.asarray(arr, dtype=np.float32)
    T = arr.shape[0]
    if T == n:
        return arr
    if T == 0:
        return np.zeros((n,) + arr.shape[1:], dtype=np.float32)
    xp = np.linspace(0.0, 1.0, T)
    x = np.linspace(0.0, 1.0, n)
    if arr.ndim == 1:
        return np.interp(x, xp, arr).astype(np.float32)
    return np.stack([np.interp(x, xp, arr[:, c]) for c in range(arr.shape[1])], axis=1).astype(np.float32)

def process_track(track_name, crop_list):
    npz_path = TIMESERIES_DIR / f"{track_name}.TIMESERIES.npz"
    if not npz_path.exists():
        return 0
    try:
        with np.load(npz_path) as z:
            if "effnet_moodtheme_ts" not in z.files:
                return 0
            arr = z["effnet_moodtheme_ts"]
            m = json.loads(str(z["__meta__"]))
            fr = float(m.get("field_rates", {}).get("effnet_moodtheme_ts", 1.0080645))
            
            written = 0
            for stem, st_sec, dur in crop_list:
                out_path = OUT_DIR / f"{stem}.npy"
                if out_path.exists() and out_path.stat().st_size > 0:
                    written += 1
                    continue
                s_idx = max(0, int(round(st_sec * fr)))
                e_idx = min(arr.shape[0], int(round((st_sec + dur) * fr)))
                slice_arr = arr[s_idx:e_idx]
                resampled = resample_axis0(slice_arr, TARGET_FRAMES).T.astype(np.float32) # (56, 280)
                np.save(out_path, resampled)
                written += 1
            return written
    except Exception as e:
        print(f"Error on {track_name}: {e}")
        return 0

def main():
    t0 = time.time()
    json_files = sorted([f for f in glob.glob(str(LATENTS_DIR / "*.json")) if not f.endswith(".TIMBRAL.json")])
    print(f"Discovered {len(json_files)} crop metadata files in {LATENTS_DIR}")

    by_track = {}
    for jf in json_files:
        stem = Path(jf).stem
        if stem == "silence":
            continue
        try:
            with open(jf) as fp:
                meta = json.load(fp)
            st = meta.get("source_track")
            st_sec = float(meta.get("seconds_start", 0.0))
            dur = float(meta.get("seconds_total", 26.0))
            if st:
                by_track.setdefault(st, []).append((stem, st_sec, dur))
        except Exception:
            continue

    print(f"Grouped into {len(by_track)} unique source tracks.")

    total_written = 0
    with ProcessPoolExecutor(max_workers=8) as exc:
        futures = [exc.submit(process_track, track, crops) for track, crops in by_track.items()]
        for f in futures:
            total_written += f.result()

    print(f"Finished caching mood targets! Total crops cached: {total_written} in {time.time() - t0:.1f}s.")
    print(f"Output directory: {OUT_DIR} (Total size: {sum(f.stat().st_size for f in OUT_DIR.glob('*.npy')) / 1e6:.1f} MB)")

if __name__ == "__main__":
    main()
