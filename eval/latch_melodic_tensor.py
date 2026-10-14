#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_melodic_tensor.py -- ONE tensor per clip that carries both the transcribed notes and the chroma colour, and a similarity on it. CPU only.

WHY (Kim 2026-10-14: "a melodic similarity meter that combines some even cheap polyphonic transcription and chroma colour into one tensor").
Per clip -> M of shape (T, 36) on the SA3 latent grid (10.766 Hz), built from two blocks that fail in different ways:
  [0:24]  NOTES  : Basic Pitch frame posteriors (polyphonic, cheap; sharpened: values <0.3 zeroed, because the raw posteriors leak into neighbouring
                   semitones and made a 1-semitone shift look 0.89 similar), folded to 12 pitch classes in TWO register bands (bass MIDI <48, mid 48-71).
                   The HIGH band (>=72) is dropped on purpose (Kim 2026-10-14: bass + mid chroma alone predict the melody well enough).
  [24:36] COLOUR : audio chroma (librosa chroma_cqt over C2..B4 only, i.e. the same bass+mid range), centred per frame: broadband/percussive sound has a FLAT
                   chroma that is identical across clips, so uncentred it scored 1.0 against anything; centred, flat -> zero -> counted as silent.
Each block is L2-normalised per frame, then the two are concatenated / sqrt(2), so the cosine of two M-frames is the AVERAGE of the block cosines.
A block that is silent in BOTH clips (no notes / no tonal energy) is excluded from the average rather than counted as agreement.
similarity(A, B) returns {"notes","colour","combined"}: mean over frames of the per-frame cosine (notes block / colour block / whole tensor).

USE: from latch_melodic_tensor import tensor, similarity ;  or CLI on a pairs manifest (same format as latch_drift_check):
    /home/kim/Projects/mir/mir/bin/python eval/latch_melodic_tensor.py --manifest pairs.json [--save-dir DIR]
Run under the MIR venv (basic_pitch + librosa). STATUS: calibrated on synthetic controls only -- see tests/test_latch_melodic_tensor.py; the weights are
NOT tuned on real renders, and the threshold is deliberately absent until a real same-seed vs different-seed gap is measured.
"""
import argparse
import json
import sys

import numpy as np

GRID_HZ = 44100 / 4096                                     # 10.766 Hz, the SA3 latent grid
BANDS = ((0, 48), (48, 72))                              # bass, mid; the high band is deliberately not used


def _resample_rows(x, n):                                  # x: (frames, d) -> (n, d), linear in time
    src = np.linspace(0, 1, len(x))
    dst = np.linspace(0, 1, n)
    return np.stack([np.interp(dst, src, x[:, c]) for c in range(x.shape[1])], 1)


def _unit(x):
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9), np.linalg.norm(x, axis=1)


def tensor(path, sr=22050):
    import librosa
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    y, _ = librosa.load(path, sr=sr, mono=True)
    n = max(2, int(len(y) / sr * GRID_HZ))
    out, _, _ = predict(path, str(ICASSP_2022_MODEL_PATH.parent / "nmp.onnx"))
    note = out["note"] if isinstance(out, dict) else out[0]   # (frames, 88), MIDI 21..108
    note = np.where(note > 0.3, note, 0.0)
    fold = np.zeros((len(note), 12 * len(BANDS)))
    for k in range(note.shape[1]):
        midi = 21 + k
        b = next((i for i, (lo, hi) in enumerate(BANDS) if lo <= midi < hi), None)
        if b is not None:
            fold[:, b * 12 + midi % 12] += note[:, k]
    notes = _resample_rows(fold, n)
    c = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=256, fmin=librosa.note_to_hz('C2'), n_octaves=3).T
    chroma = _resample_rows(c - c.mean(1, keepdims=True), n)
    return {"notes": notes, "colour": chroma}


def similarity(a, b, silence=1e-2):
    n = min(len(a["notes"]), len(b["notes"]))
    res, used = {}, {}
    for k in ("notes", "colour"):
        ua, na = _unit(a[k][:n])
        ub, nb = _unit(b[k][:n])
        live = (na > silence) | (nb > silence)             # exclude frames where BOTH are silent in this block
        cos = (ua * ub).sum(1)
        res[k] = float(cos[live].mean()) if live.any() else float("nan")
        used[k] = (cos, live)
    both = np.stack([used["notes"][0], used["colour"][0]])
    liv = np.stack([used["notes"][1], used["colour"][1]])
    res["combined"] = float((both * liv).sum() / max(liv.sum(), 1))   # = mean of the live block cosines (each block unit-normalised, concat / sqrt 2)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--save-dir", default=None, help="also write each clip's (T,48) tensor as .npy")
    a = ap.parse_args()
    pairs = json.load(open(a.manifest))
    T = [(tensor(p["base"]), tensor(p["steered"])) for p in pairs]
    print(f"{'id':16s} {'notes':>6s} {'colour':>7s} {'combined':>9s} | unrelated (mean over other rows): notes colour combined")
    for i, p in enumerate(pairs):
        s = similarity(*T[i])
        u = [similarity(T[i][0], T[j][1]) for j in range(len(pairs)) if j != i]
        um = {k: float(np.nanmean([x[k] for x in u])) for k in s} if u else None
        print(f"{p['id']:16s} {s['notes']:6.2f} {s['colour']:7.2f} {s['combined']:9.2f} | " + (f"{um['notes']:6.2f} {um['colour']:6.2f} {um['combined']:6.2f}" if um else "(need >=2 pairs)"))
        if a.save_dir:
            import os
            os.makedirs(a.save_dir, exist_ok=True)
            for nm, tt in (("base", T[i][0]), ("steered", T[i][1])):
                np.save(os.path.join(a.save_dir, f"{p['id']}__{nm}.npy"), np.concatenate([tt["notes"], tt["colour"]], 1).astype(np.float32))


if __name__ == "__main__":
    sys.exit(main())
