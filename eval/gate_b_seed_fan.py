"""gate_b_seed_fan.py — Gate B of the residual-preservation plan (docs/ai-research/
residual-preservation-2026-07-19.md §3). THE load-bearing measurement: is the latent deficit
a WITHIN-CONTEXT (conditional-mean) collapse, or per-sample oversmoothing?

The 1-seed-per-prompt corpus on disk could not measure conditional (aleatoric) diversity —
the exact quantity the "conditional-mean collapse" diagnosis is about. This fans N seeds
through the model on ONE fixed prompt and measures inter-seed latent variance per frequency
band, vs the inter-CROP variance of N real-goa corpus latents.

Because the workflow found the deficit is BASE-MODEL-INTRINSIC (base loses 57% of the eff-rank
before any adapter), the decisive test is on the BASE model. (A DoRA arm can be added.)

Decision:
  gen inter-seed HF variance << real inter-crop HF variance  -> conditional-mean collapse CONFIRMED
      (the model can't produce within-context HF diversity) -> a residual-recovery objective is warranted.
  gen inter-seed variance ~= real  -> diversity is fine, each sample is individually low-pass ->
      conditional-mean FALSIFIED -> no adapter loss helps; the fix is sampler/decoder-side
      (consistent with a positive Gate A / SDE result).

Run (SA3 venv, GPU): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/gate_b_seed_fan.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import glob
import json
from pathlib import Path

import numpy as np

CORPUS = Path("/home/kim/Projects/latents_sa3")
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/gate_b_20260719"); OUT.mkdir(parents=True, exist_ok=True)
PROMPT = "aggressive upbeat goa trance"      # rhythmic; matches the real-goa corpus
N_SEEDS = 24
DURATION = 26.0                               # ~280 latent frames (matches the saved gen z0 length)
STEPS = 24
CFG = 7.0
NBANDS = 4                                    # temporal-frequency bands (LF..HF)


def band_power(z, T):
    """z: (C, T) -> (C, NBANDS) mean temporal PSD per band (rfft along time)."""
    P = np.abs(np.fft.rfft(z[:, :T], axis=-1)) ** 2        # (C, F)
    edges = np.linspace(0, P.shape[1], NBANDS + 1).astype(int)
    return np.stack([P[:, edges[b]:edges[b + 1]].mean(-1) for b in range(NBANDS)], axis=-1)


def inter_sample_var(feats):
    """feats: (N, C, NBANDS) -> (NBANDS,) variance across the N samples, averaged over channels."""
    return feats.var(axis=0).mean(axis=0)                  # var over N, mean over C


def main():
    import torch
    from stable_audio_3 import StableAudioModel
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    print(f"[gate-B] fanning {N_SEEDS} seeds through base on '{PROMPT}'")
    gen_feats, Tref = [], None
    for s in range(N_SEEDS):
        z0 = model.generate(prompt=PROMPT, duration=DURATION, steps=STEPS, cfg_scale=CFG,
                            seed=1000 + s, return_latents=True)
        z = z0[0].detach().float().cpu().numpy()           # (C, T)
        if Tref is None:
            Tref = z.shape[-1]
            print(f"[gate-B] gen latent shape {z.shape}")
        np.save(OUT / f"gen_s{s}.npy", z.astype(np.float16))
        gen_feats.append(band_power(z, Tref))
        if s % 6 == 0:
            print(f"  seed {s}/{N_SEEDS}")
    gen_feats = np.stack(gen_feats)                         # (N, C, NBANDS)

    # real reference: N corpus crops (different tracks = the real within-"context" diversity),
    # sliced to the same T
    crops = sorted(glob.glob(str(CORPUS / "*.npy")))[:N_SEEDS]
    real_feats = np.stack([band_power(np.load(p).astype(np.float32), Tref) for p in crops])

    gv = inter_sample_var(gen_feats)                       # (NBANDS,)
    rv = inter_sample_var(real_feats)
    ratio = gv / (rv + 1e-12)

    print(f"\n[gate-B] inter-sample variance per temporal band (LF..HF), gen (24 seeds) vs real (24 crops):")
    print(f"{'band':>6s} {'gen_var':>12s} {'real_var':>12s} {'gen/real':>10s}")
    for b in range(NBANDS):
        print(f"{('LF' if b==0 else 'HF' if b==NBANDS-1 else f'b{b}'):>6s} "
              f"{gv[b]:12.4g} {rv[b]:12.4g} {ratio[b]:10.3f}")
    hf_ratio = float(ratio[-1])
    verdict = ("CONFIRMED: within-context HF diversity collapsed (gen HF var << real) -> "
               "conditional-mean is real; a residual-recovery objective is warranted"
               if hf_ratio < 0.5 else
               "FALSIFIED: gen within-context diversity ~= real -> per-sample oversmoothing, "
               "NOT conditional-mean collapse -> the fix is sampler/decoder-side, no adapter loss helps")
    print(f"\n[gate-B] HF gen/real inter-seed variance ratio = {hf_ratio:.3f}\n[gate-B] VERDICT: {verdict}")

    (OUT / "gate_b_result.json").write_text(json.dumps({
        "prompt": PROMPT, "n_seeds": N_SEEDS, "T": int(Tref), "nbands": NBANDS,
        "gen_inter_seed_var": gv.tolist(), "real_inter_crop_var": rv.tolist(),
        "ratio_per_band": ratio.tolist(), "hf_ratio": hf_ratio, "verdict": verdict,
    }, indent=1))


if __name__ == "__main__":
    main()
