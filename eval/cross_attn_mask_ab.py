#!/usr/bin/env python
"""cross_attn_mask_ab.py — A/B the re-enabled text cross-attention padding mask (CONTINUITY
2026-08-03; the semantic-gutting-sweep standout — SA3 nulls the T5Gemma padding mask so text
cross-attn attends over PADDED tokens on every gen). Renders a fixed prompt/seed grid; the ARM is
chosen by the SA3_ENABLE_CROSS_ATTN_MASK env (read at import in dit.py), and the output auto-tags
masked/ vs control/. Run BOTH arms on SDPA so the comparison isolates the mask, not the backend:

  masked : SA3_ENABLE_CROSS_ATTN_MASK=1 SA3_DISABLE_FLASH_ATTN=1 /home/kim/Projects/SAO/.venv/bin/python eval/cross_attn_mask_ab.py
  control:                             SA3_DISABLE_FLASH_ATTN=1 /home/kim/Projects/SAO/.venv/bin/python eval/cross_attn_mask_ab.py

Then listen: matched filenames across masked/ and control/ -> same-playhead compare. Prompts vary in
LENGTH on purpose (short = more padding = bigger expected mask effect). GPU MUTEX: hold the .gpu.lock
(or run only when the card is free). Output on the eval drive, NOT the SAO tree.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")   # rocBLAS 5.2-vs-5.5 validator mismatch = noisy untuned fallback
import argparse, sys
sys.path.insert(0, "/home/kim/Projects/SAO/control")
import torch  # noqa: F401  (import after env so the flag/flash settings are seen)
from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio

PROMPTS = [
    ("short_bare",   "goa trance"),
    ("short_tagged", "TrackType: Music, VocalType: Instrumental, mid-90s goa trance, hypnotic, 145 bpm"),
    ("medium",       "An energetic goa trance track with a driving acid bassline, swirling arpeggiated "
                     "leads, and a hypnotic four-on-the-floor kick."),
    ("long",         "A high-energy mid-90s Goa trance journey: a relentless rolling acid bassline anchors "
                     "the mix while layered arpeggiated synth leads weave a hypnotic, psychedelic melody; "
                     "shimmering pads and tape-delay flourishes build tension across long phrases, punctuated "
                     "by filter sweeps and a breakdown that strips back to a resonant drone before the full "
                     "groove returns — dark, trance-inducing, and dancefloor-focused."),
]
SEEDS = [1234, 4242]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=None, help="optional adapter ckpt (default: medium-base, no adapter)")
    ap.add_argument("--out", default="/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/cross_attn_mask_ab")
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--duration", type=float, default=47.55)  # T512
    a = ap.parse_args()

    masked = os.environ.get("SA3_ENABLE_CROSS_ATTN_MASK", "").strip().lower() in ("1", "true", "yes", "on")
    tag = "masked" if masked else "control"
    outdir = os.path.join(a.out, tag)
    os.makedirs(outdir, exist_ok=True)
    print(f"[ab] arm={tag}  SA3_ENABLE_CROSS_ATTN_MASK={masked}  "
          f"SA3_DISABLE_FLASH_ATTN={os.environ.get('SA3_DISABLE_FLASH_ATTN')}  -> {outdir}", flush=True)

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    if a.ckpt:
        model.load_lora([a.ckpt])
        print(f"[ab] adapter: {a.ckpt}", flush=True)

    for pid, text in PROMPTS:
        for seed in SEEDS:
            audio = model.generate(prompt=text, duration=a.duration, steps=a.steps,
                                   cfg_scale=a.cfg, seed=seed, batch_size=1)
            if audio.dim() == 3:                      # drop the batch dim -> (C, T) for save_audio
                audio = audio.squeeze(1) if audio.shape[1] == 1 else audio.squeeze(0)
            fn = os.path.join(outdir, f"{pid}_seed{seed}.flac")
            save_audio(fn, audio, 44100)
            print(f"[ab] wrote {tag}/{pid}_seed{seed}.flac", flush=True)
    print(f"[ab] DONE arm={tag} -> {outdir}", flush=True)

if __name__ == "__main__":
    main()
    # Hard-exit: skips the ROCm/torch/native-lib atexit teardown that can double-free
    # ("corrupted double-linked list / Aborted") AFTER all outputs are already written.
    import sys
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(0)
