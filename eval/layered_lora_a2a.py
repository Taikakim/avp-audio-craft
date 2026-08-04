#!/usr/bin/env python
"""layered_lora_a2a.py — per-LAYER staggered LoRA onset for gradual a2a morph (Kim 2026-07-11).

Kim's idea: don't apply the adapter uniformly — ramp EACH DiT block's LoRA strength at a
DIFFERENT rate so the style emerges gradually (shallow blocks = structure/rhythm cross
first, deep blocks = surface/timbre lag), a smoother morph than a uniform switch. Each
LoRAParametrization has its own lora_strength buffer, so per-layer control is a real knob
(global set_lora_strength just fills them all uniformly).

Per window k (t = k/(N-1) across the track), layer i (depth_frac in [0,1] shallow->deep):
    strength_i(t) = clamp01( t*(1+spread) - depth_frac_i*spread )
  spread=0 -> uniform ramp (the baseline); spread>0 -> shallow leads, deep lags.

Run (SA3 venv, GPU): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/layered_lora_a2a.py ...
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse, json, re, sys
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sa3_control.audio_io import save_audio                    # noqa: E402
from stable_audio_3 import StableAudioModel                    # noqa: E402
from stable_audio_3.models.lora.model import LoRAParametrization  # noqa: E402
from breathing_a2a import plan_windows, _crossfade_join        # noqa: E402


def lora_layers(model):
    """(param, depth_frac shallow->deep) for every LoRA param, depth from the module name."""
    named = []
    for name, mod in model.model.model.named_modules():
        plist = getattr(getattr(mod, "parametrizations", None), "weight", None)
        if plist is None:
            continue
        m = re.search(r"(?:layers?|blocks?)\.(\d+)\b", name)
        depth = int(m.group(1)) if m else 0
        for p in plist:
            if isinstance(p, LoRAParametrization):
                named.append((p, depth, name))
    depths = sorted({d for _, d, _ in named})
    dmax = max(depths[-1], 1)
    return [(p, d / dmax) for p, d, _ in named], len(depths)


def set_layered_strength(layers, t, spread):
    for p, df in layers:
        s = min(1.0, max(0.0, t * (1.0 + spread) - df * spread))
        p.lora_strength.fill_(float(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--prompts-json", default=None,
                    help="JSON list of rich section prompts (Kim's arc); windows mapped evenly "
                         "across sections. Tests the per-layer interleave under DIFFERENT prompts.")
    ap.add_argument("--only", choices=["staggered", "uniform", "both"], default="both",
                    help="which pass(es) to render; 'staggered' = just the interleaved one")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--nl", type=float, default=0.55)
    ap.add_argument("--window-sec", type=float, default=25.0)
    ap.add_argument("--overlap-sec", type=float, default=5.0)
    ap.add_argument("--spread", type=float, default=1.0, help="0=uniform ramp, 1=full stagger")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audio, sr = sf.read(args.track, dtype="float32", always_2d=True)
    audio = audio.T
    wins = plan_windows(audio.shape[1] / sr, args.window_sec, args.overlap_sec)
    n = len(wins)
    prompts = json.load(open(args.prompts_json)) if args.prompts_json else [args.prompt]

    def prompt_for(k):
        return prompts[min(len(prompts) - 1, int(k * len(prompts) / n))]  # even section map

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    layers, n_depths = lora_layers(model)
    print(f"[layered] {len(layers)} LoRA params across {n_depths} DiT depths; {n} windows", flush=True)

    def render(tag, spread):
        import torch
        pieces, traj = [], []
        for k, (lo, hi) in enumerate(wins):
            t = k / max(n - 1, 1)
            set_layered_strength(layers, t, spread)
            traj.append(round(min(1.0, max(0.0, t * (1.0 + spread))), 3))   # shallow-layer strength
            chunk = audio[:, int(lo * sr):int(hi * sr)]
            dur = chunk.shape[1] / sr
            ds = model.model.pretransform.downsampling_ratio
            budget = int(np.ceil((dur + 8.0) * sr / ds)) * ds
            pr = prompt_for(k)
            out = model.generate(prompt=pr, duration=dur, steps=args.steps,
                                 cfg_scale=args.cfg_scale, seed=args.seed, batch_size=1,
                                 sample_size=budget, init_audio=(sr, torch.tensor(chunk)),
                                 init_noise_level=float(args.nl))
            pieces.append(out[0].float().cpu().numpy()[:, :chunk.shape[1]])
            print(f"[{tag} w{k:02d}] t={t:.2f} shallow_str={traj[-1]} :: {pr[:44]}", flush=True)
        save_audio(args.out_dir / f"{tag}.wav", torch.tensor(_crossfade_join(pieces, sr, args.overlap_sec)), sr, normalize=True)
        return traj

    stag = render("staggered", args.spread) if args.only in ("staggered", "both") else None
    unif = render("uniform", 0.0) if args.only in ("uniform", "both") else None
    arc = args.prompts_json is not None
    (args.out_dir / "run_meta.json").write_text(json.dumps(
        {"purpose": "per-layer staggered LoRA onset (Kim): style emerges shallow(structure)->deep"
                    "(timbre) gradually vs uniform ramp. fixed nl a2a, adapter strength 0->1 across track."
                    + (" WITH prompt-arc: tests whether the slow per-layer interleave smooths the "
                       "morph even under DIFFERENT section prompts (Kim's .75 ask)." if arc else ""),
         "track": os.path.basename(args.track), "ckpt": args.ckpt,
         "prompt": args.prompt, "prompts_json": args.prompts_json,
         "prompts": prompts if arc else None, "per_window_prompt": [prompt_for(k)[:60] for k in range(n)] if arc else None,
         "seed": args.seed, "nl": args.nl, "spread": args.spread, "n_depths": n_depths, "only": args.only,
         "shallow_strength_traj": stag, "uniform_strength_traj": unif}, indent=2, default=float))
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
