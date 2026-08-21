#!/usr/bin/env python
"""render_showcase.py — the "long playlist" showcase run (Kim direct 2026-08-21: render t2048 +
t4096 clips at random cfg {5,7,9} x w {0.8,1.0,1.2} on W's known-good checkpoint list
(lumi/genre_fusion_checkpoints.txt — top-12-by-PQ, transcribed by G), prompts drawn at random
from the TRAINING CAPTION sidecars, ~128 renders on 1 node x 8 GCDs. 50 steps normally; ptm
checkpoints render at their native operating point: 8 steps, cfg 1. Every render records its
full parameter set + prompt + checkpoint in a .json sidecar AND the global units manifest).

Two modes:
  build  — runs ONCE (rank-free, stdlib-only) on LUMI: resolves checkpoints against
           $SCRATCH/runs via genre_fusion_shards.resolve_ckpt, builds the caption pool from the
           training sidecars in code/lumi/, draws all 128 units with a FIXED rng seed and writes
           units.jsonl. Deterministic: re-running with the same inputs regenerates the same
           units, so a refill run resumes instead of re-drawing.
  render — one rank: takes units where unit["rank"] == --rank, groups by checkpoint (one model
           load per ckpt, not per render), renders wav + fp16 z0 sibling (standing directive:
           latents saved with audio) + per-clip .json manifest. Idempotent per clip.

Unit balance: exactly floor(128/n_ckpts) renders per checkpoint (+1 for the remainder few) so
the playlist covers every known-good model; all OTHER axes (prompt, length, cfg, w, seed) are
random per unit. fullft checkpoints pin w=1.0 (strength is meaningless for a whole-model FT).
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                  # genre_fusion_shards
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "control"))

FPS = 44100 / 4096  # 10.7666 Hz — canonical SA3-medium latent frame rate

CAPTION_SIDECARS = [  # {id: {t1,t2,t3}} — t3 is the rich Music-Flamingo-style caption
    "avp_captions_tiered.json",
    "suomisoundi_caption_sidecar.json",
    "goa_longform_sidecar.json",
]


def build_pool(captions_dir):
    pool = []
    for name in CAPTION_SIDECARS:
        p = Path(captions_dir, name)
        if not p.exists():
            print(f"[show] WARNING: sidecar missing, skipping: {p}", file=sys.stderr)
            continue
        d = json.load(open(p))
        n0 = len(pool)
        for cid, tiers in d.items():
            text = tiers.get("t3") or tiers.get("t2") or tiers.get("t1")
            if text and len(text.strip()) > 20:
                pool.append({"text": text.strip(), "src": f"{name}:{cid}"})
        print(f"[show] pool += {len(pool)-n0} from {name}")
    return pool


def cmd_build(a):
    from genre_fusion_shards import resolve_ckpt
    rng = random.Random(a.rng)

    ckpts = []
    for line in open(a.checkpoints):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        label, epoch = parts[0], parts[1]
        is_ptm = len(parts) > 2 and parts[2].lower() == "ptm"
        path, _ = resolve_ckpt(a.scratch_runs, label, epoch)
        if path is None:
            print(f"[show] WARNING: unresolved, skipping: {label} ep{epoch}", file=sys.stderr)
            continue
        ckpts.append({"label": label, "tag": f"ep{epoch}", "ckpt": path, "is_ptm": is_ptm,
                      "is_fullft": label.startswith("fullft_")})
        print(f"[show] {label} {ckpts[-1]['tag']}{' ptm' if is_ptm else ''} -> {path}")
    if not ckpts:
        print("[show] FATAL: no checkpoints resolved", file=sys.stderr)
        sys.exit(1)

    pool = build_pool(a.captions_dir)
    if len(pool) < 100:
        print(f"[show] FATAL: caption pool too small ({len(pool)})", file=sys.stderr)
        sys.exit(1)

    # rank assignment by CHECKPOINT (one load per ckpt per rank); interleave ptm/non-ptm so no
    # rank ends up all-slow (50-step t4096) or all-fast (8-step ptm).
    nonptm = [c for c in ckpts if not c["is_ptm"]]
    ptm = [c for c in ckpts if c["is_ptm"]]
    rng.shuffle(nonptm), rng.shuffle(ptm)
    ordered = []
    while nonptm or ptm:
        if nonptm: ordered.append(nonptm.pop())
        if ptm: ordered.append(ptm.pop())
    for j, c in enumerate(ordered):
        c["rank"] = j % a.ranks

    per = a.n // len(ordered)
    extra = a.n - per * len(ordered)
    units, idx = [], 0
    for j, c in enumerate(ordered):
        for _ in range(per + (1 if j < extra else 0)):
            frames = rng.choice([2048, 4096])
            u = dict(c)
            u.update({
                "idx": idx,
                "frames": frames,
                "duration": round(frames / FPS, 2),
                "cfg": 1 if c["is_ptm"] else rng.choice([5, 7, 9]),
                "weight": 1.0 if c["is_fullft"] else rng.choice([0.8, 1.0, 1.2]),
                "steps": 8 if c["is_ptm"] else 50,
                "seed": rng.randrange(1, 2**31),
                "prompt": None, "prompt_src": None,
            })
            pick = rng.choice(pool)
            u["prompt"], u["prompt_src"] = pick["text"], pick["src"]
            units.append(u)
            idx += 1

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for u in units:
            f.write(json.dumps(u) + "\n")
    from collections import Counter
    print(f"[show] wrote {len(units)} units -> {a.out}")
    print(f"[show] per-rank: {sorted(Counter(u['rank'] for u in units).items())}")
    print(f"[show] frames: {sorted(Counter(u['frames'] for u in units).items())}  "
          f"cfg: {sorted(Counter(u['cfg'] for u in units).items())}  "
          f"w: {sorted(Counter(u['weight'] for u in units).items())}")


def clip_name(u):
    return (f"show__{u['label']}__{u['tag']}__cfg{int(u['cfg'])}"
            f"__w{int(round(u['weight'] * 100)):03d}__T{u['frames']}__s{u['seed']}.wav")


def load_fullft_state(model, ckpt_path):
    """Whole-model load, EMA shadow preferred when present (what actually deploys)."""
    import torch
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    sd_raw = ck.get("state_dict", ck)
    tgt = model.model.model
    want = set(dict(tgt.named_parameters())) | set(dict(tgt.named_buffers()))
    has_ema = any(k.startswith("diffusion_ema.ema_model.") for k in sd_raw)
    prefixes = ("diffusion_ema.ema_model.",) if has_ema else ("diffusion.model.", "model.")
    sd = max(({(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
              for pfx in prefixes),
             key=lambda d: sum(1 for k in d if k in want))
    missing, _ = tgt.load_state_dict(
        {k: v.to(next(tgt.parameters()).dtype) for k, v in sd.items() if k in want}, strict=False)
    cov = 1 - len(missing) / max(1, len(list(tgt.state_dict())))
    assert cov > 0.99, f"fullft ckpt covers only {cov:.1%} ({len(missing)} missing)"
    print(f"[show] fullft load cov {cov:.2%} (ema={has_ema})")
    del ck, sd_raw, sd


def cmd_render(a):
    units = [json.loads(l) for l in open(a.units)]
    mine = [u for u in units if u["rank"] == a.rank]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    todo = [u for u in mine if a.force or not (out / clip_name(u)).exists()]
    print(f"[show r{a.rank}] {len(mine)} units assigned, {len(todo)} to render", flush=True)
    if not todo:
        return

    import numpy as np
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    # group by checkpoint — one model load per ckpt
    by_ckpt = {}
    for u in todo:
        by_ckpt.setdefault(u["ckpt"], []).append(u)

    for ckpt_path, group in by_ckpt.items():
        g0 = group[0]
        base = "medium" if g0["is_ptm"] else "medium-base"
        t0 = time.time()
        model = StableAudioModel.from_pretrained(base, device="cuda")
        if g0["is_fullft"]:
            load_fullft_state(model, ckpt_path)
        else:
            model.load_lora([ckpt_path])
        sr = model.model.sample_rate
        decode_dtype = next(model.same.parameters()).dtype
        print(f"[show r{a.rank}] {g0['label']}/{g0['tag']} ({base}) loaded in "
              f"{time.time()-t0:.0f}s; {len(group)} renders", flush=True)

        for u in group:
            if not g0["is_fullft"]:
                try:
                    model.set_lora_strength(u["weight"])
                except Exception:
                    pass
            wav = out / clip_name(u)
            t0 = time.time()
            z0 = model.generate(prompt=u["prompt"], duration=u["duration"], steps=u["steps"],
                                cfg_scale=float(u["cfg"]), seed=int(u["seed"]), batch_size=1,
                                sample_size=u["frames"] * 4096, return_latents=True)
            assert z0.shape[-1] == u["frames"], (z0.shape, u["frames"])
            np.save(wav.with_suffix(".z0.npy"), z0.detach().to(torch.float16).cpu().numpy())
            with torch.no_grad():
                audio = model.same.decode(z0.to(decode_dtype))
            audio = audio.to(torch.float32)[:, :, :int(u["duration"] * sr)]
            save_audio(wav, audio[0].cpu(), sr, normalize=True)
            wav.with_suffix(".json").write_text(json.dumps(u, indent=1))
            print(f"  [r{a.rank} #{u['idx']} {u['label']}/{u['tag']} cfg{u['cfg']} "
                  f"w{u['weight']} T{u['frames']} s{u['seed']}] {time.time()-t0:.0f}s", flush=True)
        del model
        torch.cuda.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("--checkpoints", required=True, help="genre_fusion_checkpoints.txt format")
    b.add_argument("--scratch-runs", required=True)
    b.add_argument("--captions-dir", required=True, help="dir holding the caption sidecar jsons")
    b.add_argument("--out", required=True, help="units.jsonl path")
    b.add_argument("--n", type=int, default=128)
    b.add_argument("--ranks", type=int, default=8)
    b.add_argument("--rng", type=int, default=20260821)
    r = sub.add_parser("render")
    r.add_argument("--units", required=True)
    r.add_argument("--rank", type=int, required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cmd_build(a) if a.mode == "build" else cmd_render(a)


if __name__ == "__main__":
    main()
