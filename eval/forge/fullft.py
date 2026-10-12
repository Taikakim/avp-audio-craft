"""Full-finetune checkpoints in the render server (2026-10-09).

A full finetune replaces the whole DiT, so it cannot go through `load_lora`. This is the
model-matrix renderer's tested loader (SAO eval/model_matrix_gen.py, the `is_fullft` branch),
lifted into a function:

- ONLINE weights by default (Kim 2026-09-11, same default as the matrix). `weights="ema"` takes
  the `diffusion_ema.ema_model.*` set and refuses a checkpoint that has none.
- LUMI checkpoints prefix DiT params `diffusion.model.model.X`; the target expects `model.X`.
  Both prefixes are tried and the one that matches more keys wins.
- FAIL LOUD below 99% coverage: a part-loaded model would quietly render base weights.
- Conditioner tensors are loaded when present (merged adapter soups carry them).

Which checkpoints are full finetunes comes from eval/model_db.py (family "fullft"), whose
checkpoint probe is the census's ground truth; see `explorer_render_server.ckpt_family`.
"""
from __future__ import annotations

import math

import torch

DIT_PREFIXES = ("diffusion.model.", "model.")
EMA_PREFIX = "diffusion_ema.ema_model."


def _state_dict(path):
    ck = torch.load(str(path), map_location="cpu", weights_only=False)
    return ck.get("state_dict", ck) if isinstance(ck, dict) else ck


def ema_info(sd):
    """How far the EMA shadow travelled from its start (matrix `ema_convergence`, beta 0.9999)."""
    step = sd.get("diffusion_ema.ema_step")
    if step is None:
        return None
    r = int(step) / (math.log(2) / (1.0 - 0.9999))
    return {"ema_step": int(step), "halflives": r, "residual_init": 0.5 ** r, "converged": r >= 3.0}


def load_fullft(model, path, weights="online", sd=None, log=print):
    """Load a full-FT checkpoint over `model` (a StableAudioModel). Returns a summary dict."""
    sd_raw = sd if sd is not None else _state_dict(path)
    tgt = model.model.model                      # the ConditionedDiffusionModelWrapper's DiT side
    params, buffers = dict(tgt.named_parameters()), dict(tgt.named_buffers())
    tgt_keys = set(params) | set(buffers)
    has_ema = any(k.startswith(EMA_PREFIX) for k in sd_raw)
    if weights == "ema" and not has_ema:
        raise ValueError(f"weights=ema but {path} carries no EMA tensors")
    prefixes = (EMA_PREFIX,) if weights == "ema" else DIT_PREFIXES
    sd = max(({(k[len(p):] if k.startswith(p) else k): v for k, v in sd_raw.items()} for p in prefixes),
             key=lambda d: sum(1 for k in d if k in tgt_keys))
    dtype = next(tgt.parameters()).dtype
    missing, _ = tgt.load_state_dict({k: v.to(dtype) for k, v in sd.items() if k in tgt_keys}, strict=False)
    cov = 1 - len(missing) / max(1, len(tgt.state_dict()))
    if cov <= 0.99:
        raise ValueError(f"full-FT checkpoint covers only {cov:.1%} of the model; refusing to render "
                         f"a part-loaded model ({len(missing)} missing, e.g. {list(missing)[:3]})")
    csd = {k[len("conditioner."):]: v for k, v in sd_raw.items() if k.startswith("conditioner.")}
    if csd:
        ctgt = model.model.conditioner
        cparams = dict(ctgt.named_parameters())
        unknown = [k for k in csd if k not in cparams]
        if unknown:
            raise ValueError(f"full-FT conditioner keys not in the model: {unknown[:3]}")
        ctgt.load_state_dict({k: v.to(cparams[k].dtype) for k, v in csd.items()}, strict=False)
    info = ema_info(sd_raw)
    out = {"weights": weights, "coverage": cov, "has_ema": has_ema, "conditioner": len(csd), "ema": info}
    msg = f"[fullft] {weights} weights, coverage {cov:.1%}, +{len(csd)} conditioner"
    if weights == "ema" and info and not info["converged"]:
        msg += (f"; EMA is still {info['residual_init']:.0%} its STARTING weights "
                f"({info['halflives']:.2f} half-lives): mostly the run's start, not what it learned")
    log(msg)
    return out
