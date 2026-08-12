#!/usr/bin/env python3
"""dawp_to_frames.py — Bitwig .dawproject notes -> tick-exact frame-aligned key-roll + gate.

Kim 2026-08-12. The DAW-truth counterpart to prep_notegrid88.py (MuScriptor). Per MIDI track,
expands looped clips, converts to seconds (beats x 60/bpm), and rasterises to a (T, K) key-roll
at the SAME 10.7666 Hz latent frame rate, plus a per-frame GATE / negative-space stream from the
exact note durations (the thing MuScriptor's transcription can't give). Voice-agnostic MERGED roll
too (all MIDI tracks) for direct comparison to the MuScriptor full-mix roll.

LOOP EXPANSION (the non-obvious correctness piece): a clip with loopEnd-loopStart < duration repeats
its loop-window notes every L beats until the clip ends. Assumes playStart==loopStart (true for all
Two Suns clips); counts + warns on any clip that violates it rather than mis-expanding silently.

KEY RANGE configurable (--kmin/--kmax; default 88 = MIDI 21..108). Reports the ACTUAL note range so
88-vs-128 is an evidence call, not a guess.

Run: python3 dawp_to_frames.py <project.xml> [--kmin 21 --kmax 108] [--out DIR]
"""
import argparse, json, os
import numpy as np
import xml.etree.ElementTree as ET

FRAME_DUR = 4096.0 / 44100.0        # 0.0928798 s (10.7666 Hz), matches prep_notegrid88 / SAME latent


def clip_events(clip, warn):
    """-> list of (abs_beat, dur_beat, key, vel), loops expanded. warn: dict counter."""
    ct = float(clip.get("time", 0)); dur = float(clip.get("duration", 0))
    ps = float(clip.get("playStart", 0)); ls = float(clip.get("loopStart", ps))
    le = clip.get("loopEnd"); le = float(le) if le is not None else None
    raw = [(float(n.get("time")), float(n.get("duration", 0)),
            int(n.get("key")), float(n.get("vel", 1)))
           for n in clip.iter("Note")]
    out = []
    looping = le is not None and (le - ls) > 1e-6 and (le - ls) < dur - 1e-6
    if looping and abs(ps - ls) > 1e-6:
        warn["playstart_ne_loopstart"] = warn.get("playstart_ne_loopstart", 0) + 1
    if looping and abs(ps - ls) <= 1e-6:
        L = le - ls
        for t, nd, k, v in raw:
            if not (ls - 1e-6 <= t < le):        # pickup/tail note outside loop window: place once
                if 0 <= (t - ps) < dur:
                    out.append((ct + (t - ps), nd, k, v))
                continue
            j = 0
            while (t - ls) + j * L < dur - 1e-9:
                st = (t - ls) + j * L
                out.append((ct + st, min(nd, dur - st), k, v))
                j += 1
    else:                                        # non-looping: place each note once
        for t, nd, k, v in raw:
            e = t - ps
            if -1e-6 <= e < dur:
                out.append((ct + e, min(nd, dur - e), k, v))
    return out


def rasterise(events, n_frames, kmin, kmax, spb, use_vel=True):
    """(abs_beat,dur_beat,key,vel) events -> (T,K) roll + (T,) gate duty-cycle."""
    K = kmax - kmin + 1
    roll = np.zeros((n_frames, K), np.float32)
    gate = np.zeros(n_frames, np.float32)          # any-note-on presence (0/1-ish, overlap-weighted)
    for ab, db, key, v in events:
        if key < kmin or key > kmax:
            continue
        s0 = ab * spb; e0 = s0 + max(db * spb, 0.25 * FRAME_DUR)
        ki = int(key) - kmin
        w = (float(v)) if use_vel else 1.0
        f0 = max(0, int(np.floor(s0 / FRAME_DUR))); f1 = min(n_frames, int(np.ceil(e0 / FRAME_DUR)))
        for f in range(f0, f1):
            ov = min(e0, (f + 1) * FRAME_DUR) - max(s0, f * FRAME_DUR)
            if ov > 0:
                frac = ov / FRAME_DUR
                roll[f, ki] += frac * w
                gate[f] = max(gate[f], frac)       # duty: fraction of frame any note sounds
    return roll, gate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_xml")
    ap.add_argument("--kmin", type=int, default=21)      # A0
    ap.add_argument("--kmax", type=int, default=108)     # C8  (88 keys)
    ap.add_argument("--out", default="/home/kim/dawp_two_suns/frames")
    ap.add_argument("--no-velocity", action="store_true")
    args = ap.parse_args()
    root = ET.parse(args.project_xml).getroot()
    tr = root.find("Transport"); bpm = float(tr.find("Tempo").get("value")); spb = 60.0 / bpm

    tracks = {}
    def walk(el):
        for t in el.findall("Track"):
            tracks[t.get("id")] = dict(name=t.get("name", "?"), ctype=t.get("contentType", "?"))
            walk(t)
    walk(root.find("Structure"))

    warn = {}
    per_track = {}       # tid -> events
    top = root.find("Arrangement").find("Lanes")
    for ln in top.findall("Lanes"):
        tid = ln.get("track"); clips_el = ln.find("Clips")
        if clips_el is None:
            continue
        evs = []
        for c in clips_el.findall("Clip"):
            evs += clip_events(c, warn)
        if evs:
            per_track[tid] = evs

    # drop the section-marker track (name 'Arrangement', all key data absent anyway)
    all_ev = [e for tid, evs in per_track.items()
              for e in evs if tracks.get(tid, {}).get("name") != "Arrangement"]
    if not all_ev:
        print("no note events found"); return
    end_beat = max(ab + db for ab, db, _, _ in all_ev)
    n_frames = int(np.ceil(end_beat * spb / FRAME_DUR)) + 1
    keys = [k for _, _, k, _ in all_ev]
    kmn, kmx = min(keys), max(keys)

    os.makedirs(args.out, exist_ok=True)
    use_vel = not args.no_velocity
    summ = {}
    # merged voice-agnostic roll (all pitched tracks)
    merged, mgate = rasterise(all_ev, n_frames, args.kmin, args.kmax, spb, use_vel)
    np.save(os.path.join(args.out, "_MERGED.roll.npy"), merged.astype(np.float16))
    np.save(os.path.join(args.out, "_MERGED.gate.npy"), mgate.astype(np.float16))
    for tid, evs in per_track.items():
        nm = tracks.get(tid, {}).get("name", tid)
        if nm == "Arrangement":
            continue
        roll, gate = rasterise(evs, n_frames, args.kmin, args.kmax, spb, use_vel)
        safe = nm.replace("/", "_")[:40]
        np.save(os.path.join(args.out, f"{safe}.roll.npy"), roll.astype(np.float16))
        np.save(os.path.join(args.out, f"{safe}.gate.npy"), gate.astype(np.float16))
        active = gate > 0.05
        cen = 0.0
        if active.any():
            ks = np.arange(roll.shape[1])
            e = roll[active]
            cen = float(((e * ks).sum(1) / np.maximum(e.sum(1), 1e-6)).std())
        summ[nm] = dict(n_events=len(evs), duty=round(float((gate > 0.05).mean()), 3),
                        centroid_key_std=round(cen, 2))

    meta = dict(bpm=bpm, frame_rate_hz=1 / FRAME_DUR, n_frames=n_frames,
                track_seconds=round(end_beat * spb, 1),
                key_range_requested=[args.kmin, args.kmax],
                key_range_actual=[kmn, kmx], n_events_total=len(all_ev),
                velocity_weighted=use_vel, loop_warnings=warn, per_track=summ)
    json.dump(meta, open(os.path.join(args.out, "_meta.json"), "w"), indent=1)

    print(f"=== dawp_to_frames: {bpm:.0f}bpm, {end_beat*spb:.0f}s, {n_frames} frames @10.77Hz ===")
    print(f"note events (loop-expanded): {len(all_ev)}   loop-warnings: {warn or 'none'}")
    print(f"ACTUAL key range: MIDI {kmn}..{kmx}  (requested {args.kmin}..{args.kmax} = "
          f"{args.kmax-args.kmin+1} keys)")
    lo_out = sum(1 for k in keys if k < args.kmin); hi_out = sum(1 for k in keys if k > args.kmax)
    print(f"notes below kmin: {lo_out}   above kmax: {hi_out}   "
          f"-> {'88 sufficient' if lo_out+hi_out==0 else 'some notes clipped; consider 128'}")
    print(f"\nper-track (events / duty-cycle / register-centroid-std semitones):")
    for nm, s in sorted(summ.items(), key=lambda kv: -kv[1]["n_events"]):
        print(f"  {nm:<34} {s['n_events']:>6}  duty {s['duty']:.3f}  cenStd {s['centroid_key_std']:.2f}")
    print(f"\nwrote rolls+gates -> {args.out}")


if __name__ == "__main__":
    main()
