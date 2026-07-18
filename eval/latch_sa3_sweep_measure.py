#!/usr/bin/env python3
"""latch_sa3_sweep_measure.py — measure achieved LatCH target features on the
rendered sweep clips (stage 2/3, see latch_sa3_sweep_render.py's docstring).

Reuses the SAME raw-feature extractors the training targets were built from
(mir/src/spectral/*), so requested-vs-measured is apples-to-apples — the same
discipline onset_eval.py uses for onset density. Per clip: extract the
per-frame feature timeseries, take its mean (the constant-target kind
broadcasts one scalar to every frame, so the mean is the correct comparison
point), write {measured, delta = measured-target} into scores.json.

Heads flagged measurable=False (onset_envelope_drums, rms_drums) need a
separated drum stem the rendered mix doesn't have — clip is scored None,
not faked.

Run (mir venv, CPU):
  /home/kim/Projects/mir/mir/bin/python eval/latch_sa3_sweep_measure.py
"""
import json
import os
import sys

sys.path.insert(0, "/home/kim/Projects/mir/src")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np
from core.file_utils import read_audio
from spectral.timeseries_features import _compute_multiband_rms_ts, _compute_spectral_ts

OUT_DIR = "/run/media/kim/Mantu/sa3_control_runs/latch_sa3_sweep_20260719"
MANIFEST = os.path.join(OUT_DIR, "latch_sweep_manifest.json")
SCORES = os.path.join(OUT_DIR, "scores.json")

FRAME_RATE = 100

_RMS_KEYS = {"rms_energy_bass": "rms_energy_bass_ts", "rms_energy_body": "rms_energy_body_ts",
            "rms_energy_mid": "rms_energy_mid_ts", "rms_energy_air": "rms_energy_air_ts"}
_SPEC_KEYS = {"spectral_flatness": "spectral_flatness_ts", "spectral_flux": "spectral_flux_ts",
             "spectral_kurtosis": "spectral_kurtosis_ts", "spectral_skewness": "spectral_skewness_ts"}


def measure(feature: str, audio: np.ndarray, sr: int) -> float | None:
    hop = round(sr / FRAME_RATE)
    n_frames = round(len(audio) / sr * FRAME_RATE)
    if feature in _RMS_KEYS:
        d = _compute_multiband_rms_ts(audio, sr, n_frames)
        return float(np.mean(d[_RMS_KEYS[feature]]))
    if feature in _SPEC_KEYS:
        d = _compute_spectral_ts(audio, sr, n_frames, hop_length=hop)
        return float(np.mean(d[_SPEC_KEYS[feature]]))
    if feature == "onset_envelope":
        import librosa
        oe = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop)
        return float(np.mean(oe))
    return None  # hardness / beat_activation / downbeat_activation: handled in main()
                 # (need a file path or shared madmom processor instances, not just the array)


def main():
    manifest = json.load(open(MANIFEST))
    scores = json.load(open(SCORES)) if os.path.exists(SCORES) else {}

    from spectral.whole_track_timeseries import make_madmom_processors, _madmom_activations
    beat_proc, downbeat_proc = None, None

    for c in manifest["cells"]:
        clip = c["clip"]
        if clip in scores:
            continue
        path = os.path.join(OUT_DIR, clip)
        if not os.path.exists(path):
            continue
        feat = c["head"]
        if feat == "baseline":
            scores[clip] = {"measured": None, "note": "baseline (no guidance target)"}
            continue
        if c.get("measurable") is False:
            scores[clip] = {"measured": None, "note": "needs stem separation — not measured"}
            continue
        audio, sr = read_audio(path)
        mono = audio.mean(axis=1).astype(np.float32) if audio.ndim > 1 else audio.astype(np.float32)

        if feat in ("beat_activation", "downbeat_activation"):
            if beat_proc is None:
                beat_proc, downbeat_proc = make_madmom_processors()
            n_frames = round(len(mono) / sr * FRAME_RATE)
            acts = _madmom_activations(path, n_frames, beat_proc, downbeat_proc)
            key = "beat_activation_ts" if feat == "beat_activation" else "downbeat_activation_ts"
            m = float(np.mean(acts[key])) if key in acts else None
        elif feat == "hardness":
            from timbral.audio_commons import analyze_hardness
            m = float(analyze_hardness(path))
        else:
            m = measure(feat, mono, sr)

        target = c.get("target")
        scores[clip] = {"measured": m, "delta": (m - target) if (m is not None and target is not None) else None}
        print(f"{clip}: target={target} measured={m}")
        json.dump(scores, open(SCORES, "w"), indent=1)

    print(f"[measure] {len(scores)}/{len(manifest['cells'])} clips scored -> {SCORES}")


if __name__ == "__main__":
    sys.exit(main())
