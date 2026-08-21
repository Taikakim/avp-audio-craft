#!/usr/bin/env python3
"""render_morph.py — first LISTEN of the D12 morph-contour arms (morphcond_bracket.sbatch /
STREAM=ioi): condition a trained Head-B morph adapter on REAL contour-symbol streams and
render them paired with the reference.

Why not melody_pilot_eval.py: its synthetic motif streams are the 9-class fold alphabet and its
encoder is built at the default vocab — the morph arms use K&P symbol alphabets (vocab 5/15/77,
IOI 15), so both the stream source and the Embedding size would be wrong.

Per checkpoint (vocab + FT backbone path both read from ck["args"]):
  refs   = N sidecar crops (<stem>.melody8.npy in the arm's morph dir), the 512-frame window of
           each with the highest defined-symbol coverage; chosen ONCE per morph dir with a fixed
           seed so every arm of that alphabet renders the SAME refs (and the same crop windows
           are shared across L2/L3/L4 because the stem draw is seeded on the stem list).
  render = for each ref x gain: conditioned clip (prompt = the crop's goa caption t3 if the
           sidecar knows it, else a fixed goa prompt); plus ONE null-stream clip per ref (gain
           irrelevant — zero tokens = the trained null) = the unconditioned control.
  refs/  = the ORIGINAL latent window decoded (latents_sa3/<stem>.npy) = what the contour was
           read from, written once per stem into <out>/refs/.
Every clip: .wav + .z0.npy (fp16) + .stream.npy (int8) + .json (ckpt, stem, window, gain, cfg,
prompt, seed, vocab, backbone). Idempotent per clip.
"""
import argparse
import glob
import json
import os
import random
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np

FPS = 44100 / 4096
SR = 44100
FALLBACK_PROMPT = ("psychedelic goa trance, hypnotic melodic acid lead line, driving rolling "
                   "bassline, 143 BPM")


def best_window(stream, n):
    """start index of the length-n window with the most DEFINED symbols (stream != 0)."""
    s = (np.asarray(stream) != 0).astype(np.int32)
    if len(s) <= n:
        return 0, float(s.mean())
    cs = np.concatenate([[0], np.cumsum(s)])
    cov = cs[n:] - cs[:-n]
    i = int(np.argmax(cov))
    return i, float(cov[i] / n)


def pick_refs(melody_dir, n_refs, frames, seed, min_cov=0.8):
    files = sorted(glob.glob(os.path.join(melody_dir, "*.melody8.npy")))
    assert files, f"no sidecars under {melody_dir}"
    rng = random.Random(seed)
    rng.shuffle(files)
    picks = []
    for f in files:
        st = np.load(f)
        i, cov = best_window(st, frames)
        if cov >= min_cov:
            picks.append((os.path.basename(f).replace(".melody8.npy", ""), i, cov))
        if len(picks) >= n_refs:
            break
    assert picks, "no sidecar reaches min coverage"
    return picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True, help="riffer_final.pt of a morph arm")
    ap.add_argument("--label", required=True)
    ap.add_argument("--melody-dir", required=True, help="the arm's morph sidecar dir")
    ap.add_argument("--latent-dir", required=True, help="latents_sa3 (for the reference decode)")
    ap.add_argument("--caption-sidecar", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-refs", type=int, default=8)
    ap.add_argument("--frames", type=int, default=512)
    ap.add_argument("--gains", default="1.0,2.0")
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=20260822)
    ap.add_argument("--base-state-ckpt", default=None,
                    help="override; default = ck['args']['base_state_ckpt'] (None for base arms)")
    a = ap.parse_args()

    import torch
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))       # render_showcase
    from stable_audio_3 import StableAudioModel
    from sa3_control.adapters import ControlContext, use_control_context
    from sa3_control.audio_io import save_audio
    from sa3_control.conditioner import MelodyContourEncoder
    from sa3_control.generate import load_adapter_state
    from sa3_control.inject import install_adapters
    from render_showcase import load_fullft_state

    out = Path(a.out)
    (out / "refs").mkdir(parents=True, exist_ok=True)
    gains = [float(g) for g in a.gains.split(",")]
    caps = json.load(open(a.caption_sidecar)) if a.caption_sidecar else {}

    ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    assert ck.get("control_mode") == "melody_contour", ck.get("control_mode")
    cargs = ck["args"]
    vocab = int(cargs.get("melody_vocab", 9))
    assert int(cargs.get("dora_rank", 0) or 0) == 0, "dora-rows arm: use melody_pilot_eval's path"
    base_state = a.base_state_ckpt or cargs.get("base_state_ckpt")
    refs = pick_refs(a.melody_dir, a.n_refs, a.frames, a.seed)
    duration = a.frames / FPS
    print(f"[morph:{a.label}] vocab={vocab} backbone={'base' if not base_state else os.path.basename(base_state)} "
          f"refs={[r[0] for r in refs]}", flush=True)

    # plan all clips first; skip the whole load if nothing to do
    plan = []
    for stem, i0, cov in refs:
        for g in gains:
            plan.append((stem, i0, cov, g, True))
        plan.append((stem, i0, cov, 1.0, False))

    def clip_name(stem, g, cond):
        return f"morph__{a.label}__{stem}__{'g%.1f' % g if cond else 'null'}__cfg{a.cfg:g}.wav"

    todo = [p for p in plan if not (out / clip_name(p[0], p[3], p[4])).exists()]
    need_refs = [r for r in refs if not (out / "refs" / f"ref__{r[0]}.wav").exists()]
    if not todo and not need_refs:
        print(f"[morph:{a.label}] all {len(plan)} clips present", flush=True)
        return

    device = "cuda"
    sam = StableAudioModel.from_pretrained(cargs.get("model", "medium-base"), device=device)
    if base_state:
        assert os.path.exists(base_state), base_state
        load_fullft_state(sam, base_state)
    md = next(sam.model.model.parameters()).dtype
    wrappers = install_adapters(sam, control_dim=int(cargs.get("control_dim", 768)))
    cond_enc = MelodyContourEncoder(control_dim=int(cargs.get("control_dim", 768)),
                                    n_classes=vocab).to(device=device, dtype=md)
    load_adapter_state(ck["state"], wrappers, cond_enc)
    for w in wrappers:
        w.adapter.to(device=device, dtype=md)
    cond_enc.eval()
    decode_dtype = next(sam.model.pretransform.parameters()).dtype

    def decode_save(z0, path):
        with torch.no_grad():
            audio = sam.model.pretransform.decode(z0.type(decode_dtype))
        audio = audio.to(torch.float32).cpu()
        audio = (audio / audio.abs().amax().clamp(min=1.0))[0]
        save_audio(str(path), audio, SR)

    # references: decode the ORIGINAL latent window once per stem
    for stem, i0, cov in need_refs:
        lp = os.path.join(a.latent_dir, stem + ".npy")
        if not os.path.exists(lp):
            print(f"[morph] ref latent missing for {stem}; skipping ref", flush=True)
            continue
        z = np.load(lp, mmap_mode="r")
        z = np.asarray(z[..., i0:i0 + a.frames]).astype(np.float32)
        if z.ndim == 2:
            z = z[None]
        decode_save(torch.from_numpy(z).to(device), out / "refs" / f"ref__{stem}.wav")
        json.dump({"stem": stem, "window": [i0, i0 + a.frames], "coverage": cov},
                  open(out / "refs" / f"ref__{stem}.json", "w"))
        print(f"[morph] ref {stem} window {i0} cov {cov:.2f}", flush=True)

    for stem, i0, cov, g, cond in todo:
        name = clip_name(stem, g, cond)
        t0 = time.time()
        full = np.load(os.path.join(a.melody_dir, stem + ".melody8.npy"))
        stream = full[i0:i0 + a.frames].astype(np.int64)
        if len(stream) < a.frames:
            stream = np.pad(stream, (0, a.frames - len(stream)))
        if not cond:
            stream = np.zeros_like(stream)
        prompt = (caps.get(stem) or {}).get("t3") or FALLBACK_PROMPT
        seed = int(re.sub(r"\D", "", stem) or 0) % (2 ** 31) + 7
        with torch.inference_mode():
            ctrl = cond_enc(torch.from_numpy(stream)[None].to(device))
            if not cond:
                ctrl = torch.zeros_like(ctrl)            # trained null = zero TOKENS
            if a.cfg != 1.0:
                ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
            with use_control_context(ControlContext(ctrl, gain=g)):
                z0 = sam.generate(prompt=prompt, duration=duration, steps=a.steps,
                                  cfg_scale=a.cfg, seed=seed, sampler_type="euler",
                                  return_latents=True)
        np.save(out / (name[:-4] + ".z0.npy"), z0.cpu().to(torch.float16).numpy())
        np.save(out / (name[:-4] + ".stream.npy"), stream.astype(np.int8))
        decode_save(z0, out / name)
        json.dump({"label": a.label, "ckpt": a.ckpt, "stem": stem, "window": [i0, i0 + a.frames],
                   "coverage": cov, "conditioned": cond, "gain": g, "cfg": a.cfg, "steps": a.steps,
                   "prompt": prompt, "seed": seed, "vocab": vocab, "frames": a.frames,
                   "backbone": base_state or "medium-base", "melody_dir": a.melody_dir},
                  open(out / (name[:-4] + ".json"), "w"), indent=1)
        print(f"[morph:{a.label}] {name} {time.time() - t0:.0f}s", flush=True)
    print(f"[morph:{a.label}] done", flush=True)


if __name__ == "__main__":
    main()
