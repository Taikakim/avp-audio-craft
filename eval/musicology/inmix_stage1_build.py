#!/usr/bin/env python3
"""inmix_stage1_build.py — in-mix interval floor test, STAGE 1 (build mixes).
Kim 2026-08-06: the atlas ladder was the clean isolated-note ceiling; this tests whether a
semitone melodic move SURVIVES inside a full dense mix above the codec floor.

Reconstruct a real multitrack from its LEAF stems (Kim: group/bus mixes must NOT be summed —
this song has none), transpose ONLY the melody stem (vocals) with BUNGEE (never sox), and
build 4 arms over one section, all at an identical sum-gain so Δlatent is comparable:
  orig        = sum(leaf stems)
  min2        = vocals +1 semitone (a small second) + other stems
  fifth       = vocals +7 semitones (calibration anchor) + other stems
  codecnoise  = orig -> mp3@256 -> back (ffmpeg; the codec fidelity-noise floor, in-mix)

RUN WITH THE BUNGEE VENV:  mir/pitch_venv/bin/python eval/musicology/inmix_stage1_build.py
Stage 2 (SAO/.venv, GPU) SAME-encodes the 4 wavs and computes the Δlatent floor test.
"""
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from bungee_python import bungee as B

SRC = Path("/run/media/kim/Mantu/Stems/No Doubt - Don't Speak Multitrack")
MELODY = "04 - Vocals.wav"          # the monophonic melodic line
STEMS = ["01 - Drums.wav", "02 - Bass.wav", "03 - Guitar.wav", "04 - Vocals.wav", "05 - Extras.wav"]
OUT = Path("/home/kim/Projects/SAO/eval/musicology/inmix_floor_2026-08-06")
OUT.mkdir(parents=True, exist_ok=True)
SR = 44100
DUR = 256 * 4096 / SR               # 23.78 s — match the codec-floor 256-frame window
PAD = 1.0                            # bungee edge guard, trimmed off after


def load(name):
    a, sr = sf.read(SRC / name, dtype="float32", always_2d=True)
    assert sr == SR, f"{name} sr={sr}"
    return a  # [N,2]


def shift(a, semis):
    st = B.Bungee(sample_rate=SR, channels=a.shape[1])
    st.set_pitch(2.0 ** (semis / 12.0))
    out = np.asarray(st.process(a.astype(np.float32)), dtype=np.float32)
    if out.ndim == 1:
        out = np.column_stack([out, out])
    return out


def main():
    stems = {n: load(n) for n in STEMS}
    nmin = min(len(v) for v in stems.values())

    # --- pick a dense, vocal-present window: max vocal RMS among full-band windows ---
    def rms(x):
        return float(np.sqrt(np.mean(x ** 2) + 1e-12))
    win = int(DUR * SR); step = int(6 * SR)
    best = None
    for s0 in range(int(20 * SR), min(nmin - win - int(PAD * SR), int(160 * SR)), step):
        w = {n: stems[n][s0:s0 + win] for n in STEMS}
        band = min(rms(w[n]) for n in STEMS if n != MELODY)   # every backing stem playing
        voc = rms(w[MELODY])
        if band > 0.003 and (best is None or voc > best[1]):
            best = (s0, voc, band)
    s0 = best[0]
    print(f"[window] start={s0/SR:.1f}s dur={DUR:.1f}s  vocalRMS={best[1]:.4f} bandRMS={best[2]:.4f}")

    a0 = s0 - int(PAD * SR); a1 = s0 + win + int(PAD * SR)
    seg = {n: stems[n][a0:a1] for n in STEMS}
    p = int(PAD * SR)

    def summix(melody_variant):
        # explicit sum of LEAF stems only (this song has no bus/group-mix track)
        acc = np.zeros((win, 2), dtype=np.float32)
        for n in STEMS:
            s = (melody_variant if n == MELODY else seg[n])[p:p + win]
            acc[:len(s)] += s[:win]
        return acc

    voc_seg = seg[MELODY]
    voc_min2 = shift(voc_seg, 1)
    voc_fifth = shift(voc_seg, 7)
    # bungee preserves length up to a few samples; pad/trim to seg length for windowing
    def fixlen(x, n):
        return x[:n] if len(x) >= n else np.pad(x, ((0, n - len(x)), (0, 0)))
    voc_min2 = fixlen(voc_min2, len(voc_seg))
    voc_fifth = fixlen(voc_fifth, len(voc_seg))

    orig = summix(voc_seg)
    min2 = summix(voc_min2)
    fifth = summix(voc_fifth)

    g = 0.97 / (float(np.max(np.abs(orig))) + 1e-9)   # ONE gain for all arms -> Δ comparable
    orig, min2, fifth = orig * g, min2 * g, fifth * g

    sf.write(OUT / "mix_orig.wav", orig, SR)
    sf.write(OUT / "mix_min2.wav", min2, SR)
    sf.write(OUT / "mix_fifth.wav", fifth, SR)

    # codec-noise arm: orig -> mp3@256 -> back (in-mix codec fidelity floor)
    tmp = OUT / "_orig_for_mp3.wav"; sf.write(tmp, orig, SR)
    subprocess.run(["ffmpeg", "-y", "-i", str(tmp), "-c:a", "libmp3lame", "-b:a", "256k",
                    str(OUT / "_n.mp3")], capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(OUT / "_n.mp3"), str(OUT / "mix_codecnoise.wav")],
                   capture_output=True)
    print(f"[built] {OUT}/mix_{{orig,min2,fifth,codecnoise}}.wav  (gain={g:.3f}, "
          f"melody stem = {MELODY}, {len(STEMS)} leaf stems, no bus)")


if __name__ == "__main__":
    main()
