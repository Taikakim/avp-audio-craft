#!/usr/bin/env python
"""mp_crossmodel_render.py — uniform 6-prompt x checkpoint grid for the multiprompt
cross-model eval page (Kim 2026-07-10: add AVP + recent-goa HoF checkpoints to mp.html
with explicit prompts + per-model recipes). One dir, one render config, so the
checkpoint pulldown compares like-for-like. Reuses the proven eval_prompt_styles pattern
(load_lora + set_lora_strength + generate). Idempotent: skips existing wavs.

Config matches the avp boards exactly: steps16, cfg5.0, dur47, seed1234, DoRA 1.0.
Run (SA3 venv): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/mp_crossmodel_render.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio          # noqa: E402
from stable_audio_3 import StableAudioModel           # noqa: E402
import torch                                          # noqa: E402

RUNS = "/run/media/kim/Mantu/sa3_lora_runs"
OUT = Path(RUNS) / "mp_crossmodel"

# 6-prompt set (Kim-confirmed): 3 shared + 3 AVP-only
PROMPTS = {
    "goa1":   "aggressive upbeat goa trance",
    "psy":    "psytrance, 140 bpm",
    "upbeat": "upbeat dance music",
    "trig":   "aavepyörä",
    "tstyle": "upbeat dance music, aavepyörä style",
    "kimlong": ("bittersweet synth music with influences from goa trance and 80s retro "
                "videogame music, dorian scale, BPM 138, steady 90s trance beat, punchy "
                "bright kick, 16th octave bass runs, tight snares every second beat"),
}

# label -> ckpt path (None = base model, no adapter)
CKPTS = {
    "base":           None,
    "orig_ep02":      f"{RUNS}/dora16_avp_originals_earlyeps/epoch=2-step=108.ckpt",
    "orig_ep06f":     f"{RUNS}/dora16_avp_originals_densewin/epoch=6-step=252.ckpt",
    "orig_ep31":      f"{RUNS}/dora16_avp_originals_64ep/epoch=31-step=1152.ckpt",
    "armG_ep14":      f"{RUNS}/dora128adj_avp_aug10_lr1e4/epoch=14-step=600.ckpt",
    "r64tiered_ep7":  f"{RUNS}/dora64_avp_tiered_lr1e4/epoch=7-step=288.ckpt",
    "newstack_ep7":   f"{RUNS}/dora16_goa_newstack_8ep/epoch=7-step=10800.ckpt",
    "everything_ep7": f"{RUNS}/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt",
}

SEED, STRENGTH, STEPS, CFG, DUR = 1234, 1.0, 16, 5.0, 47.0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"purpose": "uniform 6-prompt x checkpoint grid for the multiprompt cross-model "
                       "eval page; steps16 cfg5 dur47 seed1234 DoRA1.0",
            "prompts": PROMPTS, "checkpoints": {k: (v or "medium-base (no adapter)")
                                                for k, v in CKPTS.items()},
            "gen": {"steps": STEPS, "cfg": CFG, "dur": DUR, "seed": SEED, "strength": STRENGTH},
            "note": "orig_ep13f/ep27f dropped: fine-ladder ckpts no longer on disk. "
                    "recipes: eval/mp_checkpoint_recipes.json"}
    (OUT / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    for label, ckpt in CKPTS.items():
        # all 6 prompts for this ckpt exist? skip the (re)load entirely
        need = [p for p in PROMPTS if not (OUT / f"{label}__{p}__s{SEED}__st10.wav").exists()]
        if not need:
            print(f"[skip-all] {label}", flush=True); continue
        # fresh model per checkpoint => guaranteed-clean adapter state (no stacking)
        model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        sr = model.model.sample_rate
        if ckpt:
            model.load_lora([ckpt])
            try: model.set_lora_strength(STRENGTH)
            except Exception: pass
        print(f"[load] {label} <- {ckpt or 'base'}", flush=True)
        for p in need:
            t0 = time.time()
            out = model.generate(prompt=PROMPTS[p], duration=DUR, steps=STEPS,
                                 cfg_scale=CFG, seed=SEED, batch_size=1)
            y = out[0].float().cpu()
            save_audio(OUT / f"{label}__{p}__s{SEED}__st10.wav", y, sr, normalize=True)
            print(f"[{label}/{p}] {time.time()-t0:5.1f}s", flush=True)
        del model
        torch.cuda.empty_cache()
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
