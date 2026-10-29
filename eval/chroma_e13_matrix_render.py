#!/usr/bin/env python3
# Owner: ANTIGRAVITY (created 2026-10-29)
"""chroma_e13_matrix_render.py -- Exploration matrix for the E13 modular retrained head
(latch_sa3_same_chroma_ep10.pt, 384-d SAME octave-band chroma) on curated Goa DoRA checkpoint
(subloss_k24 biggoa t512 ep63) across:
  - Guidance Weight (Gain): 0, 512, 1024, 2048, 4096
  - CFG scale: 3.0, 5.0, 7.0
  - Sampling steps: 25, 40, 50
  - Guidance schedule: alpha (back-loaded TFG default) vs flat (equal per-step weight)
  - Seeds: 1234, 5678 (Kim weak-seed diagnosis)
  - Targets: hold C, hold Am, keylift C -> Eb -> F#

Resumable from OUT/cells.jsonl.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SAO = HERE.parent
sys.path.insert(0, str(SAO / "control"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")

import chroma_steer_targets as T  # noqa: E402
from chroma_steer_render import build_target_raw, _chroma12_per_frame  # noqa: E402
from harmonic import same_chroma as sc  # noqa: E402

OUT = Path("/run/media/kim/Mantu/sa3_control_runs/chroma_e13_matrix_20261029")
E13_BASE_DIR = Path("/home/kim/evals_aac/control_runs/chroma_e13_20261028")

C3_HEAD = Path("/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt")
DORA_FT = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/epoch=63-step=12480.ckpt")

PROMPT = "melodic goa trance, hypnotic arpeggiated lead, driving rolling bassline"
SEEDS = [1234, 5678]
DURATION_SEC = 20.05
FPS = 10.7666
MIN_FREE_GB = 10


def target_spec(tid):
    return next(t for t in T.TARGETS if t["id"] == tid)


def build_target(tid, n_frames):
    return build_target_raw(384, target_spec(tid), n_frames)


def clip_name(tid, gain, cfg, steps, sched, seed):
    if gain == 0:
        return f"e13m__base__g0__cfg{cfg:.1f}__st{steps}__s{seed}.m4a"
    return f"e13m__{tid}__g{gain}__cfg{cfg:.1f}__st{steps}__{sched}__s{seed}.m4a"


def measure(wav_np, tid, n_frames):
    """Per band (bass, mid): frame-wise cosine and pitch-class hit rate."""
    chroma = sc.compute_same_chroma(wav_np.T, sc.SAME_SR, align_to_latent=False)
    folded = sc.fold_to_12(chroma)
    M = folded.shape[-1]
    out = {}
    tids = [tid] if tid else ["C", "Am", "keylift"]
    for t in tids:
        c12 = _chroma12_per_frame(target_spec(t), n_frames)
        idx = np.minimum((np.arange(M) * n_frames / M).astype(int), n_frames - 1)
        tgt = c12[:, idx]
        tn = tgt / (np.linalg.norm(tgt, axis=0, keepdims=True) + 1e-9)
        res = {}
        for bi, band in ((0, "bass"), (1, "mid")):
            f = folded[bi]
            fn = f / (np.linalg.norm(f, axis=0, keepdims=True) + 1e-9)
            res[band] = {
                "fcos": round(float((fn * tn).sum(axis=0).mean()), 4),
                "hit": round(float((f.argmax(axis=0) == tgt.argmax(axis=0)).mean()), 4),
            }
        out[t] = res
    return out


def free_gb(path):
    return shutil.disk_usage(path).free / 2**30


def build_plan():
    """Build the targeted parameter cells to evaluate."""
    cells = []
    seen = set()

    def add(tid, gain, cfg, steps, sched, seed, group):
        cid = clip_name(tid, gain, cfg, steps, sched, seed)
        if cid in seen:
            return
        seen.add(cid)
        cells.append({
            "id": cid,
            "target": tid if gain > 0 else None,
            "gain": gain,
            "cfg": cfg,
            "steps": steps,
            "sched": sched,
            "seed": seed,
            "group": group,
        })

    # Group A: Guidance Weight Ladder on subloss_k24, 50 steps, cfg 7.0, alpha schedule
    for s in SEEDS:
        add(None, 0, 7.0, 50, "alpha", s, "weight_ladder")
        for tid in ["C", "Am", "keylift"]:
            for g in [512, 1024, 2048, 4096]:
                add(tid, g, 7.0, 50, "alpha", s, "weight_ladder")

    # Group B: CFG Scale Sweep (3.0, 5.0, 7.0) at steps 50, target C, gain 0 and 2048
    for s in SEEDS:
        for cfg in [3.0, 5.0, 7.0]:
            add(None, 0, cfg, 50, "alpha", s, "cfg_sweep")
            add("C", 2048, cfg, 50, "alpha", s, "cfg_sweep")

    # Group C: Steps Sweep (25, 40, 50) at cfg 7.0, target C, gain 0 and 2048
    for s in SEEDS:
        for st in [25, 40, 50]:
            add(None, 0, 7.0, st, "alpha", s, "steps_sweep")
            add("C", 2048, 7.0, st, "alpha", s, "steps_sweep")

    # Group D: Guidance Schedule (alpha vs flat) at steps 50, cfg 7.0
    for s in SEEDS:
        for tid in ["C", "keylift"]:
            for g in [1024, 2048]:
                for sc_name in ["alpha", "flat"]:
                    add(tid, g, 7.0, 50, sc_name, s, "sched_sweep")

    return cells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    jl_path = out_dir / "cells.jsonl"

    plan = build_plan()
    print(f"[matrix] Total unique cells in plan: {len(plan)}")

    if args.dry_run:
        for c in plan[:10]:
            print(" ", c)
        print(f"  ... and {len(plan) - 10} more.")
        return

    # Check hardware checkpoints
    if not C3_HEAD.exists():
        sys.exit(f"Error: E13 retrained head missing: {C3_HEAD}")
    if not DORA_FT.exists():
        sys.exit(f"Error: DoRA finetune checkpoint missing: {DORA_FT}")

    # Resume support
    done_cells = {}
    if jl_path.exists():
        for line in jl_path.read_text().splitlines():
            if line.strip():
                item = json.loads(line)
                done_cells[item["id"]] = item

    todo = [c for c in plan if c["id"] not in done_cells or not (out_dir / c["id"]).exists()]
    print(f"[matrix] {len(todo)} cells to render ({len(done_cells)} already done)")

    # Copy / reference the 4 medium-base reference clips from chroma_e13 if available
    ref_clips = [
        ("base0__goa__s5678.m4a", "ref_mediumbase__base__g0__cfg7.0__st24__s5678.m4a"),
        ("base0__goa__s1234.m4a", "ref_mediumbase__base__g0__cfg7.0__st24__s1234.m4a"),
        ("C3_ep10_ema1__goa__C__g2048__s5678.m4a", "ref_mediumbase__C__g2048__cfg7.0__st24__s5678.m4a"),
        ("C3_ep10_ema1__goa__C__g2048__s1234.m4a", "ref_mediumbase__C__g2048__cfg7.0__st24__s1234.m4a"),
    ]
    for src_name, dst_name in ref_clips:
        src = E13_BASE_DIR / src_name
        dst = out_dir / dst_name
        if src.exists() and not dst.exists():
            shutil.copyfile(src, dst)
            print(f"[matrix] Staged medium-base comparison clip: {dst_name}")

    if not todo:
        print("[matrix] All clips already rendered!")
        return

    import torch
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio

    print("[matrix] Loading StableAudioModel (medium-base)...", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    print(f"[matrix] Loading Goa DoRA adapter ({DORA_FT.name})...", flush=True)
    model.load_lora([str(DORA_FT)])
    model.set_lora_strength(1.0)
    print("[matrix] Model ready on GPU.", flush=True)

    n_frames = int(round(DURATION_SEC * FPS))

    # Pre-build targets for speed
    targets_raw = {
        "C": build_target("C", n_frames),
        "Am": build_target("Am", n_frames),
        "keylift": build_target("keylift", n_frames),
    }

    t_start = time.time()
    for idx, c in enumerate(todo):
        if free_gb(out_dir) < MIN_FREE_GB:
            sys.exit(f"[matrix] Error: under {MIN_FREE_GB} GB free on {out_dir}")

        cid = c["id"]
        t0 = time.time()
        print(f"[{idx+1}/{len(todo)}] Rendering {cid}...", flush=True)

        gen = dict(
            prompt=PROMPT,
            duration=DURATION_SEC,
            steps=c["steps"],
            cfg_scale=c["cfg"],
            seed=c["seed"],
            sampler_type="euler",
            apg_scale=1.0,
        )

        # Baseline (gain 0) goes through guided sampler at gain 0 per MASTER §5 gotcha
        target_name = c["target"] or "C"
        gen["latch_configs"] = [{
            "model_path": str(C3_HEAD),
            "target_raw": targets_raw[target_name],
            "weight": 1.0,
            "loss_type": "cosine",
        }]
        gen["latch_hparams"] = {
            "rho": float(c["gain"]),
            "mu": float(c["gain"]),
            "guide_schedule": c["sched"],
        }

        sink = []
        audio = model.generate(latents_sink=sink, **gen)
        z = sink[-1].float() if sink else None

        wav = audio[0].float().cpu()
        wav_path = out_dir / cid.replace(".m4a", ".wav")
        save_audio(str(wav_path), wav, sc.SAME_SR)

        m = measure(wav.numpy(), c["target"], n_frames)

        # Convert to 256k AAC
        m4a_path = out_dir / cid
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-c:a", "aac", "-b:a", "256k", str(m4a_path)],
            check=True,
        )
        wav_path.unlink()

        elapsed = round(time.time() - t0, 1)
        z_std = round(float(z.std()), 4) if z is not None else 0.0

        res_entry = {
            **c,
            "z_std": z_std,
            "elapsed": elapsed,
            "m": m,
        }

        with open(jl_path, "a") as f:
            f.write(json.dumps(res_entry) + "\n")

        print(f"  done in {elapsed}s (z_std: {z_std})", flush=True)

    total_time = round(time.time() - t_start, 1)
    print(f"[matrix] Finished rendering {len(todo)} clips in {total_time}s!", flush=True)


if __name__ == "__main__":
    main()
