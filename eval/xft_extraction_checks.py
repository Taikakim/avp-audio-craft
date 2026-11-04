#!/usr/bin/env python3
"""xft_extraction_checks.py -- why did the SVD-extracted adapters glitch? (2026-11-04)

The July 2026 extraction (eval/extract_svd_adapters.py) turned the full fine-tunes into LoRA/DoRA
adapters at ranks 16/64/128. All of them glitched by ear, and the cause was put down to rank: rank 128
keeps 26 % of the whole-model delta energy. Three things were never isolated:
  - the extractor carries only the weights of the 229 target modules. Every other tensor the
    fine-tune changed (AdaLN to_scale_shift_gate, the 64 memory tokens, RMSNorm and q/k-norm gains,
    feed-forward biases, embeddings) stays at base;
  - the full-rank delta was never pushed through the real adapter loader and rendered;
  - save_lora_safetensors stores adapters in fp16, so the July files were fp16.
SA3 medium also uses differential attention (attn_kwargs.differential, lambda fixed at 1): the output
is softmax(q k) v - softmax(q2 k2) v, so an uneven error between the two maps can be amplified.

Stages (one fine-tune checkpoint, no training):
  measure  (CPU)  per-tensor delta of the fine-tune against medium-base, summed per family, target vs
                  omitted; EMA presence and the EMA-vs-online distance; per-module SVD energy kept at
                  each rank, and the per-block (q, k, v, q2, k2) error of the attention projections.
  render   (GPU)  the variants below with fixed prompts and seeds through StableAudioModel.generate:
                  a wav and the latents per render, plus a teacher-forced probe. Every DiT call of the
                  fine-tune's own render is replayed through each variant and the outputs compared.

Variants (W = the 229 target weights, N = every other tensor):
  fullft                   W ft,     N ft      the reference
  base                     W base,   N base
  matrices_only            W ft,     N base    check 2: a perfect extract of the 229 modules
  nonmatrix_only           W base,   N ft      the omitted part on its own
  all_r{R}                 W rank R, N base    the July LoRA, merged in weight space
  all_r{R}_plus_nonmatrix  W rank R, N ft      the omitted tensors copied as well
  attn_r{R}                attention W rank R, other W ft, N ft    check 4: the attention cut alone
  nonattn_r{R}             attention W ft, other W rank R, N ft    its complement
  loader_lora_full_fp16, loader_dora_full_fp16, loader_dora_full_fp32
                           check 3: the full-rank extract through load_lora (twin: matrices_only)
  loader_lora_r{R}, loader_dora_r{R}
                           the July files rebuilt (fp16) through load_lora (LoRA twin: all_r{R})

How to read the report: docs/xft-extraction-checks-2026-11-04.md.

Run (desktop, from the repo root):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $PY eval/xft_extraction_checks.py \
      --ckpt <fullft .ckpt> --out <dir> [--stage measure|render|all] [--ranks 16,128]
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_svd_adapters as xsvd  # noqa: E402

DIT_ONLINE = "diffusion.model."
DIT_EMA = "diffusion_ema.ema_model."
COND = "diffusion.conditioner."

# Output blocks of the fused projections, in the order transformer.py chunks them.
ATTN_BLOCKS = {
    ".self_attn.to_qkv": ("q", "k", "v", "q2", "k2"),
    ".cross_attn.to_q": ("q", "q2"),
    ".cross_attn.to_kv": ("k", "k2", "v"),
}

FAMILY_RULES = (
    ("conditioner", lambda n: n.startswith("conditioners.")),
    ("adaln_gate", lambda n: "to_scale_shift_gate" in n),
    ("memory_tokens", lambda n: "memory_tokens" in n),
    ("qk_norm", lambda n: ".q_norm." in n or ".k_norm." in n),
    ("norm", lambda n: re.search(r"(^|\.)\w*norm\w*\.", n) is not None),
    ("self_attn", lambda n: ".self_attn." in n),
    ("cross_attn", lambda n: ".cross_attn." in n),
    ("ff", lambda n: ".ff." in n),
    ("local_embed", lambda n: "to_local_embed" in n),
    ("timestep_embed", lambda n: "timestep" in n),
    ("cond_embed", lambda n: "to_global_embed" in n or "to_cond_embed" in n),
)

DEFAULT_PROMPTS = (
    "psychedelic goa trance, 145 BPM, rolling acid bassline, squelchy lead, hypnotic",
    "dark minimal techno, 128 BPM, deep kick, sparse percussion, dub chords",
    "ambient downtempo, warm pads, soft breakbeat, slow evolving textures",
)


def family(name: str) -> str:
    for fam, rule in FAMILY_RULES:
        if rule(name):
            return fam
    return "other"


def is_attn(mod: str) -> bool:
    return ".self_attn." in mod or ".cross_attn." in mod


def attn_blocks(mod: str):
    for suffix, names in ATTN_BLOCKS.items():
        if mod.endswith(suffix):
            return names
    return None


# ----------------------------------------------------------------------------------------- states

def split_state(raw: dict, weights: str = "online") -> dict:
    """Lightning state_dict -> the 'model.X' / 'conditioners.X' namespace of extract_svd_adapters.
    weights='ema' takes the DiT from the EMA shadow; the conditioner always comes from the online set."""
    dit = DIT_EMA if weights == "ema" else DIT_ONLINE
    out = {}
    for k, v in raw.items():
        if k.startswith(dit):
            out[k[len(dit):]] = v
        elif k.startswith(COND):
            out[k[len(COND):]] = v
    return out


def load_raw(path) -> dict:
    try:
        ck = torch.load(str(path), map_location="cpu", weights_only=False, mmap=True)
    except RuntimeError:                     # legacy (non-zip) format cannot be memory-mapped
        ck = torch.load(str(path), map_location="cpu", weights_only=False)
    return ck.get("state_dict", ck)


def coverage_gate(base: dict, ft: dict, targets) -> dict:
    """FAIL LOUD like the extractor: a wrong prefix would silently compare base with base."""
    dit_keys = [k for k in base if not k.startswith("conditioners.")]
    dit_cov = sum(1 for k in dit_keys if k in ft) / max(1, len(dit_keys))
    tgt_cov = sum(1 for m in targets if m + ".weight" in ft) / max(1, len(targets))
    if dit_cov <= xsvd.COVERAGE_MIN or tgt_cov <= xsvd.COVERAGE_MIN:
        raise SystemExit(f"fine-tune covers {dit_cov:.1%} of the DiT tensors and {tgt_cov:.1%} of the "
                         f"targets; refusing to trust any delta (key-prefix mismatch?)")
    return {"dit_coverage": dit_cov, "target_coverage": tgt_cov}


# ---------------------------------------------------------------------------------------- measure

def measure(base: dict, ft: dict, targets) -> list[dict]:
    """One row per tensor: family, target or omitted, and the delta's size."""
    tw = {m + ".weight" for m in targets}
    rows = []
    for k in sorted(set(base) | set(ft)):
        row = {"name": k, "family": family(k), "target": k in tw}
        if k not in ft or k not in base:
            row["status"] = "only_base" if k in base else "only_ft"
            rows.append(row)
            continue
        b, f = base[k], ft[k]
        if not b.is_floating_point():
            continue
        if b.shape != f.shape:
            row["status"] = f"shape {tuple(b.shape)} vs {tuple(f.shape)}"
            rows.append(row)
            continue
        dtypes = f"{str(b.dtype).replace('torch.', '')}/{str(f.dtype).replace('torch.', '')}"
        b, f = b.float(), f.float()
        bn, dn = float(b.norm()), float((f - b).norm())
        # what rounding base to bf16 alone would show as a "delta": a fine-tune saved in bf16 against
        # an fp32 base carries this much full-rank noise even in tensors that did not train
        floor = float((b - b.to(torch.bfloat16).float()).norm())
        row.update(status="ok", dtypes=dtypes, numel=b.numel(), shape="x".join(map(str, b.shape)),
                   base_norm=bn, delta_norm=dn, rel=dn / bn if bn > 0 else (math.inf if dn > 0 else 0.0),
                   bf16_floor=floor, delta_over_floor=dn / floor if floor > 0 else None)
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    """Per (family, target|omitted): count, changed count, share of the total delta energy, rel spread."""
    ok = [r for r in rows if r.get("status") == "ok"]
    total = sum(r["delta_norm"] ** 2 for r in ok) or 1.0
    groups = {}
    for r in ok:
        g = groups.setdefault(f'{r["family"]}/{"target" if r["target"] else "omitted"}', [])
        g.append(r)
    out = {}
    for key, rs in sorted(groups.items()):
        rel = sorted(r["rel"] for r in rs if math.isfinite(r["rel"]))
        out[key] = {"tensors": len(rs), "changed": sum(1 for r in rs if r["delta_norm"] > 0),
                    "below_2x_bf16_floor": sum(1 for r in rs if r["delta_norm"] > 0 and r["delta_over_floor"]
                                               is not None and r["delta_over_floor"] < 2.0),
                    "dtypes": sorted({r["dtypes"] for r in rs}),
                    "numel": sum(r["numel"] for r in rs),
                    "delta_energy_share": sum(r["delta_norm"] ** 2 for r in rs) / total,
                    "rel_median": rel[len(rel) // 2] if rel else None, "rel_max": rel[-1] if rel else None}
    omitted = [r for r in ok if not r["target"]]
    out["_omitted_total"] = {"tensors": len(omitted), "changed": sum(1 for r in omitted if r["delta_norm"] > 0),
                             "delta_energy_share": sum(r["delta_norm"] ** 2 for r in omitted) / total}
    out["_not_compared"] = [f'{r["name"]}: {r["status"]}' for r in rows if r.get("status") not in (None, "ok")]
    return out


def ema_report(raw: dict, base: dict, online: dict) -> dict:
    if not any(k.startswith(DIT_EMA) for k in raw):
        return {"has_ema": False}
    ema = split_state(raw, "ema")
    d_eo = d_ob = 0.0
    for k, v in online.items():
        if k in ema and k in base and v.is_floating_point() and not k.startswith("conditioners."):
            o = v.float()
            d_eo += float((ema[k].float() - o).pow(2).sum())
            d_ob += float((o - base[k].float()).pow(2).sum())
    step = raw.get("diffusion_ema.ema_step")
    return {"has_ema": True, "ema_step": int(step) if step is not None else None,
            "ema_minus_online_over_online_minus_base": math.sqrt(d_eo / d_ob) if d_ob > 0 else None}


# -------------------------------------------------------------------------------------------- SVD

def svd_module(base_w: torch.Tensor, ft_w: torch.Tensor, ranks, device="cpu"):
    """Same SVD and sign convention as extract_svd_adapters.extract_module, done once per module.
    Returns full (B, A) in fp32 on the CPU, the energy kept per rank, and for the fused attention
    projections the relative error of each output block at each rank."""
    fan_out = ft_w.shape[0]
    d = ft_w.reshape(fan_out, -1).double().to(device) - base_w.reshape(fan_out, -1).double().to(device)
    U, S, Vh = torch.linalg.svd(d, full_matrices=False)
    U, Vh = xsvd._canonicalize_svd_signs(U, Vh)
    sq = S.sqrt()
    B, A = U * sq.unsqueeze(0), sq.unsqueeze(1) * Vh
    e = S.pow(2)
    tot = float(e.sum())
    kept = {r: (float(e[:r].sum()) / tot if tot > 0 else 1.0) for r in ranks}
    return B.float().cpu(), A.float().cpu(), kept, d, tot


def block_errors(d: torch.Tensor, B: torch.Tensor, A: torch.Tensor, names, ranks) -> dict:
    """Relative Frobenius error of each output block (rows split evenly) at each rank."""
    out = {}
    rows = d.shape[0] // len(names)
    Bd, Ad = B.to(d), A.to(d)
    for r in ranks:
        approx = Bd[:, :r] @ Ad[:r]
        for i, n in enumerate(names):
            sl = slice(i * rows, (i + 1) * rows)
            dn = float(d[sl].norm())
            out[f"r{r}_{n}"] = float((d[sl] - approx[sl]).norm()) / dn if dn > 0 else 0.0
    return out


def pad_factors(B: torch.Tensor, A: torch.Tensor, rank: int):
    """Zero-pad (B, A) to a common rank: B @ A is unchanged and every module loads at one config rank."""
    k = B.shape[1]
    if k > rank:
        raise ValueError(f"cannot pad rank {k} down to {rank}")
    if k == rank:
        return B, A
    return (torch.cat([B, B.new_zeros(B.shape[0], rank - k)], 1),
            torch.cat([A, A.new_zeros(rank - k, A.shape[1])], 0))


def adapter_state(factors: dict, ft: dict, rank: int | None, method: str, pad_to: int | None = None,
                  dtype=torch.float32) -> dict:
    """The extractor's file layout. rank=None = full rank. DoRA magnitude = row norms of the fine-tune.
    dtype=float16 builds the fp16 file directly (save_lora_safetensors would halve it anyway)."""
    sd = {}
    for mod, (B, A) in factors.items():
        if rank is not None:
            B, A = B[:, :rank], A[:rank]
        if pad_to is not None:
            B, A = pad_factors(B, A, pad_to)
        p = f"{mod}.parametrizations.weight.0"
        sd[f"{p}.lora_A"] = A.to(dtype).contiguous()
        sd[f"{p}.lora_B"] = B.to(dtype).contiguous()
        if method == "dora-rows":
            w = ft[mod + ".weight"]
            sd[f"{p}.magnitude"] = w.reshape(w.shape[0], -1).float().norm(dim=1).to(dtype).contiguous()
    return sd


def write_adapter(sd: dict, rank: int, method: str, path: Path, ckpt: str) -> Path:
    cfg = {"rank": rank, "alpha": float(rank), "adapter_type": method, "dropout": 0.0, "include": None,
           "exclude": None, "extracted_from": ckpt, "extraction_method": "svd-fullft-delta (xft checks)"}
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".safetensors":
        from stable_audio_3.models.lora.utils import save_lora_safetensors
        save_lora_safetensors(sd, cfg, path)                      # fp16, exactly as in July
    else:
        torch.save({"state_dict": sd, "lora_config": cfg}, path)  # fp32 through the .ckpt branch
    return path


# --------------------------------------------------------------------------------------- variants

def compose(base: dict, ft: dict, targets, factors: dict, w_mode, n_mode: str) -> dict:
    """A full state dict. w_mode(mod) -> 'base' | 'ft' | int rank (base + rank-R delta);
    n_mode picks the source of every non-target tensor ('base' | 'ft')."""
    tw = {m + ".weight": m for m in targets}
    src = ft if n_mode == "ft" else base
    out = {}
    for k, v in base.items():
        mod = tw.get(k)
        if mod is None:
            out[k] = src.get(k, v)
            continue
        mode = w_mode(mod)
        if mode == "base":
            out[k] = v
        elif mode == "ft":
            out[k] = ft[k]
        else:
            B, A = factors[mod]
            out[k] = (v.float() + (B[:, :mode] @ A[:mode]).reshape(v.shape)).to(v.dtype)
    return out


def variant_specs(ranks) -> list[dict]:
    """Weight-space variants first (one model, reloaded in place), loader variants last (fresh model each)."""
    W = "weights"
    v = [dict(name="fullft", kind=W, w=lambda m: "ft", n="ft"),
         dict(name="base", kind=W, w=lambda m: "base", n="base"),
         dict(name="matrices_only", kind=W, w=lambda m: "ft", n="base"),
         dict(name="nonmatrix_only", kind=W, w=lambda m: "base", n="ft")]
    for r in ranks:
        v += [dict(name=f"all_r{r}", kind=W, w=lambda m, r=r: r, n="base"),
              dict(name=f"all_r{r}_plus_nonmatrix", kind=W, w=lambda m, r=r: r, n="ft"),
              dict(name=f"attn_r{r}", kind=W, w=lambda m, r=r: r if is_attn(m) else "ft", n="ft"),
              dict(name=f"nonattn_r{r}", kind=W, w=lambda m, r=r: "ft" if is_attn(m) else r, n="ft")]
    v += [dict(name="loader_lora_full_fp16", kind="loader", rank=None, method="lora", ext=".safetensors",
               twin="matrices_only"),
          dict(name="loader_dora_full_fp16", kind="loader", rank=None, method="dora-rows", ext=".safetensors",
               twin="matrices_only"),
          dict(name="loader_dora_full_fp32", kind="loader", rank=None, method="dora-rows", ext=".ckpt",
               twin="matrices_only")]
    for r in ranks:
        v += [dict(name=f"loader_lora_r{r}", kind="loader", rank=r, method="lora", ext=".safetensors",
                   twin=f"all_r{r}"),
              dict(name=f"loader_dora_r{r}", kind="loader", rank=r, method="dora-rows", ext=".safetensors",
                   twin=None)]
    return v


# ------------------------------------------------------------------------------------ the probe

def _to(obj, device):
    if torch.is_tensor(obj):
        return obj.detach().to(device).clone() if device == "cpu" else obj.to(device)
    if isinstance(obj, (list, tuple)):
        return type(obj)(_to(o, device) for o in obj)
    if isinstance(obj, dict):
        return {k: _to(v, device) for k, v in obj.items()}
    return obj


class CallRecorder:
    """Records every forward of one module (args, kwargs, output) to the CPU."""

    def __init__(self, module):
        self.calls = []
        self.handle = module.register_forward_hook(self._hook, with_kwargs=True)

    def _hook(self, module, args, kwargs, output):
        self.calls.append((_to(args, "cpu"), _to(kwargs, "cpu"), _to(output, "cpu")))

    def close(self):
        self.handle.remove()


def _out_tensor(o):
    return o if torch.is_tensor(o) else o[0]


@torch.inference_mode()
def replay(module, calls, device) -> list[torch.Tensor]:
    return [_out_tensor(module(*_to(a, device), **_to(kw, device))).float().cpu() for a, kw, _ in calls]


def probe_errors(outs, ref, base_outs=None, twin=None) -> dict:
    """Per-call errors against the fine-tune's recorded outputs, averaged over thirds of the trajectory.
    rel_ft = |y - y_ft| / |y_ft|;  rel_change = |y - y_ft| / |y_base - y_ft| (1.0 = as far as base)."""
    def stats(vals):
        n = len(vals)
        thirds = [vals[: max(1, n // 3)], vals[n // 3: max(n // 3 + 1, 2 * n // 3)], vals[2 * n // 3:]]
        return {"mean": float(np.mean(vals)), "early": float(np.mean(thirds[0])),
                "mid": float(np.mean(thirds[1])), "late": float(np.mean(thirds[2] or vals[-1:]))}
    rel_ft = [float((y - r).norm() / r.norm().clamp_min(1e-12)) for y, r in zip(outs, ref)]
    out = {"rel_ft": stats(rel_ft)}
    if base_outs is not None:
        rc = [float((y - r).norm() / (b - r).norm().clamp_min(1e-12)) for y, r, b in zip(outs, ref, base_outs)]
        out["rel_change"] = stats(rc)
    if twin is not None:
        out["rel_twin"] = stats([float((y - t).norm() / t.norm().clamp_min(1e-12)) for y, t in zip(outs, twin)])
    return out


def audio_stats(audio: torch.Tensor, sr: int) -> dict:
    x = audio.float().cpu().numpy()
    finite = np.isfinite(x)
    x = np.where(finite, x, 0.0)
    mono = x.mean(axis=0)
    spec = np.abs(np.fft.rfft(mono)) ** 2
    freqs = np.fft.rfftfreq(mono.shape[-1], 1.0 / sr)
    tot = float(spec.sum()) or 1.0
    return {"peak": float(np.abs(x).max()), "rms": float(np.sqrt((x ** 2).mean())),
            "clip_frac": float((np.abs(x) >= 0.999).mean()), "nonfinite": int((~finite).sum()),
            "hf16k_share": float(spec[freqs >= 16000].sum()) / tot}


# --------------------------------------------------------------------------------------- stages

def write_csv(path: Path, rows: list[dict]):
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def run_measure(args, base, ft, raw, targets, out: Path, ranks):
    out.mkdir(parents=True, exist_ok=True)
    rows = measure(base, ft, targets)
    write_csv(out / "tensors.csv", rows)
    fam = summarize(rows)
    fam["_ema"] = ema_report(raw, base, ft)
    (out / "families.json").write_text(json.dumps(fam, indent=1))
    print("[measure] delta energy per family (share of the whole fine-tune's change):")
    for k, s in fam.items():
        if not k.startswith("_"):
            print(f"  {k:32s} {s['tensors']:4d} tensors  {s['changed']:4d} changed  "
                  f"({s['below_2x_bf16_floor']} under 2x the bf16 floor)  share {s['delta_energy_share']:.4f}  "
                  f"rel median {s['rel_median']}  {s['dtypes']}")
    print(f"[measure] omitted total: {fam['_omitted_total']}")
    print(f"[measure] EMA: {fam['_ema']}")


def run_svd(args, base, ft, targets, out: Path, ranks):
    """One SVD per target module: energy and block-error tables, the truncated factors for the
    weight-space variants, and the loader adapters written to disk."""
    out.mkdir(parents=True, exist_ok=True)
    rmax = max(ranks)
    loaders = [s for s in variant_specs(ranks) if s["kind"] == "loader" and _wanted(s["name"], args.variants)
               ] if args.stage in ("render", "all") else []
    need_full = any(s["rank"] is None for s in loaders)       # full factors cost about 8 GB of RAM
    trunc, full, mod_rows, blk_rows, pad = {}, {}, [], [], 0
    t0 = time.time()
    for i, mod in enumerate(targets):
        B, A, kept, d, tot = svd_module(base[mod + ".weight"], ft[mod + ".weight"], ranks, args.svd_device)
        row = {"module": mod, "family": family(mod), "shape": "x".join(map(str, d.shape)),
               "delta_norm": math.sqrt(tot)}
        row.update({f"kept_r{r}": kept[r] for r in ranks})
        mod_rows.append(row)
        names = attn_blocks(mod)
        if names and d.shape[0] % len(names) == 0:
            blk_rows.append({"module": mod, **block_errors(d, B, A, names, ranks)})
        trunc[mod] = (B[:, :rmax].contiguous(), A[:rmax].contiguous())
        if need_full:
            full[mod] = (B, A)
        pad = max(pad, min(d.shape))
        del d, B, A
        if (i + 1) % 20 == 0:
            print(f"[svd] {i + 1}/{len(targets)} modules, {time.time() - t0:.0f} s")
    write_csv(out / "svd_modules.csv", mod_rows)
    if blk_rows:
        write_csv(out / "attn_blocks.csv", blk_rows)
        for r in ranks:
            for n in ("q", "k", "v", "q2", "k2"):
                vals = [b[f"r{r}_{n}"] for b in blk_rows if f"r{r}_{n}" in b]
                if vals:
                    print(f"[svd] rank {r} block {n:2s}: median relative error {float(np.median(vals)):.3f} "
                          f"over {len(vals)} modules")
    adapters = {}
    for spec in loaders:
        rank = spec["rank"]
        sd = adapter_state(full if rank is None else trunc, ft, rank, spec["method"],
                           pad_to=pad if rank is None else None,
                           dtype=torch.float16 if spec["ext"] == ".safetensors" else torch.float32)
        path = write_adapter(sd, pad if rank is None else rank, spec["method"],
                             out / "adapters" / f'{spec["name"]}{spec["ext"]}', str(args.ckpt))
        adapters[spec["name"]] = path
        print(f"[svd] wrote {path.name} ({len(sd)} tensors, config rank {pad if rank is None else rank})")
        del sd
    del full
    gc.collect()
    return trunc, adapters


def _wanted(name: str, pattern: str | None) -> bool:
    return pattern is None or name == "fullft" or name == "base" or re.search(pattern, name) is not None


def load_model(args):
    from stable_audio_3 import StableAudioModel
    return StableAudioModel.from_pretrained("medium-base", device=args.device, model_half=not args.fp32)


def set_weights(m, sd: dict):
    dit = {k: v for k, v in sd.items() if not k.startswith("conditioners.")}
    cond = {k: v for k, v in sd.items() if k.startswith("conditioners.")}
    with torch.no_grad():
        m.model.model.load_state_dict(dit, strict=True)
        m.model.conditioner.load_state_dict(cond, strict=True)


def run_render(args, base, ft, targets, trunc, adapters, out: Path, ranks):
    import soundfile as sf
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(pi, p, s) for pi, p in enumerate(args.prompts) for s in args.seeds]
    probe_jobs = jobs[: args.probe_renders]
    specs = [s for s in variant_specs(ranks) if _wanted(s["name"], args.variants)]
    report = {"ckpt": str(args.ckpt), "steps": args.steps, "cfg_scale": args.cfg, "duration": args.duration,
              "precision": "fp32" if args.fp32 else "bf16", "prompts": args.prompts, "seeds": args.seeds,
              "variants": {}}
    calls, ref_out, base_out, twin_out, ref_lat, base_lat = {}, {}, {}, {}, {}, {}
    twins = {s.get("twin") for s in specs if s.get("twin")}

    m = load_model(args)
    sr = m.model.sample_rate
    for spec in specs:
        name = spec["name"]
        t0 = time.time()
        if spec["kind"] == "weights":
            set_weights(m, compose(base, ft, targets, trunc, spec["w"], spec["n"]))
        else:
            del m
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            m = load_model(args)
            m.load_lora([str(adapters[name])])
        dit = m.model.model
        rec = {}
        renders = {}
        for pi, prompt, seed in jobs:
            key = f"p{pi}_s{seed}"
            recorder = CallRecorder(dit) if (name == "fullft" and (pi, prompt, seed) in probe_jobs) else None
            sink = []
            try:
                audio = m.generate(prompt=prompt, duration=args.duration, steps=args.steps,
                                   cfg_scale=args.cfg, seed=seed, latents_sink=sink)
            finally:
                if recorder is not None:
                    recorder.close()
                    if not recorder.calls:
                        raise SystemExit("the DiT recorded no calls: the probe hook is on the wrong module")
                    calls[key] = recorder.calls
                    ref_out[key] = [_out_tensor(c[2]).float() for c in recorder.calls]
            lat = sink[0].float().cpu() if sink else None
            vdir = out / name
            vdir.mkdir(exist_ok=True)
            sf.write(str(vdir / f"{key}.wav"), audio[0].float().cpu().numpy().T, sr, subtype="PCM_16")
            if lat is not None:
                torch.save(lat, vdir / f"{key}_latents.pt")
            r = audio_stats(audio[0], sr)
            if lat is not None:
                if name == "fullft":
                    ref_lat[key] = lat
                if name == "base":
                    base_lat[key] = lat
                if key in ref_lat:
                    zf = ref_lat[key]
                    r["latent_rel_ft"] = float((lat - zf).norm() / zf.norm())
                    if key in base_lat:
                        r["latent_rel_change"] = float((lat - zf).norm() / (base_lat[key] - zf).norm().clamp_min(1e-12))
            renders[key] = r
        for key, cs in calls.items():
            outs = replay(dit, cs, args.device)
            if name == "base":
                base_out[key] = outs
            if name in twins:
                twin_out.setdefault(name, {})[key] = outs
            rec[key] = probe_errors(outs, ref_out[key], base_out.get(key),
                                    twin_out.get(spec.get("twin"), {}).get(key))
        report["variants"][name] = {"kind": spec["kind"], "twin": spec.get("twin"), "renders": renders,
                                    "probe": rec, "seconds": time.time() - t0}
        (out / "report.json").write_text(json.dumps(report, indent=1))
        p = next(iter(rec.values()), {})
        print(f"[render] {name}: probe rel_ft {p.get('rel_ft', {}).get('mean', float('nan')):.4f}  "
              f"rel_change {p.get('rel_change', {}).get('mean', float('nan')):.4f}  "
              f"twin {p.get('rel_twin', {}).get('mean', float('nan')):.4f}  ({time.time() - t0:.0f} s)")
    write_markdown(report, out / "report.md")
    print(f"[render] report: {out / 'report.md'}")


def write_markdown(report: dict, path: Path):
    lines = [f"# Extraction checks: {Path(report['ckpt']).parent.name}", "",
             f"{report['steps']} steps, guidance {report['cfg_scale']}, {report['duration']} s, "
             f"{report['precision']}, {len(report['prompts'])} prompts x {len(report['seeds'])} seeds.", "",
             "Probe: the fine-tune's own DiT calls replayed through each variant. rel_change 0 = the fine-tune, "
             "1 = as far off as base. Twin: the weight-space variant the loader should reproduce.", "",
             "| variant | probe rel_change (early/mid/late) | probe rel_ft | twin | latent rel_change | "
             "peak | clip | >16 kHz |",
             "|---|---|---|---|---|---|---|---|"]

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return f"{float(np.mean(vals)):.3f}" if vals else "-"

    for name, v in report["variants"].items():
        pr = list(v["probe"].values())
        rc = [p.get("rel_change") for p in pr if p.get("rel_change")]
        rc_s = (f"{mean([x['mean'] for x in rc])} ({mean([x['early'] for x in rc])}/"
                f"{mean([x['mid'] for x in rc])}/{mean([x['late'] for x in rc])})") if rc else "-"
        rr = list(v["renders"].values())
        lines.append(f"| {name} | {rc_s} | {mean([p['rel_ft']['mean'] for p in pr])} | "
                     f"{mean([p['rel_twin']['mean'] for p in pr if p.get('rel_twin')])} | "
                     f"{mean([r.get('latent_rel_change') for r in rr])} | {mean([r['peak'] for r in rr])} | "
                     f"{mean([r['clip_frac'] for r in rr])} | {mean([r['hf16k_share'] for r in rr])} |")
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ckpt", required=True, type=Path, help="one full fine-tune Lightning checkpoint")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--stage", choices=("measure", "render", "all"), default="all")
    ap.add_argument("--weights", choices=("online", "ema"), default="online",
                    help="fine-tune weight set (online = what the July extraction read)")
    ap.add_argument("--targets-from", type=Path, default=xsvd.REFERENCE_DORA_CKPT,
                    help="a trained DoRA checkpoint whose wrapped modules are the targets (the extractor's 229)")
    ap.add_argument("--ranks", default="16,128")
    ap.add_argument("--variants", default=None, help="regex on variant names (fullft and base always run)")
    ap.add_argument("--prompt", action="append", dest="prompts", default=None)
    ap.add_argument("--seeds", default="11,23")
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg", type=float, default=6.0)
    ap.add_argument("--probe-renders", type=int, default=2, help="prompt/seed pairs replayed by the probe")
    ap.add_argument("--fp32", action="store_true", help="render in fp32 (default bf16, as the July renders)")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--svd-device", default="cpu")
    args = ap.parse_args()
    args.prompts = args.prompts or list(DEFAULT_PROMPTS)
    args.seeds = [int(s) for s in args.seeds.split(",")]
    ranks = sorted({int(r) for r in args.ranks.split(",")})
    os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
    if args.stage != "measure" and args.device == "cpu":
        raise SystemExit("the render stage needs a GPU (or pass --device explicitly)")

    xsvd.REFERENCE_DORA_CKPT = args.targets_from
    targets = xsvd.load_target_modules()
    print(f"[xft] {len(targets)} target modules from {args.targets_from.name}")
    base = xsvd.load_base_weights()
    raw = load_raw(args.ckpt)
    ft = split_state(raw, args.weights)
    gate = coverage_gate(base, ft, targets)
    print(f"[xft] {args.ckpt.name} ({args.weights}): {gate}")
    missing = [m for m in targets if m + ".weight" not in ft or m + ".weight" not in base]
    if missing:
        print(f"[xft] {len(missing)} targets missing on one side, left out: {missing[:3]}")
        targets = [m for m in targets if m not in missing]
    (args.out).mkdir(parents=True, exist_ok=True)
    (args.out / "run.json").write_text(json.dumps({**{k: str(v) for k, v in vars(args).items()},
                                                   "ranks": ranks, "targets": len(targets), **gate}, indent=1))

    run_measure(args, base, ft, raw, targets, args.out / "measure", ranks)
    trunc, adapters = run_svd(args, base, ft, targets, args.out / "measure", ranks)
    if args.stage in ("render", "all"):
        del raw
        gc.collect()
        run_render(args, base, ft, targets, trunc, adapters, args.out / "render", ranks)


if __name__ == "__main__":
    main()
