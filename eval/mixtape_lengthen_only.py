#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-27)
"""mixtape_lengthen_only.py -- the 3x-extension step of mixtape_lengthen_and_prep.py WITHOUT its outgoing fade/a2a prep (v7 places
clips on one timeline and band-swaps, it does not want a pre-dissolved tail). Same settings as the earlier mixtape pipeline:
medium-base + BRIDGE_CKPT, prompt 'aggressive upbeat goa trance', 24 steps, cfg 6, seed 1234, chain_dj_overlay.outpaint_forward
(Kim's validated 3x outpaint). Input --clips-json = [{"id","path"}], output <out>/<id>_len3x.wav (skips existing).
Owner ask 2026-10-27: 'we already know how to make clean mixes ... remember to 3x extend the clips before cross-fading'."""
import argparse, json, os, sys
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE"); os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
from pathlib import Path
sys.path.insert(0, "/home/kim/Projects/SAO/eval"); sys.path.insert(0, "/home/kim/Projects/SAO/control")
from chain_dj_overlay import outpaint_forward, BRIDGE_CKPT
from chroma_morph_transitions import load
from sa3_control.audio_io import save_audio
from stable_audio_3 import StableAudioModel

ap = argparse.ArgumentParser(); ap.add_argument("--clips-json", type=Path, required=True); ap.add_argument("--out-dir", type=Path, required=True)
ap.add_argument("--mult", type=float, default=3.0); ap.add_argument("--steps", type=int, default=24); ap.add_argument("--cfg-scale", type=float, default=6.0)
ap.add_argument("--prompt", default="aggressive upbeat goa trance"); ap.add_argument("--seed", type=int, default=1234)
a = ap.parse_args(); a.out_dir.mkdir(parents=True, exist_ok=True)
clips = json.loads(a.clips_json.read_text())
model = StableAudioModel.from_pretrained("medium-base", device="cuda"); model.load_lora([BRIDGE_CKPT]); sr = model.model.sample_rate
for i, c in enumerate(clips):
    out = a.out_dir / f"{c['id']}_len{a.mult:g}x.wav"
    if out.exists(): print("[skip]", out.name, flush=True); continue
    audio, s = load(c["path"]); assert s == sr
    d = audio.shape[1] / sr
    ext = outpaint_forward(model, audio, sr, (a.mult - 1) * d, a.prompt, a.steps, a.cfg_scale, a.seed)
    save_audio(str(out), ext, sr); print(f"[{i + 1}/{len(clips)}] {out.name} {ext.shape[1] / sr:.1f}s", flush=True)
print("LENGTHEN DONE", flush=True)
