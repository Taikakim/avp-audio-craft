#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e23a_contour_meter.py -- EXPERIMENTS E23 part (a): can our pitch meter read a contour we know, alone and under a goa backing? CPU only.
Every conditioner and head test on melody reads renders with Melodia. If the meter cannot read a clean, exaggerated line, those nulls say nothing; if it reads them well,
a flat conditioner result means the conditioner learned nothing about contour.

Battery: 8 melodies with known contours (range about 2 octaves, notes 0.25 to 1 s) x 3 soundfonts x 3 lead programs = 72 lines, 20 s, from fluidsynth.
Each is read alone and mixed at 0 dB over drums + bass stems from a goa track. Meter as in eval/morph_f0_contour_ab.py: Melodia, frame 2048, hop 441, 55-1760 Hz, EqualLoudness.
Score: Pearson r of semitone curves on jointly voiced frames, own melody vs the other 7 (foreign floor), plus voiced coverage and the share of frames within a semitone of
the true pitch up to octave. Also the direction score E4b uses: on the up/down and arch/valley pairs, corr with own minus corr with mirror.
Writes ~/evals_aac/control_runs/e23a_contour_meter_20261103/report.txt, results.json, run_meta.json. RUN: mir/bin/python eval/e23a_contour_meter.py
"""
import json
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

OUT = Path("/home/kim/evals_aac/control_runs/e23a_contour_meter_20261103")
SF = Path("/home/kim/Downloads/sf2")
FONTS = ("Super_Italo_DiscoFont_Directors_Cut.sf2", "Edirol_SD-20_Contemporary.sf2", "OPL-3_FM_128M.sf2")
PROGRAMS = (80, 81, 73)          # square lead, saw lead, flute
ROOT = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
SR = 44100
DUR = 20.0
LOW = 55                          # A3 = MIDI 57; lines span about 55-79


def melodies():
    n = 80                        # 0.25 s grid over 20 s
    x = np.arange(n) / (n - 1)
    def stairs(y, step):
        return np.repeat(y[::step], step)[:n]
    tri = lambda p: 1 - np.abs(2 * ((x * p) % 1) - 1)
    return {"up": stairs(x, 4), "down": stairs(1 - x, 4), "arch": stairs(1 - np.abs(2 * x - 1), 4), "valley": stairs(np.abs(2 * x - 1), 4),
            "wave_5s": stairs(tri(4), 2), "wave_2s": stairs(tri(10), 1), "steps_big": stairs(np.where((x * 5) % 1 < .5, .15, .85), 2), "arp_fast": np.array([0, .33, .58, 1] * 20)[:n]}


def render_line(args):
    import pretty_midi as pm
    name, y, font, prog = args
    notes = (LOW + np.round(y * 24)).astype(int)
    midi = pm.PrettyMIDI(initial_tempo=120)
    inst = pm.Instrument(program=prog)
    t, i = 0.0, 0
    while i < len(notes):
        j = i
        while j + 1 < len(notes) and notes[j + 1] == notes[i]:
            j += 1
        dur = (j - i + 1) * 0.25
        inst.notes.append(pm.Note(velocity=100, pitch=int(notes[i]), start=t, end=t + dur))
        t += dur
        i = j + 1
    midi.instruments.append(inst)
    with tempfile.TemporaryDirectory() as td:
        mp, wp = f"{td}/m.mid", f"{td}/o.wav"
        midi.write(mp)
        subprocess.run(["fluidsynth", "-ni", "-g", "0.8", "-r", str(SR), "-F", wp, str(SF / font), mp], capture_output=True, check=True, env={k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"})
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", wp, "-ac", "1", "-ar", str(SR), "-t", str(DUR), "-f", "f32le", "-"], capture_output=True, check=True)
    a = np.frombuffer(r.stdout, dtype=np.float32).copy()
    a = np.pad(a, (0, max(0, int(DUR * SR) - len(a))))[: int(DUR * SR)]
    return a / (np.sqrt((a ** 2).mean()) + 1e-9) * 0.1


def melodia(x):
    import essentia.standard as es
    f0, _ = es.PredominantPitchMelodia(frameSize=2048, hopSize=441, sampleRate=SR, minFrequency=55, maxFrequency=1760)(es.EqualLoudness()(x.astype(np.float32)))
    return np.asarray(f0, dtype=np.float64)


def score(f0, y, others, mirror):
    v = f0 > 0
    if v.sum() < 50:
        return dict(coverage=float(v.mean()), own=None)
    st = 12 * np.log2(f0[v] / 440.0)
    idx = np.minimum((np.arange(len(f0))[v] / 100 / 0.25).astype(int), len(y) - 1)
    c = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else 0.0
    true = (LOW + np.round(y * 24))[idx]
    oct_err = ((st + 69 - true + 6) % 12) - 6
    out = dict(coverage=float(v.mean()), own=c(st, y[idx]), foreign=float(np.mean([c(st, o[idx]) for o in others])), within_st=float((np.abs(oct_err) <= 1).mean()))
    if mirror is not None:
        out["follow"] = c(st, y[idx]) - c(st, mirror[idx])
    return out


def job(a):
    name, font, prog, cond, x, mel = a
    f0 = melodia(x)
    y = mel[name]
    mirror = {"up": "down", "down": "up", "arch": "valley", "valley": "arch"}.get(name)
    return dict(melody=name, font=font, program=prog, cond=cond, **score(f0, y, [mel[k] for k in mel if k != name], mel[mirror] if mirror else None))


def backing():
    dirs = sorted(d for d in ROOT.iterdir() if d.is_dir())
    rng = np.random.default_rng(23)
    rng.shuffle(dirs)
    out = []
    for d in dirs:
        st = [next(iter(sorted(d.glob(f"{s}.*"))), None) for s in ("drums", "bass")]
        if not all(st):
            continue
        ys = []
        for p in st:
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "60", "-t", str(DUR), "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
            ys.append(np.frombuffer(r.stdout, dtype=np.float32))
        n = min(map(len, ys))
        if n >= int(DUR * SR) - 10:
            b = sum(y[:n] for y in ys)
            out.append(np.pad(b, (0, int(DUR * SR) - n))[: int(DUR * SR)])
        if len(out) == 3:
            return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mel = melodies()
    args = [(k, mel[k], f, p) for k in mel for f in FONTS for p in PROGRAMS]
    with ProcessPoolExecutor(8) as ex:
        lines = list(ex.map(render_line, args))
    back = backing()
    jobs = []
    for i, ((k, _, f, p), x) in enumerate(zip(args, lines)):
        jobs.append((k, f, p, "alone", x, mel))
        b = back[i % 3]
        jobs.append((k, f, p, "over_backing", (x + b / (np.sqrt((b ** 2).mean()) + 1e-9) * 0.1) * 0.5, mel))
    with ProcessPoolExecutor(10) as ex:
        res = list(ex.map(job, jobs))
    (OUT / "results.json").write_text(json.dumps(res, indent=0))
    m = lambda rows, k: round(float(np.mean([r[k] for r in rows if r.get(k) is not None])), 3) if any(r.get(k) is not None for r in rows) else None
    L = ["Melodia on known lines. own = corr with the true melody; foreign = with the other 7; within_st = frames within a semitone up to octave.", ""]
    for cond in ("alone", "over_backing"):
        sub = [r for r in res if r["cond"] == cond]
        L.append(f"{cond}: own {m(sub, 'own')} foreign {m(sub, 'foreign')} within_st {m(sub, 'within_st')} coverage {m(sub, 'coverage')} follow(up/down, arch/valley) {m(sub, 'follow')}")
        for k in mel:
            s = [r for r in sub if r["melody"] == k]
            L.append(f"   {k:10s} own {m(s, 'own')} foreign {m(s, 'foreign')} within_st {m(s, 'within_st')} coverage {m(s, 'coverage')}")
        for f in FONTS:
            s = [r for r in sub if r["font"] == f]
            L.append(f"   {f[:16]:16s} own {m(s, 'own')} within_st {m(s, 'within_st')}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    (OUT / "run_meta.json").write_text(json.dumps({"run": "e23a_contour_meter_20261103", "created": "2026-11-03", "owner": "WINTERMUTE", "purpose": "EXPERIMENTS E23 (a): can the melody meter read a known contour, alone and under a goa backing?", "hypothesis": "If Melodia reads clean exaggerated lines well, flat results on conditioners are real; if not, those nulls say little.", "script": "eval/e23a_contour_meter.py", "related": ["EXPERIMENTS.md E23", "eval/morph_f0_contour_ab.py"], "recipe": {"melodies": list(mel), "fonts": FONTS, "programs": PROGRAMS}, "result": {cond: {k: m([r for r in res if r["cond"] == cond], k) for k in ("own", "foreign", "within_st", "coverage", "follow")} for cond in ("alone", "over_backing")}, "kim_feedback": None}, indent=2))
    print("\n".join(L))


if __name__ == "__main__":
    main()
