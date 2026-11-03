#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e13_fix_baselines.py -- re-render E13's 12 gain-0 baselines without expandable_segments (MASTER section 5). Goa s77 and s9012 came out wrong: same
latent as a clean render, about 40% of the level, Audiobox CE about 4, and every steered clip on those two seeds then "failed" the gate on CE drift.
Old clips go to _flag_replaced/. cells.jsonl gets the new measures, and their clip_metrics rows are deleted so the scoring pass redoes them.
Also renders goa s77, s9012, s5678 through generate() with no LatCH config, to check the older note that the default sampler is a different render.
RUN (GPU lock held by the caller): SAO/.venv/bin/python eval/e13_fix_baselines.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "stable-audio-3"))
sys.path.insert(0, str(HERE))
import numpy as np
import torch
import chroma_e13_render as E
from harmonic import same_chroma as sc
from sa3_control.audio_io import save_audio
from stable_audio_3 import StableAudioModel

O = E.OUT
KEEP = O / "_flag_replaced"
CHECK = O / "_default_sampler_check"


def main():
    KEEP.mkdir(exist_ok=True)
    CHECK.mkdir(exist_ok=True)
    lines = [json.loads(l) for l in (O / "cells.jsonl").read_text().splitlines() if l.strip()]
    base = [c for c in lines if c.get("clip", "").startswith("base0__")]
    n_frames = int(round(E.DURATION_SEC * E.FPS))
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    def guided(c):
        sink = []
        a = model.generate(prompt=E.prompt_text(c["prompt"]), duration=E.DURATION_SEC, steps=E.STEPS, cfg_scale=E.CFG, seed=c["seed"], latents_sink=sink,
                           latch_configs=[{"model_path": str(E.PROD), "target_raw": E.build_target("C", n_frames), "weight": 1.0, "loss_type": "cosine"}],
                           latch_hparams={"rho": 0.0, "mu": 0.0})
        return a[0].float().cpu(), sink[-1].float().cpu()

    guided(base[0])                                      # first render of a process, not used
    for c in base:
        wav, z = guided(c)
        if not torch.isfinite(wav).all() or float(wav.std()) < 1e-3:
            print("DEAD", c["clip"], flush=True)
            continue
        wp = O / "_fix.wav"
        save_audio(str(wp), wav, sc.SAME_SR)
        old = O / c["clip"]
        if not (KEEP / c["clip"]).exists():
            shutil.copy2(old, KEEP / c["clip"])
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wp), "-c:a", "aac", "-b:a", "192k", str(old)], check=True)
        wp.unlink()
        print(c["clip"], "z old", c["z_std"], "new", round(float(z.std()), 4), flush=True)
        c["m"] = E.measure(wav.numpy(), None, n_frames)
        c["z_std"] = round(float(z.std()), 4)
        c["rerendered"] = "2026-11-03 without expandable_segments"
    tmp = O / "cells.jsonl.tmp"
    tmp.write_text("".join(json.dumps(c) + "\n" for c in lines))
    tmp.replace(O / "cells.jsonl")
    db = sqlite3.connect(HERE / "clip_metrics.db")
    for c in base:
        db.execute("delete from metrics where path = ?", (str(O / c["clip"]),))
    db.commit()
    for seed in (77, 9012, 5678):
        a = model.generate(prompt=E.prompt_text("goa"), duration=E.DURATION_SEC, steps=E.STEPS, cfg_scale=E.CFG, seed=seed)
        save_audio(str(CHECK / f"default__goa__s{seed}.wav"), a[0].float().cpu(), sc.SAME_SR)
        print("default sampler goa", seed, "std", round(float(a[0].float().std()), 4), flush=True)


if __name__ == "__main__":
    main()
