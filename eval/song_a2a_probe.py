#!/usr/bin/env python
"""song_a2a_probe.py — Kim 2026-09-15, stage 2: take the finished song-structure
composites (song_structure_probe.py's output) and run audio-to-audio at
init_noise_level 0.5 and 0.75, each through a few DIFFERENT models (not the
one that made the piece) to see how a foreign checkpoint's "take" sounds.
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

import soundfile as sf
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/control")
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

SONG_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/song_structure_probe")
OUT_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/song_a2a_probe")
OUT_DIR.mkdir(parents=True, exist_ok=True)
NOISE_LEVELS = [0.5, 0.75]

CLIPS = {
    "A": dict(prompt="2020s goa trance, melodic mood, 148 bpm", seed=1102008041, steps=8, cfg=1.0,
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"),
    "B": dict(prompt="2020s goa trance, melodic mood, 148 bpm", seed=1102008041, steps=8, cfg=1.0,
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_aug10_lr1e4/epoch=74-step=3000.weights.ckpt"),
    "C": dict(prompt="mid 90s goa trance, melodic space mood, 140 bpm", seed=225176290, steps=8, cfg=1.0,
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/fp32cmp_avp_t512_bs8_lr1e4_repr/epoch=7-step=2392.ckpt"),
    "D": dict(prompt="mid 90s goa trance, techno, space dark mood, 140 bpm", seed=278158216, steps=8, cfg=1.0,
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt"),
}


def load(track):
    a, sr = sf.read(track, dtype="float32", always_2d=True)
    return a.T, sr


def main():
    print("[load] model", flush=True)
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

    for song_key, song_clip in CLIPS.items():
        song_path = SONG_DIR / f"{song_key}_song.wav"
        audio, sra = load(str(song_path))
        assert sra == sr
        dur = audio.shape[1] / sr

        for model_key, model_clip in CLIPS.items():
            if model_key == song_key:
                continue  # a foreign model only
            ensure_lora(model_clip["ckpt"])
            for nl in NOISE_LEVELS:
                out_name = f"{song_key}_song__model-{model_key}__nl{int(nl*100)}"
                out_path = OUT_DIR / f"{out_name}.wav"
                if out_path.exists():
                    print(f"[skip] {out_name}", flush=True)
                    continue
                print(f"[gen] {out_name}", flush=True)
                out = model.generate(
                    prompt=model_clip["prompt"], duration=dur, steps=model_clip["steps"],
                    cfg_scale=model_clip["cfg"], seed=model_clip["seed"], batch_size=1,
                    init_audio=(sr, torch.tensor(audio)), init_noise_level=nl,
                )
                save_audio(str(out_path), out[0].float().cpu(), sr)
                print(f"[done] {out_name}", flush=True)


if __name__ == "__main__":
    main()
