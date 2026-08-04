#!/usr/bin/env python
"""measure_density_control_onsets.py — cheap librosa onset-density measurement pass
over a density_control_eval.py output dir (arm x prompt x style x seed x condition x
density wavs). CPU-only (mir venv, has librosa) -- the control-authority readout for
the eval-grid UI, same onset_density() approach as sa3_control/multi_eval.py.

    /home/kim/Projects/mir/mir/bin/python measure_density_control_onsets.py <dir>

Writes <dir>/_onset_measurements.json, keyed by clip stem.
"""
import argparse
import glob
import json
import os
import re

import librosa

FNAME_RE = re.compile(
    r"^(?P<prompt>\w+)_(?P<style>plain|styled)_s(?P<seed>\d+)$"
)
COND_RE = re.compile(r"^(?P<cond>latch|film|both)_d(?P<density>\d+)$")


def onset_density(path):
    y, sr = librosa.load(path, sr=None, mono=True)
    dur = len(y) / sr
    if dur <= 0:
        return None
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    return len(onsets) / dur


def parse_stem(stem):
    parts = stem.split("__")
    if len(parts) != 3:
        return None
    arm, mid, cond_part = parts
    m1 = FNAME_RE.match(mid)
    m2 = COND_RE.match(cond_part)
    if not (m1 and m2):
        return None
    return {
        "arm": arm, "prompt": m1["prompt"], "style": m1["style"], "seed": int(m1["seed"]),
        "condition": m2["cond"], "requested_density": int(m2["density"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out_path = args.out or os.path.join(args.dir, "_onset_measurements.json")

    results = {}
    if os.path.exists(out_path):
        try:
            results = json.load(open(out_path))
        except Exception:
            results = {}

    wavs = sorted(glob.glob(os.path.join(args.dir, "*.wav")))
    todo = [p for p in wavs if os.path.splitext(os.path.basename(p))[0] not in results]
    print(f"[measure] {len(wavs)} wavs, {len(todo)} to measure ({len(results)} cached)", flush=True)
    for i, path in enumerate(todo):
        fn = os.path.basename(path)
        stem = os.path.splitext(fn)[0]
        parsed = parse_stem(stem)
        if not parsed:
            print(f"[skip] unparsed: {fn}", flush=True)
            continue
        try:
            measured = onset_density(path)
        except Exception as e:
            print(f"[err] {fn}: {e}", flush=True)
            continue
        results[stem] = {**parsed, "measured_density": round(measured, 3)}
        if (i + 1) % 25 == 0 or i + 1 == len(todo):
            json.dump(results, open(out_path, "w"), indent=1)
            print(f"[{i+1}/{len(todo)}] {fn} -> {measured:.2f}", flush=True)

    json.dump(results, open(out_path, "w"), indent=1)
    print(f"[done] {len(results)}/{len(wavs)} measured -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
