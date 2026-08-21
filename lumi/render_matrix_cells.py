#!/usr/bin/env python
"""render_matrix_cells.py — LUMI worker: render the STANDARD model-matrix grid for one
(label, ckpt) — Kim direct 2026-07-21: "I also want the full ft evals from LUMI" (two local
GPU wedges in 12h; the fullft checkpoints live on $SCRATCH anyway).

Grid = the exact local axes from lumi/matrix_prompts_snapshot.json (18 prompts with the SAME
ids/texts/seeds as the local board, cfg {1,7,16}, steps 24, 20 s). Strength axis: fullft is a
whole-model fine-tune -> strength collapses to 1.0 (W's loader convention); DoRA ckpts get
--strengths to sweep. Per cell: wav + fp16 z0 sibling + .mmline.json manifest fragment (same
schema as local model_matrix_gen appends; 'file' = final .m4a name). W's ingest transcodes +
appends + rebuilds; page cells join by (model, ckpt, cfg, strength, prompt_id).

Idempotent per cell. Run (in SIF, one GCD):
  python render_matrix_cells.py --label fullft_goa_t4096 --tag ep7 \
    --ckpt /scratch/.../fullft_goa_t4096/epoch=7-....weights.ckpt \
    --prompts /project/.../code/lumi/matrix_prompts_snapshot.json \
    --out /scratch/.../renders/matrix_cells
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# self-add control/ so `from sa3_control.audio_io import save_audio` works regardless of the
# caller's PYTHONPATH (job 20190736 lost all its eval renders to ModuleNotFoundError:
# sa3_control — every eval-render sbatch had stable-audio-3:lumi/vendor but not control/).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "control"))

STEPS, DURATION = 24, 20.0
FPS = 44100 / 4096  # = 10.7666 Hz, the canonical SA3-medium latent frame rate


def clip_name(label, tag, cfg, w, pid, seed, steps=STEPS, duration=DURATION):
    # byte-identical to eval/model_matrix_gen.clip_name: steps/duration suffixes ONLY when
    # non-default, so a native (__dNNN) or PT (__st8) pass lands as a SIBLING, never an overwrite.
    st = f"__st{steps}" if steps != STEPS else ""
    du = f"__d{int(round(duration))}" if duration != DURATION else ""
    return f"{label}__{tag}__cfg{int(cfg)}__w{int(round(w * 100)):03d}__{pid}__s{seed}{st}{du}.wav"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ckpt", required=True, help="checkpoint path, or 'none' for base")
    ap.add_argument("--prompts", required=True, help="matrix_prompts_snapshot.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--strengths", default=None,
                    help="comma floats for adapter ckpts (default: 1.0 only — fullft/base)")
    ap.add_argument("--steps", type=int, default=STEPS,
                    help="sampler steps (default 24; PT-medium native config = 8)")
    ap.add_argument("--frames", type=int, default=None,
                    help="NATIVE-length render: target latent T (must be a multiple of 256, e.g. "
                         "4096=380s, 2048=190s). Sets sample_size=frames*4096 on generate() — "
                         "WITHOUT this, generate(duration=) silently runs a 120s/1292-frame context "
                         "(the LUMI 2026-07-22 native-cell bug). Omit for the standard 20s grid.")
    ap.add_argument("--pt-medium", action="store_true",
                    help="load the POST-TRAINED 'medium' (rf_denoiser/ping-pong) instead of "
                         "medium-base; suffixes the label with '_ptm'. Pair with --steps 8 "
                         "--only-cfgs 1 for the PT-native config (cfg>1 cooks PT output).")
    ap.add_argument("--only-cfgs", default=None,
                    help="comma ints to restrict the cfg axis (e.g. '1' for PT-medium)")
    ap.add_argument("--use-ema", action="store_true",
                    help="load the EMA shadow weights (diffusion_ema.ema_model.*) instead of the "
                         "online weights — REQUIRED for EMA-trained fullft ckpts (precision ladder, "
                         "#68 big-FT); the online weights are the un-averaged model, not what deploys.")
    ap.add_argument("--base-state-ckpt", default=None,
                    help="STACKING (Kim 2026-08-21): load this full-FT checkpoint's weights into "
                         "the base BEFORE applying --ckpt as an adapter — renders 'good DoRA on "
                         "good full finetune'. EMA shadow auto-preferred when present.")
    ap.add_argument("--fullft", action="store_true",
                    help="force the full-finetune load path (whole-model state_dict) regardless of "
                         "the label prefix — for fullft runs not named 'fullft_*' (e.g. precision_ladder).")
    ap.add_argument("--force", action="store_true",
                    help="re-render cells even if the output .wav already exists (default skips them). "
                         "Use when re-rendering the SAME (label,tag) with changed code/ckpt.")
    a = ap.parse_args()

    # native-length mode: derive duration from the target T; assert the 256-multiple invariant.
    if a.frames is not None:
        assert a.frames % 256 == 0, f"--frames {a.frames} must be a multiple of 256"
        duration = round(a.frames / FPS, 2)
        sample_size = a.frames * 4096
    else:
        duration, sample_size = DURATION, None

    label = a.label
    if a.pt_medium and not label.endswith("_ptm"):
        label += "_ptm"

    snap = json.load(open(a.prompts))
    prompts, cfgs = snap["prompts"], snap["cfgs"]
    if a.only_cfgs:
        keep = {float(c) for c in a.only_cfgs.split(",")}
        cfgs = [c for c in cfgs if float(c) in keep]
    strengths = [float(s) for s in a.strengths.split(",")] if a.strengths else [1.0]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    todo = [(p, c, w) for p in prompts for c in cfgs for w in strengths
            if a.force or not (out / clip_name(label, a.tag, c, w, p["id"], p["seed"], a.steps, duration)).exists()]
    if not todo:
        print(f"[cells] {label}/{a.tag}: all {len(prompts)*len(cfgs)*len(strengths)} cells exist, skip "
              f"(pass --force to re-render)")
        return

    import numpy as np
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    t0 = time.time()
    model = StableAudioModel.from_pretrained("medium" if a.pt_medium else "medium-base", device="cuda")
    sr = model.model.sample_rate
    if a.base_state_ckpt:
        from render_showcase import load_fullft_state   # auto-EMA whole-model load, cov assert
        load_fullft_state(model, a.base_state_ckpt)
    is_fullft = a.fullft or a.label.startswith("fullft_")
    if a.ckpt != "none" and is_fullft:
        ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
        sd_raw = ck.get("state_dict", ck)
        tgt = model.model.model
        want = set(dict(tgt.named_parameters())) | set(dict(tgt.named_buffers()))
        # real fullft ckpts prefix DiT params "diffusion.model.model.X" (target expects
        # leading "model.") -- bare "model." strip 0%-covers them; same bug as
        # model_matrix_gen 2026-07-21 (LUMI job 20094762: all 10 tasks died on the cov
        # assert). Try both prefixes, keep whichever matches the target.
        # EMA-trained fullft ckpts carry BOTH online (diffusion.model.*) AND the EMA shadow
        # (diffusion_ema.ema_model.*). --use-ema loads the shadow (what actually deploys);
        # both cover the target equally, so we must pick EXPLICITLY, not by max-coverage.
        prefixes = ("diffusion_ema.ema_model.",) if a.use_ema else ("diffusion.model.", "model.")
        sd = max(
            ({(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
             for pfx in prefixes),
            key=lambda d: sum(1 for k in d if k in want))
        missing, _ = tgt.load_state_dict(
            {k: v.to(next(tgt.parameters()).dtype) for k, v in sd.items() if k in want},
            strict=False)
        cov = 1 - len(missing) / max(1, len(list(tgt.state_dict())))
        assert cov > 0.99, (f"fullft ckpt covers only {cov:.1%} ({len(missing)} missing keys)"
                            + (" — --use-ema set but no diffusion_ema.ema_model.* keys found?" if a.use_ema else ""))
        del ck, sd_raw, sd
    elif a.ckpt != "none":
        model.load_lora([a.ckpt])
    decode_dtype = next(model.same.parameters()).dtype
    mode = f"NATIVE T={a.frames} ({duration}s)" if a.frames is not None else f"{int(DURATION)}s"
    print(f"[cells] {label}/{a.tag} loaded in {time.time()-t0:.0f}s; {len(todo)} cells to render ({mode}, steps {a.steps})", flush=True)

    for p, cfg, w in todo:
        if a.ckpt != "none" and not is_fullft:
            try:
                model.set_lora_strength(w)
            except Exception:
                pass
        wav = out / clip_name(label, a.tag, cfg, w, p["id"], p["seed"], a.steps, duration)
        t0 = time.time()
        gen_kwargs = dict(prompt=p["text"], duration=duration, steps=a.steps,
                          cfg_scale=float(cfg), seed=int(p["seed"]), batch_size=1,
                          return_latents=True)
        if sample_size is not None:          # native: pin the context window (else 120s default)
            gen_kwargs["sample_size"] = sample_size
        z0 = model.generate(**gen_kwargs)
        if a.frames is not None:
            assert z0.shape[-1] == a.frames, (z0.shape, a.frames)
        np.save(wav.with_suffix(".z0.npy"), z0.detach().to(torch.float16).cpu().numpy())
        with torch.no_grad():
            audio = model.same.decode(z0.to(decode_dtype))
        audio = audio.to(torch.float32)[:, :, :int(duration * sr)]
        save_audio(wav, audio[0].cpu(), sr, normalize=True)
        wav.with_suffix(".mmline.json").write_text(json.dumps({
            "model": label, "ckpt": a.tag, "cfg": float(cfg), "strength": w,
            "prompt_id": p["id"], "prompt_text": p["text"], "seed": p["seed"],
            "steps": a.steps, "duration": duration, "file": wav.name.replace(".wav", ".m4a"),
            **({"base_state": os.path.basename(a.base_state_ckpt)} if a.base_state_ckpt else {})}))
        print(f"  [{label}/{a.tag} cfg{cfg} w{w} {p['id']} {mode}] {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
