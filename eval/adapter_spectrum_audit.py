#!/usr/bin/env python3
# Owner: KUANG (created 2026-10-17)
"""adapter_spectrum_audit.py -- how spread out is a trained adapter's change? (test plan section P, adapter audit)

WHY. arXiv 2606.31591 ("Evil Spectra", papers/knowledge.md) found that, among adaptive optimizers, LoRA adapters with a
FLAT singular-value spectrum (Muon: stable rank 17 of 32) caused much less collateral change outside the fine-tuning
target than concentrated ones (Adam / Lion: ~2.4). Our analogue is the FiLM adapter leaking training-set style and the
LatCH heads being "transparent". This script measures the spectrum of each adapter CHANGE so it can be set against the
style drift (CLAP) already measured per run in EXPERIMENTS E7-E11. It reads checkpoints only; no GPU, no rendering.

WHAT IS MEASURED, per matrix:
- LoRA / DoRA: the effective change B @ A (never A and B separately: they are optimized as factors, and only the
  product is the weight change).
- Other adapters (FiLM): W - W_init when --init is given, else W itself (correct only for zero-initialised adapter
  matrices; the output says which).
  stable_rank = ||dW||_F^2 / s_1^2;  frob_nuclear = ||dW||_F / ||dW||_* - 1/sqrt(r) (0 = perfectly flat over the r
  nonzero directions; the Evil Spectra regulariser);  spectral_entropy (normalised to [0, 1]);  condition = s_1 / s_r.
All four are scale-invariant: they describe the SHAPE of the change, not its size (size is reported separately).

RUN:  SAO/.venv/bin/python eval/adapter_spectrum_audit.py CKPT [CKPT ...] [--init INIT_CKPT] [--out audit.json]
"""
import argparse
import json
import math
import re
import sys

import torch


def _state_dict(obj):
    if isinstance(obj, dict):
        for k in ("state_dict", "state", "model", "module"):
            if k in obj and isinstance(obj[k], dict) and any(torch.is_tensor(v) for v in obj[k].values()):
                return obj[k]
        if any(torch.is_tensor(v) for v in obj.values()):
            return obj
    raise ValueError("no state dict found in checkpoint")


def spectrum_metrics(dW):
    s = torch.linalg.svdvals(dW.float())
    if s.numel() == 0 or float(s[0]) == 0.0:
        return {"zero": True}
    nz = s[s > 1e-6 * s[0]]
    r = nz.numel()
    fro, nuc = float(nz.pow(2).sum().sqrt()), float(nz.sum())
    p = nz.pow(2) / nz.pow(2).sum()
    ent = float(-(p * p.clamp_min(1e-30).log()).sum()) / math.log(r) if r > 1 else 0.0
    return {"zero": False, "rank": r, "fro": fro, "stable_rank": float(nz.pow(2).sum() / s[0] ** 2),
            "frob_nuclear": fro / nuc - 1.0 / math.sqrt(r), "spectral_entropy": ent,
            "condition": float(s[0] / nz[-1]), "top1_energy": float(p[0])}


def adapter_changes(sd, init_sd=None):
    """Yield (name, kind, dW). LoRA pairs '<x>lora_A' / '<x>lora_B' -> B @ A; other 2-D tensors -> W (- W_init)."""
    keys = list(sd.keys())
    paired = set()
    for k in keys:
        if k.endswith("lora_A"):
            kb = k[: -len("lora_A")] + "lora_B"
            if kb in sd:
                A, B = sd[k].float(), sd[kb].float()
                if A.ndim == 2 and B.ndim == 2 and B.shape[1] == A.shape[0]:
                    paired.update((k, kb))
                    yield k[: -len("lora_A")].rstrip("."), "lora_BA", B @ A
    if any(k.endswith("lora_A") for k in keys):
        return
    for k in keys:
        v = sd[k]
        if k in paired or not torch.is_tensor(v) or v.ndim != 2 or min(v.shape) < 2:
            continue
        if init_sd is not None and k in init_sd:
            yield k, "delta_from_init", v.float() - init_sd[k].float()
        else:
            yield k, "weight_as_is", v.float()


def family(name):
    n = re.sub(r"\.\d+\.", ".#.", name)
    return re.sub(r"^.*?(attn|mlp|ff|proj|qkv|to_q|to_k|to_v|to_out|adaLN|adapter|cond|film|lora)", r"\1", n)


def audit(path, init_sd=None, match=None):
    sd = _state_dict(torch.load(path, map_location="cpu", weights_only=False))
    rows = []
    for name, kind, dW in adapter_changes(sd, init_sd):
        if match and not re.search(match, name):
            continue
        m = spectrum_metrics(dW)
        if m.get("zero"):
            continue
        rows.append({"name": name, "kind": kind, "shape": list(dW.shape), "family": family(name), **m})
    summ = {}
    if rows:
        for key in ("stable_rank", "frob_nuclear", "spectral_entropy", "condition", "top1_energy"):
            vals = sorted(r[key] for r in rows)
            summ[key] = {"median": vals[len(vals) // 2], "mean": sum(vals) / len(vals)}
        summ["n_matrices"] = len(rows)
        summ["kinds"] = sorted({r["kind"] for r in rows})
    return {"ckpt": path, "summary": summ, "matrices": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ckpts", nargs="+")
    ap.add_argument("--init", default=None, help="checkpoint to subtract (non-LoRA adapters)")
    ap.add_argument("--match", default=None, help="regex on parameter names (e.g. 'adapter' to skip the base)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    init_sd = _state_dict(torch.load(a.init, map_location="cpu", weights_only=False)) if a.init else None
    res = [audit(p, init_sd, a.match) for p in a.ckpts]
    for r in res:
        s = r["summary"]
        if not s:
            print(f"{r['ckpt']}: no nonzero 2-D adapter matrices found")
            continue
        print(f"{r['ckpt']}: {s['n_matrices']} matrices ({', '.join(s['kinds'])}); median stable rank "
              f"{s['stable_rank']['median']:.2f}, Frob/nuclear {s['frob_nuclear']['median']:.3f}, "
              f"entropy {s['spectral_entropy']['median']:.3f}, condition {s['condition']['median']:.1f}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
        print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
