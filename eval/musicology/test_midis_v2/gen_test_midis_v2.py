#!/usr/bin/env python
"""gen_test_midis_v2.py -- v2 of the SAME melody-encoding synthetic battery (10x scale-up).

Extends eval/musicology/test_midis/ (v1: 6 patterns x 2 tempos x 5 timbres + 1 sweep = 65
renders). v2 factorial:
  - 19 one-bar patterns: the 6 v1 patterns VERBATIM (same pitches/gates) + 13 new
    (Kim's list names 13 items; the task header says "12 new"/18 total -- we keep all 13
    described patterns rather than drop one: wholetone-rock, fifth-ping, octave-bounce,
    fourth-seesaw, stepwise-zigzag, phrygian-run, pat1@E2, pat1@E4, pat2@E2, pat2@E4,
    pat1 gate50 (staccato), pat1 gate100 (legato), rest-on-beat-3 8ths).
  - 4 tempos: 161.4990234375 (16th==1 frame, lock), 80.74951171875 (16th==2 frames,
    2nd lock point), 143.0 (16th=1.1294 fr, drift), 150.0 (16th=1.07666 fr, slow drift).
    Bars per tempo computed so total <= 512 frames (161.5:32, 80.75:16, 143:28, 150:29 --
    NOTE 150 gets 29 bars, not the 30 in the task sketch: 30 bars = 516.8 frames > 512).
  - 10 GM timbres (FluidR3_GM): v1's 5 + epiano(4), synthbass(38), synthbrass(62),
    flute(73), vibraphone(11).
  - chromatic C2->C8 8th sweep at both lock tempos (2 and 4 frames/note) x 10 timbres.
  => 19*4*10 + 2*10 = 780 fluidsynth renders.

ADDENDUM (Kim 2026-07-22, BPM-phase robustness probe): pat1 + pat5 at 20 BPMs whose
16th/frame ratios sample [0.93, 1.90] low-discrepancy (ratios 1.0 and 1.5 pinned exactly),
x 3 timbres: pure numpy SINE (5 ms linear ramps, sample-accurate onsets, no soundfont
confounds) + sawlead + piano. >=8 bar-repetitions each, capped at 512 frames.
  => 2*20*3 = 120 extra renders. Grand total 900.

MIDI conventions == v1 (verified by parsing the v1 files): tpb 480, 16th = 120 ticks,
gate 80% (96/120 or 192/240), velocity 100, channel 0, set_tempo int(60e6/bpm), no
program_change in the base MIDI (inserted per-timbre at render time).

Usage:  gen_test_midis_v2.py gen | render [--jobs N] | all
CPU only. Renders -> renders/ as <midistem>__<timbre>.wav (44.1k stereo s16).
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

BASE = Path("/home/kim/Projects/SAO/eval/musicology/test_midis_v2")
RENDERS = BASE / "renders"
SF2 = "/usr/share/soundfonts/FluidR3_GM.sf2"
SR = 44100
FPS = 10.7666015625
BPM_LOCK1 = 161.4990234375   # 16th == 1 frame
BPM_LOCK2 = 80.74951171875   # 16th == 2 frames
TPB = 480
TICKS_16TH = 120
VEL = 100

TIMBRES = {  # name -> GM program (0-based)
    "sawlead": 81, "squarelead": 80, "piano": 0, "strings": 48, "churchorgan": 19,
    "epiano": 4, "synthbass": 38, "synthbrass": 62, "flute": 73, "vibraphone": 11,
}
V1_TIMBRES = ["sawlead", "squarelead", "piano", "strings", "churchorgan"]

E2, E3, E4 = 40, 52, 64

# ---------------------------------------------------------------- patterns
# pattern = list of (onset_16ths, dur_16ths, pitch, gate_frac) covering ONE bar (16 16ths)
def alt16(a, b):
    return [(i, 1, a if i % 2 == 0 else b, 0.8) for i in range(16)]

def const16(p, gate=0.8):
    return [(i, 1, p, gate) for i in range(16)]

PHRYG_UP = [52, 53, 55, 57, 59, 60, 62, 64]     # E phrygian: E F G A B C D E
PATTERNS = {
    # --- v1 verbatim (pitches/gates identical to the parsed v1 MIDIs) ---
    "pat1_const16_1pitch": {"desc": "constant 16ths, single pitch E3", "steps": const16(E3)},
    "pat2_const16_2pitch": {"desc": "constant 16ths alternating E3/G3 (corpus minor-3rd seesaw)",
                            "steps": alt16(52, 55)},
    "pat3_const16_arp4": {"desc": "constant 16ths, 4-pitch arp E3-G3-B3-E4",
                          "steps": [(i, 1, [52, 55, 59, 64][i % 4], 0.8) for i in range(16)]},
    "pat4_rise16": {"desc": "rising chromatic 16ths E3..G4, restarts each bar",
                    "steps": [(i, 1, 52 + i, 0.8) for i in range(16)]},
    "pat5_const8_fifthjump": {"desc": "constant 8ths on E3, single fifth-jump to B3 on step 5",
                              "steps": [(2 * i, 2, 59 if i == 4 else 52, 0.8) for i in range(8)]},
    "pat6_pedal_b2trill": {"desc": "16th pedal E3, semitone trill to F3 on last 4 steps (corpus phrygian cell)",
                           "steps": [(i, 1, 53 if i >= 12 else 52, 0.8) for i in range(16)]},
    # --- v2 new ---
    "pat7_wholetone_rock": {"desc": "whole-tone rock: 16ths alternating E3/D3", "steps": alt16(52, 50)},
    "pat8_fifth_ping": {"desc": "fifth ping: 16ths alternating E3/B3", "steps": alt16(52, 59)},
    "pat9_octave_bounce": {"desc": "octave bounce: 16ths alternating E3/E4", "steps": alt16(52, 64)},
    "pat10_fourth_seesaw": {"desc": "fourth seesaw: 16ths alternating E3/A3", "steps": alt16(52, 57)},
    "pat11_stepwise_zigzag": {"desc": "stepwise zigzag: 16ths cycling E3-F#3-G3-F#3",
                              "steps": [(i, 1, [52, 54, 55, 54][i % 4], 0.8) for i in range(16)]},
    "pat12_phrygian_run": {"desc": "phrygian scalar run: 8 16ths up E-phrygian (E3..E4) then 8 down",
                           "steps": [(i, 1, (PHRYG_UP + PHRYG_UP[::-1])[i], 0.8) for i in range(16)]},
    "pat13_pat1_e2": {"desc": "pat1 transposed to E2 (register probe)", "steps": const16(E2)},
    "pat14_pat1_e4": {"desc": "pat1 transposed to E4 (register probe)", "steps": const16(E4)},
    "pat15_pat2_e2": {"desc": "pat2 transposed to E2: 16ths alternating E2/G2", "steps": alt16(40, 43)},
    "pat16_pat2_e4": {"desc": "pat2 transposed to E4: 16ths alternating E4/G4", "steps": alt16(64, 67)},
    "pat17_pat1_gate50": {"desc": "pat1 E3 16ths with 50% gate (staccato)", "steps": const16(E3, gate=0.5)},
    "pat18_pat1_gate100": {"desc": "pat1 E3 16ths with 100% gate (legato)", "steps": const16(E3, gate=1.0)},
    "pat19_rest8_beat3": {"desc": "8th notes E3 with a rest on beat 3 (8th positions 4+5 silent)",
                          "steps": [(2 * i, 2, 52, 0.8) for i in [0, 1, 2, 3, 6, 7]]},
}

TEMPOS = [  # (tag, bpm, bars)  bars chosen so 16*bars*frames_per_16th <= 512
    ("bpm161p5", BPM_LOCK1, 32),   # 1.0 fr/16th -> 512.0 frames (lock 1)
    ("bpm80p75", BPM_LOCK2, 16),   # 2.0 fr/16th -> 512.0 frames (lock 2)
    ("bpm143", 143.0, 28),         # 1.129364 fr/16th -> 505.9 frames (drift, v1)
    ("bpm150", 150.0, 29),         # 1.07666 fr/16th -> 499.6 frames (slow-drift; 30 bars would be 516.8 > 512)
]

SWEEP_TEMPOS = [("bpm161p5", BPM_LOCK1, 2.0), ("bpm80p75", BPM_LOCK2, 4.0)]  # frames/note

# ---------------------------------------------------------------- addendum: BPM-phase probe
def bpm_phase_points():
    """20 (bpm, ratio) points; ratio = frames per 16th = BPM_LOCK1/bpm, low-discrepancy
    over [0.93, 1.90]; the points nearest 1.0 and 1.5 pinned to the exact lock ratios."""
    n = 20
    phi = 0.6180339887498949
    rats = []
    for k in range(n):
        r = 0.93 + 0.97 * k / (n - 1)
        r += 0.012 * ((k * phi) % 1.0 - 0.5)  # +/-0.006 golden-ratio jitter, kills simple fractions
        rats.append(r)
    for pin in (1.0, 1.5):
        i = int(np.argmin([abs(r - pin) for r in rats]))
        rats[i] = pin
    out = []
    for k, r in enumerate(sorted(rats)):
        bpm = BPM_LOCK1 / r
        bars = int(512 // (16 * r))
        assert bars >= 8
        out.append({"k": k, "ratio_frames_per_16th": r, "bpm": bpm, "bars": bars,
                    "frames": 16 * bars * r})
    return out

ADD_PATS = ["pat1_const16_1pitch", "pat5_const8_fifthjump"]
ADD_FLUID_TIMBRES = ["sawlead", "piano"]

def bp_tag(bpm):
    return f"bpm{bpm:07.3f}".replace(".", "p")

# ---------------------------------------------------------------- midi + sine writers
def write_midi(path, steps, bars, bpm):
    import mido
    mid = mido.MidiFile(type=1, ticks_per_beat=TPB)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=int(60e6 / bpm), time=0))
    events = []  # (tick, prio, msg-kind, pitch)  prio: off before on at same tick
    for b in range(bars):
        for on16, dur16, pitch, gate in steps:
            t_on = (b * 16 + on16) * TICKS_16TH
            t_off = t_on + max(1, int(round(dur16 * TICKS_16TH * gate)))
            events.append((t_on, 1, "on", pitch))
            events.append((t_off, 0, "off", pitch))
    events.sort()
    last = 0
    import mido as _m
    for tick, _, kind, pitch in events:
        dt = tick - last
        last = tick
        if kind == "on":
            tr.append(_m.Message("note_on", note=pitch, velocity=VEL, time=dt, channel=0))
        else:
            tr.append(_m.Message("note_off", note=pitch, velocity=0, time=dt, channel=0))
    mid.save(path)

def write_sweep_midi(path, bpm):
    steps = [(2 * i, 2, 36 + i, 0.8) for i in range(73)]  # one long "bar" of 8ths
    import mido
    mid = mido.MidiFile(type=1, ticks_per_beat=TPB)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=int(60e6 / bpm), time=0))
    last = 0
    for on16, dur16, pitch, gate in steps:
        t_on = on16 * TICKS_16TH
        t_off = t_on + int(round(dur16 * TICKS_16TH * gate))
        tr.append(mido.Message("note_on", note=pitch, velocity=VEL, time=t_on - last, channel=0))
        tr.append(mido.Message("note_off", note=pitch, velocity=0, time=t_off - t_on, channel=0))
        last = t_off
    mid.save(path)

def synth_sine(steps, bars, bpm, out_path, amp=0.35, ramp_ms=5.0):
    """Pure-sine render: sample-accurate onsets from BPM, 5 ms linear attack/release,
    no reverb/tail. Stereo s16 to match fluidsynth output format."""
    import soundfile as sf
    sec16 = 60.0 / bpm / 4.0
    total = int(round((bars * 16 * sec16 + 0.5) * SR))  # +0.5 s pad like a short tail
    y = np.zeros(total, dtype=np.float64)
    nramp = int(round(ramp_ms * 1e-3 * SR))
    for b in range(bars):
        for on16, dur16, pitch, gate in steps:
            t0 = (b * 16 + on16) * sec16
            i0 = int(round(t0 * SR))
            ndur = int(round(dur16 * sec16 * gate * SR))
            f = 440.0 * 2.0 ** ((pitch - 69) / 12.0)
            t = np.arange(ndur) / SR
            seg = np.sin(2 * np.pi * f * t)
            env = np.ones(ndur)
            r = min(nramp, ndur // 2)
            env[:r] = np.linspace(0, 1, r, endpoint=False)
            env[ndur - r:] = np.linspace(1, 0, r)
            seg *= env
            y[i0:i0 + ndur] += seg
    y *= amp
    sf.write(out_path, np.stack([y, y], 1).astype(np.float32), SR, subtype="PCM_16")

# ---------------------------------------------------------------- generation
def gen():
    BASE.mkdir(parents=True, exist_ok=True)
    RENDERS.mkdir(parents=True, exist_ok=True)
    manifest = {
        "same_fps": FPS,
        "bpm_lock_exact": BPM_LOCK1,
        "bpm_lock2_exact": BPM_LOCK2,
        "render_notes": "constant patch per render; 44.1kHz stereo s16; fluidsynth -ni -g 0.5 "
                        "-r 44100 FluidR3_GM.sf2, program_change injected per timbre at render "
                        "time; names <midistem>__<timbre>.wav; sine renders are numpy "
                        "(5ms linear ramps, sample-accurate onsets, no soundfont).",
        "timbres_gm_program": TIMBRES,
        "v1_timbres": V1_TIMBRES,
        "files": [], "sweeps": [], "bpm_phase_probe": {"patterns": ADD_PATS,
            "timbres": ["sine"] + ADD_FLUID_TIMBRES, "points": [], "files": []},
        "patterns": {k: v["desc"] for k, v in PATTERNS.items()},
        "pattern_steps_16ths": {k: [list(s) for s in v["steps"]] for k, v in PATTERNS.items()},
    }
    # main factorial MIDIs
    for pname, p in PATTERNS.items():
        for tag, bpm, bars in TEMPOS:
            fp16 = (60.0 / bpm / 4.0) * FPS
            fname = f"{pname}_{tag}_{bars}bars.mid"
            write_midi(BASE / fname, p["steps"], bars, bpm)
            manifest["files"].append({
                "file": fname, "pattern": pname, "desc": p["desc"], "bpm": bpm, "bars": bars,
                "frames": round(bars * 16 * fp16, 1),
                "alignment": ("16th==1 frame (lock 1)" if bpm == BPM_LOCK1 else
                              "16th==2 frames (lock 2)" if bpm == BPM_LOCK2 else
                              f"16th={fp16:.4f} frames (phase-drift probe)"),
            })
    # sweeps
    for tag, bpm, fpn in SWEEP_TEMPOS:
        fname = f"sweep_chromatic_8ths_C2toC8_{tag}.mid"
        write_sweep_midi(BASE / fname, bpm)
        manifest["sweeps"].append({
            "file": fname, "bpm": bpm, "notes": 73, "frames_per_note": fpn,
            "frames": 73 * fpn,
            "desc": f"chromatic 8th sweep C2(36)->C8(108), {fpn:g} frames/note",
        })
    # addendum
    pts = bpm_phase_points()
    manifest["bpm_phase_probe"]["points"] = [
        {k: (round(v, 10) if isinstance(v, float) else v) for k, v in p.items()} for p in pts]
    for p in pts:
        for pname in ADD_PATS:
            fname = f"{pname}_{bp_tag(p['bpm'])}_{p['bars']}bars.mid"
            write_midi(BASE / fname, PATTERNS[pname]["steps"], p["bars"], p["bpm"])
            manifest["bpm_phase_probe"]["files"].append(
                {"file": fname, "pattern": pname, "k": p["k"], "bpm": round(p["bpm"], 10),
                 "ratio_frames_per_16th": round(p["ratio_frames_per_16th"], 10),
                 "bars": p["bars"], "frames": round(p["frames"], 1)})
            # sine render straight to renders/
            wav = RENDERS / f"{fname[:-4]}__sine.wav"
            if not wav.exists():
                synth_sine(PATTERNS[pname]["steps"], p["bars"], p["bpm"], wav)
    with open(BASE / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    nmid = len(list(BASE.glob("*.mid")))
    print(f"[gen] {nmid} MIDIs, {len(pts)} bpm-phase points, manifest written")

# ---------------------------------------------------------------- rendering
def render_one(args):
    midi_path, timbre, prog = args
    out = RENDERS / f"{midi_path.stem}__{timbre}.wav"
    if out.exists():
        return f"skip {out.name}"
    import mido
    mid = mido.MidiFile(midi_path)
    tr = mid.tracks[0]
    tr.insert(1, mido.Message("program_change", program=prog, channel=0, time=0))
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tf:
        tmp = Path(tf.name)
    mid.save(tmp)
    try:
        r = subprocess.run(
            ["fluidsynth", "-ni", "-g", "0.5", "-r", str(SR), "-F", str(out), SF2, str(tmp)],
            capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not out.exists():
            return f"FAIL {out.name}: {r.stderr[-200:]}"
    finally:
        tmp.unlink(missing_ok=True)
    return f"ok {out.name}"

def render(jobs):
    tasks = []
    mids = sorted(BASE.glob("*.mid"))
    man = json.load(open(BASE / "manifest.json"))
    bp_files = {f["file"] for f in man["bpm_phase_probe"]["files"]}
    for m in mids:
        if m.name in bp_files:
            tbs = ADD_FLUID_TIMBRES
        else:
            tbs = list(TIMBRES)
        for tb in tbs:
            tasks.append((m, tb, TIMBRES[tb]))
    print(f"[render] {len(tasks)} fluidsynth renders, {jobs} workers")
    fails = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for i, res in enumerate(ex.map(render_one, tasks, chunksize=4)):
            if res.startswith("FAIL"):
                fails += 1
                print(res, flush=True)
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(tasks)}", flush=True)
    n = len(list(RENDERS.glob("*.wav")))
    print(f"[render] done: {n} wavs present, {fails} failures")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "render", "all"])
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    if a.cmd in ("gen", "all"):
        gen()
    if a.cmd in ("render", "all"):
        render(a.jobs)
