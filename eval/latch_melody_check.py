#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_melody_check.py -- did the NOTES survive the steer? Transcribe base and steered with Basic Pitch and compare the note events. CPU only.

WHY (Kim 2026-10-14): a good steer (grainy thin render fixed with the bass/mid heads) changes timbre, dynamics and balance but must keep the melodies; and
"the ultimate test would be Muscriptor or even cheaper Basic Pitch tests about the melodic content". Chroma similarity could not separate 'same notes, EQ'd'
from 'different notes' (latch_drift_check.py), and chroma is also what CLAUDE.md records failing to see a real transcription effect (2026-08-28, MuScriptor
+0.100 where chroma cosine read +0.022). This compares NOTES.

INPUT: manifest JSON, a list of {"id","base","steered"} (same seed/prompt, gain 0 vs steered). For each pair:
  note_f1     mir_eval onset-only note F1 (pitch exact within 50 cents, onset within +-50 ms) -- 'same notes at the same times'
  pc_f1       the same after folding pitches to pitch class -- tolerant of octave moves
  pc_hist_cos duration-weighted pitch-class histogram cosine -- 'same melodic colour', timing-free
  n_base / n_steered  note counts (a steer that adds 3x the notes is not 'the same melody')
CONTROL BUILT IN: every base is also scored against the steered clip of a DIFFERENT row ('unrelated' column). Read the gap between the matched and the
unrelated numbers; with one row there is no unrelated control and the tool says so. Not flagged by an invented threshold -- thresholds come from that gap.

RUN (mir venv has basic_pitch + mir_eval; the SAO venvs do not):
    /home/kim/Projects/mir/mir/bin/python eval/latch_melody_check.py --manifest pairs.json [--out melody.json]
Basic Pitch note: the default model path fails in this install; the ONNX file is passed explicitly.
"""
import argparse
import json
import sys

import numpy as np


def transcribe(path):
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    _, _, ev = predict(path, str(ICASSP_2022_MODEL_PATH.parent / "nmp.onnx"))
    if not ev:
        return np.zeros((0, 2)), np.zeros(0)
    a = np.array([(s, e, p) for s, e, p, *_ in ev], dtype=float)
    return a[:, :2], a[:, 2]


def _hz(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=float) - 69) / 12)


def pc_hist(iv, pit):
    h = np.zeros(12)
    for (s, e), p in zip(iv, pit):
        h[int(round(p)) % 12] += max(e - s, 1e-3)
    return h


def compare_notes(a, b):
    import mir_eval
    (iva, pa), (ivb, pb) = a, b
    if len(pa) == 0 or len(pb) == 0:
        return {"note_f1": 0.0, "pc_f1": 0.0, "pc_hist_cos": 0.0}
    f1 = mir_eval.transcription.precision_recall_f1_overlap(iva, _hz(pa), ivb, _hz(pb), offset_ratio=None)[2]
    fold = lambda p: _hz(60 + (np.round(p).astype(int) % 12))                     # noqa: E731
    f1pc = mir_eval.transcription.precision_recall_f1_overlap(iva, fold(pa), ivb, fold(pb), offset_ratio=None)[2]
    ha, hb = pc_hist(iva, pa), pc_hist(ivb, pb)
    cos = float(ha @ hb / (np.linalg.norm(ha) * np.linalg.norm(hb) + 1e-12))
    return {"note_f1": float(f1), "pc_f1": float(f1pc), "pc_hist_cos": cos}


def run(pairs):
    T = [(transcribe(p["base"]), transcribe(p["steered"])) for p in pairs]
    rows = []
    for i, p in enumerate(pairs):
        m = compare_notes(T[i][0], T[i][1])
        r = {"id": p["id"], "n_base": int(len(T[i][0][1])), "n_steered": int(len(T[i][1][1])), "matched": m}
        if len(pairs) > 1:
            others = [compare_notes(T[i][0], T[j][1]) for j in range(len(pairs)) if j != i]
            r["unrelated"] = {k: float(np.mean([o[k] for o in others])) for k in m}
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = run(json.load(open(a.manifest)))
    print(f"{'id':16s} {'notes b/s':>10s} | matched: {'note_f1':>7s} {'pc_f1':>6s} {'pc_cos':>6s} | unrelated: {'note_f1':>7s} {'pc_f1':>6s} {'pc_cos':>6s}")
    for r in rows:
        m, u = r["matched"], r.get("unrelated")
        ut = f"{u['note_f1']:7.2f} {u['pc_f1']:6.2f} {u['pc_hist_cos']:6.2f}" if u else "   (need >=2 pairs for the control)"
        print(f"{r['id']:16s} {r['n_base']:>4d}/{r['n_steered']:<5d} |          {m['note_f1']:7.2f} {m['pc_f1']:6.2f} {m['pc_hist_cos']:6.2f} |            {ut}")
    if a.out:
        json.dump(rows, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
