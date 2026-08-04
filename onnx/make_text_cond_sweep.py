#!/usr/bin/env python
"""make_text_cond_sweep.py — precache text cond/uncond npzs for the DoRA
quality/weight/length sweep (Kim, 2026-07-05/06). Generalizes make_text_cond.py
(same cdm.conditioner()-direct workaround) across multiple prompts x length rungs.

Prompts chosen by RANK in the merged 5-corpus caption frequency table (t1 tier,
6110 captions, 1882 unique) -- the count distribution is extremely long-tailed
(median count = 2, so percentile-of-count degenerates; rank position in the
frequency-sorted list is the meaningful axis instead):
  COMMON: rank 1/1882   (n=60) "2020s goa trance, 145 bpm"
  MEDIUM: rank ~50%      (n=2)  "early 90s techno, house, 128 bpm"
  RARE:   rank ~85%      (n=2)  "ambient, experimental, dark soundscape mood, 107 bpm"

Length rungs (T frames -> seconds_total, hop=4096 @ 44.1kHz): 256->23.775,
512->47.550, 1024->95.100, 4096->380.436.

    SA3 venv:  /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python
    python make_text_cond_sweep.py --out-dir /home/kim/Projects/SAO/onnx/exports/textcond
"""
import argparse
import os
os.environ["SA3_DISABLE_FLASH_ATTN"] = "1"
from pathlib import Path

import numpy as np

from make_text_cond import load_conditioner, build_text_cond

SEQ = 128
SAMPLE_RATE = 44100
HOP = 4096

PROMPTS = {
    "common": "2020s goa trance, 145 bpm",
    "medium": "early 90s techno, house, 128 bpm",
    "rare": "ambient, experimental, dark soundscape mood, 107 bpm",
}
LENGTHS = [256, 512, 1024, 4096]


def seconds_for(T: int) -> float:
    return T * HOP / SAMPLE_RATE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--lengths", type=int, nargs="+", default=LENGTHS)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[load] medium-base on CPU (incl T5-Gemma conditioner) ...", flush=True)
    cdm = load_conditioner("medium-base")

    for T in args.lengths:
        seconds = seconds_for(T)
        print(f"\n=== T={T} ({seconds:.3f}s) ===")

        u = build_text_cond(cdm, "", seconds, SEQ, T)
        u_out = args.out_dir / f"uncond_T{T}.npz"
        np.savez(u_out, cross_attn_cond=u[0], cross_attn_mask=u[1], global_embed=u[2])
        print(f"  [uncond] -> {u_out.name}  mask_sum={int(u[1].sum())}/{SEQ}")

        for label, prompt in PROMPTS.items():
            c = build_text_cond(cdm, prompt, seconds, SEQ, T)
            c_out = args.out_dir / f"cond_{label}_T{T}.npz"
            np.savez(c_out, cross_attn_cond=c[0], cross_attn_mask=c[1], global_embed=c[2])
            print(f"  [cond:{label}] {prompt!r} -> {c_out.name}  mask_sum={int(c[1].sum())}/{SEQ}")

    print("\n[done] all cond/uncond npzs written to", args.out_dir)


if __name__ == "__main__":
    main()
