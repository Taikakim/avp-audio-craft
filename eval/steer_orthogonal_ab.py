#!/usr/bin/env python
"""steer_orthogonal_ab.py — Gram-Schmidt orthogonalized dual-direction steering A/B
(task #58, Kim direct 2026-07-30; tests arXiv 2605.31295's orthogonalization claim on
SA3 — graduates its paper-verdicts row from untested).

Question: when TWO diff-in-means directions are injected simultaneously (mt_dark +
onset_density — proven individual steerers, Ph3 2026-07-11), does naive vector addition
leak each concept into the other's meter, and does per-(sigma,layer) Gram-Schmidt
projection (strip the protected feature's component from the other's vector) hold the
protected axis flat at equal steering strength?

Arms (per seed, all alpha=+2, same prompt/cfg/steps/seed => only the direction set varies):
  base        alpha=0 baseline (disintegration-gate + delta reference)
  dark        mt_dark solo at its layers {18,15}
  onset       onset_density solo at its layers {15,14}
  naive       both simultaneously (vectors ADD at the shared L15)
  gs_kponset  dark projected perp onset (per sigma,layer) + onset pure  -> onset-preserving
  gs_kpdark   onset projected perp dark + dark pure                     -> dark-preserving

Mechanics identical to steer_concept_direction.py: block_out += alpha*dir on the last T
positions, CONDITIONAL CFG branch only (first half of the doubled batch, dit.py:483),
sigma-matched direction bucket {0.2,0.5,0.8}. z0 latents saved next to every render
(standing directive). Analysis (mir venv, separate script) reads the wavs.

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/steer_orthogonal_ab.py \
      --out-dir /run/media/kim/Mantu/sa3_lora_runs/concept_steering/orthogonal_ab
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "latch"))
from sa3_control.audio_io import save_audio               # noqa: E402
from stable_audio_3 import StableAudioModel               # noqa: E402
from extract_layer_activations import get_blocks          # noqa: E402

DUMP = Path("/run/media/kim/Mantu/sa3_lora_runs/layer_activations_base")
SIG_KEYS = {0.2: "s20", 0.5: "s50", 0.8: "s80"}
FEAT_A = "mt_dark"          # the "style" axis
FEAT_B = "onset_density"    # the "rhythm" axis


def unit(v, axis=-1):
    return v / (np.linalg.norm(v, axis=axis, keepdims=True) + 1e-12)


def project_out(v, u_raw):
    """Remove from v its component along u (per-row = per-layer). v,u: [24,1536]."""
    u = unit(u_raw)
    return v - (v * u).sum(-1, keepdims=True) * u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=2.0)
    ap.add_argument("--seeds", default="4242,777,1313")
    ap.add_argument("--prompt", default="goa trance, 1996, 145")
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]

    z = np.load(DUMP / "concept_directions.npz")
    report = json.loads((DUMP / "concept_directions.json").read_text())["report"]
    lay_a = report[FEAT_A]["recommended_layers"][:2]
    lay_b = report[FEAT_B]["recommended_layers"][:2]

    # per-sigma raw directions [24,1536] and their GS variants
    raw = {f: {s: z[f"{f}__{k}"] for s, k in SIG_KEYS.items()} for f in (FEAT_A, FEAT_B)}
    gs_a = {s: project_out(raw[FEAT_A][s], raw[FEAT_B][s]) for s in SIG_KEYS}   # dark ⊥ onset
    gs_b = {s: project_out(raw[FEAT_B][s], raw[FEAT_A][s]) for s in SIG_KEYS}   # onset ⊥ dark

    # entanglement + norm-retention record (the paper's premise, measured on OUR directions)
    ent = {}
    for s in SIG_KEYS:
        ua, ub = unit(raw[FEAT_A][s]), unit(raw[FEAT_B][s])
        cos = (ua * ub).sum(-1)  # [24] per-layer cosine
        keep_a = np.linalg.norm(gs_a[s], axis=-1) / (np.linalg.norm(raw[FEAT_A][s], axis=-1) + 1e-12)
        keep_b = np.linalg.norm(gs_b[s], axis=-1) / (np.linalg.norm(raw[FEAT_B][s], axis=-1) + 1e-12)
        ent[SIG_KEYS[s]] = {
            "cos_per_layer": {str(l): round(float(cos[l]), 4) for l in sorted(set(lay_a + lay_b))},
            "cos_mean_all24": round(float(cos.mean()), 4),
            "gs_norm_kept_dark": {str(l): round(float(keep_a[l]), 4) for l in lay_a},
            "gs_norm_kept_onset": {str(l): round(float(keep_b[l]), 4) for l in lay_b},
        }
    print("[ent] per-layer dark/onset direction cosines + GS norm retention:")
    print(json.dumps(ent, indent=1), flush=True)

    # arm -> list of (layers, per-sigma-direction-array)
    def dirs_t(dev, dt, arr):  # {sigma: tensor}
        return {s: torch.tensor(a).to(dev, dt) for s, a in arr.items()}

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    blocks = get_blocks(model)

    A_raw = dirs_t(device, mdtype, raw[FEAT_A])
    B_raw = dirs_t(device, mdtype, raw[FEAT_B])
    A_gs = dirs_t(device, mdtype, gs_a)
    B_gs = dirs_t(device, mdtype, gs_b)

    ARMS = {
        "base":       [],
        "dark":       [(lay_a, A_raw)],
        "onset":      [(lay_b, B_raw)],
        "naive":      [(lay_a, A_raw), (lay_b, B_raw)],
        "gs_kponset": [(lay_a, A_gs),  (lay_b, B_raw)],   # protect onset: dark is projected
        "gs_kpdark":  [(lay_a, A_raw), (lay_b, B_gs)],    # protect dark: onset is projected
    }

    ds = cdm.pretransform.downsampling_ratio
    sr = cdm.sample_rate
    T = int(np.ceil(args.duration * sr / ds))

    state = {"inj": {}, "sigma": 0.5}   # inj: layer -> {sigma: vec[1536]} scaled by alpha

    def pre_hook(_m, hargs, hkwargs):
        t = hargs[1] if len(hargs) > 1 else hkwargs.get("t")
        if t is not None:
            state["sigma"] = float(t.flatten()[0])
        return None
    pre = cdm.model.register_forward_pre_hook(pre_hook, with_kwargs=True)

    def mk(layer_idx):
        def hook(_m, _inp, out):
            inj = state["inj"].get(layer_idx)
            if inj is None:
                return out
            tup = isinstance(out, tuple)
            o = out[0] if tup else out
            s = min(SIG_KEYS, key=lambda k: abs(k - state["sigma"]))
            o = o.clone()
            b = o.shape[0]
            nc = b // 2 if b > 1 else b   # conditional branch = first half (dit.py:483)
            o[:nc, -T:, :] += inj[s]
            return (o, *out[1:]) if tup else o
        return hook
    all_layers = sorted(set(lay_a + lay_b))
    hooks = [blocks[l].register_forward_hook(mk(l)) for l in all_layers]

    print(f"[ab] dark@{lay_a} onset@{lay_b} alpha={args.alpha} seeds={seeds}", flush=True)
    renders = []
    try:
        for seed in seeds:
            for arm, spec in ARMS.items():
                inj = {}
                for layers, dmap in spec:
                    for l in layers:
                        for s in SIG_KEYS:
                            v = args.alpha * dmap[s][l]
                            inj.setdefault(l, {})[s] = inj.get(l, {}).get(s, 0) + v
                state["inj"] = inj
                lat = model.generate(prompt=args.prompt, duration=args.duration,
                                     steps=args.steps, cfg_scale=args.cfg_scale,
                                     seed=seed, batch_size=1, sample_size=T * ds,
                                     return_latents=True)
                tag = f"{arm}_s{seed}"
                np.save(args.out_dir / f"{tag}.z0.npy",
                        lat.float().cpu().numpy())            # z0 next to render (standing)
                audio = cdm.pretransform.decode(lat.to(mdtype))
                save_audio(args.out_dir / f"{tag}.wav",
                           audio[0].float().cpu(), sr, normalize=True)
                renders.append(tag)
                print(f"[done] {tag}", flush=True)
    finally:
        for h in hooks:
            h.remove()
        pre.remove()
        state["inj"] = {}

    meta = {
        "hypothesis": "2605.31295 Gram-Schmidt claim on SA3: naive simultaneous injection of "
                      "two entangled diff-in-means directions (mt_dark + onset_density, shared "
                      "layer 15) leaks each concept into the other's meter; per-(sigma,layer) "
                      "orthogonalization holds the protected axis at its solo value while the "
                      "steered axis keeps moving.",
        "arms": {"base": "no injection",
                 "dark": "raw dark @18,15", "onset": "raw onset @15,14",
                 "naive": "raw dark @18,15 + raw onset @15,14 (vectors add at L15)",
                 "gs_kponset": "GS dark(perp onset) @18,15 + raw onset @15,14",
                 "gs_kpdark": "raw dark @18,15 + GS onset(perp dark) @15,14"},
        "features": {"dark": {"name": FEAT_A, "layers": lay_a, "best": report[FEAT_A]["best"]},
                     "onset": {"name": FEAT_B, "layers": lay_b, "best": report[FEAT_B]["best"]}},
        "alpha": args.alpha, "seeds": seeds, "prompt": args.prompt,
        "duration": args.duration, "steps": args.steps, "cfg_scale": args.cfg_scale,
        "entanglement": ent, "renders": renders,
        "injection": "conditional-CFG-branch only, sigma-matched bucket, last-T positions",
        "directions_from": str(DUMP / "concept_directions.npz"),
        "result": None, "kim_feedback": None,
    }
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[all done] {len(renders)} renders -> {args.out_dir}", flush=True)


if __name__ == "__main__":
    main()
