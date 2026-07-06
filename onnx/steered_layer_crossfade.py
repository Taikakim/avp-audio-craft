"""Layer-staggered ACTIVATION crossfade between two seeds (Kim's longform idea).

Two seeds share the same weights, so what differs is the per-block activations —
the neuron firings as each seed denoises. This morphs seed A into seed B by
blending their activations block-by-block, staggered so the TOP blocks (late,
surface) cross over first and the bottom (early, structure) last — a "rewire the
top of the brain first" transition rather than an audio crossfade.

v1 (this file): a FIXED per-block blend schedule for a single hybrid render — the
"is there anything to this" test. If the hybrids come out coherent (not mushy),
staggered_alpha(t) gives the time-varying schedule for the actual longform wipe.

Pure schedule/blend logic is tested (test_layer_crossfade.py); the batched-two-seed
generation with per-block hooks is the GPU integration (run to smoke-test).
"""
from __future__ import annotations

import numpy as np


# ------------------------------------------------------------------ schedules (pure)

def block_alphas(n_blocks, mode="linear", strength=1.0, level=0.5):
    """Per-block blend weight in [0,1] (0 = keep A, 1 = take B). Block index runs
    0 (early/structure) .. n-1 (late/surface).
      linear  — even ramp early->late
      top     — late blocks toward B (early stay A); strength<1 sharpens to the top
      bottom  — mirror of top (early toward B, late stay A)
      uniform — constant `level` everywhere
    """
    base = np.linspace(0.0, 1.0, n_blocks)
    if mode == "linear":
        a = base
    elif mode == "top":
        a = base ** (1.0 / max(strength, 1e-3))
    elif mode == "bottom":
        a = (base ** (1.0 / max(strength, 1e-3)))[::-1]
    elif mode == "uniform":
        a = np.full(n_blocks, float(level))
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return list(map(float, a))


def staggered_alpha(n_blocks, t, window=0.5):
    """Time-varying schedule for the longform wipe: at transition-time t in [0,1],
    per-block blend weight, staggered so the top block crosses over first. Each
    block i ramps over [start_i, start_i+window]; start_i decreases with block
    index (top-first). t=0 -> all 0, t=1 -> all 1."""
    out = []
    for i in range(n_blocks):
        start = (n_blocks - 1 - i) / (n_blocks - 1) * (1.0 - window) if n_blocks > 1 else 0.0
        out.append(float(np.clip((t - start) / window, 0.0, 1.0)))
    return out


def blend_activations(A, B, alpha):
    """Lerp two activation tensors: (1-alpha)*A + alpha*B."""
    return A * (1.0 - alpha) + B * alpha


# ------------------------------------------------------------------ GPU generation

def find_blocks(module):
    """Locate the transformer-block ModuleList (children have self_attn)."""
    import torch.nn as nn
    for m in module.modules():
        if isinstance(m, nn.ModuleList) and len(m) > 1 and hasattr(m[0], "self_attn"):
            return m
    raise RuntimeError("could not locate transformer blocks (self_attn ModuleList)")


def install_crossfade_hooks(dit, alphas):
    """Forward-hook each transformer block so its output morphs seed A toward
    seed B by alphas[block_ix]. Returns hook handles (remove after generation).

    Batch layout during CFG is [cond_A, cond_B, uncond_A, uncond_B] (batch_size=2);
    without CFG it's [A, B]. So seed-A slots are {0, N/2} and seed-B slots {1, N/2+1}
    — blend A slots toward their B partners; B stays pure for reference. The blend
    compounds down the stack: high alpha on late blocks + low on early = A's
    structure with B's surface.
    """
    blocks = find_blocks(dit)
    handles = []

    def make_hook(ix):
        a = float(alphas[ix])
        def hook(module, inp, out):
            if a <= 0.0:
                return out
            x = out[0] if isinstance(out, tuple) else out
            n = x.shape[0]
            half = n // 2
            x = x.clone()
            x[0] = blend_activations(x[0], x[1], a)          # cond: A <- B
            if n > 2:
                x[half] = blend_activations(x[half], x[half + 1], a)  # uncond: A <- B
            return (x,) + out[1:] if isinstance(out, tuple) else x
        return hook

    for ix in range(len(blocks)):
        handles.append(blocks[ix].register_forward_hook(make_hook(ix)))
    return handles


def remove_hooks(handles):
    for h in handles:
        h.remove()


# ------------------------------------------------------------------ driver

def run_crossfade(sam, prompt, seed, schedules, cfg, steps, duration, out_dir, sr):
    """Render pure-A, pure-B (no hooks) + one hybrid per schedule. batch_size=2
    seeds A/B from one manual seed; same seed across all so A/B/hybrids compare."""
    import os, json, numpy as np, torch
    from sa3_control.audio_io import save_audio
    os.makedirs(out_dir, exist_ok=True)
    n_blocks = len(find_blocks(sam.dit))

    def gen():
        with torch.inference_mode():
            return sam.generate(prompt=prompt, batch_size=2, seed=seed,
                                cfg_scale=cfg, steps=steps, duration=duration,
                                sampler_type="euler")

    manifest = {"prompt": prompt, "seed": seed, "cfg": cfg, "steps": steps,
                "duration": duration, "n_blocks": n_blocks, "renders": []}
    ref = gen()
    for tag, idx in (("A_pure", 0), ("B_pure", 1)):
        save_audio(f"{out_dir}/{tag}.wav", ref[idx], sr)
        manifest["renders"].append({"file": f"{tag}.wav", "kind": tag})
    print(f"[ref] A_pure, B_pure saved", flush=True)

    for name, alphas in schedules:
        handles = install_crossfade_hooks(sam.dit, alphas)
        try:
            hy = gen()
        finally:
            remove_hooks(handles)
        save_audio(f"{out_dir}/hybrid_{name}.wav", hy[0], sr)
        # distinctness vs pure-A (sanity: the blend actually changed something)
        d = float(np.sqrt(np.mean((hy[0].cpu().numpy() - ref[0].cpu().numpy()) ** 2)))
        manifest["renders"].append({"file": f"hybrid_{name}.wav", "kind": name,
                                    "alphas": [round(a, 3) for a in alphas],
                                    "rms_diff_vs_A": round(d, 5)})
        print(f"[hybrid] {name}: rms_diff_vs_A={d:.5f}", flush=True)

    json.dump(manifest, open(f"{out_dir}/run_meta.json", "w"), indent=2)
    print(f"[done] -> {out_dir}", flush=True)


def default_schedules(n_blocks):
    return [
        ("top_sharp",  block_alphas(n_blocks, "top", strength=0.4)),    # only late blocks -> B
        ("top_linear", block_alphas(n_blocks, "linear")),               # even ramp
        ("bottom",     block_alphas(n_blocks, "bottom", strength=0.4)), # only early blocks -> B
        ("uniform50",  block_alphas(n_blocks, "uniform", level=0.5)),   # flat 50/50
    ]
