"""chroma_steer_render.py — render the extended chroma-steering eval set (Kim ask
2026-07-19). Solo instruments × harmonic targets (static keys/colours AND chord
progressions between colours/keys) × every chroma steering head × a gain sweep.

Render path (PROVEN — no novel plumbing): the same high-level entry point as the
scalar LatCH sweep, `model.generate(latch_configs=[...], latch_hparams=...)`, using the
`target_raw` slot — a raw per-frame target [C, T] that model.py nearest-resamples to the
latent grid and standardizes per the head. This is exactly the slot the chroma-morph
transitions used, so a time-varying chroma target = a chord progression is a first-class
input. Per MASTER §5 the DiT forward stays fp16 + CK-FA (only the ~few-M head is fp32),
so this runs at base speed with no fp32 VRAM blow-up.

The chroma-trap (MASTER §5): absolute chroma similarity is meaningless on tonal music.
Every clip is rendered WITH its gain-0 baseline (same seed/prompt/target); the reported
metric is Δcos12 = cos12(steered, target) − cos12(baseline, target), per band. Positive =
steering moved the output toward the target relative to what the prompt alone produced.

Modes (pick one):
  --smoke       CPU only. Build every target_raw for every head, assert shapes, and write
                the full clip manifest as 'pending'. No GPU, no model. Verifies wiring and
                hands the page its structure.
  --verify-one  GPU. Render ONE clip (hpcp, a progression) + its baseline, measure whether
                the chroma actually moved. The go/no-go before any grid — the engine's
                on-GPU behaviour was never validated (chroma_guided_generator STUB-THIS-PASS).
  --pilot       GPU. A small grid: hpcp × 3 instruments × {1 static, 1 progression} × full
                gain ladder × 1 seed + baselines (~spec §4 pilot size).
  --full        GPU. Everything in chroma_steer_targets (all heads, prompts, targets, seeds).

Resumable: skips clips already in the manifest. SA3 venv, GPU for the non-smoke modes:
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/chroma_steer_render.py --pilot
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SAO = HERE.parent
sys.path.insert(0, str(SAO / "control"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")

import chroma_steer_targets as T  # noqa: E402
from sa3_control.chroma_guided_generator import (  # noqa: E402
    chord_to_chroma, parse_progression, ChromaSchedule)
from harmonic import same_chroma as sc  # noqa: E402

HEADS_DIR = SAO / "stable-audio-3" / "latch_weights_sa3_medium"
OUT_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/chroma_steer_20260719")
DATA_JSON = SAO / "riffer-evals" / "chroma_steer_data.json"   # the page reads this
MODELS_FILTER = None   # None = all; else a set of model ids (set via --models)

FPS = 10.7666
DURATION_SEC = 20.05          # ~216 frames; matches the original chroma_steer clip length
STEPS = 24
CFG = 7.0


# ── target_raw builders ─────────────────────────────────────────────────────────────
# One 12-d chroma curve per frame is the common representation; the 384-d heads expand it
# to (3 bands × 128) via the SAME semitone-bump expansion (bass locked to the frame's
# dominant pitch class). Both return (C, n_frames) float32.

def _chroma12_per_frame(target_spec: dict, n_frames: int) -> np.ndarray:
    """(12, n_frames) unit-per-frame chroma from a target spec (static or progression)."""
    if target_spec["kind"] == "static":
        v = chord_to_chroma(target_spec["chord"]).astype(np.float64)   # (12,)
        return np.repeat(v[:, None], n_frames, axis=1).astype(np.float32)
    prog = parse_progression(target_spec["prog"])
    sch = ChromaSchedule(prog, fps=FPS, blend_sec=1.0)
    return sch.target_numpy(0.0, n_frames)                             # (12, n_frames), standardize=off


def build_target_raw(dim: int, target_spec: dict, n_frames: int) -> np.ndarray:
    """(dim, n_frames) raw target for the head. dim=12 -> hpcp; dim=384 -> 3-band SAME."""
    c12 = _chroma12_per_frame(target_spec, n_frames)                   # (12, n_frames)
    if dim == 12:
        return c12
    if dim == 384:
        out = np.empty((3, 128, n_frames), dtype=np.float32)
        for f in range(n_frames):
            mel12 = c12[:, f]
            bass_root = int(np.argmax(mel12))
            tgt = sc.make_steering_target(1, mel12, bass_root=bass_root,
                                          bass_gain=1.0, mid_gain=1.0, air_gain=0.3)
            out[:, :, f] = tgt[:, :, 0]
        return out.reshape(384, n_frames)
    raise ValueError(f"unsupported head dim {dim}")


# ── output chroma measurement (CPU; the chroma-trap-safe Δ is computed page-side) ────

def measure_cos12(wav_np: np.ndarray, target_spec: dict, n_frames: int):
    """Per-band (bass, mid) mean-frame cos12 between the OUTPUT audio's SAME chroma folded
    to 12 and the target's 12-d chroma. wav_np: (C, T) @ SAME_SR."""
    chroma = sc.compute_same_chroma(wav_np.T, sc.SAME_SR, align_to_latent=False)  # (3,128,M)
    c12 = _chroma12_per_frame(target_spec, n_frames)                              # (12, n_frames)
    tgt12 = c12.mean(axis=1); tgt12 = tgt12 / (np.linalg.norm(tgt12) + 1e-9)
    out = {}
    for bi, band in ((0, "bass"), (1, "mid")):
        folded = sc.fold_to_12(chroma[bi].mean(axis=-1))
        folded = folded / (np.linalg.norm(folded) + 1e-9)
        out[band] = round(float(folded @ tgt12), 4)
    return out


# ── enumeration ─────────────────────────────────────────────────────────────────────

def cells_for_mode(mode: str):
    """Yield (model, prompt, target, gain, seed) tuples for the chosen mode."""
    if mode == "pilot":
        models = [m for m in T.MODELS if m["id"] in ("hpcp", "same_chroma")]
        prompts = [p for p in T.SOLO_INSTRUMENTS if p["id"] in ("piano", "violin", "sax")]
        targets = [t for t in T.TARGETS if t["id"] in ("Am", "keylift")]
        seeds = T.SEEDS[:1]
    else:  # full
        models, prompts, targets, seeds = T.MODELS, T.ALL_PROMPTS, T.TARGETS, T.SEEDS
    if MODELS_FILTER is not None:
        models = [m for m in models if m["id"] in MODELS_FILTER]
    for m in models:
        for p in prompts:
            for t in targets:
                for s in seeds:
                    for g in T.GAIN_LADDER:
                        yield m, p, t, g, s


# ── render ──────────────────────────────────────────────────────────────────────────

def _to_mp3(wav_path: Path):
    mp3 = wav_path.with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                    "-b:a", "128k", str(mp3)], check=True)
    wav_path.unlink(missing_ok=True)
    return mp3


def render(mode: str):
    import torch  # noqa: F401
    from stable_audio_3 import StableAudioModel
    from stable_audio_3.models.latch import load_latch_from_checkpoint
    from sa3_control.audio_io import save_audio

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_frames = int(round(DURATION_SEC * FPS))
    manifest_path = OUT_DIR / "chroma_steer_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"cells": []}
    done = {c["clip"] for c in manifest["cells"]}

    # head out-channel probe (validates the head dims match our target_raw before rendering)
    for m in T.MODELS:
        ck = HEADS_DIR / m["ckpt"]
        if ck.exists():
            h = load_latch_from_checkpoint(str(ck), device="cpu")
            oc = int(getattr(h, "out_channels", -1))
            if oc != m["dim"]:
                print(f"[chroma-steer] WARNING head {m['id']} out_channels={oc} != declared {m['dim']}")
            del h
        else:
            print(f"[chroma-steer] MISSING head {m['ckpt']} — its tab will stay pending")

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    if mode == "verify-one":
        cells = [(next(m for m in T.MODELS if m["id"] == "hpcp"),
                  next(p for p in T.SOLO_INSTRUMENTS if p["id"] == "piano"),
                  next(t for t in T.TARGETS if t["id"] == "keylift"),
                  g, T.SEEDS[0]) for g in (0, 2048)]
    else:
        cells = list(cells_for_mode(mode))

    for m, p, t, g, s in cells:
        ck = HEADS_DIR / m["ckpt"]
        if not ck.exists():
            continue
        name = T.clip_name(m["id"], p["id"], t["id"], g, s)
        if name in done:
            continue
        t0 = time.time()
        gen = dict(prompt=p["text"], duration=DURATION_SEC, steps=STEPS,
                   cfg_scale=CFG, seed=s)
        if g > 0:
            target_raw = build_target_raw(m["dim"], t, n_frames)
            gen["latch_configs"] = [{"model_path": str(ck), "target_raw": target_raw,
                                     "weight": 1.0, "loss_type": "cosine"}]
            gen["latch_hparams"] = {"rho": float(g), "mu": float(g)}
        audio = model.generate(**gen)
        wav = audio[0].float().cpu()
        wav_path = OUT_DIR / T.clip_name(m["id"], p["id"], t["id"], g, s).replace(".mp3", ".wav")
        save_audio(str(wav_path), wav, sc.SAME_SR)
        cos12 = measure_cos12(wav.numpy(), t, n_frames)
        _to_mp3(wav_path)
        cell = {"clip": name, "model": m["id"], "prompt_id": p["id"], "prompt": p["text"],
                "target_id": t["id"], "target_label": t["label"], "target_family": t["family"],
                "gain": g, "seed": s, "cos12": cos12, "elapsed": round(time.time() - t0, 1)}
        manifest["cells"].append(cell)
        done.add(name)
        manifest_path.write_text(json.dumps(manifest, indent=1))
        print(f"[{m['id']}/{p['id']}/{t['id']}/g{g}/s{s}] cos12={cos12} ({cell['elapsed']}s)")

    _write_run_meta(manifest, mode)
    _emit_page_data(manifest)

    if mode == "verify-one":
        return _verify_report(manifest)
    return True


def _verify_report(manifest) -> bool:
    """Did steering move the chroma vs baseline on the verify clip? Returns True iff any
    band moved toward the target (gates the driver's pilot step)."""
    cells = {c["gain"]: c for c in manifest["cells"]
             if c["model"] == "hpcp" and c["prompt_id"] == "piano" and c["target_id"] == "keylift"}
    moved = False
    if 0 in cells and 2048 in cells:
        for band in ("bass", "mid"):
            d = cells[2048]["cos12"][band] - cells[0]["cos12"][band]
            verdict = "MOVED" if d > 0.02 else ("flat" if abs(d) <= 0.02 else "MOVED WRONG WAY")
            moved = moved or d > 0.02
            print(f"[verify] {band}: dcos12(g2048-base) = {d:+.4f}  -> {verdict}")
    print(f"[verify] result: {'GO — chroma moved, pilot is safe to run' if moved else 'NO-GO — chroma did not move; the engine needs a rho/mu tune before any grid'}")
    return moved


def _write_run_meta(manifest, mode):
    """MANIFEST v2 (MASTER §4): hypothesis, recipe, dataset info, result, ❗-until-feedback."""
    (OUT_DIR / "run_meta.json").write_text(json.dumps({
        "purpose": ("Extended chroma-steering eval (Kim ask 2026-07-19): does a chroma "
                    "steering head move a SOLO instrument's harmony toward a target key — "
                    "and toward a moving CHORD PROGRESSION between colours/keys — across "
                    "the chroma heads we have, over a gain sweep."),
        "hypothesis": ("Chroma heads have usable harmonic authority on clean solo-instrument "
                       "prompts (a more legible bed than the dense goa mix), and a time-varying "
                       "target steers a developing progression, not just a static key. Open "
                       "question this answers: is hpcp's MASTER-§5 'dead' label an artifact of "
                       "the energy-focused sweep that couldn't see harmonic motion."),
        "recipe": {"entry": "model.generate(latch_configs target_raw, latch_hparams rho=mu=gain)",
                   "gain_ladder": T.GAIN_LADDER, "steps": STEPS, "cfg": CFG,
                   "duration_sec": DURATION_SEC, "loss_type": "cosine",
                   "chroma_trap_control": "metric is Δcos12 vs same-seed gain-0 baseline"},
        "models": [{"id": m["id"], "ckpt": m["ckpt"], "dim": m["dim"]} for m in T.MODELS],
        "dataset_info": "no training here — pretrained SA3 medium-base + shipped LatCH chroma heads",
        "result": {"mode_run": mode, "clips": len(manifest["cells"])},
        "kim_feedback": None,
        "related": ["eval/chroma_steer_render.py", "eval/chroma_steer_targets.py",
                    "docs/superpowers/specs/2026-07-16-chroma384-eval-design.md",
                    "control/sa3_control/chroma_guided_generator.py"],
    }, indent=2))


def _emit_page_data(manifest):
    """Fold the manifest into the JSON the page reads (models/prompts/targets + cells)."""
    # redaction seam (W, 2026-07-20): checkpoint FILENAMES stay off public pages — the page
    # reads id/label/dim/note, never ckpt, so strip it from the emitted models.
    pub_models = [{k: v for k, v in m.items() if k != "ckpt"} for m in T.MODELS]
    DATA_JSON.write_text(json.dumps({
        "models": pub_models, "prompts": T.ALL_PROMPTS, "targets": T.TARGETS,
        "gains": T.GAIN_LADDER, "seeds": T.SEEDS,
        "clip_base": "https://aavepyora.online/files/clips/chroma_steer_20260719",
        "cells": manifest["cells"],
    }, indent=1))
    print(f"[chroma-steer] page data -> {DATA_JSON} ({len(manifest['cells'])} cells)")


def smoke():
    """CPU-only: build every target_raw, assert shapes, write structure-only page data
    (empty cells — the page renders any missing cell as 'pending' until a render lands)."""
    n_frames = int(round(DURATION_SEC * FPS))
    for m, p, t, g, s in cells_for_mode("full"):
        if g == 0:
            continue
        raw = build_target_raw(m["dim"], t, n_frames)
        assert raw.shape == (m["dim"], n_frames), (m["id"], t["id"], raw.shape)
    total = sum(1 for _ in cells_for_mode("full"))
    # merge with any already-rendered cells so a smoke re-run doesn't wipe real clips
    mpath = OUT_DIR / "chroma_steer_manifest.json"
    existing = json.loads(mpath.read_text())["cells"] if mpath.exists() else []
    _emit_page_data({"cells": existing})
    print(f"[smoke] built all target_raw shapes OK; full grid = {total} clips "
          f"({total // len(T.GAIN_LADDER) * (len(T.GAIN_LADDER)-1)} steered + "
          f"{total // len(T.GAIN_LADDER)} baselines)")
    print(f"[smoke] models={[m['id'] for m in T.MODELS]}  "
          f"prompts={len(T.ALL_PROMPTS)}  targets={len(T.TARGETS)}  "
          f"gains={T.GAIN_LADDER}  seeds={T.SEEDS}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--smoke", action="store_true")
    grp.add_argument("--verify-one", action="store_true")
    grp.add_argument("--pilot", action="store_true")
    grp.add_argument("--full", action="store_true")
    ap.add_argument("--heads-dir", default=None, help="override the LatCH head dir (e.g. an EMA-retrain dir with <feat>_best.pt symlinks)")
    ap.add_argument("--tag", default=None, help="namespace the output dir + page-data file (keeps an EMA run from clobbering the shipped run)")
    ap.add_argument("--models", default=None, help="comma-separated model ids to render (default all)")
    a = ap.parse_args()
    global HEADS_DIR, OUT_DIR, DATA_JSON, MODELS_FILTER
    if a.heads_dir:
        HEADS_DIR = Path(a.heads_dir)
    if a.models:
        MODELS_FILTER = set(a.models.split(","))
    if a.tag:
        OUT_DIR = Path(str(OUT_DIR) + "_" + a.tag)
        DATA_JSON = DATA_JSON.with_name(f"chroma_steer_data_{a.tag}.json")
    if a.smoke:
        smoke()
    elif a.verify_one:
        sys.exit(0 if render("verify-one") else 2)  # exit 2 = chroma didn't move (gate the pilot)
    elif a.pilot:
        render("pilot")
    else:
        render("full")


if __name__ == "__main__":
    main()
