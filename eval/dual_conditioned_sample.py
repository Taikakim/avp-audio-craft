#!/usr/bin/env python
"""dual_conditioned_sample.py — Kim 2026-09-15: a reusable module for
generating ONE clip whose TEXT conditioning and LoRA weights blend
continuously from (prompt_a, checkpoint_a) to (prompt_b, checkpoint_b)
across the timeline, rather than switching abruptly.

Mechanism: both LoRAs loaded into ONE resident model (rank need not match --
LoRA deltas always project back to the frozen base's full weight shape
regardless of internal rank, so two adapters compose/toggle freely). At each
Euler step: set_lora_strength(A=1,B=0), forward with prompt A's conditioning
-> v_a; set_lora_strength(A=0,B=1), forward with prompt B's conditioning ->
v_b; blend v = (1-alpha)*v_a + alpha*v_b, where alpha is a per-LATENT-FRAME
vector ramping along the TIME axis (not across steps) -- so position 0 of
the clip is fully "A" and the end is fully "B", continuously in between.
2x compute per step (two forward passes), not 2x VRAM (one resident model).

SCOPE OF THIS FIRST VERSION: no classifier-free guidance (cfg_scale=1
behavior only -- reimplementing CFG batching/rescale_cfg/apg correctly from
scratch was judged higher-risk than shipping a working un-guided version
first), no chroma or HF guidance heads yet. Both are addable once this core
blend is validated by ear.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import sys
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/control")
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.models.lora.model import set_lora_strength  # noqa: E402
from stable_audio_3.inference.sampling import build_schedule  # noqa: E402


def _cond_inputs(model, prompt, seconds_total, device, frames):
    conditioning = [{"prompt": prompt, "seconds_total": seconds_total}]
    tensors = model.model.conditioner(conditioning, device)
    # generate() always injects these two before get_conditioning_inputs (local_add_cond
    # = inpaint_mask + masked_input, projected WITH BIAS -- None != zeros); for a plain
    # text2audio call outside generate(), supply the "no inpainting" zeros ourselves.
    # mask=0 (not 1) is "generate everything" -- matches generate()'s own default
    # (torch.zeros(...)) when no inpaint_audio/inpaint_mask is given at all.
    tensors["inpaint_mask"] = [torch.zeros(1, 1, frames, device=device)]
    tensors["inpaint_masked_input"] = [torch.zeros(1, model.model.io_channels, frames, device=device)]
    return model.model.get_conditioning_inputs(tensors)


def dual_conditioned_generate(model, ckpt_a, ckpt_b, prompt_a, prompt_b,
                               duration, steps=24, seed=1234, alpha_curve=None):
    """Generate one clip blending (prompt_a, ckpt_a) -> (prompt_b, ckpt_b).

    alpha_curve: optional 1D torch tensor of length `frames` in [0,1]; default
    is a plain linear ramp across the whole clip (position 0 = pure A, end =
    pure B). Returns (audio_tensor[C,N], sample_rate).
    """
    device = model.device
    sr = model.model.sample_rate
    ds_ratio = model.model.pretransform.downsampling_ratio
    latent_fps = float(sr) / float(ds_ratio)
    frames = round(duration * latent_fps)
    audio_sample_size = frames * ds_ratio

    model.load_lora([ckpt_a, ckpt_b])

    cond_a = _cond_inputs(model, prompt_a, duration, device, frames)
    cond_b = _cond_inputs(model, prompt_b, duration, device, frames)

    if alpha_curve is None:
        alpha_curve = torch.linspace(0, 1, frames, device=device)
    alpha = alpha_curve.view(1, 1, -1).to(device)

    torch.manual_seed(seed)
    x = torch.randn([1, model.model.io_channels, frames], device=device)
    sigmas = build_schedule(steps=steps, sigma_max=1.0, dist_shift=None,
                             fallback_seq_len=frames, include_endpoint=True, device=device)

    dit = model.model.model
    model_dtype = next(dit.parameters()).dtype
    for i in range(len(sigmas) - 1):
        t_curr = sigmas[i]
        t_next = sigmas[i + 1]
        t_tensor = t_curr.expand(x.shape[0])

        set_lora_strength(model.model, 1.0, lora_index=0)
        set_lora_strength(model.model, 0.0, lora_index=1)
        with torch.no_grad():
            v_a = dit(x.to(model_dtype), t_tensor, **cond_a).float()

        set_lora_strength(model.model, 0.0, lora_index=0)
        set_lora_strength(model.model, 1.0, lora_index=1)
        with torch.no_grad():
            v_b = dit(x.to(model_dtype), t_tensor, **cond_b).float()

        v = (1.0 - alpha) * v_a + alpha * v_b
        dt = (t_next - t_curr)
        x = x + dt * v

    with torch.inference_mode():
        audio = model.model.pretransform.decode(x.to(model_dtype))[0]
    return audio.float().cpu(), sr


if __name__ == "__main__":
    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    audio, sr = dual_conditioned_generate(
        model,
        ckpt_a="/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt",
        ckpt_b="/run/media/kim/Mantu/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt",
        prompt_a="2020s goa trance, melodic mood, 148 bpm",
        prompt_b="mid 90s goa trance, techno, space dark mood, 140 bpm",
        duration=60.0, steps=24, seed=1234,
    )
    out_path = "/tmp/claude-1000/-home-kim-Projects-SAO-stable-audio-3/cd7a9ba8-7c77-4763-a269-4b41c0eb857d/scratchpad/dual_cond_test.wav"
    save_audio(out_path, audio, sr)
    print(f"[done] wrote {out_path}", flush=True)
