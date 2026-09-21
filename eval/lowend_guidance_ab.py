#!/usr/bin/env python
"""lowend_guidance_ab.py — can low-end guidance fix the clips Kim called harsh?

THE CHAIN THAT LED HERE (2026-09-16/17). An rms_energy_air head was supposed to damp harsh
high end on post-trained medium and did nothing. Three causes, in order of discovery:
  1. guidance silently swapped the model's native pingpong sampler for euler (FIXED);
  2. the target was the head's own std_mean, i.e. "be corpus-average" -- a ~0.26 sigma
     request that was nearly satisfied before guidance began (grad norms ~1e-5 vs |x|~400);
  3. the BAND was wrong. Measured against Kim's own 167 masters and against unflagged
     siblings, harsh clips are not bright -- they are THIN. Six bands survive Bonferroni
     and every one is low; across the whole 2.5-22 kHz air span, not one.

The severity evidence is the strongest result of that work: on the seven clips Kim called
severe (as opposed to merely "I'd have toned the treble down"), low-mid energy orders
monotonically severe < mild < clean, and ALL SEVEN sit below the 18th percentile of the
other 76. P(7/7 in the bottom 17% by chance) ~ 4e-6.

So: ADD low end rather than cut highs. This renders each severe clip's exact config with and
without low-end guidance, matched seed, and measures what actually moved.

DESIGN DECISIONS, each one a lesson from the failures above:

* TARGETS ARE LARGE ON PURPOSE. The deficit is 3-4 dB, which in bass-head units (sigma
  14.5 dB) is ~0.25 sigma -- the same size as the request that did nothing. Asking for the
  deficit would reproduce that null and teach us nothing. Arms ask +0.5 and +1.0 sigma so
  the request is unambiguous, and a ladder tells us the authority curve instead of one
  ambiguous result.
* A TWO-HEAD ARM expresses the level-invariant target. "More bass" alone is satisfiable by
  making everything louder; bass raised WHILE air is held is a ratio, which is what the
  analysis said the target should be -- assembled from two existing heads, no retraining.
* NATIVE SAMPLER. No sampler_type override: resolve_guided_sampler picks pingpong for
  rf_denoiser. Before the fix this path silently ran euler and every guided render shared
  one wrong-sampler sound.
* z0 IS CAPTURED AND CHECKED. A non-finite latent writes a full-scale DC file that peaks at
  exactly 1.000 while ffprobe reports the right duration (DISCOVERIES 2026-09-08). Healthy
  peaks at 0.8913. We check rather than discover it by ear.
* BANDS ARE MEASURED, NOT ASSUMED. A null needs to distinguish "guidance did not move the
  band" from "it moved the band and that did not help" -- those demand different responses.

CONFOUND, STATED UP FRONT: every severe clip comes from the genre-fusion probe, and those
prompts explicitly ask for thrash-metal aggression fused with goa. Some of the "defect" may
be the model complying with a request for distortion in a genre it has no coverage for. A
cleaner target population would be thin clips from ordinary goa prompts; this set is what
Kim actually flagged, so it is where we start.

Run (needs the GPU lock):
    python3 Misc/filelock.py acquire /home/kim/Projects/SAO/.gpu.lock \
        --handle WINTERMUTE --pid-aware --pid $$
    SAO/.venv/bin/python -u eval/lowend_guidance_ab.py
    python3 Misc/filelock.py release /home/kim/Projects/SAO/.gpu.lock --handle WINTERMUTE
"""
import os

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import json
from pathlib import Path

import numpy as np
import torch

from stable_audio_3 import StableAudioModel

HEADS = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium"
RUNS = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep"
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/lowend_guidance_ab_2026-09-17")

# head standardisation, read from the checkpoints (NOT guessed)
BASS_MEAN, BASS_STD = -21.927, 14.534
AIR_MEAN = -32.961

STEPS, CFG, DURATION, GAIN = 24, 1.0, 47.556, 512.0      # 47.556 s == T512 exactly

# The severe clips, with the exact ep/seed/prompt each was rendered from.
CLIPS = [
    {"tag": "gf_07_s2003", "ep": "epoch=3-step=1196", "seed": 2003,
     "why": "Kim's distortion example; grit 0.2698 = 93rd pct of real goa",
     "prompt": "psychedelic space rock meets 1996 goa trance, acid techno pulse, "
               "thrash metal intensity"},
    {"tag": "gf_13_s2009", "ep": "epoch=6-step=2093", "seed": 2009,
     "why": "'cheesegrater timbre'; lowest low-mid of the severe set (6.42 dB)",
     "prompt": "psychedelic acid techno, thrash metal aggression, synth arpeggios, "
               "melodic goa trance hook"},
    {"tag": "gf_09_s2005", "ep": "epoch=6-step=2093", "seed": 2005,
     "why": "'vast 8dB bump 1.5-4.5k', midrange crunch",
     "prompt": "1996 goa trance with distorted thrash metal riffs and acid techno "
               "percussion, upbeat"},
]


def bass_target(k):
    return BASS_MEAN + k * BASS_STD


ARMS = [
    ("baseline", None),
    ("bass_p50", [{"model_path": f"{HEADS}/latch_sa3_rms_energy_bass_best.pt",
                   "kind": "constant", "value": bass_target(0.5)}]),
    ("bass_p100", [{"model_path": f"{HEADS}/latch_sa3_rms_energy_bass_best.pt",
                    "kind": "constant", "value": bass_target(1.0)}]),
    # the level-invariant arm: raise bass WHILE holding air, i.e. a ratio
    ("bass_p100_air_held", [
        {"model_path": f"{HEADS}/latch_sa3_rms_energy_bass_best.pt",
         "kind": "constant", "value": bass_target(1.0)},
        {"model_path": f"{HEADS}/latch_sa3_rms_energy_air_best.pt",
         "kind": "constant", "value": AIR_MEAN}]),
]


def measure(path):
    """Level-anchored band balance, same convention as the analysis that motivated this."""
    import soundfile as sf
    a, sr = sf.read(str(path), always_2d=True)
    x = a.mean(axis=1)
    n = len(x)
    x = x[int(.2 * n):int(.8 * n)]
    N = 8192
    win = np.hanning(N)
    step = N // 2
    m = (len(x) - N) // step
    if m < 4:
        return None
    idx = np.unique(np.linspace(0, m - 1, min(m, 160)).astype(int))
    acc = np.zeros(N // 2 + 1)
    for i in idx:
        acc += np.abs(np.fft.rfft(x[i * step:i * step + N] * win)) ** 2
    acc /= len(idx)
    f = np.fft.rfftfreq(N, 1 / sr)

    def E(lo, hi):
        s = (f >= lo) & (f < hi)
        return 10 * np.log10(acc[s].mean() + 1e-20) if s.any() else float("nan")

    anc = E(1000, 3000)
    return {"bass": E(20, 120) - anc, "body": E(120, 600) - anc,
            "mid": E(600, 2500) - anc, "air": E(2500, 16000) - anc,
            "peak": float(np.max(np.abs(a)))}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from sa3_control.audio_io import save_audio

    results = []
    model = None
    loaded_ep = None
    for clip in CLIPS:
        ckpt = f"{RUNS}/{clip['ep']}.weights.ckpt"
        if loaded_ep != clip["ep"]:
            print(f"\n[load] medium (post-trained) + {clip['ep']}", flush=True)
            model = StableAudioModel.from_pretrained("medium", device="cuda")
            model.load_lora([ckpt])
            loaded_ep = clip["ep"]
            sr = model.model.sample_rate
        for arm, latch in ARMS:
            name = f"{clip['tag']}__{arm}"
            wav = OUT / f"{name}.wav"
            if wav.exists():
                print(f"[skip] {name}", flush=True)
                continue
            print(f"[gen] {name}", flush=True)
            sink = []
            kw = dict(prompt=clip["prompt"], duration=DURATION, steps=STEPS,
                      cfg_scale=CFG, seed=clip["seed"], batch_size=1, latents_sink=sink)
            if latch:
                kw["latch_configs"] = latch
                kw["latch_hparams"] = {"rho": GAIN, "mu": GAIN}
            out = model.generate(**kw)
            save_audio(str(wav), out[0].float().cpu(), sr)
            z_ok = bool(torch.isfinite(sink[0]).all()) if sink else None
            z_std = float(sink[0].float().std()) if sink else None
            b = measure(wav)
            if b and abs(b["peak"] - 1.0) < 1e-6:
                print(f"  [FAIL] {name}: peak exactly 1.000 -> the NaN/DC failure, "
                      f"not a guidance result", flush=True)
            results.append({"clip": clip["tag"], "arm": arm, "z0_finite": z_ok,
                            "z0_std": z_std, **(b or {})})
            print(f"   z0 finite={z_ok} std={z_std:.3f}  "
                  f"bass {b['bass']:+.2f}  body {b['body']:+.2f}  air {b['air']:+.2f}"
                  if b else "   (measure failed)", flush=True)

    print(f"\n{'clip':16s} {'arm':20s} {'bass':>7s} {'body':>7s} {'air':>7s} "
          f"{'bass-air':>9s}")
    print("-" * 72)
    base = {}
    for r in results:
        if r.get("bass") is None:
            continue
        if r["arm"] == "baseline":
            base[r["clip"]] = r
        d = ""
        if r["clip"] in base and r["arm"] != "baseline":
            d = f"   (bass {r['bass']-base[r['clip']]['bass']:+.2f} vs baseline)"
        print(f"{r['clip']:16s} {r['arm']:20s} {r['bass']:7.2f} {r['body']:7.2f} "
              f"{r['air']:7.2f} {r['bass']-r['air']:9.2f}{d}")

    json.dump({"purpose": "Does adding low end fix clips Kim called harsh? The harshness "
                          "signature is a low-mid deficit (7/7 severe clips below the 18th "
                          "percentile), so this ADDS bass rather than cutting air.",
               "targets_are_large_on_purpose": "the 3-4 dB deficit is ~0.25 sigma, the same "
                          "size as the request that produced ~1e-5 gradients and did nothing; "
                          "arms ask 0.5 and 1.0 sigma instead",
               "confound": "all severe clips come from genre-fusion prompts that explicitly "
                          "request thrash-metal aggression; some 'defect' may be compliance",
               "steps": STEPS, "cfg": CFG, "duration_s": DURATION, "gain": GAIN,
               "sampler": "native (pingpong for rf_denoiser)",
               "results": results, "kim_feedback": None},
              open(OUT / "run_meta.json", "w"), indent=2)
    print(f"\n[done] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
