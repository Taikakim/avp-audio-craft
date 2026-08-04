#!/usr/bin/env python3
"""gen_layer_curves.py — per-DiT-layer update-weight curves for the FusionOpt
--layer-update-weights schedule (CONTINUITY 2026-07-24, for W's mechanism).

Produces lumi/layer_curves/curves.json with three curves (each {layer_idx: multiplier},
default 1.0 for non-transformer params):
  protect_melody_log / protect_melody_exp — SOFT-KNEE: damp late-layer updates, but PROTECT
     layers that carry melody (Kim's ruling). multiplier = 1 - depth_damp(L,shape)*(1-m_norm(L)),
     where m_norm = per-layer melody readout (head_a_ceiling_act val_bacc, peaks ~L06) minmaxed,
     depth_damp ramps past the mid-depth knee (log = concave/early, exp = convex/late).
  delta_upweight — subtly UPWEIGHT high-delta layers so salient features grow faster:
     multiplier = 1 + BOOST * d_norm(L), d_norm = per-layer ||scaling*(B@A)|| (winning goa a128).

Multiplier applies to the update AFTER NS5 (scales the orthogonalized step per layer).
CPU/adapter-only. Run: stable-audio-3/.venv/bin/python lumi/gen_layer_curves.py
"""
import json, glob, re, os, math
import torch

HEADA = "/home/kim/Projects/SAO/eval/musicology/head_a_ceiling_act/summary.json"
GOA_A128 = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/fp32_winning/winning_goa_t512_a128_fp32"
OUT = "/home/kim/Projects/SAO/lumi/layer_curves/curves.json"
MAXD, KK, BOOST = 0.6, 4.0, 0.3           # max damp, curve steepness, delta boost

# ---- melody per-layer readout (best val_bacc per layer) ----
tbl = json.load(open(HEADA))["table"]
mel = {}
for k, v in tbl.items():
    L = int(re.search(r"L(\d+)", k).group(1)); vb = v.get("val_bacc")
    if vb is not None: mel[L] = max(mel.get(L, 0), vb)

# ---- per-layer delta norm from the goa a128 adapter ----
p = max(glob.glob(f"{GOA_A128}/epoch=*.ckpt"), key=lambda x: int(re.search(r"epoch=(\d+)", x).group(1)))
ck = torch.load(p, map_location="cpu", weights_only=False)
sd = ck.get("state_dict", ck)
cfg = ck.get("lora_config") or {}
r = int(cfg.get("rank", 128)); a = float(cfg.get("alpha", r)); sc = a / r
layer_delta, depth = {}, 0
for kk in sd:
    if ".parametrizations.weight.0.lora_A" not in kk: continue
    m = re.search(r"layers\.(\d+)\.", kk)
    mod = kk.rsplit(".parametrizations.weight.0.", 1)[0]; pfx = mod + ".parametrizations.weight.0"
    d = (sc * (sd[pfx + ".lora_B"].double() @ sd[pfx + ".lora_A"].double())).norm().item()
    if m:
        L = int(m.group(1)); layer_delta[L] = layer_delta.get(L, 0.0) + d**2; depth = max(depth, L + 1)
layer_delta = {L: math.sqrt(v) for L, v in layer_delta.items()}
print(f"[curves] depth={depth} layers; melody layers sampled={sorted(mel)}")

def interp(dic, L):     # linear interp over sampled layer keys
    ks = sorted(dic)
    if L in dic: return dic[L]
    lo = max([k for k in ks if k <= L], default=ks[0]); hi = min([k for k in ks if k >= L], default=ks[-1])
    if lo == hi: return dic[lo]
    t = (L - lo) / (hi - lo); return dic[lo] * (1 - t) + dic[hi] * t

def minmax(vals):
    lo, hi = min(vals), max(vals); return lambda x: (x - lo) / (hi - lo) if hi > lo else 0.5

m_all = [interp(mel, L) for L in range(depth)]; mnorm = minmax(m_all)
d_all = [interp(layer_delta, L) for L in range(depth)]; dnorm = minmax(d_all)
knee = depth // 2

def depth_damp(L, shape):
    if L < knee: return 0.0
    dd = (L - knee) / max(1, depth - 1 - knee)               # 0 at knee -> 1 at last
    if shape == "log": return MAXD * math.log1p(KK * dd) / math.log1p(KK)
    return MAXD * (math.exp(KK * dd) - 1) / (math.exp(KK) - 1)   # exp

curves = {"protect_melody_log": {}, "protect_melody_exp": {}, "delta_upweight": {}}
for L in range(depth):
    mn = mnorm(interp(mel, L)); dn = dnorm(interp(layer_delta, L))
    curves["protect_melody_log"][str(L)] = round(1 - depth_damp(L, "log") * (1 - mn), 4)
    curves["protect_melody_exp"][str(L)] = round(1 - depth_damp(L, "exp") * (1 - mn), 4)
    curves["delta_upweight"][str(L)] = round(1 + BOOST * dn, 4)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc = {"meta": {"depth": depth, "knee": knee, "max_damp": MAXD, "steepness": KK, "boost": BOOST,
                "melody_src": "head_a_ceiling_act/summary.json val_bacc",
                "delta_src": os.path.basename(p) + " (goa a128)",
                "applies_to": "post-NS5 update step, transformer.layers.N params; default 1.0 elsewhere",
                "note": "protect_melody: damp late layers inversely to melody content; delta_upweight: boost high-delta layers"},
       "default": 1.0, "curves": curves}
json.dump(doc, open(OUT, "w"), indent=1)
print(f"[curves] wrote {OUT}")
for name, c in curves.items():
    vals = [c[str(L)] for L in range(depth)]
    print(f"  {name:20} L0={vals[0]:.2f} Lknee={vals[knee]:.2f} Llast={vals[-1]:.2f}  "
          f"[{', '.join(f'{v:.2f}' for v in vals)}]")
