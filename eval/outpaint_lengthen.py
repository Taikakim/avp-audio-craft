#!/usr/bin/env python
"""outpaint_lengthen.py — Kim 2026-09-15: outpaint a handful of clips to 2x,
3x, 4x, and 6x their original length in one shot each (single masked
continuation call, original clip as the only real context — no chaining).
Own model/prompt/seed per clip, matching outpaint_precede_probe.py's clip set.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/control")
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

OUT_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/lengthen_probe")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MULTIPLIERS = [2, 3, 4, 6]

CLIPS = {
    "A": dict(path="/home/kim/evals_aac/model_matrix/dora128adj_avp_8ep_final_ptm__ep0__cfg1__w100__rb_bracket_0__s1102008041__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt",
              prompt="2020s goa trance, melodic mood, 148 bpm", seed=1102008041, steps=8, cfg=1.0),
    "B": dict(path="/home/kim/evals_aac/model_matrix/dora128adj_avp_aug10_lr1e4_ptm__ep74__cfg1__w100__rb_bracket_0__s1102008041__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_aug10_lr1e4/epoch=74-step=3000.weights.ckpt",
              prompt="2020s goa trance, melodic mood, 148 bpm", seed=1102008041, steps=8, cfg=1.0),
    "C": dict(path="/home/kim/evals_aac/model_matrix/fp32cmp_avp_t512_bs8_lr1e4_repr_ptm__ep7__cfg1__w100__rb_common_1__s225176290__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/fp32cmp_avp_t512_bs8_lr1e4_repr/epoch=7-step=2392.ckpt",
              prompt="mid 90s goa trance, melodic space mood, 140 bpm", seed=225176290, steps=8, cfg=1.0),
    "D": dict(path="/home/kim/evals_aac/model_matrix/dora16_avp_familiarity_8ep_ptm__ep4__cfg1__w100__rb_rare_8__s278158216__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt",
              prompt="mid 90s goa trance, techno, space dark mood, 140 bpm", seed=278158216, steps=8, cfg=1.0),
}


def load(track):
    try:
        a, sr = sf.read(track, dtype="float32", always_2d=True)
        if sr != 44100:
            raise ValueError("resample")
    except Exception:
        with tempfile.TemporaryDirectory() as td:
            wav = f"{td}/dec.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", track, "-ar", "44100",
                            "-ac", "2", wav], check=True)
            a, sr = sf.read(wav, dtype="float32", always_2d=True)
    return a.T, sr


def main():
    print("[load] model (medium, post-trained)", flush=True)
    model = StableAudioModel.from_pretrained("medium", device="cuda")
    sr = model.model.sample_rate
    loaded_ckpt = None

    def ensure_lora(ckpt):
        nonlocal loaded_ckpt, model
        if ckpt != loaded_ckpt:
            del model
            torch.cuda.empty_cache()
            model = StableAudioModel.from_pretrained("medium", device="cuda")
            model.load_lora([ckpt])
            loaded_ckpt = ckpt

    for key, clip in CLIPS.items():
        ensure_lora(clip["ckpt"])
        audio, sra = load(clip["path"])
        assert sra == sr
        orig_dur = audio.shape[1] / sr
        n_orig = audio.shape[1]

        for mult in MULTIPLIERS:
            out_name = f"{key}_x{mult}"
            out_path = OUT_DIR / f"{out_name}.wav"
            if out_path.exists():
                print(f"[skip] {out_name}", flush=True)
                continue
            n_total = n_orig * mult
            n_ext = n_total - n_orig
            padded = np.concatenate([audio, np.zeros((audio.shape[0], n_ext), dtype=audio.dtype)], axis=1)
            print(f"[gen] {out_name} orig={orig_dur:.1f}s -> {n_total/sr:.1f}s (+{n_ext/sr:.1f}s)", flush=True)
            out = model.generate(
                prompt=clip["prompt"], duration=n_total / sr, steps=clip["steps"], cfg_scale=clip["cfg"],
                seed=clip["seed"], batch_size=1, sample_size=int((n_total / sr + 8) * sr),
                inpaint_audio=(sr, torch.tensor(padded)),
                inpaint_mask_start_seconds=orig_dur,
                inpaint_mask_end_seconds=n_total / sr,
            )
            save_audio(str(out_path), out[0].float().cpu(), sr)
            print(f"[done] {out_name}", flush=True)


if __name__ == "__main__":
    main()
