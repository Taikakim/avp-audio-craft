#!/usr/bin/env python3
"""extract_svd_adapters.py -- distill each fullft (whole-DiT fine-tune) checkpoint into
LoRA/DoRA adapters at ranks {16,64,128} via truncated SVD of the weight delta.

(Kim/CONTINUITY 2026-07-23/24, task tracked as #71.) Kim's hypothesis: FT-extracted
adapters may beat straight-trained DoRAs at matched rank (fp32+fullft is "just better,
period" -- does that transfer down to a small adapter?). Design verified against the
actual reconstruction code (stable_audio_3/models/lora/model.py:dora_forward) and a real
on-disk DoRA checkpoint, reviewed by CONTINUITY (2026-07-24 03:42, conditioner namespace).

Math (alpha=rank, the standard convention used everywhere in this codebase, so
scaling=alpha/rank=1):
  deltaW = W_fullft - W_base                              (per target module, 2D-flattened)
  U, S, Vh = svd(deltaW), sign-canonicalized (_canonicalize_svd_signs, reused from
             stable_audio_3.models.lora.model -- same convention the LoRA-XS bases use)
  B = U[:, :r] * sqrt(S[:r])         (fan_out, r)
  A = sqrt(S[:r])[:, None] * Vh[:r]  (r, fan_in)
  => B @ A is the best rank-r Frobenius approximation of deltaW (Eckart-Young).
  LoRA variant:  save A, B only.
  DoRA variant:  ALSO save magnitude = ||W_fullft||_row (row_dim=1) -- the row norms of
                 the ACTUAL fullft target, not W_base (this is extraction, not from-scratch
                 training init). dora_forward then reconstructs V=W0+B@A, normalizes V per
                 row, rescales by this magnitude -- so even though B@A is only a rank-r
                 approx of the direction, the MAGNITUDE is exact, which is the whole point
                 of the decomposition (Kim's hypothesis test).

Key namespace (both fullft and the base model use the SAME "model.X"/"conditioners.X"
space DoRA checkpoints are keyed in -- verified empirically, not assumed):
  DiT side:         fullft raw "diffusion.model.X"      -> strip "diffusion.model."  -> "model.X"
                     base:  StableAudioModel.model.model.state_dict()                -> "model.X"
  Conditioner side: fullft raw "diffusion.conditioner.X" -> strip "diffusion.conditioner." -> "conditioners.X"
                     base:  StableAudioModel.model.conditioner.state_dict()          -> "conditioners.X"

Target modules: the exact 229 module paths a real straight-trained dora16 checkpoint
covers (include=None/exclude=None in that checkpoint's own lora_config -- full uniform
coverage, no filtering), read live from a reference checkpoint so "matched-rank fairness"
never has to guess which modules count.

Gate (CONTINUITY's rec, mirrors the earlier fullft key-prefix bug that silently 0%-covered
everything): coverage must exceed 99% per checkpoint per side before trusting any SVD delta
from it. FAIL LOUD, do not silently skip.

Run: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE stable-audio-3/.venv/bin/python
     eval/extract_svd_adapters.py [--only-parent fullft_goa_t256] [--dry-run]
"""
import argparse
import json
import re
from pathlib import Path

import torch

RANKS = (16, 64, 128)
METHODS = ("lora", "dora-rows")
RUNS = Path("/run/media/kim/Mantu/sa3_lora_runs")
BRACKET = Path(__file__).resolve().parent / "rarity_bracket_manifest.json"
OUT_ROOT = RUNS / "xft_extracted"
REFERENCE_DORA_CKPT = RUNS / "dora16_avp_8ep" / "epoch=7-step=2392.ckpt"
COVERAGE_MIN = 0.99


def _fullft_labels():
    d = json.loads(BRACKET.read_text())
    return {k: v for k, v in d["models"].items() if k.startswith("fullft_")}


def _ckpt_path(label, spec):
    root = Path(spec["root"]) if "root" in spec else RUNS / label
    return root / spec["picks"][0]


def load_target_modules():
    """The exact module paths a real straight-trained dora16 checkpoint covers."""
    ck = torch.load(REFERENCE_DORA_CKPT, map_location="cpu", weights_only=False)
    sd = ck.get("state_dict", ck)
    mods = sorted({k.split(".parametrizations.")[0] for k in sd
                   if ".parametrizations.weight.0." in k})
    return mods


def load_base_weights():
    """medium-base weights in the same 'model.X'/'conditioners.X' namespace DoRA uses."""
    import os
    os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
    from stable_audio_3 import StableAudioModel
    m = StableAudioModel.from_pretrained("medium-base", device="cpu", model_half=False)
    out = {}
    out.update(m.model.model.state_dict())        # DiT side -> "model.X"
    out.update(m.model.conditioner.state_dict())   # conditioner side -> "conditioners.X"
    return out


def load_fullft_weights(ckpt_path):
    """fullft raw state_dict, remapped into the same 'model.X'/'conditioners.X' namespace."""
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    raw = ck.get("state_dict", ck)
    out = {}
    for k, v in raw.items():
        if k.startswith("diffusion.model."):
            out[k[len("diffusion.model."):]] = v
        elif k.startswith("diffusion.conditioner."):
            # raw key is "diffusion.conditioner.conditioners.X" -- stripping the prefix
            # alone already lands on "conditioners.X" (matching the base namespace);
            # do NOT also prepend "conditioners." (that double-prefixes to
            # "conditioners.conditioners.X" and silently 0%-covers -- caught by the gate).
            out[k[len("diffusion.conditioner."):]] = v
    return out


def _canonicalize_svd_signs(U, Vh):
    """Same convention as stable_audio_3.models.lora.model -- reused verbatim so extracted
    adapters and LoRA-XS bases agree on sign convention (not required for correctness here,
    but keeps behavior deterministic/reproducible the same way)."""
    max_abs_idx = U.abs().argmax(dim=0)
    signs = U[max_abs_idx, torch.arange(U.shape[1])].sign()
    signs[signs == 0] = 1
    return U * signs.unsqueeze(0), Vh * signs.unsqueeze(1)


def extract_module(base_w, fullft_w, rank):
    """SVD-decompose one module's weight delta. Returns (A, B, magnitude_1d)."""
    orig_shape = fullft_w.shape
    fan_out = orig_shape[0]
    base_2d = base_w.reshape(fan_out, -1).double()
    fullft_2d = fullft_w.reshape(fan_out, -1).double()
    delta = fullft_2d - base_2d
    U, S, Vh = torch.linalg.svd(delta, full_matrices=False)
    U, Vh = _canonicalize_svd_signs(U, Vh)
    r = min(rank, S.shape[0])
    sqrtS = S[:r].sqrt()
    B = (U[:, :r] * sqrtS.unsqueeze(0)).float().contiguous()          # (fan_out, r)
    A = (sqrtS.unsqueeze(1) * Vh[:r, :]).float().contiguous()          # (r, fan_in)
    magnitude = fullft_2d.norm(dim=1).float().contiguous()             # (fan_out,)  row norms of the TARGET
    return A, B, magnitude


def build_adapter(base_sd, fullft_sd, target_modules, rank, method):
    state_dict = {}
    n_hit = 0
    for mod in target_modules:
        wkey = mod + ".weight"
        if wkey not in base_sd or wkey not in fullft_sd:
            continue
        A, B, mag = extract_module(base_sd[wkey], fullft_sd[wkey], rank)
        prefix = f"{mod}.parametrizations.weight.0"
        state_dict[f"{prefix}.lora_A"] = A
        state_dict[f"{prefix}.lora_B"] = B
        if method == "dora-rows":
            state_dict[f"{prefix}.magnitude"] = mag
        n_hit += 1
    coverage = n_hit / len(target_modules)
    return state_dict, coverage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-parent", default=None, help="restrict to one fullft label")
    ap.add_argument("--dry-run", action="store_true", help="report coverage only, write nothing")
    args = ap.parse_args()

    from stable_audio_3.models.lora.utils import save_lora_safetensors

    target_modules = load_target_modules()
    print(f"[extract] {len(target_modules)} target modules (from reference dora16 checkpoint)")

    print("[extract] loading base model weights...")
    base_sd = load_base_weights()
    print(f"[extract] base: {len(base_sd)} weight tensors")

    fullft_labels = _fullft_labels()
    if args.only_parent:
        fullft_labels = {k: v for k, v in fullft_labels.items() if k == args.only_parent}
        if not fullft_labels:
            raise SystemExit(f"unknown --only-parent {args.only_parent!r}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    n_written = 0
    for parent, spec in sorted(fullft_labels.items()):
        ckpt_path = _ckpt_path(parent, spec)
        print(f"[extract] {parent}: loading {ckpt_path}")
        fullft_sd = load_fullft_weights(ckpt_path)

        # coverage gate -- FAIL LOUD, mirrors the earlier fullft key-prefix bug that
        # silently 0%-covered everything when the strip prefix was wrong.
        dit_targets = [m for m in target_modules if m.startswith("model.")]
        cond_targets = [m for m in target_modules if m.startswith("conditioners.")]
        dit_cov = sum(1 for m in dit_targets if m + ".weight" in fullft_sd) / max(1, len(dit_targets))
        cond_cov = sum(1 for m in cond_targets if m + ".weight" in fullft_sd) / max(1, len(cond_targets))
        print(f"[extract] {parent}: DiT coverage {dit_cov:.1%} ({len(dit_targets)} targets), "
              f"conditioner coverage {cond_cov:.1%} ({len(cond_targets)} targets)")
        assert dit_cov > COVERAGE_MIN, (
            f"{parent}: DiT-side coverage {dit_cov:.1%} <= {COVERAGE_MIN:.0%} -- "
            f"key-prefix mismatch, refusing to trust SVD deltas from this checkpoint")
        assert cond_cov > COVERAGE_MIN, (
            f"{parent}: conditioner-side coverage {cond_cov:.1%} <= {COVERAGE_MIN:.0%} -- "
            f"key-prefix mismatch, refusing to trust SVD deltas from this checkpoint")

        if args.dry_run:
            continue

        for rank in RANKS:
            for method in METHODS:
                state_dict, coverage = build_adapter(base_sd, fullft_sd, target_modules, rank, method)
                assert coverage > COVERAGE_MIN, f"{parent} r{rank} {method}: build coverage {coverage:.1%}"
                mtag = "lora" if method == "lora" else "dora"
                label = f"xft{mtag}{rank}_{parent}"
                out_dir = OUT_ROOT / label
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / "adapter.safetensors"
                lora_config = {"rank": rank, "alpha": float(rank), "adapter_type": method,
                               "dropout": 0.0, "include": None, "exclude": None,
                               "extracted_from": str(ckpt_path), "extraction_method": "svd-fullft-delta"}
                save_lora_safetensors(state_dict, lora_config, out_path)
                n_written += 1
                print(f"[extract]   wrote {label} ({len(state_dict)} tensors)")

    print(f"[extract] done, {n_written} adapters written to {OUT_ROOT}")


if __name__ == "__main__":
    main()
