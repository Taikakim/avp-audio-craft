#!/usr/bin/env python
"""corruption_scan_to_db.py — GHOST-NOTE 2026-09-22: persists audio_corruption_scan.py's
per-clip amplitude-jump count into clip_metrics.db (metrics.n_bad_jumps), keyed by path,
so "bad sample count" is computed ONCE and both build_model_census.py and
build_clap_hyperparam_table.py can read it by a plain column SELECT instead of each
re-scanning audio or re-deriving the threshold. Upserts a row if one doesn't already
exist for that path (a fresh render may not have an Audiobox/DSP row yet).

Usage: corruption_scan_to_db.py <clips.json with a "path"/"file" field per entry> [threshold]
Same "bad" definition as audio_corruption_scan.py: count of |diff|>threshold single-sample
jumps in the mono-summed waveform (threshold default 0.6 — calibrated so a clean clip in
this corpus shows 0-2, real corruption showed thousands; see that script's docstring).
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chroma_morph_transitions import load  # noqa: E402
from audio_corruption_scan import scan_clip  # noqa: E402

DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")


def _nonfinite_latent_flag(wav_path):
    """The amplitude-JUMP screen (scan_clip) is BLIND to the DC-constant NaN-latent failure
    (MASTER.md sec5, 2026-09-08): a fully non-finite latent decodes to every sample being the
    SAME constant (peak exactly 1.000, save_audio's `peak > 1e-6` normalize-guard reads NaN as
    False), so consecutive-sample diffs are ~0 and scan_clip reports a clean 0. Caught here by
    checking the sibling .z0.npy directly when one exists -- 2026-09-24, found on
    goa3_avp_r256_2026-09-23's abort_lossnan_ep10 checkpoint (6/6 clips 100% non-finite latent,
    0 bad jumps by the amplitude screen alone)."""
    z0 = wav_path.parent / (wav_path.stem + ".z0.npy")
    if not z0.exists():
        return None
    try:
        z = np.load(z0)
    except Exception:
        return None
    finite_frac = float(np.isfinite(z).mean())
    return None if finite_frac >= 1.0 else (1.0 - finite_frac)


def main():
    clips_json = Path(sys.argv[1])
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
    clips = json.loads(clips_json.read_text())

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    n_ok, n_err = 0, 0
    for c in clips:
        p = Path(c["path"])
        wav = p.with_suffix(".wav")
        used = wav if wav.exists() else p
        try:
            n_bad, max_jump = scan_clip(used, threshold)
        except Exception as e:
            print(f"[error] {c.get('file', p.name)}: {e}", flush=True)
            n_err += 1
            continue
        nonfinite_frac = _nonfinite_latent_flag(used)
        if nonfinite_frac is not None:
            # sentinel: "every sample is bad" -- sorts to the top of any n_bad_jumps ranking,
            # distinct from a genuinely-0 clean clip, without inventing a second column every
            # downstream consumer (build_clap_hyperparam_table.py's bad_samples_cfg17_w1 etc.)
            # would need to know about.
            n_bad = max(n_bad, 999999)
            print(f"  NON-FINITE LATENT ({nonfinite_frac*100:.0f}% of samples): {p.name}", flush=True)
        # path in the DB is whatever the Audiobox/DSP pass keyed on (wav OR m4a per-stem,
        # see build_clap_hyperparam_table.py's coalesce comment) -- write against BOTH
        # sibling paths that could exist for this stem so the join can't miss either.
        for cand in (str(p.with_suffix(".wav")), str(p.with_suffix(".m4a"))):
            cur.execute("SELECT 1 FROM metrics WHERE path = ?", (cand,))
            if cur.fetchone():
                cur.execute("UPDATE metrics SET n_bad_jumps = ? WHERE path = ?", (n_bad, cand))
            else:
                cur.execute("INSERT INTO metrics (path, n_bad_jumps) VALUES (?, ?)", (cand, n_bad))
        n_ok += 1
        if n_bad > 0:
            print(f"  n_bad={n_bad:4d} max_jump={max_jump:.3f}  {p.name}", flush=True)
    con.commit()
    con.close()
    print(f"[done] {n_ok} scanned, {n_err} errors -> {DB}", flush=True)


if __name__ == "__main__":
    main()
