#!/usr/bin/env python3
"""
reverb_eval.py -- AudioCommons RT60 / reverb_prob / depth on EVAL render clips (Kim 2026-07-22:
the reverb axis for the pad-fill theory -- "the model papers over under-constrained regions with
reverby atmosphere"). Companion to eval/spectral_fidelity.py; reference baseline is
mir/stats/reverb_depth_baseline.csv (goa rt60 0.896, avp 0.871).

timbral_reverb/timbral_depth take a FILE PATH and read via soundfile (no m4a) and timbral_reverb
can hang -> decode each clip to a /dev/shm wav first, per-file SIGALRM timeout (from
extract_reverb_depth.py). mir venv, CPU, GPU-free, SLOW (~10-30 s/clip) -> sample, background.

Run: mir/bin/python eval/reverb_eval.py --models bf16cmp_goa_t512_bs8_lr1e4 fp32cmp_goa_t512_bs8_lr1e4 \
        --sample-per-model 40 --out /tmp/reverb_eval.csv
"""
import argparse
import csv
import os
import signal
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/mir/repos/timbral_models")
CLIPS = Path.home() / ".cache/evals_aac/model_matrix"
CLAP = Path("/home/kim/Projects/SAO/eval/clap_degen_model_matrix.csv")
TIMEOUT = 90


class _TO(Exception):
    pass


def _alarm(sig, frm):
    raise _TO()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+")
    ap.add_argument("--sample-per-model", type=int, default=40)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    import numpy as np
    import soundfile as sf
    import timbral_models as T
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    from core.file_utils import read_audio

    signal.signal(signal.SIGALRM, _alarm)
    rows = [r for r in csv.DictReader(open(CLAP)) if r.get("duration_mode") != "native"]
    if a.models:
        rows = [r for r in rows if r["model"] in a.models]
    by = {}
    for r in rows:
        by.setdefault(r["model"], []).append(r)
    sel = []
    for rs in by.values():
        step = max(1, len(rs) // a.sample_per_model)
        sel += rs[::step][:a.sample_per_model]
    print(f"[reverb] {len(sel)} clips over {len(by)} models")

    out = []
    for i, r in enumerate(sel):
        p = CLIPS / r["file"]
        if not p.exists():
            continue
        tmp = None
        try:
            audio, sr = read_audio(str(p))                 # handles m4a
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            fd, tmp = tempfile.mkstemp(suffix=".wav", dir="/dev/shm")
            os.close(fd)
            sf.write(tmp, audio, sr)
            signal.alarm(TIMEOUT)
            rt60, prob = T.timbral_reverb(tmp, dev_output=True)
            depth = T.timbral_depth(tmp)
            signal.alarm(0)
        except _TO:
            print(f"[reverb] TIMEOUT {r['file']}")
            continue
        except Exception as ex:
            signal.alarm(0)
            print(f"[reverb] skip {r['file']}: {ex}")
            continue
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        out.append({"file": r["file"], "model": r["model"], "ckpt": r["ckpt"],
                    "cfg": r["cfg"], "strength": r["strength"], "clap_matched": r.get("clap_matched"),
                    "rt60": round(float(rt60), 4), "reverb_prob": round(float(prob), 4),
                    "depth": round(float(depth), 4)})
        if (i + 1) % 20 == 0:
            print(f"[reverb] {i + 1}/{len(sel)}")

    with a.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "model", "ckpt", "cfg", "strength",
                                          "clap_matched", "rt60", "reverb_prob", "depth"])
        w.writeheader()
        w.writerows(out)
    print(f"[reverb] wrote {a.out} ({len(out)} clips)")


if __name__ == "__main__":
    main()
