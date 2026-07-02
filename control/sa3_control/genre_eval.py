"""genre_eval.py — render a genre-steering grid for a fingerprint STYLE adapter.

The test RF val loss can't do: does setting a target genre in the fingerprint actually
move the OUTPUT's genre? Holds the text prompt constant (neutral) and varies ONLY the
fingerprint genre block, so any genre shift in the render is attributable to the adapter.

Run with the SA3 .venv:
    PYTORCH_TUNABLEOP_ENABLED=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
    .venv/bin/python -m sa3_control.genre_eval \
        --adapter <run>/riffer_final.pt --out-dir <dir> --baseline

Renders WAVs + writes manifest.json. Measure genre separately with the mir discogs head
(measure_genre.py, mir venv). The fingerprint layout (pre-normalized, per _build_fingerprint):
    genre(K) | other(1) | year(1) | [A/B: bpm(1) sync(1)] | [B: onset(1) energy(1)]
Neutral dims are 0 (= normalized mean); target genre set to 1.0; all-zero = the cfg null.
"""
import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch

from sa3_control.adapters import ControlContext, use_control_context
from sa3_control.audio_io import save_audio
from sa3_control.inject import install_adapters
from sa3_control.generate import build_conditioner, load_adapter_state


def _slug(label: str) -> str:
    return label.split("---")[-1].replace(" ", "").replace("-", "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--genres", default="0,3,5,8", help="vocab indices to steer to")
    ap.add_argument("--gains", default="6,12")
    ap.add_argument("--prompt", default="electronic music", help="held constant across genres")
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--seeds", default="1234")
    ap.add_argument("--baseline", action="store_true", help="also render the null-fingerprint baseline")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    ck = torch.load(args.adapter, map_location="cpu")
    cargs = ck.get("args", {})
    control_dim = int(cargs.get("control_dim", 768))
    in_dim = int(ck["fp_in_dim"])
    variant = ck.get("fp_variant", "?")
    vocab = ck.get("genre_vocab") or []

    device = "cuda" if torch.cuda.is_available() else "cpu"
    from stable_audio_3 import StableAudioModel
    sam = StableAudioModel.from_pretrained(args.model, device=device)
    model_dtype = next(sam.model.model.parameters()).dtype

    wrappers = install_adapters(sam, control_dim=control_dim)
    cond_enc = build_conditioner(ck, device, model_dtype)
    load_adapter_state(ck["state"], wrappers, cond_enc)
    for w in wrappers:
        w.adapter.to(device=device, dtype=model_dtype)
    cond_enc.to(device=device, dtype=model_dtype).eval()

    genres = [int(x) for x in args.genres.split(",")]
    gains = [float(x) for x in args.gains.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]
    manifest = []

    def render(fp_vec, gidx, gname, gain, seed, tag):
        with torch.inference_mode():
            ctrl = cond_enc(fp_vec[None].to(device=device, dtype=model_dtype))   # (1, n, d)
        if args.cfg != 1.0:                                                       # CFG: cond=ctrl, uncond=0
            ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
        with use_control_context(ControlContext(ctrl, gain=gain)):
            audio = sam.generate(prompt=args.prompt, duration=args.duration, steps=args.steps,
                                 cfg_scale=args.cfg, seed=seed, sampler_type="euler")
        out = os.path.join(args.out_dir, tag + ".wav")
        save_audio(out, audio[0], sam.model.sample_rate)
        manifest.append({"file": tag + ".wav", "variant": variant, "genre_idx": gidx,
                         "genre": gname, "gain": gain, "seed": seed})
        print(f"[genre_eval] {tag}", flush=True)

    for seed in seeds:
        if args.baseline:
            render(torch.zeros(in_dim), -1, "baseline", gains[0], seed,
                   f"{variant}_baseline_gain{gains[0]:g}_s{seed}")
        for g in genres:
            gname = vocab[g].split("---")[-1] if g < len(vocab) else f"g{g}"
            for gain in gains:
                fp = torch.zeros(in_dim)
                fp[g] = 1.0                                                       # target genre = strong
                render(fp, g, gname, gain, seed,
                       f"{variant}_{g:02d}{_slug(vocab[g] if g < len(vocab) else str(g))}_gain{gain:g}_s{seed}")

    with open(os.path.join(args.out_dir, "manifest.json"), "w") as f:
        json.dump({"adapter": args.adapter, "variant": variant, "prompt": args.prompt,
                   "duration": args.duration, "steps": args.steps, "cfg": args.cfg,
                   "vocab": vocab, "clips": manifest}, f, indent=1)
    print(f"[genre_eval] {len(manifest)} clips -> {args.out_dir}", flush=True)
    sys.stdout.flush()
    os._exit(0)   # bypass the ROCm/torch teardown core-dump (outputs are already written)


if __name__ == "__main__":
    main()
