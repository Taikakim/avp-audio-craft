#!/usr/bin/env python
"""prep_notegrid88.py — MuScriptor MIDIs -> voice-AGNOSTIC 88-key piano-roll at SAME rate.

Kim 2026-08-12 (movement thread): collapse the register-blind melody8 (8 folded
interval classes, monophonic skyline) into an 88-key register-AWARE roll. NOT a MIDI
transcription and NOT human-readable — a continuous per-frame energy-per-key map that
tracks pitch MOVEMENT (incl. octave leaps that chroma/melody8 throw away).

WHY VOICE-AGNOSTIC: MuScriptor timing is excellent but its voice attribution is not —
Kim saw a bassline dominate and transpose into a second lead voice. This builder uses
EVERY non-drum note merged into one roll, so it consumes only what MuScriptor gets right
(when + which pitch) and never asks "lead or bass". That deletes the skyline reduction,
bass-exclusion, interval-fold and kick-phase recovery that prep_targets.py (the melody8
builder) needs — this is strictly simpler AND dodges those exact failure modes.

Residual label noise (Kim's caveat): a bass note mis-transposed up an octave lands on
the wrong KEY -> soft targets + register-tolerant evaluation absorb it.

Roll: (N_FRAMES, 88), key k = MIDI pitch (21=A0 .. 108=C8), value = sum over notes of
(frame time-overlap fraction) * (velocity/127). Polyphonic (no argmax); simultaneous
notes add. Same 0.0928798 s SAME frame as prep_targets.py.

Run: /home/kim/Projects/mir/mir/bin/python prep_notegrid88.py [--workers N] [--limit N] [--no-velocity]
Outputs: notegrid88/<id>.npy  (float16 (4096,88)), _meta.json
"""
import argparse, json, os, sys, time
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))          # eval/musicology
sys.path.insert(0, HERE)
import hook_metric as HM

MELODIES = os.path.join(HERE, 'melodies.jsonl')
MIDI_DIR = '/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/muscriptor_full'
LATENTS = '/home/kim/Projects/latents_sa3'
OUT = '/home/kim/Projects/latents_sa3_notegrid88'   # NVMe sidecar dir, beside latents (like latents_sa3_melody); NOT the repo tree

N_FRAMES = 4096
FRAME_DUR = 4096.0 / 44100.0        # 0.0928798 s (10.7666 Hz), matches prep_targets.py
KEY_MIN, KEY_MAX = 21, 108          # A0..C8 = 88 keys (piano); MIDI pitch -> k = pitch-21
N_KEYS = KEY_MAX - KEY_MIN + 1      # 88


def notes_to_roll88(notes, n_frames=N_FRAMES, frame_dur=FRAME_DUR, use_velocity=True):
    """Pure fn: list of (start,end,pitch,vel,is_drum,track) -> (n_frames,88) float32.
    Voice-agnostic: every non-drum note in [21,108] contributes time-overlap*vel to its key."""
    roll = np.zeros((n_frames, N_KEYS), np.float32)
    for (s0, e0, p, v, is_drum, _t) in notes:
        if is_drum or p < KEY_MIN or p > KEY_MAX:
            continue
        e0 = max(e0, s0 + 0.25 * frame_dur)          # floor tiny/zero-length notes
        k = int(p) - KEY_MIN
        w_vel = (float(v) / 127.0) if use_velocity else 1.0
        f0 = max(0, int(np.floor(s0 / frame_dur)))
        f1 = min(n_frames, int(np.ceil(e0 / frame_dur)))
        for f in range(f0, f1):
            ov = min(e0, (f + 1) * frame_dur) - max(s0, f * frame_dur)
            if ov > 0:
                roll[f, k] += (ov / frame_dur) * w_vel
    return roll


def _self_test():
    fd = FRAME_DUR
    # one note, pitch 60 (k=39), exactly one frame long, full velocity -> roll[0,39]=1
    r = notes_to_roll88([(0.0, fd, 60, 127, False, 0)])
    assert abs(r[0, 39] - 1.0) < 1e-5 and r[1:, 39].sum() < 1e-6, r[0, 39]
    # 1.5-frame note -> frame0=1.0, frame1=0.5
    r = notes_to_roll88([(0.0, 1.5 * fd, 60, 127, False, 0)])
    assert abs(r[0, 39] - 1.0) < 1e-5 and abs(r[1, 39] - 0.5) < 1e-5, (r[0, 39], r[1, 39])
    # velocity scaling: vel 64 -> ~0.504
    r = notes_to_roll88([(0.0, fd, 60, 64, False, 0)])
    assert abs(r[0, 39] - 64 / 127) < 1e-4, r[0, 39]
    # drums + out-of-range dropped; polyphony adds
    r = notes_to_roll88([(0.0, fd, 60, 127, True, 9),      # drum -> ignored
                         (0.0, fd, 20, 127, False, 0),     # <21 -> ignored
                         (0.0, fd, 60, 127, False, 0),     # counted
                         (0.0, fd, 72, 127, False, 1)])    # k=51, counted (polyphony)
    assert abs(r[0, 39] - 1.0) < 1e-5 and abs(r[0, 51] - 1.0) < 1e-5 and r[0].sum() > 1.5, r[0].sum()
    print('[self-test] notes_to_roll88 OK')


def process_one(args_tuple):
    fid, use_velocity = args_tuple
    try:
        import pretty_midi
        pm = pretty_midi.PrettyMIDI(os.path.join(MIDI_DIR, fid + '.mid'))
        notes = HM.notes_from_pretty_midi(pm)
    except Exception as e:
        return fid, dict(ok=False, err=str(e)[:80])
    roll = notes_to_roll88(notes, use_velocity=use_velocity)
    np.save(os.path.join(OUT, fid + '.npy'), roll.astype(np.float16))
    active = roll.max(axis=1) > 0.05
    # crude register spread: std of the energy-weighted key centroid over active frames
    if active.any():
        ks = np.arange(N_KEYS)
        cen = (roll[active] * ks).sum(1) / np.maximum(roll[active].sum(1), 1e-6)
        cen_std = float(cen.std())
        cen_mean = float(cen.mean())
    else:
        cen_std = cen_mean = 0.0
    return fid, dict(ok=True, active_frac=float(active.mean()),
                     centroid_key_mean=round(cen_mean + KEY_MIN, 2),
                     centroid_key_std=round(cen_std, 3),
                     n_notes=len(notes))


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--no-velocity', action='store_true', help='presence-only roll (no vel weighting)')
    ap.add_argument('--out-dir', default=OUT)
    args = ap.parse_args()
    OUT = args.out_dir      # forked workers inherit this global (Linux fork start method)
    _self_test()
    os.makedirs(OUT, exist_ok=True)
    ids = [json.loads(l)['id'] for l in open(MELODIES)]
    ids = [i for i in ids
           if os.path.exists(os.path.join(LATENTS, i + '.npy'))
           and os.path.exists(os.path.join(MIDI_DIR, i + '.mid'))]
    if args.limit:
        ids = ids[:args.limit]
    use_vel = not args.no_velocity
    print(f'{len(ids)} ids with latent+MIDI; velocity={use_vel}')
    summ = {}
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, (i, use_vel)): i for i in ids}
        for j, fu in enumerate(as_completed(futs)):
            fid, info = fu.result()
            summ[fid] = info
            if (j + 1) % 200 == 0:
                print(f'{j+1}/{len(ids)}', flush=True)
    ok = [v for v in summ.values() if v['ok']]
    meta = dict(built=time.strftime('%Y-%m-%d %H:%M:%S'),
                n=len(summ), n_ok=len(ok), n_fail=len(summ) - len(ok),
                velocity_weighted=use_vel, n_keys=N_KEYS, key_min=KEY_MIN, key_max=KEY_MAX,
                frame_dur=FRAME_DUR, midi_dir=MIDI_DIR,
                encoding='float16 (4096,88); k=MIDI_pitch-21; value=sum overlap*vel; voice-agnostic',
                active_frac_mean=round(float(np.mean([v['active_frac'] for v in ok])), 4) if ok else 0,
                centroid_key_std_mean=round(float(np.mean([v['centroid_key_std'] for v in ok])), 3) if ok else 0)
    json.dump(meta, open(os.path.join(OUT, '_meta.json'), 'w'), indent=1)
    print(f"done: n_ok={len(ok)}/{len(summ)} active_frac~{meta['active_frac_mean']} "
          f"centroid_key_std~{meta['centroid_key_std_mean']}")


if __name__ == '__main__':
    main()
