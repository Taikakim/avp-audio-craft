#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-28)
"""chroma_e13_render.py -- EXPERIMENTS E13: does the same_chroma head retrained under the ModularOptimizer steer
chords better than the production head (AdamW, EMA 0.999, depth 4, 20 ep, train-loss selected)?

Two GPU stages, one process (the model loads once), resumable from OUT/cells.jsonl:
  screen  every retrained weight set (C2 lr 1e-2 / C3 1e-3 / C4 1e-4 x ep 5/10/15/20 x {EMA 1 ep, EMA 0.25 ep, online
          SF average} = 36) + the production head, at gain 2048 (where the production head was most audible, listening
          2026-10-16), 3 prompts x 2 targets (hold C, key-lift C -> Eb -> F#) x 2 seeds.
  ladder  the production head + the 3 best retrained weight sets from the screen, at gains 512 .. 8192 (the ladder
          extended above 2048, as E13 asks), 3 prompts x 4 targets x 4 seeds.
Every steered clip has its same-prompt, same-seed unguided render (gain 0), and the metric is the CHANGE against it
(the chroma trap, MASTER section 5: absolute chroma similarity means little on tonal music).

Per clip (CPU, from the decoded wav before it is encoded): SAME chroma of the output, folded to 12, per band (bass, mid):
  fcos   mean over frames of cos(output chroma, target chroma at that frame) -- follows a progression, not only its mean
  hit    fraction of frames whose strongest pitch class is the target's strongest pitch class at that frame
  z_std  std of the final latent (the gate's latent-level leg: > 1.3 x the unguided render = saturation)
The texture/Audiobox legs of the disintegration gate come afterwards from clip_metrics.db (eval/chroma_e13_report.py).
Screen ranking = mean (d_fcos bass + d_fcos mid) / 2 over the screen cells, excluding any weight set with a latent-level
failure in more than a quarter of its cells.

Clips: 192 kbps AAC .m4a in /home/kim/evals_aac/control_runs/chroma_e13_20261028/ (where clip_metrics looks), wav deleted
after measuring. Disk guard: stops if that drive has < 10 GB free.
RUN (GPU, SA3 fast venv): eval/run_chroma_e13.sh  (waits for the GPU lock, then both stages, then scoring)
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections import defaultdict
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

OUT = Path("/home/kim/evals_aac/control_runs/chroma_e13_20261028")
RETRAIN = Path("/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16")
PROD = SAO / "stable-audio-3" / "latch_weights_sa3_medium" / "latch_sa3_same_chroma_best.pt"
ARMS = {"C2": "C2_chroma_d512_lr1e-2", "C3": "C3_chroma_d512_lr1e-3", "C4": "C4_chroma_d512_lr1e-4"}
WEIGHTS = {"ema1": "", "ema025": "_ema0.25", "online": "_online"}
EPOCHS = (5, 10, 15, 20)

FPS = 10.7666
DURATION_SEC = 20.05
STEPS = 24
CFG = 7.0
PROMPTS = ("goa", "guitar", "piano")
SCREEN = {"gains": [2048], "targets": ["C", "keylift"], "seeds": [1234, 5678]}
LADDER = {"gains": [512, 1024, 2048, 3072, 4096, 6144, 8192], "targets": ["C", "Am", "keylift", "i-VI-III-VII"],
          "seeds": [1234, 5678, 9012, 77]}
N_PICK = 3
Z_STD_FAIL = 1.3
MIN_FREE_GB = 10


def heads():
    """{head_id: checkpoint path}: the production head and the 36 retrained weight sets."""
    out = {"prod": PROD}
    for arm, d in ARMS.items():
        for ep in EPOCHS:
            for w, suf in WEIGHTS.items():
                out[f"{arm}_ep{ep}_{w}"] = RETRAIN / d / f"latch_sa3_same_chroma_ep{ep}{suf}.pt"
    return out


def target_spec(tid):
    return next(t for t in T.TARGETS if t["id"] == tid)


def prompt_text(pid):
    return next(p for p in T.ALL_PROMPTS if p["id"] == pid)["text"]


def clip_name(head, pid, tid, gain, seed):
    return f"base__{pid}__s{seed}.m4a" if gain == 0 else f"{head}__{pid}__{tid}__g{gain}__s{seed}.m4a"


def measure(wav_np, tid, n_frames):
    """Per band: fcos (frame-wise cos to the target) and hit (frame-wise strongest-class match). tid None = baseline:
    measured against every target the run uses, so each steered clip can be compared with its own baseline value."""
    chroma = sc.compute_same_chroma(wav_np.T, sc.SAME_SR, align_to_latent=False)       # (3, 128, M)
    folded = sc.fold_to_12(chroma)                                                     # (3, 12, M)
    M = folded.shape[-1]
    out = {}
    tids = [tid] if tid else sorted(set(SCREEN["targets"]) | set(LADDER["targets"]))
    for t in tids:
        c12 = _chroma12_per_frame(target_spec(t), n_frames)                            # (12, n_frames)
        idx = np.minimum((np.arange(M) * n_frames / M).astype(int), n_frames - 1)
        tgt = c12[:, idx]
        tn = tgt / (np.linalg.norm(tgt, axis=0, keepdims=True) + 1e-9)
        res = {}
        for bi, band in ((0, "bass"), (1, "mid")):
            f = folded[bi]
            fn = f / (np.linalg.norm(f, axis=0, keepdims=True) + 1e-9)
            res[band] = {"fcos": round(float((fn * tn).sum(axis=0).mean()), 4),
                         "hit": round(float((f.argmax(axis=0) == tgt.argmax(axis=0)).mean()), 4)}
        out[t] = res
    return out


def free_gb(path):
    return shutil.disk_usage(path).free / 2**30


def load_cells():
    p = OUT / "cells.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def plan(stage, picked):
    """[(head, pid, tid, gain, seed)] for a stage; baselines (gain 0) once per prompt x seed."""
    cfg = SCREEN if stage == "screen" else LADDER
    hs = list(heads()) if stage == "screen" else ["prod"] + picked
    cells = [(None, p, None, 0, s) for p in PROMPTS for s in cfg["seeds"]]
    cells += [(h, p, t, g, s) for h in hs for p in PROMPTS for t in cfg["targets"] for s in cfg["seeds"]
              for g in cfg["gains"]]
    return cells


def pick(cells):
    """Top N_PICK retrained weight sets from the screen by mean d_fcos (bass+mid)/2 against the same-seed baseline."""
    base = {(c["prompt"], c["seed"]): c for c in cells if c["gain"] == 0}
    score, zfail, n = defaultdict(list), defaultdict(int), defaultdict(int)
    for c in cells:
        if c["gain"] != 2048 or c["head"] == "prod" or c["target"] not in SCREEN["targets"]:
            continue
        b = base.get((c["prompt"], c["seed"]))
        if not b:
            continue
        m, mb = c["m"][c["target"]], b["m"][c["target"]]
        score[c["head"]].append(((m["bass"]["fcos"] - mb["bass"]["fcos"]) + (m["mid"]["fcos"] - mb["mid"]["fcos"])) / 2)
        n[c["head"]] += 1
        zfail[c["head"]] += c["z_std"] / b["z_std"] > Z_STD_FAIL
    ranked = sorted((h for h in score if zfail[h] <= n[h] / 4), key=lambda h: -np.mean(score[h]))
    table = [(h, round(float(np.mean(score[h])), 4), zfail[h], n[h]) for h in sorted(score, key=lambda h: -np.mean(score[h]))]
    return ranked[:N_PICK], table


def write_meta(extra):
    meta_p = OUT / "run_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    meta.update({
        "purpose": ("EXPERIMENTS E13: does the same_chroma LatCH head retrained under the ModularOptimizer (Shampoo, Muon on "
                    "all 2-D, Schedule-Free, d512 depth 8, 20 ep, val by relpath) steer chords further than the production "
                    "head, and does the extra range survive the disintegration gate?"),
        "hypothesis": ("The production head steers transparently and is most audible at gain 2048 (listening 2026-10-16), so a "
                       "better-trained head, or a higher gain, may steer further. Kill: no retrained weight set beats the "
                       "production head's change toward the target at equal gain, or all extra range fails the gate."),
        "recipe": {"model": "medium-base (no finetune)", "steps": STEPS, "cfg": CFG, "duration_sec": DURATION_SEC,
                   "guidance": "model.generate(latch_configs target_raw, loss cosine, rho = mu = gain), default alpha schedule",
                   "screen": SCREEN, "ladder": LADDER, "prompts": PROMPTS,
                   "metric": "change in frame-wise cos and strongest-class hit vs the same-prompt, same-seed gain-0 render",
                   "z_std_fail": Z_STD_FAIL},
        "heads": {"prod": "production same_chroma head (AdamW, EMA 0.999, depth 4, 20 ep, train-loss selected)",
                  "retrained": "Mantu latch_sweep chroma_retrain_2026-10-16 (C2 lr 1e-2, C3 1e-3, C4 1e-4), run by "
                               "latch/run_chroma_retrain.sh; ema1 = EMA half-life 1 epoch, ema025 = 0.25 epoch, online = SF average",
                  "val_loss_best": {"C2": 0.0843, "C3": 0.0973, "C4": 0.1604}},
        "dataset_info": "heads trained on latents_sa3 (goa, 5400 crops) with other-stem SAME chroma targets; 5% held out by relpath",
        "related": ["eval/chroma_e13_render.py", "eval/run_chroma_e13.sh", "eval/chroma_e13_report.py",
                    "latch/run_chroma_retrain.sh", "EXPERIMENTS.md E13", "riffer-evals/clips/chroma_steer/run_meta.json"],
        "kim_feedback": meta.get("kim_feedback"),
    })
    meta.update(extra)
    meta_p.write_text(json.dumps(meta, indent=1))


def run(stages):
    import torch
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio

    OUT.mkdir(parents=True, exist_ok=True)
    write_meta({"status": "running"})
    n_frames = int(round(DURATION_SEC * FPS))
    hp = heads()
    missing = [h for h, p in hp.items() if not Path(p).exists()]
    if missing:
        sys.exit(f"missing heads: {missing}")
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cells = load_cells()
    done = {c["clip"] for c in cells}
    log = open(OUT / "cells.jsonl", "a")
    picked = []
    for stage in stages:
        if stage == "ladder":
            picked, table = pick(cells)
            (OUT / "screen_ranking.json").write_text(json.dumps({"picked": picked, "table": table}, indent=1))
            print(f"[e13] screen ranking (head, mean d_fcos, z fails, n): {table[:8]}", flush=True)
            print(f"[e13] ladder heads: prod + {picked}", flush=True)
            write_meta({"screen_picked": picked})
        todo = [c for c in plan(stage, picked) if clip_name(c[0], c[1], c[2], c[3], c[4]) not in done]
        print(f"[e13] {stage}: {len(todo)} clips to render", flush=True)
        t_stage = time.time()
        for i, (h, pid, tid, g, s) in enumerate(todo):
            if free_gb(OUT) < MIN_FREE_GB:
                write_meta({"status": f"stopped: under {MIN_FREE_GB} GB free"})
                sys.exit(f"[e13] stopping: under {MIN_FREE_GB} GB free on {OUT}")
            name = clip_name(h, pid, tid, g, s)
            t0 = time.time()
            gen = dict(prompt=prompt_text(pid), duration=DURATION_SEC, steps=STEPS, cfg_scale=CFG, seed=s)
            if g > 0:
                gen["latch_configs"] = [{"model_path": str(hp[h]), "target_raw": build_target_raw(384, target_spec(tid), n_frames),
                                         "weight": 1.0, "loss_type": "cosine"}]
                gen["latch_hparams"] = {"rho": float(g), "mu": float(g)}
            sink = []
            audio = model.generate(latents_sink=sink, **gen)
            z = sink[-1].float()
            if not torch.isfinite(z).all():
                print(f"[e13] {name}: non-finite latent, cell left out", flush=True)
                continue
            wav = audio[0].float().cpu()
            wav_path = OUT / name.replace(".m4a", ".wav")
            save_audio(str(wav_path), wav, sc.SAME_SR)
            m = measure(wav.numpy(), tid, n_frames)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-c:a", "aac", "-b:a", "192k",
                            str(OUT / name)], check=True)
            wav_path.unlink()
            cell = {"clip": name, "stage": stage, "head": h or "base", "prompt": pid, "target": tid, "gain": g, "seed": s,
                    "m": m, "z_std": round(float(z.std()), 4), "elapsed": round(time.time() - t0, 1)}
            cells.append(cell)
            done.add(name)
            log.write(json.dumps(cell) + "\n")
            log.flush()
            if i % 25 == 0:
                rate = (time.time() - t_stage) / (i + 1)
                print(f"[e13] {stage} {i + 1}/{len(todo)} {name} {cell['elapsed']}s, ~{rate * (len(todo) - i - 1) / 60:.0f} min left",
                      flush=True)
    write_meta({"status": "rendered", "clips": len(cells)})


def main():
    ap = argparse.ArgumentParser(description="EXPERIMENTS E13 chroma head screen + gain ladder")
    ap.add_argument("--stages", default="screen,ladder")
    ap.add_argument("--dry", action="store_true", help="CPU: check heads exist, print the plan sizes, build every target")
    a = ap.parse_args()
    if a.dry:
        hp = heads()
        print("heads", len(hp), "missing", [h for h, p in hp.items() if not Path(p).exists()])
        n_frames = int(round(DURATION_SEC * FPS))
        for t in set(SCREEN["targets"]) | set(LADDER["targets"]):
            assert build_target_raw(384, target_spec(t), n_frames).shape == (384, n_frames)
        for p in PROMPTS:
            prompt_text(p)
        print("screen clips", len(plan("screen", [])), "ladder clips", len(plan("ladder", ["a", "b", "c"])))
        fake = np.random.default_rng(0).standard_normal((2, int(DURATION_SEC * sc.SAME_SR))).astype(np.float32) * 0.1
        print("measure ok", list(measure(fake, None, n_frames)))
        return
    run(a.stages.split(","))


if __name__ == "__main__":
    main()
