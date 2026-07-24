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
import time
from pathlib import Path

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
            if not (out / clip_name(label, a.tag, c, w, p["id"], p["seed"], a.steps, duration)).exists()]
    if not todo:
        print(f"[cells] {label}/{a.tag}: all {len(prompts)*len(cfgs)*len(strengths)} cells exist, skip")
        return

    import numpy as np
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    t0 = time.time()
    model = StableAudioModel.from_pretrained("medium" if a.pt_medium else "medium-base", device="cuda")
    sr = model.model.sample_rate
    is_fullft = a.label.startswith("fullft_")
    if a.ckpt != "none" and is_fullft:
        ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
        sd_raw = ck.get("state_dict", ck)
        tgt = model.model.model
        want = set(dict(tgt.named_parameters())) | set(dict(tgt.named_buffers()))
        # real fullft ckpts prefix DiT params "diffusion.model.model.X" (target expects
        # leading "model.") -- bare "model." strip 0%-covers them; same bug as
        # model_matrix_gen 2026-07-21 (LUMI job 20094762: all 10 tasks died on the cov
        # assert). Try both prefixes, keep whichever matches the target.
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
            "steps": a.steps, "duration": duration, "file": wav.name.replace(".wav", ".m4a")}))
        print(f"  [{label}/{a.tag} cfg{cfg} w{w} {p['id']} {mode}] {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
