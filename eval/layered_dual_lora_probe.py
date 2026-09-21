#!/usr/bin/env python
"""layered_dual_lora_probe.py — Kim 2026-09-16: three small, cheap probes answering
questions raised about dual_conditioned_sample.py's text+weight crossfade:

1. TEXT-EMBEDDING INTERPOLATION VALIDITY (the open theoretical question: "do we even
   know that morphing the T5 outputs are meaningful in the first place?"). Note this
   is genuinely untested by dual_conditioned_sample.py -- that script never interpolates
   T5-Gemma embeddings, it runs TWO FULL forward passes (one per whole prompt) and blends
   the resulting VELOCITIES. This probe does the thing Kim is actually asking about:
   literally interpolate the (batch,128,dim) T5-Gemma embedding tensors between two
   prompts and feed the SINGLE interpolated embedding through ONE forward pass at a
   handful of alpha values, fixed LoRA (no weight blending confound). T5Gemma pads to a
   fixed max_length=128 regardless of prompt length, so the tensors are shape-compatible
   -- but that only means interpolation is DEFINED, not that it's semantically meaningful
   (token position i in prompt A's tokenization has no reason to align with position i in
   B's). Whether the DiT's cross-attention still produces something coherent from a
   position-wise blend of two unrelated token sequences is an empirical question this
   answers cheaply (5 single-pass short clips) before investing further in text-morphing.

2. PER-LAYER, PER-ADAPTER STRENGTH STAGGER, NO TEXT MORPH ("could we try that per-layer
   stagger both ways (deep/high first), without the text morph"). Generalizes
   layered_lora_a2a.py's set_layered_strength (built for ramping ONE adapter 0->1 across
   many WINDOWS of a single track) to TWO adapters loaded simultaneously
   (LoRAParametrization carries its own .lora_index, confirmed in lora/model.py) blended
   by DEPTH within a SINGLE forward pass. IMPORTANT ARCHITECTURAL LIMIT, worth stating
   plainly: lora_strength is a scalar buffer per module -- uniform across the whole
   output SEQUENCE in one forward call. So this can vary the blend by DEPTH (which layer)
   but NOT by output TIME POSITION within that one call; getting position-dependent
   blending (position 0 = pure A, the far end = pure B) requires MULTIPLE forward passes
   with per-position velocity blending -- i.e. dual_conditioned_sample.py's approach. The
   two axes (depth-stagger vs. time-position-blend) don't compose within one pass, so
   this probe fixes t=0.5 (the exact crossover moment) and asks a narrower question:
   independent of *when* along the clip you're crossing, does the *order* in which layers
   adopt the new adapter (shallow/structure first vs. deep/timbre first) audibly change
   how the SAME 50/50-ish blend sounds. Both directions rendered, single shared prompt
   (prompt_a) throughout -- no text change at all, isolating the weight axis.

3. DUAL MORPH (text AND weight both crossfade) -- re-runs the EXISTING, already-tested
   dual_conditioned_sample.dual_conditioned_generate() at matched duration/seed/
   checkpoints/prompts for a clean side-by-side against 1 and 2, rather than building
   anything new.

Same two checkpoints/prompts as the original dual_conditioned_sample.py test throughout,
for direct comparability. No CFG in any of these (matches dual_conditioned_sample's v1
scope).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import re
import sys
from pathlib import Path

import torch

sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.sampling import build_schedule  # noqa: E402
from stable_audio_3.models.lora.model import LoRAParametrization, set_lora_strength  # noqa: E402
from dual_conditioned_sample import dual_conditioned_generate  # noqa: E402

CKPT_A = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"
CKPT_B = "/run/media/kim/Mantu/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt"
PROMPT_A = "2020s goa trance, melodic mood, 148 bpm"
PROMPT_B = "mid 90s goa trance, techno, space dark mood, 140 bpm"
DURATION = 24.0
STEPS = 24
SEED = 1234


def lora_layers_dual(model):
    """(param, lora_index, depth_frac shallow->deep) for every LoRA param of EITHER
    adapter -- generalizes layered_lora_a2a.lora_layers to multiple loaded adapters,
    keyed by LoRAParametrization.lora_index."""
    named = []
    for name, mod in model.model.model.named_modules():
        plist = getattr(getattr(mod, "parametrizations", None), "weight", None)
        if plist is None:
            continue
        m = re.search(r"(?:layers?|blocks?)\.(\d+)\b", name)
        depth = int(m.group(1)) if m else 0
        for p in plist:
            if isinstance(p, LoRAParametrization):
                named.append((p, p.lora_index, depth))
    depths = sorted({d for _, _, d in named})
    dmax = max(depths[-1], 1)
    return [(p, idx, d / dmax) for p, idx, d in named], len(depths)


def set_layered_dual_strength(layers, t, spread, reverse):
    """B's strength at depth d: clamp01(t*(1+spread) - d*spread) (shallow leads when
    spread>0); reverse=True flips d -> 1-d (deep leads instead). A's strength is the
    complement, so the two adapters always sum to 1 per layer."""
    for p, idx, df in layers:
        d = (1.0 - df) if reverse else df
        b_strength = min(1.0, max(0.0, t * (1.0 + spread) - d * spread))
        p.lora_strength.fill_(float(b_strength if idx == 1 else 1.0 - b_strength))


def euler_generate(model, cond, duration, steps, seed):
    """Plain single-pass Euler sampler -- no CFG, no dual forward (the LoRA-stagger and
    text-interp probes each only need ONE forward call per step)."""
    device = model.device
    sr = model.model.sample_rate
    ds_ratio = model.model.pretransform.downsampling_ratio
    frames = round(duration * sr / ds_ratio)
    torch.manual_seed(seed)
    x = torch.randn([1, model.model.io_channels, frames], device=device)
    sigmas = build_schedule(steps=steps, sigma_max=1.0, dist_shift=None,
                             fallback_seq_len=frames, include_endpoint=True, device=device)
    dit = model.model.model
    model_dtype = next(dit.parameters()).dtype
    for i in range(len(sigmas) - 1):
        t_curr, t_next = sigmas[i], sigmas[i + 1]
        with torch.no_grad():
            v = dit(x.to(model_dtype), t_curr.expand(x.shape[0]), **cond).float()
        x = x + (t_next - t_curr) * v
    with torch.inference_mode():
        audio = model.model.pretransform.decode(x.to(model_dtype))[0]
    return audio.float().cpu(), sr


def cond_for(model, prompt, duration, frames, device):
    conditioning = [{"prompt": prompt, "seconds_total": duration}]
    tensors = model.model.conditioner(conditioning, device)
    tensors["inpaint_mask"] = [torch.zeros(1, 1, frames, device=device)]
    tensors["inpaint_masked_input"] = [torch.zeros(1, model.model.io_channels, frames, device=device)]
    return tensors, model.model.get_conditioning_inputs(tensors)


def raw_prompt_embed(tensors):
    key = [k for k in tensors if k not in ("inpaint_mask", "inpaint_masked_input")][0]
    embed, mask = tensors[key]
    return embed, mask


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/layered_dual_probe")
    out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda"
    sr_expected = 44100
    ds_ratio_guess = 4096
    frames = round(DURATION * sr_expected / ds_ratio_guess)

    # ---- probe 1: text-embedding interpolation, single fixed adapter ----
    print("[load] model for text-interp probe (single adapter)", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device=device)
    model.load_lora([CKPT_A])
    frames = round(DURATION * model.model.sample_rate / model.model.pretransform.downsampling_ratio)
    tensors_a, cond_full_a = cond_for(model, PROMPT_A, DURATION, frames, device)
    tensors_b, _ = cond_for(model, PROMPT_B, DURATION, frames, device)
    embed_a, mask_a = raw_prompt_embed(tensors_a)
    embed_b, _ = raw_prompt_embed(tensors_b)
    assert embed_a.shape == embed_b.shape, f"shape mismatch {embed_a.shape} vs {embed_b.shape}"

    for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
        out_path = out_dir / f"textinterp_a{int(alpha*100):03d}.wav"
        if out_path.exists():
            print(f"[skip] {out_path.name}", flush=True)
            continue
        embed = (1 - alpha) * embed_a + alpha * embed_b
        cond = dict(cond_full_a)
        cond["cross_attn_cond"] = embed
        cond["cross_attn_mask"] = mask_a  # unused downstream (cross_attn_cond_mask nulled in dit.py)
        set_lora_strength(model.model, 1.0, lora_index=0)
        print(f"[gen] {out_path.name}", flush=True)
        audio, sr = euler_generate(model, cond, DURATION, STEPS, SEED)
        save_audio(str(out_path), audio, sr)
    del model
    torch.cuda.empty_cache()

    # ---- probe 2: per-layer per-adapter stagger, both directions, no text morph ----
    print("[load] model for layered-stagger probe (two adapters)", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device=device)
    model.load_lora([CKPT_A, CKPT_B])
    frames = round(DURATION * model.model.sample_rate / model.model.pretransform.downsampling_ratio)
    _, cond_a = cond_for(model, PROMPT_A, DURATION, frames, device)  # fixed prompt throughout
    layers, n_depths = lora_layers_dual(model)
    print(f"[layered] {len(layers)} LoRA params / {n_depths} depths", flush=True)

    for reverse, tag in ((False, "shallow_first"), (True, "deep_first")):
        out_path = out_dir / f"stagger_{tag}.wav"
        if out_path.exists():
            print(f"[skip] {out_path.name}", flush=True)
            continue
        set_layered_dual_strength(layers, t=0.5, spread=1.0, reverse=reverse)
        print(f"[gen] {out_path.name}", flush=True)
        audio, sr = euler_generate(model, cond_a, DURATION, STEPS, SEED)
        save_audio(str(out_path), audio, sr)
    del model
    torch.cuda.empty_cache()

    # ---- probe 3: dual morph (text AND weight crossfade) -- existing mechanism, matched params ----
    out_path = out_dir / "dualmorph_textandweight.wav"
    if not out_path.exists():
        print("[load] model for dual-morph comparison", flush=True)
        model = StableAudioModel.from_pretrained("medium-base", device=device)
        print(f"[gen] {out_path.name}", flush=True)
        audio, sr = dual_conditioned_generate(
            model, CKPT_A, CKPT_B, PROMPT_A, PROMPT_B,
            duration=DURATION, steps=STEPS, seed=SEED,
        )
        save_audio(str(out_path), audio, sr)
    else:
        print(f"[skip] {out_path.name}", flush=True)

    print("[done]", flush=True)


if __name__ == "__main__":
    main()
