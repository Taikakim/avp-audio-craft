"""Composed control + LatCH guidance over the CONTROL-DiT ONNX (CPU).

The "easier terrain" experiment (spec: docs/superpowers/specs/
2026-07-03-composed-control-latch-sweep.md): weight-space control (a trained adapter
baked into the control-DiT graph, driven by control tokens + gain) and sample-space
steering (LatCH TFG guidance) running SIMULTANEOUSLY, so the sweep can measure whether
guidance walks farther on terrain the adapter has already reshaped.

This module is ADDITIVE — a faithful derivative of ``sa3_latch_onnx.
generate_z0_latch_guided`` (schedule, APG CFG, two-stage variance+mean guidance,
per-guide windows, RNG order: all identical) with exactly one change: the DiT forward
carries the control inputs (``control_tokens``, ``gain``) of the control-DiT export,
cond passes receiving ``cond_tok`` and uncond passes ``zero_tok`` — the same routing
``sa3_control_onnx.generate_z0`` / control_eval_server use. Nothing in the two parent
gen-cores is modified.

numpy + torch only at import; the ORT session is passed in (importable from any venv).
"""
from __future__ import annotations

import time

import numpy as np
import torch

from sa3_latch_onnx import latch_schedule, make_criterion, apg_cfg_velocity  # noqa: E402
from sa3_control_onnx import LATENT_DIM, LOCAL_ADD_DIM  # noqa: E402


def build_latch_guides(latch_spec: dict, frames: int, load_head=None, head_cache=None):
    """Job-dict -> (guides, rho, mu, provenance) adapter for the composed eval path.

    latch_spec (the job's "latch" object): head_ckpt + target_raw required;
    optional weight (1.0), loss_type (head metadata), rho/mu (512.0 — the
    onset_envelope operating point, to be confirmed by the calibration probe),
    start_pct/end_pct (sampler defaults). target_raw is in RAW feature units;
    standardization to the head's output space happens here via make_latch_target.
    load_head is injectable for tests; head_cache (dict) makes repeat jobs free.
    """
    from sa3_latch_onnx import load_latch_head, make_latch_target

    load_head = load_head or load_latch_head
    ckpt = latch_spec["head_ckpt"]
    if head_cache is not None and ckpt in head_cache:
        head, metadata = head_cache[ckpt]
    else:
        head, metadata = load_head(ckpt)
        if head_cache is not None:
            head_cache[ckpt] = (head, metadata)

    raw = float(latch_spec["target_raw"])
    target = make_latch_target(raw, metadata, frames)
    loss_type = latch_spec.get("loss_type") or (
        metadata.get("loss_type", "mse") if hasattr(metadata, "get") else "mse")
    guide = {"head": head, "target": target, "weight": float(latch_spec.get("weight", 1.0)),
             "loss_type": loss_type,
             "huber_beta": (metadata.get("huber_beta") or 1.0) if hasattr(metadata, "get") else 1.0}
    for k in ("start_pct", "end_pct"):
        if k in latch_spec:
            guide[k] = float(latch_spec[k])

    rho = float(latch_spec.get("rho", 512.0))
    mu = float(latch_spec.get("mu", 512.0))
    prov = {"head_ckpt": str(ckpt), "target_raw": raw,
            "target_std": float(target.flatten()[0]), "rho": rho, "mu": mu,
            "weight": guide["weight"], "loss_type": loss_type}
    return [guide], rho, mu, prov


def generate_z0_control_latch_guided(
    dit_session,
    *,
    cond,
    uncond,
    cond_tok,
    zero_tok,
    gain: float,
    guides,
    frames: int,
    steps: int = 24,
    cfg_scale: float = 6.0,
    seed: int = 1234,
    rho: float = 64.0,
    mu: float = 64.0,
    gamma: float = 0.3,
    n_iter: int = 4,
    start_pct: float = 0.4,
    end_pct: float = 1.0,
):
    """LatCH-guided z0 over the CONTROL DiT ONNX. See module docstring; the guide-dict
    schema and all guidance math match generate_z0_latch_guided exactly."""
    c_cross, c_mask, c_glob = cond
    u_cross, u_mask, u_glob = uncond
    T = int(frames)
    b = 1
    local_add = np.zeros((1, LOCAL_ADD_DIM, T), np.float32)
    gain_arr = np.array([gain], np.float32)
    cond_tok = np.asarray(cond_tok, np.float32)
    zero_tok = np.asarray(zero_tok, np.float32)

    sigmas = latch_schedule(steps)
    num_steps = sigmas.shape[-1] - 1
    sig_np = sigmas.numpy().astype(np.float32)
    alpha = (1.0 - sigmas[:-1]).clamp(min=0.0)
    sum_alphas = float(alpha.sum().clamp(min=1e-8))

    for g in guides:
        g["_start"] = int(num_steps * g.get("start_pct", start_pct))
        g["_end"] = int(num_steps * g.get("end_pct", end_pct))
        g["_criterion"] = (g["criterion"] if g.get("criterion") is not None
                           else make_criterion(g.get("loss_type", "mse"),
                                               g.get("huber_beta", 1.0)))

    torch.manual_seed(seed)
    x = torch.randn(1, LATENT_DIM, T, dtype=torch.float32).numpy().astype(np.float32)

    def dit_v(cross1, mask1, glob1, t_cur, ctrl_tok):
        """Control-DiT forward: the ONE divergence from the plain-DiT parent."""
        return dit_session.run(None, {
            "x": x,
            "t": np.full((1,), t_cur, np.float32),
            "cross_attn_cond": cross1[None],
            "cross_attn_cond_mask": mask1[None],
            "global_embed": glob1[None],
            "local_add_cond": local_add,
            "control_tokens": ctrl_tok,
            "gain": gain_arr,
        })[0].astype(np.float32)

    t_loop = time.time()
    for i in range(num_steps):
        t_cur = float(sig_np[i])
        t_prev = float(sig_np[i + 1])
        s_t = float(alpha[i]) / sum_alphas
        rho_t = rho * s_t
        mu_t = mu * s_t
        active_guides = [g for g in guides if g["_start"] <= i < g["_end"]]

        # (A) variance guidance on x at t_cur
        if active_guides and rho_t > 0.0:
            with torch.enable_grad():
                xt = torch.tensor(x, dtype=torch.float32, requires_grad=True)
                t_ten = torch.full((b,), t_cur, dtype=torch.float32)
                loss = sum(g["weight"] * g["_criterion"](g["head"](xt, t_ten), g["target"])
                           for g in active_guides)
                grad = torch.autograd.grad(loss, xt)[0]
            x = (xt - rho_t * grad).detach().numpy().astype(np.float32)

        # (B) control-DiT forward + APG CFG; cond->cond_tok, uncond->zero_tok
        v_cond = dit_v(c_cross, c_mask, c_glob, t_cur, cond_tok)
        if cfg_scale == 1.0:
            v = v_cond
        else:
            v_unc = dit_v(u_cross, u_mask, u_glob, t_cur, zero_tok)
            v = apg_cfg_velocity(x, v_cond, v_unc, t_cur, cfg_scale)
        z0 = x - t_cur * v

        # (C) mean guidance on the clean estimate
        if active_guides and mu_t > 0.0:
            with torch.enable_grad():
                z0t = torch.tensor(z0, dtype=torch.float32)
                t0 = torch.zeros(b, dtype=torch.float32)
                for _ in range(n_iter):
                    z0t = z0t.detach().requires_grad_(True)
                    z_in = z0t + gamma * torch.randn_like(z0t) if gamma > 0 else z0t
                    loss = sum(g["weight"] * g["_criterion"](g["head"](z_in, t0), g["target"])
                               for g in active_guides)
                    grad = torch.autograd.grad(loss, z0t)[0]
                    z0t = (z0t - mu_t * grad).detach()
            z0 = z0t.numpy().astype(np.float32)

        # (D) Euler update from the (possibly guided) clean estimate
        d = (x - z0) / max(t_cur, 1e-6)
        x = (x + d * (t_prev - t_cur)).astype(np.float32)

    return {"z0": x.astype(np.float32), "dit_loop_s": time.time() - t_loop}
