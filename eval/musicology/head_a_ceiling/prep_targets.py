#!/usr/bin/env python
"""prep_targets.py — melodies.jsonl -> per-frame contour class targets at SAME rate.

Head A ceiling study (spec docs/superpowers/specs/2026-07-22-melodic-latch-film.md
S0/S8). Binding rules honored:
  * supervision by TIME-OVERLAP of notes with each ~93 ms SAME frame (never
    note-index); soft overlap weights at boundary frames (v2: boundary frames
    are linear superpositions).
  * REST is a real class (LDA 0.995).
  * class set = spec S0 {rest, pedal, +-1, +-2, +-3, +-5, +-7, +-12}. Spec calls
    this "11 classes"; enumerated with direction FOLDED it is 8 labels
    (rest, pedal, |1|,|2|,|3|,|5|,|7|,|12|) — we implement the folded-8 as the
    primary target ("the 11-class set, direction folded" per tasking) and a
    directional 14-label variant (rest, pedal, +-{1,2,3,5,7,12}) as secondary.

Timing reconstruction: melodies.jsonl stores refined bpm/step + slot indices but
NOT the kick-derived grid phase (up to ~0.4 s = ~4 SAME frames) and NOT note
durations. Both are recovered from the source MIDI
(muscriptor_full/{id}.mid, same pipeline as phase1_features.py): phase =
hook_metric.grid_phase(kick onsets, beat), duration = the skyline-winning
note's MIDI end (clipped to the next lead onset; fallback = one 16th step).

Run: /home/kim/Projects/mir/mir/bin/python prep_targets.py [--workers N] [--limit N]
Outputs: targets/<id>.npz {y8 (4096,8) f16, y14 (4096,14) f16}, prep_summary.json
"""
import argparse, json, os, sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
MUS = os.path.dirname(HERE)                      # eval/musicology
sys.path.insert(0, MUS)
import hook_metric as HM

MELODIES = os.path.join(MUS, 'melodies.jsonl')
MIDI_DIR = '/run/media/kim/Kosmos/muscriptor_full'
LATENTS = '/home/kim/Projects/latents_sa3'
TARGETS = os.path.join(HERE, 'targets')

N_FRAMES = 4096
FRAME_DUR = 4096.0 / 44100.0        # SAME latent frame = 0.0928798 s (10.7666 Hz)
LEAD_PITCH_MIN = 56

FOLD_NAMES = ['rest', 'pedal', 'm1', 'm2', 'm3', 'm5', 'm7', 'm12']
DIR_NAMES = ['rest', 'pedal', '+1', '-1', '+2', '-2', '+3', '-3',
             '+5', '-5', '+7', '-7', '+12', '-12']
ALLOWED = [1, 2, 3, 5, 7, 12]
# nearest allowed magnitude, ties -> smaller: 4->3, 6->5, 8->7, 9->7, 10->12, 11->12
_MAG_MAP = {}
for a in range(1, 128):
    aa = min(a, 12)
    best = min(ALLOWED, key=lambda m: (abs(aa - m), m))
    _MAG_MAP[a] = best


def classes_of_row(row):
    """Per-note (folded, directional) class ids from melodies.jsonl row.
    Phrase-first notes have no incoming move -> pedal (a sounding note, no
    motion), matching the contour-tier semantics (intervals live inside
    phrases)."""
    pitches = row['pitches']
    bounds = row['phrase_bounds']
    n = len(pitches)
    fold = np.ones(n, np.int8)      # default pedal
    dirc = np.ones(n, np.int8)
    for bi in range(len(bounds) - 1):
        a, b = bounds[bi], bounds[bi + 1]
        for i in range(a + 1, b):
            d = pitches[i] - pitches[i - 1]
            if d == 0:
                continue
            mag = _MAG_MAP[abs(d)]
            fold[i] = 2 + ALLOWED.index(mag)
            dirc[i] = 2 + 2 * ALLOWED.index(mag) + (0 if d > 0 else 1)
    return fold, dirc


def _load_notes(fid):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(os.path.join(MIDI_DIR, fid + '.mid'))
    return HM.notes_from_pretty_midi(pm)


def process_one(row):
    fid = row['id']
    step = row['step']
    beat = step * 4.0
    slots = np.asarray(row['slots'], np.int64)
    pitches = np.asarray(row['pitches'], np.int64)
    fold, dirc = classes_of_row(row)

    phase = 0.0
    match_frac = 0.0
    ends = None
    try:
        notes = _load_notes(fid)
        kick = [n[0] for n in notes if n[4] and n[2] in (35, 36)]
        if len(kick) >= 16:
            phase = HM.grid_phase(kick, beat)
        # bass pick (phase1) to exclude bass from the lead skyline
        by_track = {}
        for n in notes:
            if not n[4]:
                by_track.setdefault(n[5], []).append(n)
        tracks = sorted(by_track)
        def bass_score(ns):
            ps = np.array([n[2] for n in ns])
            if np.median(ps) > 50:
                return -1.0
            return len(ps) * float(np.mean(ps <= 55))
        scores = [bass_score(by_track[t]) for t in tracks]
        bi = int(np.argmax(scores)) if tracks else -1
        has_bass = bool(tracks) and scores[bi] > 0
        other = [t for j, t in enumerate(tracks) if not has_bass or j != bi]
        # skyline slot -> (pitch, end)
        sky = {}
        for t in other:
            for (s0, e0, p, v, _d, _t) in by_track[t]:
                if p < LEAD_PITCH_MIN:
                    continue
                s = int(round((s0 - phase) / step))
                if s < 0:
                    continue
                cur = sky.get(s)
                if cur is None or p > cur[0]:
                    sky[s] = (p, e0)
        # match against the authoritative row stream; collect durations
        ends = np.full(len(slots), np.nan)
        hit = 0
        for i, (s, p) in enumerate(zip(slots, pitches)):
            c = sky.get(int(s))
            if c is not None and c[0] == p:
                hit += 1
                ends[i] = c[1]
        match_frac = hit / max(1, len(slots))
        if match_frac < 0.5:
            ends = None     # phase suspect -> fall back to phase 0 + step durs
            phase = 0.0
    except Exception:
        pass

    on = phase + slots * step
    if ends is None:
        off = on + step
    else:
        off = np.where(np.isnan(ends), on + step, ends)
    off = np.maximum(off, on + 0.25 * step)
    # monophonic stream: clip each note at the next lead onset
    off[:-1] = np.minimum(off[:-1], on[1:])

    y8 = np.zeros((N_FRAMES, len(FOLD_NAMES)), np.float32)
    y14 = np.zeros((N_FRAMES, len(DIR_NAMES)), np.float32)
    f0 = np.clip(np.floor(on / FRAME_DUR).astype(np.int64), 0, N_FRAMES)
    f1 = np.clip(np.ceil(off / FRAME_DUR).astype(np.int64), 0, N_FRAMES)
    for i in range(len(slots)):
        for f in range(f0[i], f1[i]):
            ov = min(off[i], (f + 1) * FRAME_DUR) - max(on[i], f * FRAME_DUR)
            if ov <= 0:
                continue
            w = ov / FRAME_DUR
            y8[f, fold[i]] += w
            y14[f, dirc[i]] += w
    for y in (y8, y14):
        tot = y.sum(axis=1)
        over = tot > 1.0
        y[over] /= tot[over, None]
        y[:, 0] = np.maximum(0.0, 1.0 - y[:, 1:].sum(axis=1))
    np.savez_compressed(os.path.join(TARGETS, fid + '.npz'),
                        y8=y8.astype(np.float16), y14=y14.astype(np.float16))
    return fid, dict(match_frac=round(float(match_frac), 4),
                     phase=round(float(phase), 5),
                     had_midi=ends is not None,
                     n_notes=int(len(slots)),
                     lead_frames8=float((y8[:, 1:].sum(axis=1) > 0.5).mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(MELODIES)]
    rows = [r for r in rows
            if os.path.exists(os.path.join(LATENTS, r['id'] + '.npy'))]
    if args.limit:
        rows = rows[:args.limit]
    print(f'{len(rows)} melody rows with latents')
    summ = {}
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, r): r['id'] for r in rows}
        for i, fu in enumerate(as_completed(futs)):
            fid, info = fu.result()
            summ[fid] = info
            if (i + 1) % 200 == 0:
                print(f'{i+1}/{len(rows)}', flush=True)
    mf = np.array([v['match_frac'] for v in summ.values()])
    midi_ok = np.mean([v['had_midi'] for v in summ.values()])
    out = dict(n=len(summ), midi_dur_ok=float(midi_ok),
               match_frac_mean=float(mf.mean()),
               match_frac_p10=float(np.percentile(mf, 10)),
               fold_names=FOLD_NAMES, dir_names=DIR_NAMES,
               frame_dur=FRAME_DUR, per_file=summ)
    json.dump(out, open(os.path.join(HERE, 'prep_summary.json'), 'w'), indent=1)
    print(f'done: n={len(summ)} midi_dur_ok={midi_ok:.3f} '
          f'match mean={mf.mean():.3f} p10={np.percentile(mf,10):.3f}')


if __name__ == '__main__':
    main()
