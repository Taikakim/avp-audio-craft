#!/usr/bin/env python3
"""lr_granularity_beat_probe.py -- Kim's ear (2026-08-02): fp32cmp_avp_t4096_bs4_lr5e5 ep7
sounds more musical / less "galloping" than lr1e4 at ep3-4, hypothesis being lr1e4's larger
per-step weight updates overshoot something fine-grained (melody, rhythm feel) that lr5e5's
smaller steps respect. Task #89 (GHOST-NOTE): objective half of that -- beat-grid steadiness
(inter-beat-interval coefficient of variation, not a named mir module, trivial from raw beat
timestamps) + syncopation (mir's existing src/rhythm/syncopation.py) across all 8 checkpoints
of both LR arms at a fixed prompt/cfg/weight (kl_1, cfg7, w1), to see whether either metric
tracks the LR gap and/or Kim's specific ep-matched comparison (lr5e5 terminal vs lr1e4 early).

Calls mir's own functions directly (detect_beats, detect_onsets, calculate_syncopation,
calculate_on_beat_ratio) rather than the file-based batch pipeline -- no sidecar files needed,
faster for a one-off 16-clip probe.

Run (mir venv): mir/bin/python eval/lr_granularity_beat_probe.py
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np

MIR = Path("/home/kim/Projects/mir")
sys.path.insert(0, str(MIR / "src"))
from rhythm.beat_grid import detect_beats  # noqa: E402
from rhythm.onsets import detect_onsets  # noqa: E402
from rhythm.syncopation import calculate_syncopation, calculate_on_beat_ratio  # noqa: E402

CLIPS_DIR = Path("/home/kim/evals_aac/model_matrix")
ARMS = ["fp32cmp_avp_t4096_bs4_lr1e4", "fp32cmp_avp_t4096_bs4_lr5e5"]
EPOCHS = range(8)
PROMPT, CFG, W = "kl_1", "cfg7", "w100"


def analyze_clip(path):
    audio, sr = librosa.load(str(path), sr=None, mono=True)
    beat_times, downbeat_times = detect_beats(path)
    onset_times, onset_strengths = detect_onsets(audio, sr, hop_length=512)
    sync = calculate_syncopation(onset_times, beat_times, onset_strengths)
    on_beat_ratio = calculate_on_beat_ratio(onset_times, beat_times)
    ibi = np.diff(beat_times)
    ibi_cv = float(ibi.std() / ibi.mean()) if len(ibi) > 1 and ibi.mean() > 0 else None
    bpm_est = 60.0 / np.median(ibi) if len(ibi) else None
    return {
        "n_beats": int(len(beat_times)),
        "n_onsets": int(len(onset_times)),
        "ibi_cv": ibi_cv,
        "bpm_est": float(bpm_est) if bpm_est else None,
        "syncopation": sync,
        "on_beat_ratio": float(on_beat_ratio),
    }


def main():
    results = {}
    for arm in ARMS:
        for ep in EPOCHS:
            fname = f"{arm}__ep{ep}__{CFG}__{W}__{PROMPT}__s1001.m4a"
            path = CLIPS_DIR / fname
            if not path.exists():
                print(f"[skip] missing {fname}")
                continue
            try:
                r = analyze_clip(path)
            except Exception as e:
                print(f"[fail] {fname}: {e}")
                continue
            r["arm"], r["ep"] = arm, ep
            results[f"{arm}__ep{ep}"] = r
            print(f"{arm} ep{ep}: ibi_cv={r['ibi_cv']:.4f} bpm~{r['bpm_est']:.1f} "
                  f"sync={r['syncopation']:.3f} on_beat={r['on_beat_ratio']:.3f} "
                  f"n_beats={r['n_beats']} n_onsets={r['n_onsets']}")

    out = Path(__file__).parent / "lr_granularity_beat_probe.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
