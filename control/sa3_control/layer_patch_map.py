#!/usr/bin/env python3
"""
layer_patch_map.py -- causal per-(block, module) attribute localization on SA3 medium.

The Axis-1 LOCALIZER for relevance-routed DoRA (docs/research-brief-relevance-routed-dora.md
+ W's rigor review): TADA-style activation patching (arXiv 2602.11910) extended past
cross-attention to ALL THREE module types (self_attn / cross_attn / ff), scored with OUR
measurable MIR meters instead of text-audio similarity. Answers: WHICH of the 24 DiT
blocks (and which module type) causally carries each controllable attribute.

Method, per (concept, prompt-pair, seed):
  A  = generate with the CONCEPT prompt, caching every module's output per step (cond
       half of the CFG batch only -- dit.py batches [cond, uncond] on dim 0).
  B  = generate with the COUNTERFACTUAL prompt (baseline, no patch).
  P(l,m) = counterfactual generation with module (l,m)'s cond-half output REPLACED by
       A's cache at every step. Impact I = (meter(P)-meter(B)) / (meter(A)-meter(B)),
       i.e. how much of the attribute shift this single site causally recovers.

Design notes baked in (don't re-derive):
  * Localization informs SOFT rank allocation only -- TADA showed hard-confining weight
    adapters to the functional layers HURTS (-21% AUC). This map routes rank, not masks.
  * Meters are target-aware (onset rate / centroid / bass ratio / flatness), NOT the RF
    loss -- RF-Fisher measures reconstruction relevance, deaf to control (rigor review).
  * medium-base, euler, fixed seed -> deterministic; same init noise for A/B/P by seed.

Run (SA3 venv, GPU; ~1800 gens full grid, resumable):
  ../.venv/bin/python layer_patch_map.py --out /run/media/kim/Mantu/sa3_control_runs/layer_map_2026-07-10 \
      [--smoke] [--concepts onset_density,brightness] [--pairs 3] [--seeds 2]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # control/
import numpy as np

# ── concepts: counterfactual prompt pairs + the meter that scores them ──────────
# Pair order: (concept_prompt, counterfactual_prompt). Meters defined below.
CONCEPTS = {
    "onset_density": {
        "meter": "onset_rate",
        "pairs": [
            ("relentless full-on psytrance, dense driving 16th-note percussion, rapid fire drum rolls",
             "sparse ambient drone, almost no percussion, long sustained pads"),
            ("busy breakbeat with constant hi-hat chatter and snare fills",
             "slow meditative soundscape with rare soft hits"),
            ("fast tribal drumming, layered congas and shakers hitting constantly",
             "still atmospheric texture, one soft drum hit every few seconds"),
            ("energetic drum and bass, frantic chopped breaks",
             "calm new age pad music with no drums"),
        ],
    },
    "brightness": {
        "meter": "centroid",
        "pairs": [
            ("bright crisp electronic music, sparkling hi-hats, shimmering airy highs",
             "dark muffled dub, subdued lows only, no high frequencies"),
            ("glittering trance leads, brilliant top end, crystal highs",
             "deep dark drone, heavily low-passed, bassy and murky"),
            ("sharp icy digital textures with abundant treble detail",
             "warm dull analog rumble, rolled-off highs"),
            ("radiant chimes and bright plucked arpeggios",
             "shadowy sub-heavy ambience, muffled and dim"),
        ],
    },
    "bass_weight": {
        "meter": "bass_ratio",
        "pairs": [
            ("massive sub-bass heavy psytrance, powerful deep rolling bassline",
             "thin airy chimes and whistles, no bass at all"),
            ("earth-shaking 808 sub bass, chest-rattling lows",
             "delicate high-register music box melody, no low end"),
            ("deep dubstep wobble bass, huge low-frequency energy",
             "light flute and bells only, treble instruments"),
            ("booming techno kick and sub bass foundation",
             "airy string harmonics, high and weightless"),
        ],
    },
    "noisiness": {
        "meter": "flatness",
        "pairs": [
            ("harsh industrial noise texture, distorted white-noise sweeps and static",
             "pure clean sine-tone melody, smooth tonal pads"),
            ("gritty distorted acid with noisy percussion and hiss",
             "soft clean piano chords, tonal and pure"),
            ("crushing wall of noise, saturated feedback and grain",
             "gentle harmonic choir pad, clear pitched tones"),
            ("abrasive glitchy static bursts over rough textures",
             "warm consonant organ chords held long"),
        ],
    },
}

MODULE_TYPES = ("self_attn", "cross_attn", "ff")


# ── meters (all librosa/np, target-aware; higher concept prompt => higher value) ─
def _mono(audio, sr):
    if hasattr(audio, "detach"):
        audio = audio.detach().float().cpu().numpy()
    x = np.asarray(audio, dtype=np.float32)
    while x.ndim > 2:
        x = x[0]
    if x.ndim == 2:  # (C, N) or (N, C)
        x = x.mean(axis=0 if x.shape[0] <= 8 else 1)
    return x, sr


def meter_onset_rate(audio, sr):
    # p95-normalized strength-gated peaks: plain onset_detect over-fires on textured
    # drones (measured 13-14/s on "sparse ambient" = flux garbage) and max-normalizing
    # lets one dominant transient suppress everything else. Validated 2026-07-10:
    # dense 9.2/s vs sparse 4.2/s, seed-consistent.
    import librosa
    y, sr = _mono(audio, sr)
    env = librosa.onset.onset_strength(y=y, sr=sr)
    env = np.clip(env / max(np.percentile(env, 95), 1e-9), 0, 3)
    peaks = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=10, post_avg=10,
                                   delta=0.3, wait=2)
    return float(len(peaks) / max(len(y) / sr, 1e-6))


def meter_centroid(audio, sr):
    import librosa
    y, sr = _mono(audio, sr)
    c = librosa.feature.spectral_centroid(y=y, sr=sr)
    return float(np.median(c))


def meter_bass_ratio(audio, sr):
    y, sr = _mono(audio, sr)
    spec = np.abs(np.fft.rfft(y)) ** 2
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    lo = spec[freqs < 150.0].sum()
    return float(lo / max(spec.sum(), 1e-12))


def meter_flatness(audio, sr):
    import librosa
    y, sr = _mono(audio, sr)
    f = librosa.feature.spectral_flatness(y=y)
    return float(np.median(f))


METERS = {"onset_rate": meter_onset_rate, "centroid": meter_centroid,
          "bass_ratio": meter_bass_ratio, "flatness": meter_flatness}


# ── hook machinery ──────────────────────────────────────────────────────────────
class PatchRig:
    """Forward hooks over every (layer, module_type). Two modes:
    cache  -- record each module's cond-half output per forward call (call index =
              denoising step, since euler calls the DiT once per step with CFG batched).
    patch  -- replace ONE (layer, module) cond-half output with the cached sequence.
    dit.py batches [cond, uncond] on dim 0, so cond half = out[:B//2] (B even) or the
    whole tensor at cfg=1 (no batching)."""

    def __init__(self, blocks):
        self.blocks = blocks            # list of TransformerBlock
        self.handles = []
        self.cache = {}                 # (layer, mtype) -> [tensor per call]
        self.mode = None
        self.target = None              # (layer, mtype) in patch mode
        self.call_idx = {}              # (layer, mtype) -> forward-call counter

    def _hook(self, layer, mtype):
        def fn(module, args, out):
            key = (layer, mtype)
            i = self.call_idx.get(key, 0)
            self.call_idx[key] = i + 1
            if self.mode == "cache":
                half = out.shape[0] // 2 if out.shape[0] % 2 == 0 and out.shape[0] > 1 else out.shape[0]
                self.cache.setdefault(key, []).append(out[:half].detach().to("cpu", torch.float16))
                return None
            if self.mode == "patch" and key == self.target:
                seq = self.cache.get(key)
                if seq is None or i >= len(seq):
                    return None
                rep = seq[i].to(out.device, out.dtype)
                half = rep.shape[0]
                if out.shape[0] == 2 * half:          # CFG-batched: swap cond half only
                    patched = out.clone()
                    patched[:half] = rep
                    return patched
                if out.shape[0] == half:
                    return rep
                return None                            # shape mismatch: leave untouched
            return None
        return fn

    def arm(self):
        for li, blk in enumerate(self.blocks):
            for mtype in MODULE_TYPES:
                mod = getattr(blk, mtype, None)
                if mod is not None:
                    self.handles.append(mod.register_forward_hook(self._hook(li, mtype)))

    def reset_calls(self):
        self.call_idx = {}

    def set_cache_mode(self):
        self.cache, self.mode = {}, "cache"
        self.reset_calls()

    def set_patch_mode(self, layer, mtype):
        self.mode, self.target = "patch", (layer, mtype)
        self.reset_calls()

    def set_off(self):
        self.mode, self.target = None, None
        self.reset_calls()

    def close(self):
        for h in self.handles:
            h.remove()
        self.handles = []


def find_blocks(model):
    """Locate the DiT's TransformerBlock list wherever it nests."""
    import torch.nn as nn
    for name, mod in model.named_modules():
        if mod.__class__.__name__ == "ContinuousTransformer" and hasattr(mod, "layers"):
            blocks = [b for b in mod.layers if hasattr(b, "self_attn")]
            if len(blocks) >= 8:                      # the DiT, not some tiny helper
                return name, blocks
    raise RuntimeError("no ContinuousTransformer with TransformerBlock layers found")


# ── driver ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="per-(block,module) causal attribute map")
    ap.add_argument("--out", required=True)
    ap.add_argument("--concepts", default=",".join(CONCEPTS))
    ap.add_argument("--pairs", type=int, default=3, help="prompt pairs per concept")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=6.0)
    ap.add_argument("--smoke", action="store_true",
                    help="1 concept x 1 pair x 1 seed x cross_attn only (~30 gens)")
    ap.add_argument("--keep-audio", action="store_true", help="save patched clips too")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "layer_map_results.jsonl"
    done = set()
    if results_path.exists():
        for ln in results_path.read_text().splitlines():
            try:
                r = json.loads(ln)
                done.add((r["concept"], r["pair"], r["seed"], r["layer"], r["module"]))
            except Exception:
                pass

    concepts = {k: CONCEPTS[k] for k in args.concepts.split(",") if k in CONCEPTS}
    if args.smoke:
        k = next(iter(concepts))
        concepts = {k: {**concepts[k], "pairs": concepts[k]["pairs"][:1]}}
        args.pairs, args.seeds = 1, 1
        module_types = ("cross_attn",)
    else:
        module_types = MODULE_TYPES

    global torch
    import torch  # noqa: F811 -- after env is set by the SA3 venv launcher
    from stable_audio_3.model import StableAudioModel

    sam = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sr = sam.model.sample_rate
    _, blocks = find_blocks(sam.model)
    n_layers = len(blocks)
    print(f"[map] {n_layers} DiT blocks; modules={module_types}; "
          f"{len(concepts)} concepts x {args.pairs} pairs x {args.seeds} seeds", flush=True)

    rig = PatchRig(blocks)
    rig.arm()

    def gen(prompt, seed):
        with torch.inference_mode():
            return sam.generate(prompt=prompt, duration=args.duration, steps=args.steps,
                                cfg_scale=args.cfg, seed=seed, sampler_type="euler")

    # provenance sidecar (REQUIRED convention)
    (out_dir / "run_meta.json").write_text(json.dumps({
        "purpose": ("Axis-1 causal localizer: which DiT blocks/modules carry each "
                    "controllable attribute (TADA-style patching extended to self_attn+ff, "
                    "scored by target-aware MIR meters). Informs SOFT rank routing for "
                    "relevance-routed DoRA -- never hard masking (TADA -21% warning)."),
        "related": ["SAO/docs/research-brief-relevance-routed-dora.md",
                    "SAO/docs/rigor-review-relevance-routed-dora.md",
                    "SAO/papers/arxiv-2602.11910.md",
                    "control/sa3_control/layer_patch_map.py"],
        "model": "medium-base (no adapter)",
        "params": {"duration": args.duration, "steps": args.steps, "cfg": args.cfg,
                   "pairs": args.pairs, "seeds": args.seeds,
                   "concepts": list(concepts), "modules": list(module_types)},
        "notes": "impact = (meter(P)-meter(B))/(meter(A)-meter(B)) per (layer,module); "
                 "cond-half patching only; euler+seed deterministic.",
    }, indent=2))

    t0, n_done = time.time(), 0
    for cname, spec in concepts.items():
        meter = METERS[spec["meter"]]
        for pi, (p_concept, p_counter) in enumerate(spec["pairs"][: args.pairs]):
            for seed in range(1, args.seeds + 1):
                # A: concept run, cache everything
                rig.set_cache_mode()
                audio_a = gen(p_concept, seed)
                m_a = meter(audio_a, sr)
                # B: counterfactual baseline (hooks off)
                rig.set_off()
                audio_b = gen(p_counter, seed)
                m_b = meter(audio_b, sr)
                denom = m_a - m_b
                print(f"[map] {cname} pair{pi} seed{seed}: A={m_a:.4g} B={m_b:.4g} "
                      f"shift={denom:.4g}", flush=True)
                if abs(denom) < 1e-9:
                    print("[map]   degenerate pair (no shift) -- skipping", flush=True)
                    continue
                if args.keep_audio:
                    import soundfile as sf
                    for tag, au in (("A", audio_a), ("B", audio_b)):
                        y, _ = _mono(au, sr)
                        y = y / max(np.abs(y).max(), 1e-9) * 0.89
                        sf.write(out_dir / f"{cname}_p{pi}_s{seed}_{tag}.flac", y, sr)
                # P: one patched run per (layer, module)
                for li in range(n_layers):
                    for mtype in module_types:
                        key = (cname, pi, seed, li, mtype)
                        if key in done:
                            continue
                        rig.set_patch_mode(li, mtype)
                        audio_p = gen(p_counter, seed)
                        m_p = meter(audio_p, sr)
                        impact = (m_p - m_b) / denom
                        with results_path.open("a") as f:
                            f.write(json.dumps({
                                "concept": cname, "pair": pi, "seed": seed,
                                "layer": li, "module": mtype,
                                "meter_A": m_a, "meter_B": m_b, "meter_P": m_p,
                                "impact": impact}) + "\n")
                        n_done += 1
                        if n_done % 24 == 0:
                            el = time.time() - t0
                            print(f"[map]   {n_done} cells, {el/60:.1f} min "
                                  f"({el/n_done:.1f}s/cell)", flush=True)
    rig.close()

    # aggregate: mean impact per (concept, module, layer) across pairs x seeds
    rows = [json.loads(ln) for ln in results_path.read_text().splitlines()]
    agg = {}
    for r in rows:
        agg.setdefault((r["concept"], r["module"]), {}).setdefault(r["layer"], []).append(r["impact"])
    summary = {f"{c}/{m}": [round(float(np.mean(v.get(li, [np.nan]))), 4)
                            for li in range(n_layers)]
               for (c, m), v in agg.items()}
    (out_dir / "layer_map_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[map] DONE {n_done} new cells -> {results_path}\n[map] summary -> "
          f"{out_dir / 'layer_map_summary.json'}", flush=True)


if __name__ == "__main__":
    main()
