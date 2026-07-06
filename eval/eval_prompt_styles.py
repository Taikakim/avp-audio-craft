#!/usr/bin/env python
"""eval_prompt_styles.py — GPU audition: usual prompts vs Stability-recommended style.

Renders the newcap 8ep continuation (+ ep4 + base reference) with BOTH prompt
styles, per Kim 2026-07-06:
  - PLAIN: the usual eval prompts (p1 replaced: the acid-techno prompt rendered
    consistently badly -> "Hypnotic melodic goa trance").
  - STYLED: the SA3-paper / docs/guides/prompting.md convention — the
    "TrackType: Music, VocalType: Instrumental," prefix + AudioSparx `Genre:`
    field tags. The base model trained with these present ~50% of the time and
    Stability recommends them at inference ("significantly improve quality").

GPU path (fp16 + CK flash-attn, MASTER §5 env). Usual eval params otherwise:
47 s, 16 steps, cfg 6, seeds 1234 + 4242. Writes run_meta.json.

Run:
    cd /home/kim/Projects/SAO/stable-audio-3
    FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
      .venv/bin/python ../eval/eval_prompt_styles.py --out-dir <dir>
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

TT = "TrackType: Music, VocalType: Instrumental, "

# (label, plain, styled) — styled = TT prefix + Genre field tags + the plain text.
PROMPTS = [
    ("aggr",  "aggressive upbeat goa trance",
              TT + "Genre: Goa Trance, aggressive upbeat goa trance"),
    ("hypno", "Hypnotic melodic goa trance",
              TT + "Genre: Goa Trance, Genre: Psychedelic Trance, hypnotic melodic goa trance"),
    ("psy",   "psytrance, 140 bpm",
              TT + "Genre: Psychedelic Trance, psytrance, 140 BPM"),
]

DEFAULT_ARMS = {
    "base":    None,
    "newcap5": "/run/media/kim/Mantu1/sa3_lora_runs/dora128_47s_newcaptions_5ep/epoch=4-step=6750.ckpt",
    "newcap8": "/home/kim/Projects/sa3_local_runs/dora128_newcap_continued_3more/epoch=2-step=4050.ckpt",
    # the everything-corpus 8ep LR pair (normal vs 3x) — Kim's LR-sweep comparison
    "evr1x":   "/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt",
    "evr3x":   "/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr3x/epoch=7-step=12216.ckpt",
}

# per-arm adapter strength (set_lora_strength after load); "arm@S" in --arms also works.
# Kim 2026-07-07: full-strength lr3x = "collages of disjointed things, same as with
# images" -> try it diluted to a third.
ARM_STRENGTH = {"evr3x_w033": ("evr3x", 0.33)}


def render_arm(arm, ckpt, out_dir, steps, duration, cfg, seeds, device, strength=1.0):
    print(f"[load] medium-base on {device} ...", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device=device)
    if ckpt:
        print(f"[lora] {arm}: {ckpt} (strength {strength})", flush=True)
        model.load_lora([str(ckpt)])
        if strength != 1.0:
            model.set_lora_strength(strength)
    sr = model.model.sample_rate
    for label, plain, styled in PROMPTS:
        for style, prompt in (("plain", plain), ("styled", styled)):
            for seed in seeds:
                out = out_dir / f"{arm}__{label}_{style}_s{seed}.wav"
                if out.exists():
                    print(f"[skip] {out.name}", flush=True)
                    continue
                t0 = time.time()
                audio = model.generate(prompt=prompt, duration=duration, steps=steps,
                                       cfg_scale=cfg, seed=seed, batch_size=1)
                a = audio[0]
                save_audio(out, a, sr, normalize=True)
                print(f"[clip] {out.name}  {time.time()-t0:5.1f}s  "
                      f"finite={bool(torch.isfinite(a).all())}", flush=True)
    del model
    if device == "cuda":
        torch.cuda.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--arms", default="base,newcap5,newcap8",
                    help="comma list from: " + ",".join(DEFAULT_ARMS))
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--duration", type=float, default=47.0)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--seeds", default="1234,4242")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    arms = {}   # name -> (ckpt_path_or_None, strength)
    for a in args.arms.split(","):
        if a in ARM_STRENGTH:
            base, s = ARM_STRENGTH[a]
            arms[a] = (DEFAULT_ARMS[base], s)
        elif "@" in a:
            base, s = a.split("@")
            arms[a.replace("@", "_w").replace(".", "")] = (DEFAULT_ARMS[base], float(s))
        else:
            arms[a] = (DEFAULT_ARMS[a], 1.0)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "purpose": ("plain-vs-Stability-styled prompt A/B (TrackType prefix + Genre tags, "
                    "prompting.md convention) on the newcap 8ep continuation; p1 replaced "
                    "per Kim (acid techno rendered badly) with 'Hypnotic melodic goa trance'"),
        "checkpoints": {a: ((p or "medium-base (no adapter)") +
                            (f" @strength {s}" if s != 1.0 else ""))
                        for a, (p, s) in arms.items()},
        "gen": {"duration": args.duration, "steps": args.steps, "cfg": args.cfg_scale,
                "seeds": seeds},
        "prompts": {lab: {"plain": pl, "styled": st} for lab, pl, st in PROMPTS},
        "related": ["SAO/eval/eval_prompt_styles.py",
                    "SAO/papers/arxiv-2605.17991.md (TrackType recommendation)",
                    "stable-audio-3/docs/guides/prompting.md"],
    }
    # merge with an existing sidecar so multi-pass renders (extra --arms into the
    # same dir) accumulate checkpoints instead of clobbering the record
    meta_path = args.out_dir / "run_meta.json"
    if meta_path.exists():
        old = json.loads(meta_path.read_text())
        old.get("checkpoints", {}).update(meta["checkpoints"])
        meta["checkpoints"] = old.get("checkpoints", meta["checkpoints"])
    meta_path.write_text(json.dumps(meta, indent=2))

    for arm, (ckpt, strength) in arms.items():
        render_arm(arm, ckpt, args.out_dir, args.steps, args.duration,
                   args.cfg_scale, seeds, args.device, strength=strength)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
