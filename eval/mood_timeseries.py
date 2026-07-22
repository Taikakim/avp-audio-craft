#!/usr/bin/env python3
"""
mood_timeseries.py -- per-eval-clip MOOD/THEME time series (Kim 2026-07-22: "when calculating
the moods, save a time series if possible. If we need to quantise, just fill frames with current
value"). The axis: does a model's output drift AWAY from the training-set mood profile
(goa = melodic / retro / atmospheric / psychedelic ...) as it degenerates?

REUSES mir's whole_track_expanded.ExpandedExtractor (the validated TF plumbing) rather than
reimplementing it -- same effnet -> mtg_jamendo_moodtheme (56-tag sigmoid) path that produces
`effnet_moodtheme_ts` on the training corpus, so eval clips and the training reference are
apples-to-apples.

TIME SERIES + ZOH: the classifier emits one 56-vector per ~1 s effnet patch (its native rate).
We keep that series; with --rate R we ZERO-ORDER-HOLD it onto a regular R-Hz grid (repeat each
patch's value forward until the next patch = "fill frames with current value").

Outputs (per clip, resumable -> --out-dir):
  <stem>.MOODTS.npz  -- mood_ts (n_frames, 56) float16, `labels` (56 tag names), `rate_hz`, meta.
Plus a summary CSV (--summary): per-clip mean mood vector + the top-5 tags, for quick drift work.

RUN (mir venv -- essentia + TF):
  mir/bin/python eval/mood_timeseries.py --models fp32cmp_goa_t512_bs8_lr1e4 --sample-per-model 40 \
      --out-dir /tmp/moodts --summary /tmp/mood_summary.csv --rate 0
  # --rate 0 keeps the native ~1 Hz patch grid (no ZOH); --rate 10 ZOH-fills to 10 Hz.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir/src")
from spectral.whole_track_expanded import ExpandedExtractor, MODEL_PATHS  # noqa: E402

CLIPS = Path.home() / ".cache/evals_aac/model_matrix"
CLAP = Path("/home/kim/Projects/SAO/eval/clap_degen_model_matrix.csv")
EFFNET_HOP_S = 1.0  # discogs-effnet embedding hop ~ 1 s (the moodtheme patch rate)


def load_labels():
    j = Path(str(MODEL_PATHS["moodtheme"]).replace(".pb", ".json"))
    return json.loads(j.read_text())["classes"] if j.exists() else [f"mood_{i}" for i in range(56)]


def zoh_fill(mood, rate_hz):
    """Zero-order-hold the ~1 Hz patch series onto a regular rate_hz grid: each grid frame
    takes the value of the most recent patch (repeat forward). rate_hz<=0 -> return as-is."""
    if rate_hz <= 0 or mood.shape[0] == 0:
        return mood
    n_out = max(1, int(round(mood.shape[0] * EFFNET_HOP_S * rate_hz)))
    idx = np.minimum((np.arange(n_out) / rate_hz / EFFNET_HOP_S).astype(int), mood.shape[0] - 1)
    return mood[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+")
    ap.add_argument("--sample-per-model", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--summary", type=Path)
    ap.add_argument("--rate", type=float, default=0.0, help="ZOH grid Hz; 0 = keep native ~1 Hz")
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)

    import essentia.standard as es
    ext = ExpandedExtractor(enable_models=True, enable_dsp=False)
    labels = load_labels()

    rows = [r for r in csv.DictReader(open(CLAP)) if r.get("duration_mode") != "native"]
    if a.models:
        rows = [r for r in rows if r["model"] in a.models]
    if a.sample_per_model > 0:
        by = {}
        for r in rows:
            by.setdefault(r["model"], []).append(r)
        rows = []
        for rs in by.values():
            step = max(1, len(rs) // a.sample_per_model)
            rows += rs[::step][:a.sample_per_model]
    print(f"[moodts] {len(rows)} clips, rate={a.rate or 'native~1Hz'}")

    summary = []
    for i, r in enumerate(rows):
        p = CLIPS / r["file"]
        if not p.exists():
            continue
        out = a.out_dir / (p.stem + ".MOODTS.npz")
        if out.exists():
            continue
        try:
            mono16 = es.MonoLoader(filename=str(p), sampleRate=16000)()
            emb = np.asarray(ext._predictor("effnet")(mono16))          # (n_patches, 1280) ~1 Hz
            mood = np.asarray(ext._predictor("moodtheme")(emb))          # (n_patches, 56) sigmoid
        except Exception as ex:
            print(f"[moodts] skip {r['file']}: {ex}")
            continue
        mood_grid = zoh_fill(mood, a.rate).astype(np.float16)
        np.savez_compressed(str(out), mood_ts=mood_grid, labels=np.array(labels),
                            rate_hz=(a.rate or EFFNET_HOP_S), model=r["model"], ckpt=r["ckpt"],
                            cfg=r["cfg"], strength=r["strength"], clip_file=r["file"])
        if a.summary is not None and mood.shape[0]:
            mean = mood.mean(axis=0)
            top = np.argsort(mean)[::-1][:5]
            summary.append({"file": r["file"], "model": r["model"], "ckpt": r["ckpt"],
                            "cfg": r["cfg"], "strength": r["strength"],
                            "clap_matched": r.get("clap_matched"),
                            "top_moods": "|".join(f"{labels[j]}:{mean[j]:.2f}" for j in top),
                            **{f"mood_{labels[j]}": round(float(mean[j]), 4) for j in range(56)}})
        if (i + 1) % 50 == 0:
            print(f"[moodts] {i + 1}/{len(rows)}")

    if a.summary is not None and summary:
        with a.summary.open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
            wr.writeheader()
            wr.writerows(summary)
        print(f"[moodts] summary -> {a.summary} ({len(summary)} clips)")
    print(f"[moodts] wrote per-clip MOODTS.npz to {a.out_dir}")


if __name__ == "__main__":
    main()
