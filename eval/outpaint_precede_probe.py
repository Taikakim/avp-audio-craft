#!/usr/bin/env python
"""outpaint_precede_probe.py — Kim 2026-09-15: for each test clip, generate a
15s continuation (outpaint past the end) and a 15s lead-in (inpaint before the
start), each in 4 variants (orig prompt/orig seed, orig prompt/new seed,
violin prompt/orig seed, violin prompt/new seed), using both the clip's OWN
LoRA and a "foreign" LoRA from another clip in the set.

Pure native SA3 inpaint (model.generate(inpaint_audio=..., inpaint_mask_*)),
no chroma guidance -- this tests raw prompt/seed/model outpaint behavior.
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

EXT_SEC = 15.0
OUT_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/outpaint_probe")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS = {
    "A": dict(name="dora128adj_avp_8ep_final_ptm__rb_bracket_0",
              path="/home/kim/evals_aac/model_matrix/dora128adj_avp_8ep_final_ptm__ep0__cfg1__w100__rb_bracket_0__s1102008041__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt",
              prompt="2020s goa trance, melodic mood, 148 bpm", seed=1102008041),
    "B": dict(name="dora128adj_avp_aug10_lr1e4_ptm__rb_bracket_0",
              path="/home/kim/evals_aac/model_matrix/dora128adj_avp_aug10_lr1e4_ptm__ep74__cfg1__w100__rb_bracket_0__s1102008041__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_aug10_lr1e4/epoch=74-step=3000.weights.ckpt",
              prompt="2020s goa trance, melodic mood, 148 bpm", seed=1102008041),
    "C": dict(name="fp32cmp_avp_t512_bs8_lr1e4_repr_ptm__rb_common_1",
              path="/home/kim/evals_aac/model_matrix/fp32cmp_avp_t512_bs8_lr1e4_repr_ptm__ep7__cfg1__w100__rb_common_1__s225176290__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/fp32cmp_avp_t512_bs8_lr1e4_repr/epoch=7-step=2392.ckpt",
              prompt="mid 90s goa trance, melodic space mood, 140 bpm", seed=225176290),
    "D": dict(name="dora16_avp_familiarity_8ep_ptm__rb_rare_8",
              path="/home/kim/evals_aac/model_matrix/dora16_avp_familiarity_8ep_ptm__ep4__cfg1__w100__rb_rare_8__s278158216__st8__d48.m4a",
              ckpt="/run/media/kim/Mantu/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt",
              prompt="mid 90s goa trance, techno, space dark mood, 140 bpm", seed=278158216),
}
FOREIGN = {"A": "B", "B": "C", "C": "D", "D": "A"}


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


def variants(orig_prompt, orig_seed):
    violin = orig_prompt + ", violin lead melody"
    new_seed = orig_seed + 1
    return [
        ("origprompt_origseed", orig_prompt, orig_seed),
        ("origprompt_newseed", orig_prompt, new_seed),
        ("violin_origseed", violin, orig_seed),
        ("violin_newseed", violin, new_seed),
    ]


def main():
    print("[load] model (medium, post-trained)", flush=True)
    model = StableAudioModel.from_pretrained("medium", device="cuda")
    sr = model.model.sample_rate
    loaded_ckpt = None

    def ensure_lora(ckpt):
        # different LoRA ranks (e.g. rank16 vs rank128) can't be swapped on a live
        # model object -- rebuild fresh from_pretrained on every checkpoint change.
        nonlocal loaded_ckpt, model
        if ckpt != loaded_ckpt:
            del model
            torch.cuda.empty_cache()
            model = StableAudioModel.from_pretrained("medium", device="cuda")
            model.load_lora([ckpt])
            loaded_ckpt = ckpt

    for key, clip in CLIPS.items():
        audio, sra = load(clip["path"])
        assert sra == sr
        orig_dur = audio.shape[1] / sr
        n_orig = audio.shape[1]
        n_ext = int(EXT_SEC * sr)
        n_total = n_orig + n_ext

        for role, ckpt_key in [("own", key), ("foreign", FOREIGN[key])]:
            ckpt = CLIPS[ckpt_key]["ckpt"]
            ensure_lora(ckpt)
            for direction in ("outpaint", "precede"):
                if direction == "outpaint":
                    padded = np.concatenate([audio, np.zeros((audio.shape[0], n_ext), dtype=audio.dtype)], axis=1)
                    mask_start, mask_end = orig_dur, n_total / sr
                else:
                    padded = np.concatenate([np.zeros((audio.shape[0], n_ext), dtype=audio.dtype), audio], axis=1)
                    mask_start, mask_end = 0.0, EXT_SEC
                for tag, prompt, seed in variants(clip["prompt"], clip["seed"]):
                    out_name = f"{key}_{direction}_{role}-{ckpt_key}_{tag}"
                    out_path = OUT_DIR / f"{out_name}.wav"
                    if out_path.exists():
                        print(f"[skip] {out_name}", flush=True)
                        continue
                    print(f"[gen] {out_name}", flush=True)
                    out = model.generate(
                        prompt=prompt, duration=n_total / sr, steps=8, cfg_scale=1.0,
                        seed=seed, batch_size=1, sample_size=int((n_total / sr + 8) * sr),
                        inpaint_audio=(sr, torch.tensor(padded)),
                        inpaint_mask_start_seconds=mask_start,
                        inpaint_mask_end_seconds=mask_end,
                    )
                    save_audio(str(out_path), out[0].float().cpu(), sr)
        print(f"[done clip] {key}", flush=True)


if __name__ == "__main__":
    main()
