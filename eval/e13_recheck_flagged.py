#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e13_recheck_flagged.py -- E13's render set expandable_segments, which on ROCm can decode a healthy latent to wrong audio that is not dead
(MASTER section 5; base0__goa__s9012: same latent, stored rms 0.109, clean decode 0.274). Finds clips well below their prompt + seed group,
re-renders them without the flag, and where the level differs by more than 10% keeps the old clip in _flag_replaced/ and installs the new one.
A low level alone proves nothing (solo piano at high gain is really quieter), so each suspect is settled by the re-render.
Writes flag_recheck.jsonl. RUN (GPU lock held by the caller): SAO/.venv/bin/python eval/e13_recheck_flagged.py
"""
import json
import os
import shutil
import sqlite3
import statistics as st
import subprocess
import sys
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "stable-audio-3"))
sys.path.insert(0, str(HERE))
import numpy as np
import chroma_e13_render as E
from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio

O = E.OUT
RATIO = 0.65
HEADS = {**E.heads(), **E.size_heads()}


def rms_of(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32)
    return float(np.sqrt((x ** 2).mean()))


def suspects():
    db = sqlite3.connect(HERE / "clip_metrics.db")
    rms = {Path(p).name: r for p, r in db.execute("select path,rms from metrics where path like ? and rms is not null", ("%chroma_e13_20261028%",))}
    groups = {}
    for l in open(O / "cells.jsonl"):
        c = json.loads(l)
        if c.get("clip") in rms and not c["clip"].startswith("base__"):
            groups.setdefault((c["prompt"], c["seed"]), []).append(c)
    out = []
    for v in groups.values():
        m = st.median(rms[c["clip"]] for c in v)
        out += [c for c in v if rms[c["clip"]] / m < RATIO]
    return out


def main():
    todo = suspects()
    done = set()
    log_path = O / "flag_recheck.jsonl"
    if log_path.exists():
        done = {json.loads(l)["clip"] for l in open(log_path)}
    todo = [c for c in todo if c["clip"] not in done]
    print(len(todo), "to re-render", flush=True)
    if not todo:
        return
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    n_frames = int(round(E.DURATION_SEC * E.FPS))
    keep = O / "_flag_replaced"
    keep.mkdir(exist_ok=True)
    tmp = O / "_recheck_tmp.wav"

    def render(c):
        head = HEADS[c["head"]] if c["head"] != "base" else HEADS["C3_ep10_ema1"]
        sink = []
        a = model.generate(prompt=E.prompt_text(c["prompt"]), duration=E.DURATION_SEC, steps=E.STEPS, cfg_scale=E.CFG, seed=c["seed"], latents_sink=sink,
                           latch_configs=[{"model_path": str(head), "target_raw": E.build_target(c["target"] or "C", n_frames), "weight": 1.0, "loss_type": "cosine"}],
                           latch_hparams={"rho": float(c["gain"]), "mu": float(c["gain"])})
        return a.float().cpu(), float(sink[0].float().std())

    render(todo[0])                                      # first render of a process, not used
    with log_path.open("a") as log:
        for c in todo:
            a, z = render(c)
            save_audio(str(tmp), a[0][:, : int(E.DURATION_SEC * 44100)], 44100, normalize=True)
            new, old = rms_of(tmp), rms_of(O / c["clip"])
            changed = abs(new / max(old, 1e-6) - 1) > 0.10
            if changed:
                shutil.move(O / c["clip"], keep / c["clip"])
                subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(O / c["clip"])], check=True)
            rec = dict(clip=c["clip"], rms_old=round(old, 4), rms_new=round(new, 4), z_old=round(c["z_std"], 4), z_new=round(z, 4), replaced=changed)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print(rec, flush=True)
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
