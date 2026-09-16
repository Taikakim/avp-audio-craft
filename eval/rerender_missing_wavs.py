#!/usr/bin/env python
"""rerender_missing_wavs.py — Kim 2026-09-17: regenerates the mixtape's model_matrix
clips whose .wav was deleted (m4a-only remains), using the exact params recorded in
manifest.jsonl (model/ckpt/cfg/strength/prompt_text/seed/steps/duration), so the
result matches the original render bit-for-bit modulo backend nondeterminism.
Grouped by (base_ckpt_dir, epoch) to minimize model reloads.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import json
import sys
from pathlib import Path

import torch
from stable_audio_3 import StableAudioModel

sys.path.insert(0, "/home/kim/Projects/SAO/control")
from sa3_control.audio_io import save_audio  # noqa: E402

FPS = 44100 / 4096


def main():
    specs = json.loads(Path(sys.argv[1]).read_text())
    ckpt_map = json.loads(Path(sys.argv[2]).read_text())

    renderable = []
    for r in specs:
        key = f"{r['model']}|{r['ckpt']}"
        p = ckpt_map.get(key)
        if isinstance(p, str):
            renderable.append({**r, "ckpt_path": p})

    # group by (ckpt_path, is_ptm) to minimize reloads
    renderable.sort(key=lambda r: r["ckpt_path"])

    current_ckpt = None
    model = None
    sr = None
    for r in renderable:
        # out_path in the spec is the ORIGINAL .m4a path (which always exists --
        # only the .wav was deleted); render to the .wav sibling instead.
        out_path = Path(r["out_path"]).with_suffix(".wav")
        if out_path.exists():
            print(f"[skip] {out_path.name}", flush=True)
            continue

        is_ptm = "_ptm" in r["model"]
        base_model_id = "medium" if is_ptm else "medium-base"

        if current_ckpt != (r["ckpt_path"], base_model_id):
            print(f"[load] {base_model_id} + {r['ckpt_path']}", flush=True)
            if model is not None:
                del model
                torch.cuda.empty_cache()
            model = StableAudioModel.from_pretrained(base_model_id, device="cuda")
            model.load_lora([r["ckpt_path"]])
            current_ckpt = (r["ckpt_path"], base_model_id)
            sr = model.model.sample_rate

        strength = float(r["strength"])
        model.set_lora_strength(strength)

        dur = float(r["duration"])
        frames = round(dur * FPS)
        sample_size = frames * 4096

        print(f"[gen] {out_path.name} cfg={r['cfg']} strength={strength} steps={r['steps']}", flush=True)
        out = model.generate(
            prompt=r["prompt_text"], duration=dur, steps=int(r["steps"]),
            cfg_scale=float(r["cfg"]), seed=int(r["seed"]), batch_size=1,
            sample_size=sample_size,
        )
        save_audio(str(out_path), out[0].float().cpu(), sr)

    print("[all done]", flush=True)


if __name__ == "__main__":
    main()
