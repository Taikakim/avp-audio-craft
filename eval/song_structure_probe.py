#!/usr/bin/env python
"""song_structure_probe.py — Kim 2026-09-15: can SA3 conjure a whole song?

Per clip: generate a fresh "intro sequence" and "outro" txt2audio clip (same
seed + model + base prompt, with ", song section: <X>" appended), place
[intro][original][outro] end to end, then mask a 60s-wide window straddling
EACH of the two seams (30s reaching into each neighboring clip) and let the
model regenerate both seams in one pass. Given the original clip is only
~47.5s, the two seam-masks (30s from each side) overlap over it -- the
entire original ends up inside the masked/generated region. That's the
literal, deliberate consequence of the confirmed geometry (Kim signed off on
1-minute-total-per-seam + keeping the original clip's own length as-is), not
a bug -- flagged here and in the run log so it's not a silent surprise.
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

OUT_DIR = Path("/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/song_structure_probe")
OUT_DIR.mkdir(parents=True, exist_ok=True)
SEAM_HALF_SEC = 30.0  # 60s total mask width per seam, 30s into each neighbor

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
        out_path = OUT_DIR / f"{key}_song.wav"
        if out_path.exists():
            print(f"[skip] {key}", flush=True)
            continue
        ensure_lora(clip["ckpt"])
        middle, sra = load(clip["path"])
        assert sra == sr
        middle_dur = middle.shape[1] / sr

        print(f"[gen] {key}_intro", flush=True)
        intro = model.generate(
            prompt=clip["prompt"] + ", song section: intro sequence",
            duration=middle_dur, steps=clip["steps"], cfg_scale=clip["cfg"],
            seed=clip["seed"], batch_size=1,
        )[0].float().cpu().numpy()
        intro_dur = intro.shape[1] / sr

        print(f"[gen] {key}_outro", flush=True)
        outro = model.generate(
            prompt=clip["prompt"] + ", song section: outro",
            duration=middle_dur, steps=clip["steps"], cfg_scale=clip["cfg"],
            seed=clip["seed"], batch_size=1,
        )[0].float().cpu().numpy()
        outro_dur = outro.shape[1] / sr

        composite = np.concatenate([intro, middle, outro], axis=1)
        total_dur = composite.shape[1] / sr

        seam1 = (intro_dur - SEAM_HALF_SEC, intro_dur + SEAM_HALF_SEC)
        seam2 = (intro_dur + middle_dur - SEAM_HALF_SEC, intro_dur + middle_dur + SEAM_HALF_SEC)
        overlap = seam1[1] > seam2[0]
        print(f"[seams] {key}: seam1={seam1} seam2={seam2} overlap={overlap} "
              f"(middle={middle_dur:.1f}s, {'ENTIRE MIDDLE MASKED' if overlap else 'middle partially preserved'})",
              flush=True)

        print(f"[gen] {key}_song dur={total_dur:.1f}s", flush=True)
        out = model.generate(
            prompt=clip["prompt"], duration=total_dur, steps=clip["steps"], cfg_scale=clip["cfg"],
            seed=clip["seed"], batch_size=1, sample_size=int((total_dur + 8) * sr),
            inpaint_audio=(sr, torch.tensor(composite)),
            inpaint_mask_start_seconds=[seam1[0], seam2[0]],
            inpaint_mask_end_seconds=[seam1[1], seam2[1]],
        )
        save_audio(str(out_path), out[0].float().cpu(), sr)
        save_audio(str(OUT_DIR / f"{key}_intro_raw.wav"), torch.tensor(intro), sr)
        save_audio(str(OUT_DIR / f"{key}_outro_raw.wav"), torch.tensor(outro), sr)
        print(f"[done] {key}_song", flush=True)


if __name__ == "__main__":
    main()
