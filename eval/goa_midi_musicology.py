#!/usr/bin/env python
"""goa_midi_musicology.py — musicological analysis of the MuScriptor Goa MIDIs
(Kim ask 2026-07-13: "run a musicological analysis for the extracted Goa midis...
look first if there's an established method for this, how to encode the structure").

Method survey result (established methods, adapted to NOISY auto-transcription):
  - Global features: the jSymbolic 2.2 / music21 feature-extraction tradition
    (pitch-class histograms, interval distributions, density) — implemented here as a
    small numpy subset rather than installing either (mir venv numpy 1.26 pin; the
    relevant features are trivial to compute and most jSymbolic features assume clean
    scores, which we do not have).
  - Key/mode: Krumhansl-Schmuckler profile correlation on the duration-weighted
    pitch-class histogram, extended with modal profiles (aeolian / phrygian /
    harmonic minor) because Goa lives in those modes.
  - Structure encoding: per-BAR feature vectors (duration-weighted chroma + register-
    band densities) -> cosine self-similarity matrix -> Foote checkerboard novelty
    segmentation + SSM lag profile for dominant loop length. Pattern discovery via
    bar-hashing (a practical stand-in for SIA/SIATEC translational-pattern discovery,
    which is exact-match brittle on noisy transcription; ostinato music makes the
    bar-hash inventory the right granularity anyway).
  - Melody: skyline extraction (highest sounding pitch on the 16th grid — the
    established MIDI melody heuristic), interval histogram + bigram entropy
    (cheap IDyOM-style information-content proxy).

Constraints from Kim: MuScriptor mixes up SOUNDS (GM program / channel labels are
unreliable) but pitches are OK and timings decent -> analysis ignores program/channel
semantics entirely; voices are segregated by REGISTER (bass < C3 <= mid < C5 <= lead),
which is pitch-derived and robust.

Time base: the source corpus's madmom BEATS_GRID (audio-domain truth), NOT MIDI tempo.
Bars are forced 4/4 (Goa is universally 4/4; madmom DOWNBEATS sometimes locks 3/4 on
trance — observed on the sample track — so downbeats only VOTE on bar phase, capped to
4-beat grouping).

Outputs (Mantu/sa3_lora_runs/muscriptor_goa_midis/musicology/):
  <track>.musicology.json   per-track features + structure
  corpus_summary.md         corpus-level distributions
  run_meta.json             manifest-v2 sidecar

Run:  /home/kim/Projects/mir/mir/bin/python eval/goa_midi_musicology.py [--limit N]
"""
import argparse
import io
import json
import math
from collections import Counter
from pathlib import Path

import mido
import numpy as np

MIDI_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/muscriptor_goa_midis")
CORPUS = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
OUT = MIDI_DIR / "musicology"

PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler major/minor profiles + modal variants (rotations of natural minor
# for phrygian; harmonic minor = minor profile with raised-7 emphasis swap).
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
# Phrygian: aeolian with the b2 promoted (swap the weights of scale degrees 2 and b2).
PHRYGIAN = KK_MINOR.copy(); PHRYGIAN[1], PHRYGIAN[2] = KK_MINOR[2], KK_MINOR[1]
# Harmonic minor: aeolian with the natural 7 promoted over b7.
HARM_MINOR = KK_MINOR.copy(); HARM_MINOR[11], HARM_MINOR[10] = KK_MINOR[10], KK_MINOR[11]
MODE_PROFILES = {"major": KK_MAJOR, "minor": KK_MINOR, "phrygian": PHRYGIAN,
                 "harmonic_minor": HARM_MINOR}

BASS_MAX = 48   # < C3
LEAD_MIN = 72   # >= C5


def load_notes(path):
    """(onset_s, end_s, pitch) list, all channels merged, tempo-map-aware."""
    m = mido.MidiFile(str(path))
    tempo = 500000
    notes, open_notes = [], {}
    for tr in m.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            sec = mido.tick2second(t, m.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
            elif msg.type == "note_on" and msg.velocity > 0:
                open_notes[(msg.channel, msg.note)] = sec
            elif msg.type in ("note_off", "note_on"):
                k = (msg.channel, msg.note)
                if k in open_notes:
                    notes.append((open_notes.pop(k), sec, msg.note))
    notes.sort()
    return notes


def load_grid(track_name):
    d = CORPUS / track_name
    beats_f = d / f"{track_name}.BEATS_GRID"
    down_f = d / f"{track_name}.DOWNBEATS"
    if not beats_f.exists():
        return None, None
    beats = np.array([float(x) for x in beats_f.read_text().split()])
    downs = (np.array([float(x) for x in down_f.read_text().split()])
             if down_f.exists() else None)
    return beats, downs


def beat_positions(onsets, beats):
    """Continuous beat index for each onset (linear interp; clipped to grid span)."""
    idx = np.interp(onsets, beats, np.arange(len(beats)))
    return idx


def pick_bar_phase(beats, downs):
    """Bar phase in [0,4): which beat index mod 4 is beat-1. Downbeats vote; forced 4/4."""
    if downs is None or len(downs) < 8:
        return 0
    db_beat = np.interp(downs, beats, np.arange(len(beats)))
    votes = Counter(int(round(b)) % 4 for b in db_beat)
    return votes.most_common(1)[0][0]


def key_estimate(pc_hist):
    best = None
    for mode, prof in MODE_PROFILES.items():
        for tonic in range(12):
            r = np.corrcoef(pc_hist, np.roll(prof, tonic))[0, 1]
            if best is None or r > best[2]:
                best = (tonic, mode, r)
    tonic, mode, r = best
    # also the plain major/minor call for cross-corpus comparability
    mm = max(((t, md, np.corrcoef(pc_hist, np.roll(p, t))[0, 1])
              for md, p in (("major", KK_MAJOR), ("minor", KK_MINOR)) for t in range(12)),
             key=lambda x: x[2])
    return {"tonic": PC_NAMES[tonic], "mode": mode, "corr": round(float(r), 3),
            "majmin_key": f"{PC_NAMES[mm[0]]} {mm[1]}", "majmin_corr": round(float(mm[2]), 3)}


def entropy(counter):
    tot = sum(counter.values())
    if tot == 0:
        return 0.0
    p = np.array(list(counter.values())) / tot
    return float(-(p * np.log2(p)).sum())


def foote_novelty(ssm, kw=8):
    """Checkerboard-kernel novelty curve over the SSM diagonal."""
    n = len(ssm)
    kernel = np.kron(np.array([[1, -1], [-1, 1]]), np.ones((kw, kw)))
    g = np.exp(-np.linspace(-2, 2, 2 * kw) ** 2)
    kernel *= np.outer(g, g)
    nov = np.zeros(n)
    for i in range(kw, n - kw):
        nov[i] = (ssm[i - kw:i + kw, i - kw:i + kw] * kernel).sum()
    return np.maximum(nov, 0)


def peak_pick(nov, min_dist=8):
    peaks = []
    thr = nov.mean() + nov.std()
    for i in range(1, len(nov) - 1):
        if nov[i] > thr and nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1]:
            if not peaks or i - peaks[-1] >= min_dist:
                peaks.append(i)
    return peaks


def analyze_track(mid_path):
    name = mid_path.stem
    notes = load_notes(mid_path)
    if len(notes) < 50:
        return {"track": name, "skip": "too few notes", "n_notes": len(notes)}
    beats, downs = load_grid(name)
    if beats is None or len(beats) < 32:
        return {"track": name, "skip": "no beat grid"}

    onsets = np.array([n[0] for n in notes])
    durs = np.array([max(n[1] - n[0], 1e-3) for n in notes])
    pitches = np.array([n[2] for n in notes])

    bpm = 60.0 / float(np.median(np.diff(beats)))
    bpos = beat_positions(onsets, beats)          # continuous beat index
    phase = pick_bar_phase(beats, downs)
    barpos = (bpos - phase) / 4.0                 # continuous bar index
    n_bars = int(math.ceil((len(beats) - phase) / 4.0))

    # --- grid deviation (transcription timing quality + microtiming) ---
    sixt = bpos * 4.0
    dev_beats = np.abs(sixt - np.round(sixt)) / 4.0          # in beats
    dev_ms = dev_beats * (60000.0 / bpm)
    sixt_in_bar = np.round(sixt).astype(int) - phase * 4
    pos16 = np.bincount(np.clip(sixt_in_bar % 16, 0, 15), minlength=16).astype(float)
    pos16 /= max(pos16.sum(), 1)
    offbeat_frac = float(pos16[np.arange(16) % 4 != 0].sum())  # not on the beat
    off8_frac = float(pos16[np.arange(16) % 4 == 2].sum())     # the offbeat 8th (Goa bass home)

    # --- global pitch features (duration-weighted) ---
    pc_hist = np.zeros(12)
    for p, d in zip(pitches, durs):
        pc_hist[p % 12] += d
    pc_hist /= max(pc_hist.sum(), 1e-9)
    key = key_estimate(pc_hist)
    tonic_idx = PC_NAMES.index(key["tonic"])
    in_scale = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
                "phrygian": [0, 1, 3, 5, 7, 8, 10], "harmonic_minor": [0, 2, 3, 5, 7, 8, 11]}[key["mode"]]
    scale_consistency = float(sum(pc_hist[(tonic_idx + s) % 12] for s in in_scale))

    # --- register bands ---
    band = np.where(pitches < BASS_MAX, 0, np.where(pitches < LEAD_MIN, 1, 2))
    bass_mask = band == 0
    bass_tonic_frac = (float((pitches[bass_mask] % 12 == tonic_idx).mean())
                       if bass_mask.sum() > 20 else None)

    # --- skyline melody (highest sounding pitch per 16th) ---
    n16 = n_bars * 16
    sky = np.full(n16, -1)
    for (s, e, p) in notes:
        i0 = int(np.floor((np.interp(s, beats, np.arange(len(beats))) - phase) * 4))
        i1 = int(np.ceil((np.interp(e, beats, np.arange(len(beats))) - phase) * 4))
        i0, i1 = max(i0, 0), min(max(i1, i0 + 1), n16)
        seg = sky[i0:i1]
        np.maximum(seg, p, out=seg)
    sky_notes = sky[sky >= 0]
    # melodic intervals: consecutive distinct skyline pitches
    changes = sky_notes[np.concatenate([[True], np.diff(sky_notes) != 0])]
    ivals = np.diff(changes)
    ival_hist = Counter(int(np.clip(v, -12, 12)) for v in ivals)
    stepwise_frac = (float(np.mean(np.abs(ivals) <= 2)) if len(ivals) else None)
    bigrams = Counter(zip(ivals[:-1].tolist(), ivals[1:].tolist()))
    melody_bigram_entropy = entropy(bigrams)

    # --- per-bar structure encoding: chroma(12) + band densities(3) ---
    bar_vec = np.zeros((n_bars, 15))
    bar_idx = np.clip(np.floor(barpos).astype(int), 0, n_bars - 1)
    for i, (p, d, b) in enumerate(zip(pitches, durs, band)):
        bi = bar_idx[i]
        bar_vec[bi, p % 12] += d
        bar_vec[bi, 12 + b] += 1
    # normalize chroma per bar; densities to notes/beat
    cn = np.linalg.norm(bar_vec[:, :12], axis=1, keepdims=True)
    bar_vec[:, :12] /= np.maximum(cn, 1e-9)
    bar_vec[:, 12:] /= 4.0
    active = bar_vec[:, 12:].sum(1) > 0.5          # bars with any real content

    v = bar_vec / np.maximum(np.linalg.norm(bar_vec, axis=1, keepdims=True), 1e-9)
    ssm = v @ v.T

    # lag profile -> dominant loop length in bars
    lags = {}
    for L in (1, 2, 4, 8, 16, 32):
        if n_bars > L + 4:
            lags[L] = round(float(np.mean(np.diag(ssm, L))), 3)
    loop_len = max(lags, key=lags.get) if lags else None

    nov = foote_novelty(ssm, kw=8)
    bounds = peak_pick(nov, min_dist=8)
    seg_edges = [0] + bounds + [n_bars]
    seg_lens = [b - a for a, b in zip(seg_edges[:-1], seg_edges[1:])]

    # --- bar-hash riff inventory per band (quantized 16th pos x pitch-class) ---
    riffs = {}
    for bname, bsel in (("bass", 0), ("mid", 1), ("lead", 2)):
        hashes = [[] for _ in range(n_bars)]
        sel = band == bsel
        for i in np.where(sel)[0]:
            bi = bar_idx[i]
            hashes[bi].append((int(sixt_in_bar[i] % 16), int(pitches[i] % 12)))
        keys_ = [tuple(sorted(set(h))) for h in hashes if len(h) >= 2]
        if len(keys_) < 8:
            riffs[bname] = None
            continue
        cnt = Counter(keys_)
        top, topn = cnt.most_common(1)[0]
        riffs[bname] = {"n_bars_active": len(keys_),
                        "n_distinct_patterns": len(cnt),
                        "top_pattern_coverage": round(topn / len(keys_), 3),
                        "pattern_entropy": round(entropy(cnt), 2)}

    span = float(onsets[-1] - onsets[0])
    return {
        "track": name, "n_notes": len(notes), "span_s": round(span, 1),
        "bpm": round(bpm, 1), "n_bars": n_bars, "bar_phase_vote": phase,
        "key": key, "scale_consistency": round(scale_consistency, 3),
        "pc_hist": [round(float(x), 4) for x in pc_hist],
        "pitch": {"median": int(np.median(pitches)), "range": int(pitches.max() - pitches.min()),
                  "band_frac": [round(float((band == i).mean()), 3) for i in range(3)]},
        "bass_tonic_frac": (round(bass_tonic_frac, 3) if bass_tonic_frac is not None else None),
        "rhythm": {"grid_dev_median_ms": round(float(np.median(dev_ms)), 1),
                   "offbeat_frac": round(offbeat_frac, 3),
                   "offbeat8_frac": round(off8_frac, 3),
                   "notes_per_beat": round(len(notes) / max(len(beats), 1), 2),
                   "pos16_hist": [round(float(x), 4) for x in pos16]},
        "melody": {"stepwise_frac": (round(stepwise_frac, 3) if stepwise_frac is not None else None),
                   "bigram_entropy_bits": round(melody_bigram_entropy, 2),
                   "top_intervals": dict(sorted(ival_hist.items(), key=lambda kv: -kv[1])[:5])},
        "structure": {"lag_profile": lags, "dominant_loop_bars": loop_len,
                      "n_sections": len(seg_lens), "section_lens_bars": seg_lens,
                      "active_bar_frac": round(float(active.mean()), 3)},
        "riffs": riffs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    mids = sorted(MIDI_DIR.glob("*.mid"))
    if args.limit:
        mids = mids[:args.limit]
    results = []
    for i, mp in enumerate(mids):
        outp = OUT / f"{mp.stem}.musicology.json"
        if outp.exists():
            results.append(json.loads(outp.read_text()))
            continue
        try:
            r = analyze_track(mp)
        except Exception as e:
            r = {"track": mp.stem, "skip": f"{type(e).__name__}: {str(e)[:120]}"}
        outp.write_text(json.dumps(r, indent=1))
        results.append(r)
        tag = r.get("skip") or (f"{r['bpm']}bpm {r['key']['tonic']} {r['key']['mode']} "
                                f"loop{r['structure']['dominant_loop_bars']} "
                                f"riff-cov {r['riffs']['bass']['top_pattern_coverage'] if r['riffs'].get('bass') else '-'}")
        print(f"[{i+1}/{len(mids)}] {mp.stem[:50]}: {tag}", flush=True)

    ok = [r for r in results if "skip" not in r]
    print(f"\n[corpus] {len(ok)}/{len(results)} analyzed")
    if not ok:
        return

    def dist(vals, fmt="{:.2f}"):
        v = np.array([x for x in vals if x is not None], dtype=float)
        if not len(v):
            return "n/a"
        return (fmt + " median (" + fmt + "-" + fmt + " IQR)").format(
            np.median(v), np.quantile(v, .25), np.quantile(v, .75))

    keys = Counter(f"{r['key']['tonic']} {r['key']['mode']}" for r in ok)
    modes = Counter(r["key"]["mode"] for r in ok)
    loops = Counter(r["structure"]["dominant_loop_bars"] for r in ok)
    lines = [
        "# Goa MIDI musicology — corpus summary",
        f"\n{len(ok)} tracks (5% seeded sample of Goa_Separated, MuScriptor medium transcription).",
        "Pitch+onset analysis only; GM program/channel labels ignored (unreliable);",
        "voices segregated by register (bass < C3 <= mid < C5 <= lead); time base =",
        "madmom BEATS_GRID from the source audio; bars forced 4/4.\n",
        f"- **BPM**: {dist([r['bpm'] for r in ok], '{:.0f}')}",
        f"- **Mode distribution**: " + ", ".join(f"{m} {c}" for m, c in modes.most_common()),
        f"- **Top keys**: " + ", ".join(f"{k} ({c})" for k, c in keys.most_common(8)),
        f"- **Key-profile corr**: {dist([r['key']['corr'] for r in ok])} | scale consistency {dist([r['scale_consistency'] for r in ok])}",
        f"- **Bass-on-tonic fraction**: {dist([r['bass_tonic_frac'] for r in ok])}",
        f"- **Grid deviation**: {dist([r['rhythm']['grid_dev_median_ms'] for r in ok], '{:.0f}')} ms (transcription+microtiming)",
        f"- **Offbeat-8th onset share**: {dist([r['rhythm']['offbeat8_frac'] for r in ok])}",
        f"- **Melody stepwise fraction**: {dist([r['melody']['stepwise_frac'] for r in ok])} | bigram entropy {dist([r['melody']['bigram_entropy_bits'] for r in ok])} bits",
        f"- **Dominant loop length (bars)**: " + ", ".join(f"{k}: {c}" for k, c in sorted(loops.items(), key=lambda kv: -kv[1])),
        f"- **Sections per track**: {dist([r['structure']['n_sections'] for r in ok], '{:.0f}')}",
        f"- **Bass riff: top-pattern coverage** {dist([r['riffs']['bass']['top_pattern_coverage'] for r in ok if r['riffs'].get('bass')])}"
        f" | distinct patterns {dist([r['riffs']['bass']['n_distinct_patterns'] for r in ok if r['riffs'].get('bass')], '{:.0f}')}",
        f"- **Lead riff: top-pattern coverage** {dist([r['riffs']['lead']['top_pattern_coverage'] for r in ok if r['riffs'].get('lead')])}",
    ]
    (OUT / "corpus_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
