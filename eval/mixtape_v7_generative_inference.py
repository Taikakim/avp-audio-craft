#!/usr/bin/env python
"""mixtape_v7_generative_inference.py
The fully realized Phase 2 custom dual-LoRA + LatCH Chroma steering ODE solver.
(Antigravity, 2026-10-08)

This module provides the core `dual_latch_guided_generate` function. 
It merges dynamic LoRA blending with LatCH Chroma steering within a custom
ODE solver loop.
"""

import torch
import sys
import numpy as np
from pathlib import Path

# Assume paths are set up
sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from stable_audio_3 import StableAudioModel
from stable_audio_3.models.lora.model import set_lora_strength
from stable_audio_3.inference.sampling import build_schedule
from stable_audio_3.models.latch import load_latch_from_checkpoint
from dual_conditioned_sample import _cond_inputs
from sa3_control.chroma_losses import chroma_loss_rung1

def _check_finite(t, name, step):
    """The live-adapter fault (training-findings 13e) returns NaN or ~1e11 at random on the ROCm box and
    nothing raises. Fail at the step it happens, not after 24 steps and a decode."""
    if not torch.isfinite(t).all() or float(t.abs().max()) > 1e4:
        raise FloatingPointError(f"{name} at step {step}: NaN/Inf or |x| > 1e4 (13e signature)")


def dual_latch_guided_generate(
    model: StableAudioModel, 
    ckpt_a: str, ckpt_b: str, 
    prompt_a: str, prompt_b: str, 
    duration: float, 
    chroma_target_tensor: torch.Tensor,
    chroma_head_path: str,
    steps: int = 24, 
    seed: int = 1234, 
    alpha_curve: torch.Tensor = None,
    latch_gain: float = 2048.0,
    latch_end_pct: float = 0.6,
    loss: str = "cosine",
    w_sec: float = 0.5,
    diag: dict = None,
):
    """
    Custom ODE solver bridging dual-LoRA velocity blending and LatCH gradients.
    
    Args:
        model: Loaded StableAudioModel
        ckpt_a/b: LoRA checkpoint paths
        prompt_a/b: Prompts for A and B
        duration: Window duration in seconds
        chroma_target_tensor: Target chroma [B, 12, T] aligned to the window
        chroma_head_path: Path to the LatCH pt file
        steps: Diffusion steps (default 24)
        seed: Random seed
        alpha_curve: [frames] tensor of interpolation weights
        latch_gain: Guidance scale for LatCH
        latch_end_pct: Stop guidance after this % of steps
        loss: "cosine" (the chroma heads' trained objective; phase-tolerant rung 1 from
            sa3_control.chroma_losses, window w_sec) or "mse" (the first version's loss)
        diag: optional dict; filled with "guidance_rel", one value per guided step =
            |latch_gain * grad| / |v_blend|. Near 0: guidance does nothing. Above ~1: it
            dominates the model. latch_gain=2048 was tuned for the canonical sampler's
            rho/mu normalization, NOT for this raw `v += gain * grad`, so read this first.

    Known gaps (review 2026-10-08): no classifier-free guidance (medium-base demos at cfg 2-7;
    dual_conditioned_sample.py documents the same limit), and `other` is generated from noise,
    not from an init/inpaint of the real clips (the proven route is chroma_morph_transitions.py).
    """
    device = model.device
    sr = model.model.sample_rate
    ds_ratio = model.model.pretransform.downsampling_ratio
    latent_fps = float(sr) / float(ds_ratio)
    frames = round(duration * latent_fps)
    
    # 1. Load LoRAs
    model.load_lora([ckpt_a, ckpt_b])
    
    # 2. Build T5-Gemma Conditioning
    cond_a = _cond_inputs(model, prompt_a, duration, device, frames)
    cond_b = _cond_inputs(model, prompt_b, duration, device, frames)
    
    # 3. Setup LatCH Head
    head = load_latch_from_checkpoint(chroma_head_path, device=device)
    head.eval()
    
    if alpha_curve is None:
        alpha_curve = torch.linspace(0, 1, frames, device=device)
    alpha = alpha_curve.view(1, 1, -1).to(device)
    
    # 4. Setup Initial Noise and Schedule
    torch.manual_seed(seed)
    x = torch.randn([1, model.model.io_channels, frames], device=device)
    sigmas = build_schedule(steps=steps, sigma_max=1.0, dist_shift=None, 
                            fallback_seq_len=frames, include_endpoint=True, device=device)
                            
    dit = model.model.model
    model_dtype = next(dit.parameters()).dtype

    # Ensure chroma target matches latent frames
    # Target may be provided at different resolution; interpolate if necessary
    if chroma_target_tensor.shape[-1] != frames:
        chroma_target_tensor = torch.nn.functional.interpolate(
            chroma_target_tensor, size=frames, mode='linear', align_corners=False
        )
    chroma_target_tensor = chroma_target_tensor.to(device)

    # 5. Core Dual-Pass + Guided ODE Loop
    for i in range(len(sigmas) - 1):
        t_curr = sigmas[i]
        t_next = sigmas[i + 1]
        t_tensor = t_curr.expand(x.shape[0])
        
        # === PASS A (LoRA A + Prompt A) ===
        set_lora_strength(model.model, 1.0, lora_index=0)
        set_lora_strength(model.model, 0.0, lora_index=1)
        with torch.no_grad():
            v_a = dit(x.to(model_dtype), t_tensor, **cond_a).float()
        _check_finite(v_a, "v_a", i)

        # === PASS B (LoRA B + Prompt B) ===
        set_lora_strength(model.model, 0.0, lora_index=0)
        set_lora_strength(model.model, 1.0, lora_index=1)
        with torch.no_grad():
            v_b = dit(x.to(model_dtype), t_tensor, **cond_b).float()
        _check_finite(v_b, "v_b", i)

        # === VELOCITY BLEND (per-frame lerp of the two adapters' velocities; not a LoRA-weight lerp) ===
        v_blend = (1.0 - alpha) * v_a + alpha * v_b
        
        # === LATCH GRADIENT GUIDANCE ===
        pct_complete = i / (len(sigmas) - 1)
        if pct_complete <= latch_end_pct:
            x_in = x.detach().requires_grad_(True)
            
            # Flow-matching x0 prediction: x0 = x - t_curr * v
            x0_pred = x_in - t_curr * v_blend
            
            # Forward pass through LatCH head
            features = head(x0_pred, t_tensor)
            
            # Loss against the chroma target. features / target are (B, C, T); the repo's
            # losses take (B, T, C).
            if loss == "cosine":
                step_loss = chroma_loss_rung1(features.transpose(1, 2), chroma_target_tensor.transpose(1, 2),
                                              latent_fps, w_sec=w_sec, metric="cosine")
            elif loss == "mse":
                step_loss = torch.nn.functional.mse_loss(features, chroma_target_tensor)
            else:
                raise ValueError(f"loss must be 'cosine' or 'mse', got {loss!r}")

            # Compute gradient
            grad = torch.autograd.grad(step_loss, x_in)[0]
            _check_finite(grad, "latch grad", i)

            # Apply guidance to velocity
            v_guided = v_blend + (latch_gain * grad)
            if diag is not None:
                diag.setdefault("guidance_rel", []).append(
                    float((latch_gain * grad).norm() / v_blend.norm().clamp_min(1e-12)))
                diag.setdefault("loss", []).append(float(step_loss))
        else:
            v_guided = v_blend
        
        # === ODE STEP ===
        dt = (t_next - t_curr)
        x = x + dt * v_guided
        
    with torch.inference_mode():
        audio = model.model.pretransform.decode(x.to(model_dtype))[0]
    return audio.float().cpu(), sr

if __name__ == "__main__":
    print("[mixtape_v7_generative_inference] Module loaded successfully.")
