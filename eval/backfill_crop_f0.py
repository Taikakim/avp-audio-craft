#!/usr/bin/env python3
"""backfill_crop_f0.py — add the f0 melody fields to crop timeseries companions that
predate them (CONTINUITY 2026-09-09, Kim: "AVP should get the f0").

WHY THIS IS A RESAMPLE AND NOT AN EXTRACTION. The f0 melody line already exists at TRACK
level for AVP (PredominantPitchMelodia on the separated stems: f0_other_ts / f0_bass_ts
+ their voiced masks, 100 Hz, all 170 tracks carry them). What was missing is the per-crop
companion — the crops were built before the 2026-08-12 f0 backfill, and nothing went back
to re-slice them. So the morph/contour conditioner sees no AVP stream and the dataset's
melody filter drops every AVP crop, silently making a "goa + AVP" run goa-only.

WHY IT DELEGATES THE POOLING. f0 uses 0.0 as the UNVOICED SENTINEL, so mean-pooling it
averages real pitches with silence and drags every window toward zero — measured at the SA3
grid as p95 +15.86 semitones with 17.2% of frames wrong by more than a semitone, while the
MEDIAN error is 0.00 (fully-voiced windows pool exactly, which is why a spot-check passes
it). mir's crop_timeseries_resample knows that, and pools f0 weighted by the voiced mask.
Do not reimplement the pooling here; that module is where the rules live.

  mir/bin/python eval/backfill_crop_f0.py \
      --crop-dir  /run/media/kim/Lehto/latents-all-backup/latents_avp_originals \
      --stems-dir /run/media/kim/Mantu/avp-analyzed-stems --dry-run
"""
import argparse
import glob
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir")
from src.tools.crop_timeseries_resample import build_crop_timeseries  # noqa: E402

F0_FIELDS = ("f0_other_ts", "f0_other_voiced_ts", "f0_bass_ts", "f0_bass_voiced_ts")


def track_meta(z):
    raw = z["__meta__"].item() if "__meta__" in z.files else {}
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crop-dir", required=True)
    ap.add_argument("--stems-dir", required=True)
    ap.add_argument("--n-frames", type=int, default=4096)
    ap.add_argument("--backup-dir", default=None,
                    help="copy each crop companion here before rewriting it")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    # crop jsons only: a latent dir also holds corpus-level files (captions_freeform.json,
    # captions_style.json) and per-crop .TIMBRAL.json siblings. Identify a crop by the
    # fields this tool actually needs rather than by filename convention.
    crops = []
    for j in sorted(glob.glob(os.path.join(a.crop_dir, "*.json"))):
        if j.endswith(".TIMBRAL.json"):
            continue
        try:
            d = json.load(open(j))
        except Exception:
            continue
        if isinstance(d, dict) and {"source_track", "start_sample", "end_sample"} <= set(d):
            crops.append(j)
    if a.limit:
        crops = crops[:a.limit]
    if a.backup_dir and not a.dry_run:
        os.makedirs(a.backup_dir, exist_ok=True)

    done = skipped = failed = 0
    reasons = {}
    for j in crops:
        stem = j[:-5]
        comp = stem + ".TIMESERIES.npz"
        try:
            m = json.load(open(j))
            src = m.get("source_track")
            tnpz = os.path.join(a.stems_dir, src, src + ".TIMESERIES.npz")
            if not os.path.exists(tnpz):
                skipped += 1; reasons.setdefault("no track sidecar", 0)
                reasons["no track sidecar"] += 1
                continue
            tz = np.load(tnpz, allow_pickle=True)
            if not all(f in tz.files for f in F0_FIELDS):
                skipped += 1; reasons.setdefault("track lacks f0", 0)
                reasons["track lacks f0"] += 1
                continue

            sr = float(m.get("sample_rate", 44100))
            start = float(m["start_sample"]) / sr
            end = float(m["end_sample"]) / sr
            # pass all four together: the resampler pairs each f0 with its voiced mask and
            # uses the mask as the pooling weight, so splitting them would silently
            # fall back to a (win > 0) guess
            arrays = {f: np.asarray(tz[f]) for f in F0_FIELDS}
            out = build_crop_timeseries(arrays, track_meta(tz), start, end,
                                        a.n_frames, strict=True)

            existing = {}
            if os.path.exists(comp):
                ez = np.load(comp, allow_pickle=True)
                existing = {k: ez[k] for k in ez.files}
            before = set(existing)
            merged = dict(existing)
            merged.update(out)
            # INTEGRITY: this rewrites the file in place, and a lost legacy field is far
            # worse than a missing f0. Refuse rather than write a lossy companion.
            lost = before - set(merged)
            if lost:
                raise RuntimeError(f"would drop existing fields {sorted(lost)}")

            if a.dry_run:
                done += 1
                if done <= 3:
                    v = merged["f0_other_ts"]
                    voiced = float(np.mean(merged["f0_other_voiced_ts"] > 0))
                    print(f"  [dry] {os.path.basename(stem)}: +{len(out)} fields, "
                          f"f0_other {v.shape} nonzero={float(np.mean(v > 0)):.2f} "
                          f"voiced={voiced:.2f}, kept {len(before)} existing")
                continue

            if a.backup_dir and os.path.exists(comp):
                shutil.copy2(comp, os.path.join(a.backup_dir, os.path.basename(comp)))
            # NOTE the .npz suffix: np.savez_compressed APPENDS ".npz" to any path that
            # does not already end in it, so a bare ".tmp" name silently becomes
            # "<crop>.TIMESERIES.npz.tmp.npz" and the os.replace below then fails on a
            # path that was never written.
            tmp = comp + ".tmp.npz"
            np.savez_compressed(tmp, **merged)
            os.replace(tmp, comp)        # atomic: never leave a half-written companion
            done += 1
        except Exception as e:
            failed += 1
            reasons.setdefault(f"{type(e).__name__}", 0)
            reasons[f"{type(e).__name__}"] += 1
            if failed <= 5:
                print(f"  FAIL {os.path.basename(j)}: {e}", file=sys.stderr)

    print(f"[backfill] {done} written, {skipped} skipped, {failed} failed "
          f"of {len(crops)} crops{' (DRY RUN)' if a.dry_run else ''}")
    if reasons:
        print(f"[backfill] reasons: {reasons}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
