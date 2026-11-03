#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
# Last edited: WINTERMUTE 2026-11-03 -- decode inside generate(), never between renders (see below); throwaway first render, chunk controls
"""mood_deconf_render.py -- De-confounded mood targets vs the naive ones, on every prompt we use.

ANTIGRAVITY's render_mood_deconfounded.py (2026-11-03) tried these targets on one prompt and one seed. Project direction: redo
it on all the prompts we have used before publishing. So: the 14 canonical matrix prompts (model_matrix_gen.build_prompts) with
their own seeds, plus the dark psytrance prompt from the mood_oppose page, 15 in all.

Grid: 4 models (medium base, AdamW ep5, Goa LoRA ep63, Fusion+Goa 50/50) x 15 prompts x
  8 targets (naive Melodic/Space/Dark, Deconf_Melodic/Space/Dark/Uplifting/AntiDark) x gains 1024/2048/4096/8192, plus one
  baseline per model x prompt = 1,980 clips. 20 s, 24 Euler steps, cfg 7, cosine loss, n_iter 4, gamma 0.3: the same recipe
  as the one-prompt run.

Differences from that run, on purpose:
  - The baseline goes through the GUIDED sampler at gain 0 (rho = mu = 0), not generate() with no config (MASTER section 5).
  - No expandable_segments: on ROCm it decodes healthy latents to wrong or NaN audio (MASTER section 5).
  - Audio comes from generate(). The first render of a process is thrown away and compared with the second, and each process repeats its
    first clip every 40 clips and at the end (chunk_checks.jsonl). In the 1,980-clip run all of these matched, so the throwaway is a check, not a need.
  - A clip with dead audio or a non-finite latent is rendered again, up to twice, then left out of cells.jsonl (logged in faults.jsonl).
Targets: the de-confounded vectors from ANTIGRAVITY's deconf_targets.json, copied into the run dir at first start so a later rebuild
of that file cannot change them mid-run.

Outputs: AAC 192k in ~/evals_aac/control_runs/mood_deconf_20261103/ (where clip_metrics looks), cells.jsonl and run_meta.json beside
them; wavs on Mantu/sa3_control_runs/mood_deconf_20261103/. Resumable from cells.jsonl. Stops if either drive has < 15 GB free.
RUN: eval/run_mood_deconf.sh (chunks of 5 prompts, GPU lock released between chunks so others can get in).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SAO = HERE.parent
sys.path.insert(0, str(SAO / "control"))
sys.path.insert(0, str(SAO / "stable-audio-3"))
sys.path.insert(0, str(HERE))

RUN = "mood_deconf_20261103"
OUT = Path("/home/kim/evals_aac/control_runs") / RUN
WAV = Path("/run/media/kim/Mantu/sa3_control_runs") / RUN
SOURCE_TARGETS = Path("/home/kim/evals_aac/mood_finegrained/deconf_targets.json")
HEAD_CKPT = "/run/media/kim/Mantu/latch_sweep/mood_56d_best_40ep_20261031/C3_mood_lr8e-4_b64_cos40/latch_sa3_effnet_moodtheme_ep40.pt"
SRC = HERE / "render_mood_deconfounded.py"

FRAMES = 280
DURATION = 20.0
STEPS = 24
CFG = 7.0
SR = 44100
GAINS = (1024, 2048, 4096, 8192)
MIN_FREE_GB = 15
TRIES = 3
CHECK_EVERY = 40
EXTRA_PROMPTS = [{"id": "prompt_dark", "text": "2020s dark psytrance, dark mood, heavy bass, 148 bpm", "seed": 1102008041}]
NAIVE = {"Melodic": {34: 1.0, 55: 0.4, 26: 0.3}, "Space": {49: 1.0, 48: 0.3, 16: 0.3}, "Dark": {11: 1.0, 27: 0.4, 12: 0.3}}   # as in render_mood_finegrained_matrix.py
DECONF = ("Deconf_Melodic", "Deconf_Space", "Deconf_Dark", "Deconf_Uplifting", "Deconf_AntiDark")


def lora_paths():
    """The same three adapters as render_mood_deconfounded.py, read from its source so the two cannot drift."""
    s = SRC.read_text()
    return {k: re.search(rf'^{k} = "([^"]+)"', s, re.M).group(1) for k in ("CKPT_ADAMW", "CKPT_FUSION", "CKPT_GOA")}


def models():
    L = lora_paths()
    return {"base": [], "adamw": [(L["CKPT_ADAMW"], 1.0)], "goa": [(L["CKPT_GOA"], 1.0)],
            "combo_fusion_goa": [(L["CKPT_FUSION"], 0.5), (L["CKPT_GOA"], 0.5)]}


def prompts():
    import model_matrix_gen as M
    out = [{"id": p["id"], "text": p.get("text") or p.get("prompt"), "seed": int(p["seed"])} for p in M.build_prompts(n_per_band=3, n_kimlong=3)]
    assert all(p["text"] for p in out), "a canonical prompt has no text"
    return out + EXTRA_PROMPTS


def targets():
    """{target_id: (56, FRAMES)}, from the run dir's frozen copy of the de-confounded vectors."""
    frozen = OUT / "deconf_targets.json"
    if not frozen.exists():
        shutil.copy2(SOURCE_TARGETS, frozen)
    d = json.loads(frozen.read_text())["targets"]
    out = {}
    for name, bins in NAIVE.items():
        v = np.zeros(56, dtype=np.float32)
        for i, x in bins.items():
            v[i] = x
        out[name] = np.repeat(v[:, None], FRAMES, axis=1)
    for name in DECONF:
        out[name] = np.repeat(np.array(d[name]["vector"], dtype=np.float32)[:, None], FRAMES, axis=1)
    return out


def clip_id(model, pid, tid, gain):
    return f"{model}__{pid}__base0" if gain == 0 else f"{model}__{pid}__{tid}__g{gain}"


def all_cells(model_ids, prompt_list, target_ids):
    out = []
    for m in model_ids:
        for p in prompt_list:
            out.append(dict(id=clip_id(m, p["id"], None, 0), model=m, pid=p["id"], tid=None, gain=0, seed=p["seed"]))
            for t in target_ids:
                for g in GAINS:
                    out.append(dict(id=clip_id(m, p["id"], t, g), model=m, pid=p["id"], tid=t, gain=g, seed=p["seed"]))
    return out


def free_gb(p):
    return shutil.disk_usage(p).free / 2 ** 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="model id")
    ap.add_argument("--prompts", default="all", help="comma-separated prompt ids")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many clips (smoke test)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    WAV.mkdir(parents=True, exist_ok=True)
    plist = prompts()
    if args.prompts != "all":
        keep = args.prompts.split(",")
        plist = [p for p in plist if p["id"] in keep]
    tg = targets()
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    todo = [c for c in all_cells([args.model], plist, list(tg)) if c["id"] not in done]
    print(f"[{args.model}] {len(plist)} prompts, {len(todo)} clips to render", flush=True)
    if not todo:
        return

    import torch
    import torch.nn.utils.parametrize as P
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio

    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    loras = models()[args.model]
    if loras:
        model.load_lora([p for p, _ in loras])
        for i, (_, s) in enumerate(loras):
            model.set_lora_strength(float(s), lora_index=i)
        for mod in list(model.model.model.modules()) + list(model.model.conditioner.modules()):
            if P.is_parametrized(mod):
                for name in list(mod.parametrizations.keys()):
                    with torch.no_grad():
                        P.remove_parametrizations(mod, name, leave_parametrized=True)
    text = {p["id"]: p["text"] for p in plist}

    def render(c):
        """(audio on CPU, latent on CPU) for one cell. Either can be non-finite: the caller checks."""
        steered = c["gain"] > 0
        tgt = tg[c["tid"]] if steered else tg["Deconf_Melodic"]
        sink = []
        audio = model.generate(prompt=text[c["pid"]], duration=DURATION, steps=STEPS, cfg_scale=CFG, seed=c["seed"], batch_size=1, latents_sink=sink,
                               latch_configs=[{"model_path": HEAD_CKPT, "target_raw": tgt, "weight": float(c["gain"]) if steered else 1.0,
                                               "loss_type": "cosine", "start_pct": 0.0, "end_pct": 1.0}],
                               latch_hparams={"n_iter": 4, "gamma": 0.3} if steered else {"n_iter": 4, "gamma": 0.3, "rho": 0.0, "mu": 0.0})
        return audio.float().cpu(), sink[0].float().cpu()

    def bad(audio, z):
        return (not bool(torch.isfinite(z).all())) or (not bool(torch.isfinite(audio).all())) or float(audio.std()) < 1e-3

    def check_line(rec):
        with (OUT / "chunk_checks.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")

    # Throwaway first render, kept only as a measurement of the first-decode fault.
    a0, z0 = render(todo[0])
    a1, z1 = render(todo[0])
    check_line(dict(kind="first_vs_second", model=args.model, id=todo[0]["id"], first_bad=bad(a0, z0), second_bad=bad(a1, z1),
                    z_rms=float((z0 - z1).pow(2).mean().sqrt()), audio_std_first=float(a0.std()), audio_std_second=float(a1.std())))
    ref_z, ref_std = z1, float(a1.std())

    n = 0
    for k, c in enumerate(todo):
        if free_gb(OUT) < MIN_FREE_GB or free_gb(WAV) < MIN_FREE_GB:
            print("STOP: under the disk floor", flush=True)
            sys.exit(4)
        t0 = time.time()
        for attempt in range(TRIES):
            audio, z = render(c)
            if not bad(audio, z):
                break
            with (OUT / "faults.jsonl").open("a") as f:
                f.write(json.dumps(dict(id=c["id"], attempt=attempt, process_index=k, z_finite=bool(torch.isfinite(z).all()),
                                        audio_finite=bool(torch.isfinite(audio).all()), audio_std=float(audio.std()))) + "\n")
            print(f"FAULT {c['id']} attempt {attempt}", flush=True)
        else:
            print(f"LEFT OUT {c['id']}: no clean render in {TRIES} tries", flush=True)
            continue
        wav_path, aac = WAV / f"{c['id']}.wav", OUT / f"{c['id']}.m4a"
        save_audio(str(wav_path), audio[0][:, : int(DURATION * SR)], SR, normalize=True)
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(wav_path), "-c:a", "aac", "-b:a", "192k", str(aac)], check=True)
        rec = dict(c, process_index=k, attempts=attempt + 1, z_std=float(z.std()), z_max=float(z.abs().max()), audio_std=float(audio.std()), secs=round(time.time() - t0, 1))
        with log.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        del audio, z
        if k % 25 == 0:
            print(f"  {k + 1}/{len(todo)} {c['id']} {rec['secs']} s", flush=True)
        if n % CHECK_EVERY == 0:                 # same request as the reference: the latent and the audio should repeat
            ac, zc = render(todo[0])
            check_line(dict(kind="mid_chunk", model=args.model, id=todo[0]["id"], after_clips=n, bad=bad(ac, zc), z_rms=float((zc - ref_z).pow(2).mean().sqrt()),
                            audio_std_ref=ref_std, audio_std_now=float(ac.std())))
        if args.limit and n >= args.limit:
            break

    a2, z2 = render(todo[0])
    check_line(dict(kind="end_of_chunk", model=args.model, id=todo[0]["id"], end_bad=bad(a2, z2), z_rms=float((z2 - ref_z).pow(2).mean().sqrt()),
                    audio_std_start=ref_std, audio_std_end=float(a2.std())))
    print(f"[{args.model}] chunk done: {n} rendered", flush=True)


if __name__ == "__main__":
    main()
