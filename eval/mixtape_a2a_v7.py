#!/usr/bin/env python
"""mixtape_a2a_v7.py — window-local a2a smoothing on the v7 plain mix (spec R0.5).

WHY (GHOST-NOTE 2026-10-07; project guidance: do the a2a transitions for good measure while the GPU is held).
v6's a2a re-encoded whole pair composites, which changed timbre at joins. Here ONLY [window - 2 bars,
window + 2 bars] of the finished v7 plain mix is processed (sine-bump depth <= nl, 0 at the window edges, via
chain_simple_crossfade.a2a_smooth_window), gain-matched to the plain segment, and blended back with a 1-bar
equal-power ramp at both segment edges. Adapter merged after load (training-findings 13e). A transition whose
a2a output carries more sample jumps than the plain segment falls back to plain (logged).
Never changes the placement timeline: output has exactly the plain mix's length, so the same timeline.json and
audits apply.

RUN (GPU; take the lock via Misc/gpu_guard.sh, hold it for the whole job; run from the eval dir):
  ROCR_VISIBLE_DEVICES=0 /home/kim/Projects/SAO/.venv/bin/python mixtape_a2a_v7.py --dir <mixtape_v7_phase0>
Outputs: <dir>/mixtape_full_a2a.wav and <dir>/a2a_report.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chain_simple_crossfade as csc  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

SR = 44100


def jumps(x, thr=0.6):
    return int((np.abs(np.diff(x, axis=1)).max(0) > thr).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--nl", type=float, default=0.7)
    ap.add_argument("--pad-bars", type=int, default=2)
    ap.add_argument("--blend-bars", type=int, default=1)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    d = Path(a.dir)
    tl = json.loads((d / "timeline.json").read_text())
    meta = json.loads((d / "run_meta.json").read_text())
    mix, sr = sf.read(str(d / "mixtape_full_plain.wav"), dtype="float32")
    assert sr == SR
    mix = mix.T.copy()
    out = mix.copy()

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([csc.BRIDGE_CKPT])
    from model_matrix_gen import merge_adapters
    print(f"[merge] merged {merge_adapters(model.model)} adapter parametrizations", flush=True)
    msr = model.model.sample_rate
    assert msr == SR

    report = []
    trans = tl["trans"][:a.limit] if a.limit else tl["trans"]
    for k, (t0, t1) in enumerate(trans):
        W = meta["transitions"][k]["window_bars"]
        bar = (t1 - t0) / W
        s0 = max(0.0, t0 - a.pad_bars * bar)
        s1 = min(mix.shape[1] / SR, t1 + a.pad_bars * bar)
        i0, i1 = round(s0 * SR), round(s1 * SR)
        seg = mix[:, i0:i1].copy()
        dur = seg.shape[1] / SR
        z = csc.a2a_smooth_window(model, seg, SR, t0 - s0, t1 - t0, a.nl, a.prompt, a.steps, a.cfg_scale,
                                  a.seed)
        z = np.asarray(z, dtype=np.float32)
        if z.ndim == 1:
            z = z[None, :]
        n = seg.shape[1]
        z = z[:, :n] if z.shape[1] >= n else np.pad(z, ((0, 0), (0, n - z.shape[1])))
        g = float(np.sqrt((seg ** 2).mean() / max((z ** 2).mean(), 1e-12)))
        z = z * g
        jp, jz = jumps(seg), jumps(z)
        ok = bool(np.isfinite(z).all()) and jz <= jp + 6
        if ok:
            nb = round(a.blend_bars * bar * SR)
            w = np.ones(n, dtype=np.float32)
            ramp = np.sin(np.linspace(0, np.pi / 2, min(nb, n // 2), dtype=np.float32)) ** 2
            w[:len(ramp)] = ramp
            w[n - len(ramp):] = ramp[::-1]
            out[:, i0:i1] = seg * (1 - w) + z * w                 # equal-power-ish (sin^2 / cos^2 sums to 1)
        report.append({"trans": k, "t0": t0, "t1": t1, "seg_sec": dur, "gain": g, "jumps_plain": jp,
                       "jumps_a2a": jz, "used_a2a": ok})
        print(f"[a2a] {k:02d} {dur:.1f}s gain {g:.2f} jumps plain {jp} a2a {jz} -> {'a2a' if ok else 'PLAIN (fallback)'}",
              flush=True)
        (d / "a2a_report.json").write_text(json.dumps(report, indent=1))

    sf.write(str(d / "mixtape_full_a2a.wav"), out.T, SR, subtype="PCM_16")
    print(f"[done] {sum(r['used_a2a'] for r in report)}/{len(report)} transitions smoothed", flush=True)


if __name__ == "__main__":
    main()
