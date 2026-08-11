#!/usr/bin/env python
"""synthetic_cross_eval.py — Head A ceiling: representation-limited vs target-noise-limited.

Applies the FROZEN corpus-trained readout `readout_mlp_ctx2_y8.pt` (held-out
artist-disjoint corpus bacc 0.280 / macro-F1 0.273, chance 0.125 — see REPORT.md)
to synthetic material with EXACT note-grid ground truth, on the SAME 8-class
folded contour set {rest,pedal,|1|,|2|,|3|,|5|,|7|,|12|}. No retraining — this
is inference-only cross-eval, CPU, no GPU/lock needed.

Branch logic (spec, from the tasking):
  A) synth-solo >> 0.28  -> representation fine on solo; corpus ceiling was
     target-noise + mix-masking. Mix set should partially recover.
  B) synth-solo ~= 0.28  -> readout genuinely can't do per-frame contour even
     noise-free -> representation-limited, confirmed.
  C) synth-solo high, synth-mix ~= corpus -> mix masking is the binding
     constraint, target noise secondary.

Four eval cells, GT built at the checkpoint's exact input pipeline (z0 raw
latent, per-channel (x-mu)/sd from the checkpoint, Conv1d ctx=2 mlp head):

  1. test_midis v1 battery (65 renders: 6 patterns x2 tempo x5 timbres + sweep)
     GT: per-note fold class from the pattern MIDI (classes_of_row logic,
     reimplemented generically for a single continuous monophonic phrase),
     soft time-overlap onto SAME frames (verbatim math from prep_targets.py).
  2. gm_multifont solo interval battery, random 100/640 timbre subset.
     GT: manifest.json 'grid' (256 frames, k-labelled move frames) mapped
     1:1 onto SAME frames (already frame-quantized); tail frames beyond the
     256-frame grid (decay/release) scored as 'rest'.
  3. gm_multifont MIX cells (32 lead+bass mixes, no drums) scored against the
     LEAD voice's GT (mix_manifest.json 'lead_grid') — the noise-free version
     of the production (mix-native) question.
  4. battery__sine.z0.npy — the pure-sine solo render (cleanest case), GT =
     the same manifest.json grid as (2).

Run: /home/kim/Projects/mir/mir/bin/python synthetic_cross_eval.py
Outputs: synthetic_cross_eval.json + prints a summary table.
"""
import glob
import json
import os
import random
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
MUS = os.path.dirname(HERE)                      # eval/musicology
sys.path.insert(0, HERE)
sys.path.insert(0, MUS)

import prep_targets as PT          # noqa: E402  (ALLOWED, _MAG_MAP, FOLD_NAMES, FRAME_DUR)
from train_readout import Readout, scores_from_cm   # noqa: E402 (reuse verbatim)

CKPT = os.path.join(HERE, 'readout_mlp_ctx2_y8.pt')
TEST_MIDIS = os.path.join(MUS, 'test_midis')
GM = os.path.join(MUS, 'gm_multifont')

FRAME_DUR = PT.FRAME_DUR
ALLOWED = PT.ALLOWED
MAG_MAP = PT._MAG_MAP
FOLD_NAMES = PT.FOLD_NAMES
N_CLS = len(FOLD_NAMES)

CORPUS_BACC = 0.280
CORPUS_MACRO_F1 = 0.273

GM_SUBSET_N = 100
GM_SUBSET_SEED = 42


# ------------------------------------------------------------------ model
def load_model():
    sd = torch.load(CKPT, map_location='cpu', weights_only=False)
    assert sd['class_names'] == FOLD_NAMES, (sd['class_names'], FOLD_NAMES)
    model = Readout(sd['arch'], sd['ctx'], sd['n_cls'], hidden=512,
                     t_cond=sd['t_conditioned'])
    model.load_state_dict(sd['model'])
    model.eval()
    mu = torch.tensor(sd['norm_mu'], dtype=torch.float32)[None, :, None]
    sd_ = torch.tensor(sd['norm_sd'], dtype=torch.float32)[None, :, None]
    return model, mu, sd_, sd


@torch.no_grad()
def apply_head(model, mu, sd, z0):
    """z0: (256,T) or (1,256,T) raw latent -> logits (n_cls,T)."""
    if z0.ndim == 3:
        z0 = z0[0]
    x = torch.from_numpy(z0.astype(np.float32))[None]     # (1,256,T)
    x = (x - mu) / sd
    logits = model(x)                                     # (1,n_cls,T)
    return logits[0]


# ------------------------------------------------------------------ GT builders
def fold_seq_from_pitches(pitches):
    """First note (phrase-first, no incoming move) = pedal; else nearest-
    allowed-magnitude fold class of the semitone diff from the previous note
    (verbatim mapping table from prep_targets.classes_of_row, generalized to
    a single continuous monophonic phrase — these synthetic patterns have no
    rests, so the whole file is one phrase)."""
    fold = np.ones(len(pitches), np.int64)   # default pedal
    for i in range(1, len(pitches)):
        d = pitches[i] - pitches[i - 1]
        if d == 0:
            continue
        mag = MAG_MAP[abs(d)]
        fold[i] = 2 + ALLOWED.index(mag)
    return fold


def soft_targets_from_notes(on, off, fold, n_frames, frame_dur=FRAME_DUR, n_cls=N_CLS):
    """Verbatim time-overlap soft-target math from prep_targets.process_one,
    generalized to arbitrary n_frames (renders here are much shorter than the
    corpus's fixed 4096)."""
    y = np.zeros((n_frames, n_cls), np.float32)
    f0 = np.clip(np.floor(on / frame_dur).astype(np.int64), 0, n_frames)
    f1 = np.clip(np.ceil(off / frame_dur).astype(np.int64), 0, n_frames)
    for i in range(len(on)):
        for f in range(f0[i], f1[i]):
            ov = min(off[i], (f + 1) * frame_dur) - max(on[i], f * frame_dur)
            if ov <= 0:
                continue
            w = ov / frame_dur
            y[f, fold[i]] += w
    tot = y.sum(axis=1)
    over = tot > 1.0
    y[over] /= tot[over, None]
    y[:, 0] = np.maximum(0.0, 1.0 - y[:, 1:].sum(axis=1))
    return y


def notes_from_pattern_midi(path):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(path)
    notes = []
    for inst in pm.instruments:
        for n in inst.notes:
            notes.append((n.start, n.end, n.pitch))
    notes.sort()
    on = np.array([n[0] for n in notes], np.float64)
    off = np.array([n[1] for n in notes], np.float64)
    pitches = np.array([n[2] for n in notes], np.int64)
    # clip each note at the next onset (verbatim corpus convention: short
    # gate-time notes are NOT stretched to fill the gap -> brief rest weight
    # in gate-gap frames is expected and matches how the corpus targets were
    # built for muscriptor renders too).
    off = off.copy()
    off[:-1] = np.minimum(off[:-1], on[1:])
    fold = fold_seq_from_pitches(pitches)
    return on, off, fold


def grid_targets(grid, n_frames, n_cls=N_CLS):
    """gm_multifont manifest 'grid' (already frame-quantized, 1:1 SAME-frame
    mapping) -> hard one-hot y (n_frames,n_cls). Frames beyond the grid
    (post-battery decay/release tail) scored as REST (no new melodic event
    triggers there)."""
    y = np.zeros((n_frames, n_cls), np.float32)
    y[:, 0] = 1.0
    for r in grid:
        f = r['frame']
        if f >= n_frames:
            continue
        k = r['k']
        cls = 1 if k is None else 2 + ALLOWED.index(k)
        y[f, :] = 0.0
        y[f, cls] = 1.0
    return y


# ------------------------------------------------------------------ eval loop
def accumulate(model, mu, sd, z0, y):
    """z0 (256,T) latent, y (T,n_cls) soft/hard target -> confusion-matrix
    contribution (n_cls,n_cls), pooled the same way train_readout.evaluate()
    pools frames across all files in a set."""
    T = min(z0.shape[-1], y.shape[0])
    logits = apply_head(model, mu, sd, z0[..., :T])
    pred = logits.argmax(0).numpy()
    yl = y[:T].argmax(-1)
    cm = np.zeros((N_CLS, N_CLS), np.int64)
    np.add.at(cm, (yl, pred), 1)
    return cm, T


def eval_set(name, items, model, mu, sd):
    """items: list of (latent_path, y_builder_fn) where y_builder_fn(T)->y."""
    cm = np.zeros((N_CLS, N_CLS), np.int64)
    n_frames_total = 0
    n_files = 0
    for lat_path, y_fn in items:
        z0 = np.load(lat_path)
        T = z0.shape[-1] if z0.ndim == 2 else z0.shape[-1]
        y = y_fn(T)
        c, t = accumulate(model, mu, sd, z0, y)
        cm += c
        n_frames_total += t
        n_files += 1
    sc = scores_from_cm(cm)
    sc['n_files'] = n_files
    sc['n_frames'] = int(n_frames_total)
    sc['class_names'] = FOLD_NAMES
    sc['confusion'] = cm.tolist()
    print(f'[{name}] n_files={n_files} n_frames={n_frames_total} '
          f'bacc={sc["balanced_acc"]:.4f} macroF1={sc["macro_f1"]:.4f}')
    return sc


def main():
    model, mu, sd, ckpt = load_model()
    out = {'checkpoint': os.path.basename(CKPT),
           'corpus_reference': dict(bacc=CORPUS_BACC, macro_f1=CORPUS_MACRO_F1,
                                     n='held-out artist-disjoint test, 273 files'),
           'class_names': FOLD_NAMES}

    # ---------------- SET 1: test_midis v1 battery (65 renders) ----------
    manifest = json.load(open(os.path.join(TEST_MIDIS, 'manifest.json')))
    pattern_notes = {}
    for f in manifest['files']:
        mid_path = os.path.join(TEST_MIDIS, f['file'])
        pattern_notes[f['file']] = notes_from_pattern_midi(mid_path)
    items = []
    for f in manifest['files']:
        stem = f['file'][:-4]           # strip .mid
        on, off, fold = pattern_notes[f['file']]
        for lat in sorted(glob.glob(os.path.join(TEST_MIDIS, 'latents',
                                                   stem + '__*.z0.npy'))):
            def y_fn(T, on=on, off=off, fold=fold):
                return soft_targets_from_notes(on, off, fold, T)
            items.append((lat, y_fn))
    print(f'test_midis: {len(items)} renders '
          f'({len(manifest["files"])} patterns x timbres)')
    out['synthetic_solo_v1'] = eval_set('synthetic_solo_v1 (test_midis)', items, model, mu, sd)

    # ---------------- SET 2: gm_multifont solo, random 100/640 -----------
    gm_manifest = json.load(open(os.path.join(GM, 'manifest.json')))
    grid = gm_manifest['grid']
    all_gm = sorted(glob.glob(os.path.join(GM, 'latents', 'gm*.z0.npy')))
    rng = random.Random(GM_SUBSET_SEED)
    subset = rng.sample(all_gm, min(GM_SUBSET_N, len(all_gm)))
    items = [(p, (lambda T, grid=grid: grid_targets(grid, T))) for p in subset]
    out['synthetic_solo_gm'] = eval_set(
        f'synthetic_solo_gm ({len(subset)}/{len(all_gm)} timbres)', items, model, mu, sd)
    out['synthetic_solo_gm']['subset_seed'] = GM_SUBSET_SEED
    out['synthetic_solo_gm']['n_available'] = len(all_gm)

    # ---------------- SET 3: MIX cells (32 lead+bass, vs LEAD gt) --------
    mix_manifest = json.load(open(os.path.join(GM, 'mix_manifest.json')))
    lead_grid = mix_manifest['lead_grid']
    mix_lats = sorted(glob.glob(os.path.join(GM, 'latents', 'mix__*.z0.npy')))
    items = [(p, (lambda T, g=lead_grid: grid_targets(g, T))) for p in mix_lats]
    out['synthetic_mix'] = eval_set(f'synthetic_mix ({len(mix_lats)} mixes vs lead GT)',
                                     items, model, mu, sd)

    # ---------------- SET 4: pure sine solo battery -----------------------
    sine_path = os.path.join(GM, 'latents', 'battery__sine.z0.npy')
    if os.path.exists(sine_path):
        items = [(sine_path, (lambda T, g=grid: grid_targets(g, T)))]
        out['synthetic_solo_sine'] = eval_set('synthetic_solo_sine (battery__sine)',
                                               items, model, mu, sd)
    else:
        print('battery__sine.z0.npy not found -- skipping SET 4')
        out['synthetic_solo_sine'] = None

    # ---------------- deltas + branch verdict -----------------------------
    d = {}
    for k in ('synthetic_solo_v1', 'synthetic_solo_gm', 'synthetic_mix', 'synthetic_solo_sine'):
        if out.get(k):
            d[k] = dict(delta_bacc_vs_corpus=round(out[k]['balanced_acc'] - CORPUS_BACC, 4),
                        delta_f1_vs_corpus=round(out[k]['macro_f1'] - CORPUS_MACRO_F1, 4))
    out['deltas_vs_corpus'] = d

    solo_bacc = max(out['synthetic_solo_v1']['balanced_acc'],
                     out['synthetic_solo_gm']['balanced_acc'])
    mix_bacc = out['synthetic_mix']['balanced_acc']
    if solo_bacc > CORPUS_BACC + 0.10:
        if abs(mix_bacc - CORPUS_BACC) < 0.05:
            verdict = 'C: synth-solo high, synth-mix ~= corpus -> mix masking is the binding constraint'
        else:
            verdict = 'A: synth-solo >> corpus -> representation fine on solo; target-noise + mix-masking explain the corpus ceiling'
    elif abs(solo_bacc - CORPUS_BACC) < 0.05:
        verdict = 'B: synth-solo ~= corpus -> representation-limited, confirmed (readout cannot do per-frame contour even noise-free)'
    else:
        verdict = f'AMBIGUOUS: solo_bacc={solo_bacc:.3f} between corpus and clean-ceiling bands; see per-set numbers'
    out['verdict'] = verdict
    print('\nVERDICT:', verdict)

    json.dump(out, open(os.path.join(HERE, 'synthetic_cross_eval.json'), 'w'), indent=1)
    print('\nwrote', os.path.join(HERE, 'synthetic_cross_eval.json'))


if __name__ == '__main__':
    main()
