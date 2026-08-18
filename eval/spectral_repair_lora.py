#!/usr/bin/env python3
"""spectral_repair_lora.py — remove, keep-only, or shrink the top-k singular directions of every
adapted matrix's B·A in a LoRA/DoRA checkpoint, re-factored at the SAME rank so the result loads
with the standard loader and renders like any other checkpoint.

WHY (C, 2026-08-18, Kim's "mask the outliers out and make a new model" — done in the right
geometry). task_vector_gram/spike found the degraded AdamW-sweep arms carry 20-30 % of each
matrix's delta energy in ONE singular direction that (a) is absent in every healthy run (2 %,
flat), (b) is the SAME direction across the four bad arms (|cos| 0.25 vs chance 0.026), and (c) is
strongest at the smallest LR — a systematic component that does not scale with learning. Per-scalar
clipping cannot touch it (it is spread over ~500 channels, participation ratio ~520); a spectral
operation on B·A can, exactly. Three probes, one tool:
    remove  k   B·A minus its top-k components          -> "the model without the spike"
    keep    k   ONLY the top-k components               -> "the spike alone"  (the control that
                                                           tells you what the spike DOES)
    shrink  k f top-k components scaled by f            -> the soft version (Gavish-Donoho style)
Optionally the DoRA magnitude vector, which the bad arms also drifted 3-7x more than healthy
ones, can be pulled toward the base row norms:  --mag keep | reset | blend:0.5

WHAT IT DOES NOT DO. It does not know whether the spike is a pathology or the part of the delta
that actually learned the task; only the render (20 s, cfg 7 / W1, Kim's ears) can say. Run all
three probes on the same seed and listen: if "remove" is clean and "keep" is broken, the spike is
the pathology; if "keep" carries the goa and "remove" is base-like, the spike IS the learning and
the flat remainder is noise. Both outcomes are informative.

USAGE
  .venv/bin/python eval/spectral_repair_lora.py --ckpt <bad.ckpt> --out <dir> \
      --mode remove --k 1 [--mag reset]      # writes <dir>/<stem>__remove_k1[_magreset].ckpt
  ... --mode keep --k 1 ; --mode shrink --k 3 --factor 0.3
Only matrices with square-ish adapted shapes are touched by default; --all-shapes touches every
adapted matrix. CPU-only.
"""
import argparse
import glob
import os
import re
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
import torch  # noqa: E402


def refactor(M, rank):
    """(A, B) with B @ A == M (up to rank), shapes (rank, in) / (out, rank): balanced sqrt split."""
    U, s, Vh = torch.linalg.svd(M, full_matrices=False)
    r = min(rank, s.numel())
    root = s[:r].clamp_min(0).sqrt()
    B = U[:, :r] * root
    A = root[:, None] * Vh[:r]
    if r < rank:                                     # pad to the checkpoint's rank with zeros
        B = torch.cat([B, torch.zeros(B.shape[0], rank - r)], 1)
        A = torch.cat([A, torch.zeros(rank - r, A.shape[1])], 0)
    return A, B


def repair_pair(A, B, mode="remove", k=1, factor=0.0):
    """Operate on the singular spectrum of B·A via the r×r problem; return new (A, B) same shapes."""
    rank = B.shape[1]
    Qb, Rb = torch.linalg.qr(B.float())
    Qa, Ra = torch.linalg.qr(A.float().T)
    U, s, Vh = torch.linalg.svd(Rb @ Ra.T)           # r×r
    s2 = s.clone()
    k = max(0, min(int(k), s.numel()))
    if mode == "remove":
        s2[:k] = 0.0
    elif mode == "keep":
        s2[k:] = 0.0
    elif mode == "shrink":
        s2[:k] *= float(factor)
    else:
        raise ValueError(mode)
    M2 = (Qb @ U * s2) @ (Vh @ Qa.T)                 # (out, in), rank <= r
    A2, B2 = refactor(M2, rank)
    return A2.to(A.dtype), B2.to(B.dtype)


BASE_ST = glob.glob("/home/kim/.cache/huggingface/hub/models--stabilityai--"
                    "stable-audio-3-medium-base/snapshots/*/model.safetensors")


def _base_rownorm(f, prefix):
    stem = prefix.replace(".parametrizations.weight.0", "")
    for cand in ("model." + stem + ".weight", "conditioner." + stem + ".weight", stem + ".weight"):
        if cand in f.keys():
            W = f.get_tensor(cand).float()
            return W.reshape(W.shape[0], -1).norm(dim=1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True, help="output dir")
    ap.add_argument("--mode", choices=("remove", "keep", "shrink"), default="remove")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--factor", type=float, default=0.0, help="shrink factor for --mode shrink")
    ap.add_argument("--mag", default="keep", help="DoRA magnitude: keep | reset | blend:<f> "
                                                  "(f toward base row norms)")
    ap.add_argument("--all-shapes", action="store_true")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()

    ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    sd = ck.get("state_dict", ck)
    cfg = ck.get("lora_config", {})
    prefixes = sorted({k.rsplit(".", 1)[0] for k in sd if k.endswith(".lora_A")})
    f = None
    if a.mag != "keep":
        from safetensors import safe_open
        if not BASE_ST:
            sys.exit("[repair] --mag needs the medium-base safetensors in the HF cache")
        f = safe_open(BASE_ST[0], framework="pt")
    n_done = n_skip = 0
    e_removed = e_total = 0.0
    for p in prefixes:
        A, B = sd[p + ".lora_A"], sd[p + ".lora_B"]
        square_ish = (A.shape[1] == B.shape[0])
        if not (square_ish or a.all_shapes):
            n_skip += 1; continue
        # energy bookkeeping (what fraction of ΔW energy the operation touched)
        Qb, Rb = torch.linalg.qr(B.float()); Qa, Ra = torch.linalg.qr(A.float().T)
        s = torch.linalg.svdvals(Rb @ Ra.T); s2 = s * s
        e_total += float(s2.sum())
        kk = max(0, min(a.k, s.numel()))
        e_removed += float(s2[:kk].sum()) if a.mode != "keep" else float(s2[kk:].sum())
        A2, B2 = repair_pair(A, B, a.mode, a.k, a.factor)
        sd[p + ".lora_A"] = A2; sd[p + ".lora_B"] = B2
        mk = p + ".magnitude"
        if mk in sd and a.mag != "keep":
            rn = _base_rownorm(f, p)
            if rn is not None:
                if a.mag == "reset":
                    sd[mk] = rn.to(sd[mk].dtype)
                elif a.mag.startswith("blend:"):
                    t = float(a.mag.split(":", 1)[1])
                    sd[mk] = ((1 - t) * sd[mk].float() + t * rn).to(sd[mk].dtype)
        n_done += 1
    os.makedirs(a.out, exist_ok=True)
    stem = a.tag or os.path.basename(os.path.dirname(a.ckpt)) or "ckpt"
    suffix = f"{a.mode}_k{a.k}" + (f"_f{a.factor}" if a.mode == "shrink" else "") + \
             (f"_mag{a.mag.replace(':', '')}" if a.mag != "keep" else "")
    dst = os.path.join(a.out, f"{stem}__{suffix}.ckpt")
    torch.save({"state_dict": sd, "lora_config": cfg, "epoch": -1, "global_step": -1,
                "spectral_repair": {"source": os.path.abspath(a.ckpt), "mode": a.mode, "k": a.k,
                                    "factor": a.factor, "mag": a.mag, "matrices": n_done,
                                    "skipped_nonsquare": n_skip,
                                    "energy_fraction_affected": e_removed / e_total if e_total else None,
                                    "tool": "eval/spectral_repair_lora.py"}}, dst)
    print(f"[repair] {a.mode} k={a.k} on {n_done} matrices ({n_skip} skipped): "
          f"{100 * e_removed / e_total if e_total else 0:.1f}% of ΔW energy "
          f"{'zeroed' if a.mode == 'remove' else 'kept' if a.mode == 'keep' else 'scaled'} -> {dst}")


if __name__ == "__main__":
    main()
