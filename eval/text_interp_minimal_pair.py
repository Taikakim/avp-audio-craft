#!/usr/bin/env python
"""text_interp_minimal_pair.py — Kim 2026-09-16: re-runs the T5-embedding-interpolation
probe (layered_dual_lora_probe.py, probe 1) with a MINIMAL-PAIR prompt difference
("aggressive" vs "peaceful", same genre/tempo) instead of the original pair (which also
changed era/genre/BPM) -- isolates whether the interpolation tracks a clean mood gradient
without those other axes moving too. Same fixed adapter, seed, duration as before.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.models.lora.model import set_lora_strength  # noqa: E402
from layered_dual_lora_probe import CKPT_A, DURATION, STEPS, SEED, cond_for, raw_prompt_embed, euler_generate  # noqa: E402

PROMPT_A = "an aggressive goa trance track, 138 bpm"
PROMPT_B = "a peaceful goa trance track, 138 bpm"


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/text_interp_minimal_pair")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([CKPT_A])
    frames = round(DURATION * model.model.sample_rate / model.model.pretransform.downsampling_ratio)
    tensors_a, cond_full_a = cond_for(model, PROMPT_A, DURATION, frames, "cuda")
    tensors_b, _ = cond_for(model, PROMPT_B, DURATION, frames, "cuda")
    embed_a, mask_a = raw_prompt_embed(tensors_a)
    embed_b, _ = raw_prompt_embed(tensors_b)
    assert embed_a.shape == embed_b.shape

    set_lora_strength(model.model, 1.0, lora_index=0)
    for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
        out_path = out_dir / f"minimalpair_a{int(alpha*100):03d}.wav"
        if out_path.exists():
            print(f"[skip] {out_path.name}", flush=True)
            continue
        embed = (1 - alpha) * embed_a + alpha * embed_b
        cond = dict(cond_full_a)
        cond["cross_attn_cond"] = embed
        cond["cross_attn_mask"] = mask_a
        print(f"[gen] {out_path.name}", flush=True)
        audio, sr = euler_generate(model, cond, DURATION, STEPS, SEED)
        save_audio(str(out_path), audio, sr)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
