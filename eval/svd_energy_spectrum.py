#!/usr/bin/env python3
"""svd_energy_spectrum.py -- full (untruncated) SVD energy spectrum of a fullft weight
delta, reproducing CONTINUITY's near-full-rank finding (DM 2026-07-24, task #77) so the
xft SVD-adapter board can cite regenerated, reproducible numbers instead of a paraphrase.

For one fullft parent (default fullft_goa_t256, her reference case): per-module full SVD
of deltaW = W_fullft - W_base, cumulative energy fraction vs rank, r90 (smallest rank
capturing >=90% of the delta's Frobenius energy) per module, aggregated by module class
(attn_qkv / attn_out / mlp_proj / other), plus whole-model UNIFORM-rank energy at a fixed
rank ladder (what fraction of total delta energy survives if every module is truncated to
the same rank r -- the number that answers "does a small adapter capture the fine-tune").

Reuses extract_svd_adapters.py's exact loaders (namespace mapping, target-module list) --
does NOT re-derive that logic.

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE stable-audio-3/.venv/bin/python \
     eval/svd_energy_spectrum.py [--parent fullft_goa_t256] -> eval/svd_energy_spectrum.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_svd_adapters import (  # noqa: E402
    _ckpt_path, _fullft_labels, load_base_weights, load_fullft_weights,
    load_target_modules,
)

RANK_LADDER = (16, 64, 128, 256, 512, 1024)


def classify(mod):
    if "self_attn.to_qkv" in mod or "cross_attn.to_q" in mod or "cross_attn.to_kv" in mod:
        return "attn_qkv"
    if "self_attn.to_out" in mod or "cross_attn.to_out" in mod:
        return "attn_out"
    if re.search(r"\.ff\.ff\.(0\.proj|2)$", mod):
        return "mlp_proj"
    return "other"


def module_spectrum(base_w, fullft_w):
    fan_out = fullft_w.shape[0]
    delta = (fullft_w.reshape(fan_out, -1).double() - base_w.reshape(fan_out, -1).double())
    S = torch.linalg.svdvals(delta)
    energy = (S ** 2)
    total = energy.sum().item()
    cum = torch.cumsum(energy, 0) / max(total, 1e-30)
    dim = min(delta.shape)
    r90 = int((cum >= 0.9).nonzero()[0].item()) + 1 if total > 0 else 0
    ladder_energy = {r: round(cum[min(r, len(cum)) - 1].item(), 4) for r in RANK_LADDER}
    return {"dim": dim, "total_energy": total, "r90": r90,
            "r90_frac": round(r90 / dim, 3) if dim else None,
            "ladder_energy": ladder_energy}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", default="fullft_goa_t256")
    ap.add_argument("--out", default=None,
                    help="output json path (default: eval/svd_energy_spectrum.json — the "
                         "reference-arm file the xft board reads; per-arm sweeps should pass "
                         "eval/svd_energy_spectrum_<parent>.json)")
    args = ap.parse_args()

    fullft = _fullft_labels()
    spec = fullft[args.parent]
    ckpt_path = _ckpt_path(args.parent, spec)
    print(f"[spectrum] {args.parent} <- {ckpt_path}")

    target_modules = load_target_modules()
    base_sd = load_base_weights()
    fullft_sd = load_fullft_weights(ckpt_path)

    per_module = {}
    for mod in target_modules:
        wkey = mod + ".weight"
        if wkey not in base_sd or wkey not in fullft_sd:
            continue
        per_module[mod] = module_spectrum(base_sd[wkey], fullft_sd[wkey])
    print(f"[spectrum] {len(per_module)}/{len(target_modules)} modules covered")

    by_class = {}
    for mod, m in per_module.items():
        by_class.setdefault(classify(mod), []).append(m)

    def median(xs):
        xs = sorted(xs)
        n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    class_summary = {}
    for cls, ms in by_class.items():
        class_summary[cls] = {
            "n_modules": len(ms),
            "dim": ms[0]["dim"] if ms else None,
            "median_r90": round(median([m["r90"] for m in ms]), 1),
            "median_r90_frac": round(median([m["r90_frac"] for m in ms if m["r90_frac"] is not None]), 3),
        }

    # whole-model uniform-rank energy: sum(per-module truncated energy at r) / sum(total energy)
    whole_model = {}
    total_energy_all = sum(m["total_energy"] for m in per_module.values())
    for r in RANK_LADDER:
        captured = sum(m["ladder_energy"][r] * m["total_energy"] for m in per_module.values())
        whole_model[r] = round(captured / max(total_energy_all, 1e-30), 4)

    out = {"parent": args.parent, "ckpt": str(ckpt_path), "n_modules": len(per_module),
           "class_summary": class_summary, "whole_model_uniform_rank_energy": whole_model,
           "per_module_r90": {m: v["r90"] for m, v in per_module.items()}}
    out_path = Path(args.out) if args.out else Path(__file__).resolve().parent / "svd_energy_spectrum.json"
    out_path.write_text(json.dumps(out, indent=1))
    print(f"[spectrum] wrote {out_path}")
    print("class summary:", json.dumps(class_summary, indent=1))
    print("whole-model uniform-rank energy:", whole_model)


if __name__ == "__main__":
    main()
