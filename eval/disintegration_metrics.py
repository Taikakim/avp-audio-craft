#!/usr/bin/env python
"""disintegration_metrics.py — the ONE home of the wav-side HF-blowout / disintegration screen.

Consumers: eval/ablate_adapter_layers2.py (layer-ablation screen -> disintegration_flags.json),
eval/eval_layer_restricted_arms.py (#56 authority+gate eval), and WINTERMUTE's eval-page badges
+ drift stat. Thresholds live HERE and nowhere else — the numbers are the wav-side subset of
control_head_disintegration_eval.THR (that script gates from clip_metrics.db, this one from wav).

Semantics: every flag needs BOTH an absolute floor (stops tiny-baseline ratios firing on
near-silence) AND a ratio vs a SAME-RECIPE unsteered baseline clip. DSP screen only — "clean"
means not-obviously-disintegrated, not musically good (the ear is the verdict).
"""
import numpy as np

# Provenance: calibrated on the 2026-07-20 goa/ambient LatCH-sweep gain-0 baselines, applied
# verbatim by the 2026-07-21 layer-ablation screen (ablate_layers2 disintegration_flags.json)
# and the #56 layer-restricted eval. Do not retune without rerunning both.
THR = {
    "flatness_abs": 0.05, "flatness_ratio": 2.5,   # whitening (droning/noise bed)
    "hf_abs": 0.05, "hf_ratio": 2.0,               # HF-blowout / static buzz
    "zcr_abs": 0.15, "zcr_ratio": 1.6,             # noise / ringing
}
SR, N_FFT, HF_CUTOFF_HZ = 22050, 2048, 6000.0


def measure(wav_path):
    """Per-clip DSP stats from a wav: onsets/s, mean spectral flatness, mean ZCR, and
    hf = fraction of STFT magnitude above 6 kHz (same quantity as clip_metrics.db hf_ratio)."""
    import librosa
    y, sr = librosa.load(str(wav_path), sr=SR, mono=True)
    S = np.abs(librosa.stft(y, n_fft=N_FFT))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    return {"onsets": len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr),
            "flatness": float(np.mean(librosa.feature.spectral_flatness(S=S))),
            "zcr": float(np.mean(librosa.feature.zero_crossing_rate(y))),
            "hf": float(S[freqs > HF_CUTOFF_HZ].sum() / S.sum())}


def gate(stats, baseline, thr=THR):
    """Flag one clip's measure() stats against its same-recipe unsteered baseline's stats.
    Returns {"blown": bool, "reasons": [str, ...]} — reason strings carry the offending values
    (format follows eval_layer_restricted_arms, the authority)."""
    r = []

    def ratio(k):
        return stats[k] / max(baseline[k], 1e-5)

    if stats["flatness"] > thr["flatness_abs"] and ratio("flatness") > thr["flatness_ratio"]:
        r.append(f"whitening({stats['flatness']:.3f})")
    if stats["hf"] > thr["hf_abs"] and ratio("hf") > thr["hf_ratio"]:
        r.append(f"hf-blowout({baseline['hf']:.4f}->{stats['hf']:.4f})")
    if stats["zcr"] > thr["zcr_abs"] and ratio("zcr") > thr["zcr_ratio"]:
        r.append(f"zcr({stats['zcr']:.3f})")
    return {"blown": bool(r), "reasons": r}
