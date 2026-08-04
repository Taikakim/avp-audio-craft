#!/usr/bin/env python
"""render_native_cells.py — LUMI worker: render the native-training-length model-matrix
cells for one LUMI-resident checkpoint (CONTINUITY, 2026-07-21; the W-split's LUMI half).

WHY: native cells at T>=2048 (188-380 s) are BANNED on Kim's desktop card (long-sequence
attention VRAM starved the compositor -> display crash, 2026-07-21). The checkpoints that
need them (fullft_*, fp32cmp_*, longctx_*, fp32frames_*) all live on $SCRATCH already, so
they render here on 64 GB headless GCDs instead.

⚠ WINDOW BUG (v1, job 20094760): model.generate()'s `duration` only sets seconds_total
conditioning + output trim; the actual latent window is `sample_size` (defaults to
5292032 samples = 120.0 s). v1 never passed it -> ALL 103 cells rendered in a 2:00 window
regardless of native length (Kim caught the uniform 2:00 by ear/eye, 2026-07-22). Now:
sample_size = frames*4096 (frames stay multiples of 256, Kim's standing rule), and the
returned z0's frame count is asserted == --frames. FAIL LOUD.

GRID — Kim 2026-07-22: full usual axes at native length, not one representative cell:
  prompt   = kl_bracket_0 (verbatim text below), seed 1000, steps 24 (NO __st suffix)
  cfg      x {1, 7, 16}          (--cfgs)
  strength x {1.0, 1.5, 2.0}     (--strengths; forced to [1.0] for fullft/base — a
                                  whole-model FT has no strength knob)
  duration = round(frames / (44100/4096), 2) s     filename __d<int(round(dur))>
  filename = {label}__{tag}__cfg{C}__w{W:03d}__kl_bracket_0__s1000__d<D>.wav (+ .z0.npy)
Output per cell: wav + fp16 z0 + .mmline.json manifest fragment (sbatch merges into
native_manifest.jsonl; W's local ingest transcodes/appends/rebuilds). Idempotent per cell.

Run (inside the SIF, one GCD): python render_native_cells.py \
  --label fullft_goa_t4096 --tag ep7 --frames 4096 \
  --ckpt /scratch/.../epoch=7-....weights.ckpt --out /scratch/.../renders/native_cells
--ckpt none renders the base model (no adapter).
"""
import argparse
import json
import time
from pathlib import Path

FPS = 44100 / 4096          # 10.7666 Hz — canonical SA3-medium latent frame rate
LATENT_HOP = 4096           # audio samples per latent frame (SAME 4096x)
STEPS, SEED = 24, 1000
PID = "kl_bracket_0"
PROMPT = ("This track is a high-energy Psytrance piece that blends driving trance rhythms "
          "with the hypnotic, acid-inflected textures typical of the genre.")


def cell_name(label, tag, cfg, w, dur):
    return f"{label}__{tag}__cfg{int(cfg)}__w{int(round(w * 100)):03d}__{PID}__s{SEED}__d{int(round(dur))}.wav"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--tag", required=True, help="checkpoint tag, e.g. ep7")
    ap.add_argument("--frames", type=int, required=True, help="trained context length T")
    ap.add_argument("--ckpt", required=True, help="checkpoint path, or 'none' for base")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cfgs", default="1,7,16")
    ap.add_argument("--strengths", default="1.0,1.5,2.0",
                    help="adapter strengths; ignored (forced 1.0) for fullft/base")
    a = ap.parse_args()
    assert a.frames % 256 == 0, f"frames must be a multiple of 256, got {a.frames}"

    dur = round(a.frames / FPS, 2)
    is_fullft = a.label.startswith("fullft_")
    is_adapter = a.ckpt != "none" and not is_fullft
    cfgs = [float(c) for c in a.cfgs.split(",")]
    strengths = [float(s) for s in a.strengths.split(",")] if is_adapter else [1.0]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    todo = [(c, w) for c in cfgs for w in strengths
            if not ((out / cell_name(a.label, a.tag, c, w, dur)).exists()
                    and (out / cell_name(a.label, a.tag, c, w, dur)).with_suffix(".mmline.json").exists())]
    if not todo:
        print(f"[native] {a.label}/{a.tag}: all {len(cfgs)*len(strengths)} cells exist, skip")
        return

    import numpy as np
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    t0 = time.time()
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sr = model.model.sample_rate
    if a.ckpt != "none" and is_fullft:
        # whole-model fine-tune: full state dict over the base DiT, FAIL LOUD on partial
        # coverage (W's guard — a part-loaded fullft would fake a result)
        ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
        sd_raw = ck.get("state_dict", ck)
        tgt = model.model.model
        want = dict(tgt.named_parameters()) | dict(tgt.named_buffers())
        # real fullft ckpts prefix DiT params "diffusion.model.model.X" -- a bare "model."
        # strip 0%-covers them (LUMI 20094762/20094760: every fullft task died here).
        # Try both prefixes, keep whichever matches the target.
        sd = max(
            ({(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
             for pfx in ("diffusion.model.", "model.")),
            key=lambda d: sum(1 for k in d if k in want))
        missing, _ = tgt.load_state_dict(
            {k: v.to(next(tgt.parameters()).dtype) for k, v in sd.items() if k in want},
            strict=False)
        cov = 1 - len(missing) / max(1, len(list(tgt.state_dict())))
        assert cov > 0.99, f"fullft ckpt covers only {cov:.1%} ({len(missing)} missing keys)"
        del ck, sd_raw, sd
    elif a.ckpt != "none":
        model.load_lora([a.ckpt])
    decode_dtype = next(model.same.parameters()).dtype
    print(f"[native] loaded {a.label}/{a.tag} in {time.time()-t0:.0f}s; "
          f"{len(todo)} cells @ {dur}s (window {a.frames} frames)", flush=True)

    for cfg, w in todo:
        if is_adapter:
            model.set_lora_strength(w)
        wav = out / cell_name(a.label, a.tag, cfg, w, dur)
        t0 = time.time()
        z0 = model.generate(prompt=PROMPT, duration=dur, steps=STEPS, cfg_scale=cfg,
                            seed=SEED, batch_size=1, return_latents=True,
                            sample_size=a.frames * LATENT_HOP)
        got = z0.shape[-1]
        assert got == a.frames, (
            f"latent window is {got} frames, requested {a.frames} — sample_size ignored?")
        np.save(wav.with_suffix(".z0.npy"), z0.detach().to(torch.float16).cpu().numpy())
        with torch.no_grad():
            audio = model.same.decode(z0.to(decode_dtype))
        audio = audio.to(torch.float32)[:, :, :int(dur * sr)]
        save_audio(wav, audio[0].cpu(), sr, normalize=True)
        wav.with_suffix(".mmline.json").write_text(json.dumps({
            "model": a.label, "ckpt": a.tag, "cfg": cfg, "strength": w,
            "prompt_id": PID, "prompt_text": PROMPT, "seed": SEED, "steps": STEPS,
            "duration": dur, "duration_mode": "native",
            "file": wav.name.replace(".wav", ".m4a")}))
        print(f"[native] {wav.name} rendered in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
