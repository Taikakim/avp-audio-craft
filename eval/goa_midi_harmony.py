#!/usr/bin/env python
"""goa_midi_harmony.py — second analysis pass over the MuScriptor Goa MIDIs
(Kim 2026-07-13: "how the bass centers vs leads/voices in the higher registers,
and the role of (implied) harmony").

Adds to goa_midi_musicology.py (which must have run first — reads its per-track
JSONs for the key estimates):
  1. Register-band tonal profiles: duration-weighted pitch-class histograms per
     band (bass < C3 <= mid < C5 <= lead), rotated to SCALE-DEGREE space relative
     to the v1 tonic — where does the bass sit vs where do the upper voices sit.
  2. Implied harmony: per-bar duration-weighted chroma -> chord-template matching
     (Fujishima/Harte chroma-template tradition, symbolic version). Templates:
     power(0,7) / major / minor / sus2 / sus4 / dim, scored as
     mean(chroma at template PCs) - mean(chroma elsewhere) so 2-note and 3-note
     templates compete fairly. From the per-bar chord stream: quality histogram,
     implied-root degree distribution, harmonic rhythm (bars per root change),
     root-movement intervals, and bass agreement (implied root == dominant bass PC).

Caveat carried into the outputs: this is implied harmony read off a NOISY
transcription of texture-heavy music — coarse by construction, corpus-level
distributions are the trustworthy layer, single-bar chord calls are not.

Output: musicology/harmony_corpus.json (per-track rows + corpus aggregates).
Run:  /home/kim/Projects/mir/mir/bin/python eval/goa_midi_harmony.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goa_midi_musicology as v1  # noqa: E402  (loaders + constants)

OUT = v1.OUT
DEGREES = ["1", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"]
TEMPLATES = {
    "power": (0, 7),
    "minor": (0, 3, 7),
    "major": (0, 4, 7),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "dim": (0, 3, 6),
}


def chord_match(chroma):
    """Best (root_pc, quality, score) for a sum-normalized 12-d chroma."""
    best = None
    for qual, tpl in TEMPLATES.items():
        for root in range(12):
            pcs = [(root + t) % 12 for t in tpl]
            inside = chroma[pcs].mean()
            rest = np.delete(chroma, pcs).mean()
            s = inside - rest
            if best is None or s > best[2]:
                best = (root, qual, s)
    return best


def analyze(mid_path, tonic_idx):
    notes = v1.load_notes(mid_path)
    beats, downs = v1.load_grid(mid_path.stem)
    onsets = np.array([n[0] for n in notes])
    durs = np.array([max(n[1] - n[0], 1e-3) for n in notes])
    pitches = np.array([n[2] for n in notes])
    bpos = v1.beat_positions(onsets, beats)
    phase = v1.pick_bar_phase(beats, downs)
    n_bars = int(np.ceil((len(beats) - phase) / 4.0))
    bar_idx = np.clip(np.floor((bpos - phase) / 4.0).astype(int), 0, n_bars - 1)
    band = np.where(pitches < v1.BASS_MAX, 0, np.where(pitches < v1.LEAD_MIN, 1, 2))

    # --- 1. per-band degree profiles (duration-weighted, rotated to tonic) ---
    band_deg = np.zeros((3, 12))
    for p, d, b in zip(pitches, durs, band):
        band_deg[b, (p - tonic_idx) % 12] += d
    band_deg /= np.maximum(band_deg.sum(axis=1, keepdims=True), 1e-9)
    band_center = [int(np.argmax(band_deg[b])) for b in range(3)]
    band_tonic = [round(float(band_deg[b, 0]), 3) for b in range(3)]

    # --- 2. per-bar chroma + dominant bass PC -> implied chord stream ---
    bar_chroma = np.zeros((n_bars, 12))
    bar_bass = np.zeros((n_bars, 12))
    bar_n = np.zeros(n_bars)
    for i, (p, d, b) in enumerate(zip(pitches, durs, band)):
        bi = bar_idx[i]
        bar_chroma[bi, p % 12] += d
        bar_n[bi] += 1
        if b == 0:
            bar_bass[bi, p % 12] += d
    chords = []  # (bar, root_pc, quality, score) for confident bars only
    for bi in range(n_bars):
        if bar_n[bi] < 3:
            continue
        c = bar_chroma[bi] / bar_chroma[bi].sum()
        root, qual, s = chord_match(c)
        if s > 0.02:
            chords.append((bi, root, qual, s))
    if len(chords) < 16:
        return {"track": mid_path.stem, "skip": "too few confident bars"}

    quals = Counter(q for _, _, q, _ in chords)
    root_deg = Counter((r - tonic_idx) % 12 for _, r, _, _ in chords)
    # harmonic rhythm: consecutive-confident-bar runs of the same root
    runs, cur = [], 1
    for (b0, r0, _, _), (b1, r1, _, _) in zip(chords[:-1], chords[1:]):
        if r1 == r0 and b1 == b0 + 1:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    # root movements between successive distinct roots (adjacent bars only)
    moves = Counter((r1 - r0) % 12 for (b0, r0, _, _), (b1, r1, _, _)
                    in zip(chords[:-1], chords[1:]) if b1 == b0 + 1 and r1 != r0)
    # bass agreement
    agree = [int(np.argmax(bar_bass[b])) == r for b, r, _, _ in chords if bar_bass[b].sum() > 0]
    n_conf = len(chords)
    return {
        "track": mid_path.stem,
        "band_degree_profile": [[round(float(x), 4) for x in row] for row in band_deg],
        "band_center_degree": [DEGREES[d] for d in band_center],
        "band_tonic_frac": band_tonic,
        "chord_quality": {k: round(v / n_conf, 3) for k, v in quals.items()},
        "root_degree": {DEGREES[k]: round(v / n_conf, 3) for k, v in root_deg.items()},
        "bars_per_root_median": float(np.median(runs)),
        "root_change_frac": round(len(runs) / n_conf, 3),
        "root_moves": {DEGREES[k]: v for k, v in moves.most_common(6)},
        "bass_agreement": (round(float(np.mean(agree)), 3) if agree else None),
        "n_confident_bars": n_conf,
    }


def main():
    rows = []
    v1_jsons = sorted(OUT.glob("*.musicology.json"))
    for i, jp in enumerate(v1_jsons):
        meta = json.loads(jp.read_text())
        if "skip" in meta:
            continue
        tonic_idx = v1.PC_NAMES.index(meta["key"]["tonic"])
        mp = v1.MIDI_DIR / f"{meta['track']}.mid"
        try:
            r = analyze(mp, tonic_idx)
        except Exception as e:
            r = {"track": meta["track"], "skip": f"{type(e).__name__}: {str(e)[:100]}"}
        r["key"] = meta["key"]
        rows.append(r)
        if (i + 1) % 25 == 0:
            print(f"[{i+1}/{len(v1_jsons)}]", flush=True)

    ok = [r for r in rows if "skip" not in r]
    prof = np.array([r["band_degree_profile"] for r in ok])   # (n, 3, 12)
    qual_agg = Counter()
    root_agg = Counter()
    move_agg = Counter()
    for r in ok:
        for k, v in r["chord_quality"].items():
            qual_agg[k] += v
        for k, v in r["root_degree"].items():
            root_agg[k] += v
        for k, v in r["root_moves"].items():
            move_agg[k] += v
    n = len(ok)
    agg = {
        "n_tracks": n,
        "band_degree_profile_mean": [[round(float(x), 4) for x in row] for row in prof.mean(0)],
        "band_center_dist": [dict(Counter(r["band_center_degree"][b] for r in ok).most_common())
                             for b in range(3)],
        "band_tonic_frac_median": [round(float(np.median([r["band_tonic_frac"][b] for r in ok])), 3)
                                   for b in range(3)],
        "chord_quality_mean": {k: round(v / n, 3) for k, v in qual_agg.most_common()},
        "root_degree_mean": {k: round(v / n, 3) for k, v in root_agg.most_common()},
        "root_moves_total": dict(move_agg.most_common(10)),
        "bars_per_root_median": round(float(np.median([r["bars_per_root_median"] for r in ok])), 1),
        "bass_agreement_median": round(float(np.median(
            [r["bass_agreement"] for r in ok if r["bass_agreement"] is not None])), 3),
    }
    (OUT / "harmony_corpus.json").write_text(json.dumps({"aggregate": agg, "tracks": rows}, indent=1))
    print(json.dumps(agg, indent=1))


if __name__ == "__main__":
    main()
