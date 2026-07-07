#!/usr/bin/env python
"""a2a_fulltrack.py — full-track audio2audio noise-ratio ladder (Kim 2026-07-07).

Runs a whole track through SA3 a2a with a fixed prompt+seed at a ladder of
init_noise_level values. Tracks longer than the 380s model max are processed in
two windows (0..380 + 370..end) joined by an equal-power crossfade in the 10s
overlap. Structure at low noise comes from the init latents, so the windows
stay coherent; at high noise the join may be audible (documented in run_meta).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import json
import time
from pathlib import Path
import sys

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

MAX_SEC = 378.0     # stay just under the 380s model max
OVERLAP = 10.0


def a2a(model, audio, sr, nl, prompt, seed, steps, cfg):
    a = torch.tensor(audio)
    dur = audio.shape[1] / sr
    # generate()'s sample_size PARAMETER defaults to 5292032 (= 120.0 s) and the
    # duration-adaptive sizing clamps to it — callers must pass the real budget
    # or every long request silently truncates to 2 minutes (bit us 2026-07-07).
    ds = model.model.pretransform.downsampling_ratio
    budget = int(np.ceil((dur + 8.0) * sr / ds)) * ds
    out = model.generate(prompt=prompt, duration=dur, steps=steps,
                         cfg_scale=cfg, seed=seed, batch_size=1,
                         sample_size=budget,
                         init_audio=(sr, a), init_noise_level=nl)
    y = out[0].float().cpu().numpy()
    if y.shape[1] < audio.shape[1] * 0.98:           # fail LOUD, never pad silence
        raise RuntimeError(f"a2a output {y.shape[1]/sr:.1f}s << requested {dur:.1f}s")
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--noise-levels", default="0.2,0.3,0.4,0.5,0.6,0.7")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audio, sr = sf.read(args.track, dtype="float32", always_2d=True)
    audio = audio.T  # (C, N)
    total_sec = audio.shape[1] / sr
    nls = [float(x) for x in args.noise_levels.split(",")]

    # window plan
    if total_sec <= MAX_SEC:
        wins = [(0.0, total_sec)]
    else:
        wins = [(0.0, MAX_SEC), (MAX_SEC - OVERLAP, total_sec)]

    meta = {"purpose": ("full-track a2a noise ladder: whole song re-rendered through the "
                        "adapter at increasing init_noise_level — where does it stop being "
                        "the song and start being the model"),
            "track": os.path.basename(args.track), "duration_sec": round(total_sec, 1),
            "prompt": args.prompt, "seed": args.seed, "steps": args.steps,
            "cfg": args.cfg_scale, "noise_levels": nls,
            "windows": wins, "overlap_crossfade_sec": OVERLAP if len(wins) > 1 else 0,
            "checkpoint": args.ckpt,
            "note": "two-window join: seamless at low nl; windows diverge more at high nl"}
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"[load] {args.ckpt}", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device=args.device)
    model.load_lora([args.ckpt])
    msr = model.model.sample_rate
    assert msr == sr, f"sr mismatch {sr} vs {msr}"

    for nl in nls:
        out_path = args.out_dir / f"a2a_nl{int(round(nl*100)):02d}.wav"
        if out_path.exists():
            print(f"[skip] {out_path.name}", flush=True)
            continue
        t0 = time.time()
        pieces = []
        for wi, (lo, hi) in enumerate(wins):
            chunk = audio[:, int(lo * sr):int(hi * sr)]
            y = a2a(model, chunk, sr, nl, args.prompt, args.seed,
                    args.steps, args.cfg_scale)[:, :chunk.shape[1]]
            pieces.append(y)
        if len(pieces) == 1:
            full = pieces[0]
        else:
            n = int(OVERLAP * sr)
            t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
            fo, fi = np.cos(t), np.sin(t)
            head, tail = pieces[0], pieces[1]
            join = head[:, -n:] * fo + tail[:, :n] * fi
            full = np.concatenate([head[:, :-n], join, tail[:, n:]], axis=1)
        save_audio(out_path, torch.tensor(full), sr, normalize=True)
        print(f"[nl {nl:.1f}] {time.time()-t0:6.1f}s -> {out_path.name}", flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
