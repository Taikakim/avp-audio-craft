#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-13)
"""render_fp8_clips.py -- same seed, same prompt: stock bf16 DiT against the FP8-linears DiT (and, if flash_attn is installed, CK attention).

WHY (GHOST-NOTE 2026-10-13, the owner asked for "a few test clips with both base medium and one of our good models"). Timing says whether FP8
is fast; only listening and a latent comparison say whether it is HARMLESS. For each model (medium-base alone, medium-base + a DoRA checkpoint
from good-ckpts, merged into the weights as model_matrix_gen does: training-findings 13e) and each prompt: render arm `bf16` and arm `fp8`
with the SAME seed, 24 steps / cfg 7 (the medium-base operating point), 20 s. Reports, per clip, the cosine / relative error of the decoded
waveforms and the render time; writes <out>/<model>__<prompt>__<arm>.wav (peak-normalised float -> never raw clipping) and a m4a at 256 kbps.

RUN: ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE <venv>/bin/python eval/render_fp8_clips.py --out DIR [--lora CKPT --lora-name NAME]
(Run from a scratch cwd, not the SAO root. Needs the GPU: take the lock first.)
"""
import argparse
import json
import os
import subprocess
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import numpy as np
import soundfile as sf
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fp8_linear as f8  # noqa: E402

PROMPTS = {
    "goa": "driving psytrance, rolling bassline, 145 bpm, acid lead",
    "dark": "dark progressive psytrance, hypnotic, 142 bpm",
    "organic": "organic goa trance, melodic, 140 bpm, warm pads",
}


def to_np(x):
    x = x.detach().float().cpu().numpy() if torch.is_tensor(x) else np.asarray(x, dtype=np.float32)
    while x.ndim > 2:
        x = x[0]
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--lora", default=None)
    ap.add_argument("--lora-name", default="base")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    from stable_audio_3 import StableAudioModel
    m = StableAudioModel.from_pretrained("medium-base", device="cuda")
    if a.lora:
        m.load_lora([a.lora])
        from model_matrix_gen import merge_adapters
        print("merged adapter parametrizations:", merge_adapters(m.model), flush=True)
    sr = m.model.sample_rate
    rows = []
    for pname, prompt in PROMPTS.items():
        wavs = {}
        for arm in ("bf16", "fp8"):
            n = 0
            if arm == "fp8":
                n, cov, tot = f8.swap_fp8(m.model.model)
            torch.cuda.synchronize(); t0 = time.time()
            y = m.generate(prompt=prompt, duration=a.duration, steps=a.steps, cfg_scale=a.cfg, seed=a.seed)
            torch.cuda.synchronize(); dt = time.time() - t0
            if arm == "fp8":
                f8.restore_fp8(m.model.model)
            w = to_np(y)
            wavs[arm] = w
            pk = float(np.abs(w).max())
            wn = w / max(pk, 1e-6) * 0.8913                                       # -1 dBFS, as save_audio does
            base = os.path.join(a.out, f"{a.lora_name}__{pname}__{arm}")
            sf.write(base + ".wav", wn.T, sr, subtype="PCM_16")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base + ".wav", "-c:a", "aac", "-b:a", "256k", base + ".m4a"])
            rows.append({"model": a.lora_name, "prompt": pname, "arm": arm, "seconds": round(dt, 2), "peak": pk,
                         "finite": bool(np.isfinite(w).all()), "fp8_layers": n})
            print(f"  {a.lora_name} {pname} {arm}: {dt:.2f}s peak {pk:.3f}", flush=True)
        n_ = min(wavs["bf16"].shape[-1], wavs["fp8"].shape[-1])
        p, q = wavs["bf16"][:, :n_].flatten(), wavs["fp8"][:, :n_].flatten()
        cos = float(p @ q / (np.linalg.norm(p) * np.linalg.norm(q) + 1e-12))
        rel = float(np.linalg.norm(p - q) / (np.linalg.norm(p) + 1e-12))
        rows[-1].update(cos_vs_bf16=cos, rel_vs_bf16=rel)
        print(f"  {a.lora_name} {pname}: waveform cosine fp8 vs bf16 {cos:.4f}, rel err {rel:.3f}", flush=True)
    json.dump({"args": vars(a), "torch": torch.__version__, "rows": rows}, open(os.path.join(a.out, f"results_{a.lora_name}.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
