#!/usr/bin/env python
"""precision_weight_diff.py — bf16 vs fp32 DoRA weight-space divergence diagnostic.

Context: SAO issue — a bf16-trained fine-tune sounds audibly different from its
fp32 twin (matched precision arms from campaign #52, same config except
--base_precision). FusionOpt Schedule-Free keeps an fp32 master, so any divergence
is a bf16-COMPUTE training-dynamics effect, not an optimizer-storage effect.

Hypothesis (Qiu et al. 2510.04212, flash-attn softmax bias): divergence is
CONCENTRATED in attention layers with INFLATED spectral norm in the bf16 arm.
Alternative: divergence is DIFFUSE and uniformly tiny (benign rounding) → the
audible gap is elsewhere.

IMPORTANT — these checkpoints are DoRA adapters (dora-rows, rank=128, alpha=128,
scale=alpha/rank=1.0), NOT full finetunes. The frozen medium-SA3 base is shared
byte-for-byte between the two arms (not even stored in the ckpt), so ALL training
divergence lives in the trained DoRA params: {lora_A, lora_B, magnitude} per module.

We measure, per module:
  - merged low-rank update  dW = scale * (B @ A)   (base-independent weight delta)
  - relative-L2 diff of dW, magnitude, lora_A, lora_B  (||bf-fp|| / ||fp||)
  - spectral norm sigma_max(dW), ratio bf16/fp32  (Qiu inflation test on the update)
  - magnitude vector: in dora-rows, m == the per-output-row L2 norm of the EFFECTIVE
    weight. ratio ||m_bf||/||m_fp|| per role is a base-independent effective-scale
    inflation test — the most direct DoRA analog of "is the attention weight larger".

CPU only, state_dict diff, no forward / no GPU.
"""
import os, json, re, sys, datetime
import torch

FP32_CKPT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/fp32_compare/fp32cmp_goa_t512_bs8_lr1e4/epoch=7-step=5400.ckpt"
BF16_CKPT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/bf16_twin/bf16cmp_goa_t512_bs8_lr1e4/epoch=7-step=5400.ckpt"
OUT_DIR   = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/analysis/precision_weight_diff_5400"

PARAM_RE = re.compile(r"^(?P<mod>.+)\.parametrizations\.weight\.0\.(?P<kind>lora_A|lora_B|magnitude)$")

def role_of(mod: str) -> str:
    m = mod
    if "self_attn" in m:
        return "attention"          # self-attention q/k/v/out
    if "cross_attn" in m:
        return "cond_crossattn"     # cross-attention to text conditioning
    if ".ff." in m:
        return "mlp"                # feedforward
    if any(t in m for t in ("cond_embed", "global_cond_embedder", "to_global_embed",
                            "to_timestep_embed", "to_cond_embed")):
        return "cond_embed"
    if any(t in m for t in ("project_in", "project_out", "to_local_embed",
                            "preprocess", "postprocess")):
        return "embed_proj"
    return "other"

def load_dora(path):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    sd = ck["state_dict"]
    mods = {}
    for k, v in sd.items():
        m = PARAM_RE.match(k)
        if not m:
            continue
        mod = m.group("mod")
        mods.setdefault(mod, {})[m.group("kind")] = v.float()
    meta = {"epoch": ck.get("epoch"), "global_step": ck.get("global_step"),
            "lora_config": ck.get("lora_config")}
    return mods, meta

def relL2(a, b):
    return (float(torch.linalg.norm((a - b).flatten())) /
            (float(torch.linalg.norm(b.flatten())) + 1e-20))

def specnorm(W):
    # largest singular value of a 2D matrix
    try:
        return float(torch.linalg.matrix_norm(W, ord=2))
    except Exception:
        return float(torch.linalg.svdvals(W)[0])

def main():
    print("loading fp32:", FP32_CKPT)
    fp, fp_meta = load_dora(FP32_CKPT)
    print("loading bf16:", BF16_CKPT)
    bf, bf_meta = load_dora(BF16_CKPT)
    print("fp32 meta:", fp_meta["epoch"], fp_meta["global_step"], fp_meta["lora_config"])
    print("bf16 meta:", bf_meta["epoch"], bf_meta["global_step"], bf_meta["lora_config"])
    scale = fp_meta["lora_config"]["alpha"] / fp_meta["lora_config"]["rank"]

    common = sorted(set(fp) & set(bf))
    only_fp = set(fp) - set(bf); only_bf = set(bf) - set(fp)
    print(f"common modules: {len(common)}  only_fp: {len(only_fp)}  only_bf: {len(only_bf)}")

    rows = []
    for mod in common:
        A_fp, B_fp, m_fp = fp[mod]["lora_A"], fp[mod]["lora_B"], fp[mod]["magnitude"]
        A_bf, B_bf, m_bf = bf[mod]["lora_A"], bf[mod]["lora_B"], bf[mod]["magnitude"]
        dW_fp = scale * (B_fp @ A_fp)
        dW_bf = scale * (B_bf @ A_bf)
        r = {
            "module": mod,
            "role": role_of(mod),
            "shape_dW": list(dW_fp.shape),
            "reldiff_dW":   relL2(dW_bf, dW_fp),
            "reldiff_mag":  relL2(m_bf, m_fp),
            "reldiff_loraA": relL2(A_bf, A_fp),
            "reldiff_loraB": relL2(B_bf, B_fp),
            # spectral norm of the low-rank update dW
            "spec_dW_fp": specnorm(dW_fp),
            "spec_dW_bf": specnorm(dW_bf),
            # magnitude = per-output-row norm of the EFFECTIVE weight (dora-rows)
            "mag_L2_fp": float(torch.linalg.norm(m_fp)),
            "mag_L2_bf": float(torch.linalg.norm(m_bf)),
            "mag_mean_fp": float(m_fp.mean()),
            "mag_mean_bf": float(m_bf.mean()),
        }
        r["spec_ratio_dW"] = r["spec_dW_bf"] / (r["spec_dW_fp"] + 1e-20)
        r["mag_ratio_L2"]  = r["mag_L2_bf"] / (r["mag_L2_fp"] + 1e-20)
        rows.append(r)

    roles = sorted(set(r["role"] for r in rows))
    def agg(role):
        rr = [r for r in rows if r["role"] == role]
        import statistics as st
        def mean(xs): return sum(xs)/len(xs)
        return {
            "n": len(rr),
            "reldiff_dW_mean":  mean([r["reldiff_dW"] for r in rr]),
            "reldiff_dW_max":   max(r["reldiff_dW"] for r in rr),
            "reldiff_mag_mean": mean([r["reldiff_mag"] for r in rr]),
            "reldiff_mag_max":  max(r["reldiff_mag"] for r in rr),
            "reldiff_loraA_mean": mean([r["reldiff_loraA"] for r in rr]),
            "reldiff_loraB_mean": mean([r["reldiff_loraB"] for r in rr]),
            # inflation tests
            "spec_ratio_dW_mean": mean([r["spec_ratio_dW"] for r in rr]),
            "spec_ratio_dW_median": st.median([r["spec_ratio_dW"] for r in rr]),
            "mag_ratio_L2_mean": mean([r["mag_ratio_L2"] for r in rr]),
            "mag_ratio_L2_median": st.median([r["mag_ratio_L2"] for r in rr]),
            # how many modules have bf16 inflated (>1)
            "frac_spec_bf_larger": mean([1.0 if r["spec_ratio_dW"] > 1 else 0.0 for r in rr]),
            "frac_mag_bf_larger":  mean([1.0 if r["mag_ratio_L2"] > 1 else 0.0 for r in rr]),
        }
    per_role = {role: agg(role) for role in roles}

    top_dW = sorted(rows, key=lambda r: r["reldiff_dW"], reverse=True)[:15]
    top_mag = sorted(rows, key=lambda r: r["reldiff_mag"], reverse=True)[:15]

    result = {
        "generated": datetime.datetime.now().isoformat(),
        "fp32_ckpt": FP32_CKPT, "bf16_ckpt": BF16_CKPT,
        "fp32_meta": fp_meta, "bf16_meta": bf_meta,
        "lora_scale": scale,
        "n_modules": len(rows),
        "roles": roles,
        "per_role": per_role,
        "top15_reldiff_dW": [{k: r[k] for k in ("module","role","reldiff_dW","spec_ratio_dW","mag_ratio_L2")} for r in top_dW],
        "top15_reldiff_mag": [{k: r[k] for k in ("module","role","reldiff_mag","mag_ratio_L2")} for r in top_mag],
        "per_module": rows,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "result.json"), "w") as f:
        json.dump(result, f, indent=1)

    # console summary
    print("\n=== PER-ROLE (mean/max relative-L2 diff of merged update dW=B@A) ===")
    print(f"{'role':<16}{'n':>4}{'dW_mean':>10}{'dW_max':>10}{'mag_mean':>10}"
          f"{'specR_med':>11}{'magR_med':>10}{'%bf>fp(spec)':>13}")
    for role in roles:
        a = per_role[role]
        print(f"{role:<16}{a['n']:>4}{a['reldiff_dW_mean']:>10.4f}{a['reldiff_dW_max']:>10.4f}"
              f"{a['reldiff_mag_mean']:>10.4f}{a['spec_ratio_dW_median']:>11.4f}"
              f"{a['mag_ratio_L2_median']:>10.4f}{a['frac_spec_bf_larger']*100:>12.0f}%")
    print("\n=== TOP-10 reldiff_dW ===")
    for r in top_dW[:10]:
        print(f"  {r['reldiff_dW']:.4f}  specR={r['spec_ratio_dW']:.3f}  magR={r['mag_ratio_L2']:.4f}  [{r['role']}] {r['module']}")
    print("\nwrote", os.path.join(OUT_DIR, "result.json"))
    return result

if __name__ == "__main__":
    main()
