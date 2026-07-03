"""Multi-adapter eval: DoRA + onset (FiLM/scalar) + style (fingerprint) conditioners
stacked on one SA3, with optional LatCH TFG guidance on top — the full multi-knob
instrument (weight-space composition; guidance is the sample-space 4th knob).

Provenance: drafted by Antigravity (Gemini), reviewed + fixed + LatCH-extended by
CONTINUITY 2026-07-04. Fixes vs the draft:
  - PE flags read from each ckpt's args (training default True; no more hardcode)
  - state-dict loads ASSERT full coverage (24 branches + conditioner) — no silent
    partial loads that leave adapters at random init
  - scalar_norm must come from the ckpt (the draft's fallback [7.219,1.424] was
    WRONG — trained values are [7.107,1.419]); hard-fail if absent
  - DoRA stays PARAMETRIZED by default (the run_gradio/eval_dora convention —
    same math, no 3GB merge cache); --merge-dora restores the bake+cache path
  - CFG null = zero TOKENS for both adapters — verified identical to training
    (train.py cfg-dropout masked_fill(0.0)); [cond, uncond] batch order verified
    against generate.py's documented convention
  - run_meta.json sidecar (MASTER §4 self-describing-outputs rule)

LatCH: --latch-head/--latch-value/--latch-gains pass through sam.generate's
latch_configs/latch_hparams (raw value; standardization + loss from head metadata;
fp16 keeps ~1/2 the fp32 authority -> operating gain ~512-1024 for energy heads).
NOTE: onset_envelope is a DEAD walker (perturbs, doesn't follow — 2026-07-03
calibration); use the energy family (rms_energy_mid/bass) for guidance.

Run in stable-audio-3/.venv (T5-Gemma lives there), with
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2.
"""

import argparse
import json
import os
import sys
from contextlib import contextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import librosa
import numpy as np
import torch
from torch import nn
import torch.nn.utils.parametrize as parametrize

from sa3_control.adapters import DecoupledControlAdapter
from sa3_control.audio_io import save_audio
from sa3_control.generate import build_conditioner
from sa3_control.inject import find_cross_attn


# --- Multi-Adapter Infrastructure ---

_MULTI_ACTIVE = {"pairs": None}

@contextmanager
def use_multi_control_context(pairs):
    """pairs: list of tuples (control_tokens, gain)"""
    _MULTI_ACTIVE["pairs"] = pairs
    try:
        yield
    finally:
        _MULTI_ACTIVE["pairs"] = None

def current_multi_control_context():
    return _MULTI_ACTIVE["pairs"]


class MultiControlledCrossAttention(nn.Module):
    """Drop-in wrapper for multiple control adapters on a single cross-attention module."""
    def __init__(self, base_attention: nn.Module, adapters: list):
        super().__init__()
        self.base_attention = base_attention
        self.adapters = nn.ModuleList(adapters)

    def forward(self, x, context=None, **kwargs):
        base = self.base_attention(x, context=context, **kwargs)
        pairs = current_multi_control_context()
        if pairs is not None:
            for i, (tokens, gain) in enumerate(pairs):
                if tokens is not None and gain != 0.0:
                    base = base + gain * self.adapters[i](x, self.base_attention, tokens)
        return base


def install_multi_adapters(sam, dims_and_pes):
    """dims_and_pes: list of (control_dim, position_encoding) per adapter branch."""
    targets = find_cross_attn(sam.model)
    if not targets:
        raise RuntimeError("no SA3 cross-attention modules found to wrap")
    wrappers = []
    for parent, attr, base in targets:
        dev = next(base.parameters()).device
        adapters = [DecoupledControlAdapter(base, dim, pe).to(device=dev) for dim, pe in dims_and_pes]
        w = MultiControlledCrossAttention(base, adapters).to(device=dev)
        setattr(parent, attr, w)
        wrappers.append(w)
    return wrappers


def load_multi_adapter_states(states, wrappers, cond_encs, names):
    """Load each adapter's state into its branch of every wrapper + its conditioner.
    ASSERTS full coverage: every wrapper must receive its branch, and the conditioner
    must load — a silent partial load leaves random-init adapters that generate
    garbage indistinguishable from 'stacking broke it'."""
    for adapter_idx, (state, name) in enumerate(zip(states, names)):
        loaded_branches = 0
        for w_idx, w in enumerate(wrappers):
            pfx = f"adapter.{w_idx}."
            sub = {k[len(pfx):]: v for k, v in state.items() if k.startswith(pfx)}
            if sub:
                w.adapters[adapter_idx].load_state_dict(sub)   # strict=True default
                loaded_branches += 1
        if loaded_branches != len(wrappers):
            raise RuntimeError(
                f"[{name}] adapter state covers {loaded_branches}/{len(wrappers)} "
                f"cross-attn branches — checkpoint/model mismatch, refusing to run")
        csub = {k[len("conditioner."):]: v for k, v in state.items() if k.startswith("conditioner.")}
        if not csub:
            raise RuntimeError(f"[{name}] no conditioner.* keys in checkpoint — refusing to run")
        cond_encs[adapter_idx].load_state_dict(csub)
        print(f"[load] {name}: {loaded_branches} branches + conditioner ok", flush=True)


def merge_and_unload_dora(sam):
    print("[merge] Merging DoRA weights and unloading parametrizations...", flush=True)
    count = 0
    for name, module in sam.model.named_modules():
        if hasattr(module, "parametrizations") and "weight" in module.parametrizations:
            parametrize.remove_parametrizations(module, "weight", leave_parametrized=True)
            count += 1
    print(f"[merge] merged {count} modules; DoRA baked into base weights.", flush=True)
    torch.cuda.empty_cache()


def onset_density(audio_t, sr):
    y = audio_t[0].float().cpu().numpy()
    if y.ndim > 1:
        y = y.mean(0)
    return len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr)


def load_checkpoint_flexible(path, device="cpu"):
    if path.endswith(".npz"):
        npz = np.load(path, allow_pickle=True)
        d = dict(npz)
        for k, v in d.items():
            if isinstance(v, np.ndarray):
                d[k] = v.item() if v.shape == () else torch.from_numpy(v).to(device)
        if "state" in d and isinstance(d["state"], dict):
            for k, v in d["state"].items():
                if isinstance(v, np.ndarray):
                    d["state"][k] = torch.from_numpy(v).to(device)
        return d
    return torch.load(path, map_location=device, weights_only=False)


def build_style_input(style_ck, reference_latent_path, device, dtype):
    """Fingerprint mode: build the (1, in_dim) vector from the reference's companion
    JSON (mirrors dataset._build_fingerprint; norms are the dataset defaults).
    audio_ref mode: load the VAE latent."""
    mode = style_ck.get("control_mode", "audio_ref")
    if mode != "fingerprint":
        x = torch.from_numpy(np.load(reference_latent_path)).to(device=device, dtype=dtype)
        return x.unsqueeze(0) if x.ndim == 2 else x, mode, None

    fp_in_dim = int(style_ck["fp_in_dim"])
    fp_variant = style_ck.get("fp_variant", "C")
    gv_raw = style_ck.get("genre_vocab", style_ck.get("args", {}).get("genre_vocab", ""))
    if isinstance(gv_raw, str) and os.path.isfile(gv_raw):
        gv = json.load(open(gv_raw))
        genre_names = gv["vocab"] if isinstance(gv, dict) and "vocab" in gv else gv
    elif isinstance(gv_raw, (list, np.ndarray)):
        genre_names = list(gv_raw)
    else:
        gv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genre_vocab.json")
        if not os.path.isfile(gv_path):
            raise RuntimeError("no genre vocab in ckpt and no genre_vocab.json fallback")
        gv = json.load(open(gv_path))
        genre_names = gv["vocab"] if isinstance(gv, dict) and "vocab" in gv else gv

    ref_json = reference_latent_path.replace(".npy", ".json")
    ref_meta = json.load(open(ref_json)) if os.path.isfile(ref_json) else {}
    if not ref_meta:
        print(f"[warn] no companion JSON at {ref_json}; zero fingerprint", flush=True)

    g = ref_meta.get("style_genre", {})
    vec = [float(g.get(name, 0.0)) for name in genre_names]
    vec.append(float(g.get("other", max(0.0, 1.0 - sum(vec)))))
    vec.append((float(ref_meta.get("release_year", 1990.0)) - 1990.0) / 30.0)  # dataset year_norm
    if fp_variant in ("A", "B"):
        vec.append((float(ref_meta.get("bpm_madmom", 140.0)) - 140.0) / 20.0)   # dataset bpm_norm
        vec.append((float(ref_meta.get("syncopation", 0.5)) - 0.5) / 0.25)      # dataset sync_norm
    while len(vec) < fp_in_dim:
        vec.append(0.0)
    vec = vec[:fp_in_dim]
    print(f"[init] fingerprint ({fp_variant}, dim={fp_in_dim}): {[f'{v:.3f}' for v in vec]}", flush=True)
    return torch.tensor([vec], device=device, dtype=dtype), mode, vec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dora-ckpt", type=str, required=True, help="DoRA checkpoint (loaded parametrized)")
    ap.add_argument("--onset-ckpt", type=str, required=True)
    ap.add_argument("--style-ckpt", type=str, required=True)
    ap.add_argument("--reference-latent", type=str, required=True,
                    help="reference .npy (fingerprint mode reads its companion .json)")
    ap.add_argument("--out-dir", type=str, required=True)
    ap.add_argument("--merge-dora", action="store_true",
                    help="bake DoRA into base weights + cache the merged state dict "
                         "(default: keep parametrized — the eval_dora/run_gradio convention)")

    ap.add_argument("--prompt", type=str, default="psychedelic goa trance")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--cfg", type=float, default=7.0)

    ap.add_argument("--densities", default="6,7,8,9,10")
    ap.add_argument("--onset-gains", default="1.0,2.0,3.0")
    ap.add_argument("--style-gains", default="1.0")

    # LatCH guidance (sample-space 4th knob). onset_envelope is a DEAD walker —
    # use the energy family. Gains: fp16 keeps ~1/2 fp32 authority; energy operating
    # point was 512 (fp32) -> try 512-1024 here.
    ap.add_argument("--latch-head", type=str, default="",
                    help="LatCH head ckpt (e.g. latch_sa3_rms_energy_mid_best.pt); empty = off")
    ap.add_argument("--latch-value", type=float, default=None,
                    help="RAW target value (standardized internally from head metadata)")
    ap.add_argument("--latch-gains", default="0",
                    help="comma list of rho=mu guidance strengths; 0 = guidance off for that cell")
    ap.add_argument("--latch-weight", type=float, default=1.0)
    ap.add_argument("--notes", default="", help="run purpose for run_meta.json")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Guidance backprop forces FlexAttention off (mask HOP); harmless when latch off.
    from stable_audio_3.models import transformer as _sa3_tf
    _sa3_tf.flex_attention_available = False
    _sa3_tf.flex_attention_compiled = None

    print("[init] loading base SA3 model...", flush=True)
    from stable_audio_3 import StableAudioModel
    sam = StableAudioModel.from_pretrained("medium-base", device=device)
    md = next(sam.model.model.parameters()).dtype
    sr = sam.model.sample_rate

    print(f"[init] loading DoRA (parametrized): {args.dora_ckpt}", flush=True)
    sam.load_lora([args.dora_ckpt])
    if args.merge_dora:
        merge_and_unload_dora(sam)

    print("[init] loading adapter checkpoints...", flush=True)
    onset_ck = load_checkpoint_flexible(args.onset_ckpt)
    style_ck = load_checkpoint_flexible(args.style_ckpt)

    if "scalar_norm" not in onset_ck:
        sys.exit("[fatal] onset ckpt has no scalar_norm — cannot map densities; refusing "
                 "to guess (the old fallback [7.219,1.424] was measurably wrong)")
    mean, std = [float(x) for x in onset_ck["scalar_norm"]]
    print(f"[init] onset scalar_norm: mean={mean:.4f} std={std:.4f}", flush=True)

    onset_args, style_args = onset_ck.get("args", {}), style_ck.get("args", {})
    onset_pe = bool(onset_args.get("position_encoding", True))   # training default True
    style_pe = bool(style_args.get("position_encoding", True))
    onset_dim = int(onset_args.get("control_dim", 768))
    style_dim = int(style_args.get("control_dim", 768))

    onset_enc = build_conditioner(onset_ck, device, md)
    style_enc = build_conditioner(style_ck, device, md)

    print(f"[init] installing multi-adapter wrappers (pe: onset={onset_pe} style={style_pe})...",
          flush=True)
    wrappers = install_multi_adapters(sam, [(onset_dim, onset_pe), (style_dim, style_pe)])
    load_multi_adapter_states([onset_ck["state"], style_ck["state"]], wrappers,
                              [onset_enc, style_enc], ["onset", "style"])

    for w in wrappers:
        for adapter in w.adapters:
            adapter.to(device=device, dtype=md)
    onset_enc.eval(); style_enc.eval()

    style_input, style_mode, fp_vec = build_style_input(
        style_ck, args.reference_latent, device, md)
    print(f"[init] style control mode: {style_mode}", flush=True)

    with torch.inference_mode():
        style_ctrl = style_enc(style_input)                      # (1, n_tokens, d)
    if args.cfg != 1.0:
        # CFG batch order [cond, uncond]; zero TOKENS = the trained null (train.py
        # cfg-dropout masks tokens to 0.0) — verified, do not change to encoder(zeros).
        style_ctrl = torch.cat([style_ctrl, torch.zeros_like(style_ctrl)], dim=0)

    latch_gains = [float(x) for x in args.latch_gains.split(",")]
    use_latch = bool(args.latch_head) and any(g > 0 for g in latch_gains)
    if use_latch and args.latch_value is None:
        sys.exit("[fatal] --latch-head set but no --latch-value (raw units)")

    def gen(onset_norm_val, onset_gain, style_gain, latch_gain):
        s = torch.tensor([onset_norm_val], device=device, dtype=md)
        with torch.inference_mode():
            onset_ctrl = onset_enc(s)
        if args.cfg != 1.0:
            onset_ctrl = torch.cat([onset_ctrl, torch.zeros_like(onset_ctrl)], dim=0)
        pairs = [(onset_ctrl, onset_gain), (style_ctrl, style_gain)]

        gkw = {}
        if latch_gain > 0:
            gkw["latch_configs"] = [{"model_path": args.latch_head, "kind": "constant",
                                     "value": args.latch_value, "weight": args.latch_weight}]
            gkw["latch_hparams"] = {"rho": latch_gain, "mu": latch_gain}
        with use_multi_control_context(pairs):
            # generate() is @inference_mode-decorated and internally escapes to
            # enable_grad for the latch branch (model.py ~407-427) — no outer ctx needed.
            return sam.generate(prompt=args.prompt, duration=args.duration,
                                steps=args.steps, cfg_scale=args.cfg, seed=args.seed,
                                sampler_type="euler", **gkw)

    densities = [float(d) for d in args.densities.split(",")]
    onset_gains = [float(g) for g in args.onset_gains.split(",")]
    style_gains = [float(sg) for sg in args.style_gains.split(",")]

    manifest = []
    total = len(densities) * len(onset_gains) * len(style_gains) * len(latch_gains)
    i = 0
    print(f"[run] {total} cells ...", flush=True)
    for lg in latch_gains:
        for sg in style_gains:
            for g in onset_gains:
                for draw in densities:
                    dn = (draw - mean) / std
                    ao = gen(dn, g, sg, lg)
                    od = onset_density(ao[0], sr)
                    fn = f"s{args.seed}_g{g:g}_d{draw:g}_styleg{sg:g}"
                    if lg > 0:
                        fn += f"_latch{lg:g}"
                    fn += ".wav"
                    save_audio(f"{args.out_dir}/{fn}", ao[0], sr)
                    manifest.append({"file": fn, "prompt": args.prompt, "seed": args.seed,
                                     "onset_gain": g, "style_gain": sg, "latch_gain": lg,
                                     "density_target": draw, "measured_density": round(od, 3)})
                    i += 1
                    print(f"  [{i}/{total}] {fn} meas={od:.2f}", flush=True)

    json.dump(manifest, open(f"{args.out_dir}/manifest.json", "w"), indent=1)
    # MASTER §4 self-describing-outputs sidecar (purpose + related files + ckpt ids)
    meta = {"purpose": args.notes or "multi-adapter (DoRA + onset + style) composition bracket"
                                    + (" + LatCH guidance" if use_latch else ""),
            "script": os.path.abspath(__file__),
            "checkpoints": {"dora": args.dora_ckpt, "onset": args.onset_ckpt,
                            "style": args.style_ckpt,
                            "latch_head": args.latch_head or None},
            "reference_latent": args.reference_latent,
            "style_fingerprint": fp_vec,
            "eval": {"prompt": args.prompt, "seed": args.seed, "steps": args.steps,
                     "cfg": args.cfg, "duration": args.duration,
                     "densities": densities, "onset_gains": onset_gains,
                     "style_gains": style_gains, "latch_gains": latch_gains,
                     "latch_value": args.latch_value,
                     "scalar_norm": [mean, std], "dora_parametrized": not args.merge_dora},
            "method": "GPU torch multi-adapter stack; CFG null = zero tokens; "
                      "NOT comparable to the CPU 24-step canonical tables"}
    json.dump(meta, open(f"{args.out_dir}/run_meta.json", "w"), indent=2)
    print(f"[done] wrote {len(manifest)} -> {args.out_dir}/manifest.json (+ run_meta.json)", flush=True)


if __name__ == "__main__":
    main()
