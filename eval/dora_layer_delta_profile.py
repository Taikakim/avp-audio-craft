#!/usr/bin/env python
"""dora_layer_delta_profile.py — where does a DoRA checkpoint actually change the model,
per DiT block? (Kim ask 2026-07-21, following Zach@Stability's Discord claim that adapter
changes concentrate in the middle layers — docs/ai-research/2026-07-21-zach-stability-discord-notes.md.)

Computes the TRUE effective weight delta per adapted matrix, replicating
stable_audio_3.models.lora.model.dora_forward exactly (strength 1):
    W' = magnitude ⊙_rows rownorm(W_base + (alpha/rank)·B·A);   ΔW = W' − W_base
and reports, aggregated per transformer block:
    rel = Σ‖ΔW‖_F / Σ‖W_base‖_F   (the normalized 'where did training change the model')
plus the raw ‖B·A‖ proxy for comparison with the quick pass, and the same split by site.

CPU-only; base weights streamed from the HF safetensors (no model build).

Run: ./stable-audio-3/.venv/bin/python eval/dora_layer_delta_profile.py \
        [--ckpt PATH] [--adapter-type dora-rows] [--json OUT]
"""
import argparse
import collections
import glob
import json
import re

import torch
from safetensors import safe_open

DEFAULT_CKPT = ("/run/media/kim/Mantu/sa3_lora_runs/fp32cmp_goa_t4096_bs4_lr1e4/"
                "epoch=4-step=6750.weights.ckpt")
BASE_ST = glob.glob("/home/kim/.cache/huggingface/hub/models--stabilityai--"
                    "stable-audio-3-medium-base/snapshots/*/model.safetensors")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--alpha", type=float, default=None, help="lora_alpha (default: rank -> scaling 1)")
    ap.add_argument("--json", default=None, help="write per-matrix results here")
    a = ap.parse_args()

    sd = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    sd = sd.get("state_dict", sd)
    groups = collections.defaultdict(dict)
    for k, v in sd.items():
        m = re.match(r"(.*)\.(lora_A|lora_B|magnitude)$", k)
        if m:
            groups[m.group(1)][m.group(2)] = v.float()

    per_matrix = []
    missing = []
    with safe_open(BASE_ST[0], framework="pt") as f:
        base_keys = set(f.keys())
        for prefix, parts in sorted(groups.items()):
            if not {"lora_A", "lora_B"} <= parts.keys():
                continue
            base_key = "model." + prefix.replace(".parametrizations.weight.0", "") + ".weight"
            if base_key not in base_keys:
                missing.append(base_key)
                continue
            W = f.get_tensor(base_key).float()
            W2 = W.view(W.shape[0], -1)
            A, B = parts["lora_A"], parts["lora_B"]
            scaling = (a.alpha / B.shape[1]) if a.alpha else 1.0
            delta = B @ A
            V = W2 + scaling * delta
            if "magnitude" in parts:  # dora-rows: row-normalize then rescale by magnitude
                Vh = V / (V.norm(dim=1, keepdim=True) + 1e-12)
                Weff = Vh * parts["magnitude"].unsqueeze(1)
            else:                      # plain lora
                Weff = V
            dW = Weff - W2
            per_matrix.append({
                "key": prefix.replace(".parametrizations.weight.0", ""),
                "dF": dW.norm().item(), "baF": delta.norm().item(), "wF": W2.norm().item(),
            })

    blk_d = collections.defaultdict(float); blk_w = collections.defaultdict(float)
    blk_ba = collections.defaultdict(float)
    oth_d = collections.defaultdict(float); oth_w = collections.defaultdict(float)
    for r in per_matrix:
        m = re.search(r"layers\.(\d+)\.", r["key"])
        if m:
            b = int(m.group(1))
            blk_d[b] += r["dF"]; blk_w[b] += r["wF"]; blk_ba[b] += r["baF"]
        else:
            name = re.sub(r"^model\.", "", r["key"])
            oth_d[name] += r["dF"]; oth_w[name] += r["wF"]

    print(f"{len(per_matrix)} adapted matrices resolved against base ({len(missing)} unresolved)")
    if missing:
        print("  unresolved:", missing[:5])
    rels = {b: blk_d[b] / blk_w[b] for b in blk_d}
    tot_ba = sum(blk_ba.values())
    print("\nper-block: rel = Σ‖ΔW_eff‖/Σ‖W_base‖   (raw ‖B·A‖ share for comparison)")
    for b in sorted(rels):
        bar = "#" * int(60 * rels[b] / max(rels.values()))
        print(f"  L{b:02d} rel={rels[b]:.4f}  (BA {100*blk_ba[b]/tot_ba:4.1f}%)  {bar}")
    t = [sum(blk_d[b] for b in r) / sum(blk_w[b] for b in r)
         for r in (range(0, 8), range(8, 16), range(16, 24))]
    print(f"\nthirds (rel): early L0-7 {t[0]:.4f}   mid L8-15 {t[1]:.4f}   late L16-23 {t[2]:.4f}")
    print("\nnon-block sites (rel):")
    for k in sorted(oth_d, key=lambda k: -oth_d[k] / oth_w[k]):
        print(f"  {k:45s} {oth_d[k]/oth_w[k]:.4f}")

    if a.json:
        json.dump({"ckpt": a.ckpt, "per_matrix": per_matrix,
                   "per_block_rel": rels,
                   "thirds_rel": {"early": t[0], "mid": t[1], "late": t[2]}},
                  open(a.json, "w"), indent=1)
        print(f"-> {a.json}")


if __name__ == "__main__":
    main()
