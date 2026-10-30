#!/usr/bin/env python3
# Owner: ANTIGRAVITY (created 2026-10-29)
"""chroma_avp_matrix_render.py -- Comparative evaluation matrix for the
retrained 384-d SAME-chroma head on the AVP augmented dataset.

Compares:
  1. unguided (gain=0 baseline)
  2. goa_e13: E13 modular retrained head on Goa (latch_sa3_same_chroma_ep10.pt, 384-d)
  3. avp_aug: Retrained on AVP augmented dataset (latents_avp, 2393 crops)
  4. goa_avp: Retrained on Goa + AVP combined dataset (7300 crops)

Across:
  - Prompts: goa ("melodic goa trance..."), suomi ("suomisoundi psychedelic trance...")
  - Seeds: 5678 (Kim seed), 1234
  - Targets: C, Am, i-VI-III-VII (Am-F-C-G), keylift (C-Eb-F#)
  - Gains: 512 (subtle), 2048 (assertive)
  - Steps: 50, CFG: 7.0, Sched: alpha, Checkpoint: subloss_k24 DoRA

Outputs .wav -> converts to 256k AAC .m4a in /home/kim/evals_aac/chroma_avp_matrix/.
Resumable from OUT/cells.jsonl.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import json
import shutil
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
from chroma_steer_render import build_target_raw, _chroma12_per_frame, latent_frames, fit_to_latent  # noqa: E402
from harmonic import same_chroma as sc  # noqa: E402

OUT = Path("/run/media/kim/Mantu/sa3_control_runs/chroma_avp_matrix_20261029")
AAC_DIR = Path("/home/kim/evals_aac/chroma_avp_matrix")

DORA_FT = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/epoch=63-step=12480.ckpt")

HEADS = {
    "goa_e13": Path("/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt"),
    # KUANG 2026-10-30: the 10-29 AVP heads learned the full-mix latent readout stored under
    # 'other', not stem chroma (see latch/run_chroma_avp_songsplit.sh). These are the
    # stem-chroma, song-split retrains; pick the epoch from val_by_t and pass --head if not best.
    "avp_aug": Path("/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_stemchroma_20261030/C3_avp_song/latch_sa3_same_chroma_best.pt"),
    "goa_avp": Path("/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_stemchroma_20261030/C3_goa_avp_song/latch_sa3_same_chroma_best.pt"),
}
# Heads the cells.jsonl records written before 2026-10-30 were rendered with (they carry no
# head_path). A record is reused only if it was rendered with the head now configured.
LEGACY_HEADS = {
    "base": "/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt",
    "goa_e13": "/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt",
    "avp_aug": "/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_20261029/C3_avp_aug/latch_sa3_same_chroma_ep10.pt",
    "goa_avp": "/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_20261029/C3_goa_avp_combined/latch_sa3_same_chroma_ep10.pt",
}

PROMPTS = {
    "goa": "melodic goa trance, hypnotic arpeggiated lead, driving rolling bassline",
    "suomi": "suomisoundi psychedelic trance, playful squelchy synth lead, funk groove bass",
}

SEEDS = [5678, 1234]
TARGET_IDS = ["C", "Am", "i-VI-III-VII", "keylift"]
GAINS = [512, 2048]
DURATION_SEC = 20.05
FPS = 10.7666
MIN_FREE_GB = 10


def target_spec(tid):
    return next(t for t in T.TARGETS if t["id"] == tid)


def build_target(tid, n_frames):
    return build_target_raw(384, target_spec(tid), n_frames)


def clip_name(head, tid, gain, pid, seed):
    if gain == 0 or head == "base":
        return f"avpm__base__p_{pid}__s{seed}.m4a"
    return f"avpm__{head}__{tid}__g{gain}__p_{pid}__s{seed}.m4a"


def measure(wav_np, tid, n_frames):
    """Per band (bass, mid): frame-wise cosine and pitch-class hit rate."""
    chroma = sc.compute_same_chroma(wav_np.T, sc.SAME_SR, align_to_latent=False)
    folded = sc.fold_to_12(chroma)
    M = folded.shape[-1]
    out = {}
    tids = [tid] if tid else TARGET_IDS
    for t in tids:
        c12 = _chroma12_per_frame(target_spec(t), n_frames)
        idx = np.minimum((np.arange(M) * n_frames / M).astype(int), n_frames - 1)
        tgt = c12[:, idx]
        tn = tgt / (np.linalg.norm(tgt, axis=0, keepdims=True) + 1e-9)
        res = {}
        for bi, band in ((0, "bass"), (1, "mid")):
            f = folded[bi]
            fn = f / (np.linalg.norm(f, axis=0, keepdims=True) + 1e-9)
            res[band] = {
                "fcos": round(float((fn * tn).sum(axis=0).mean()), 4),
                "hit": round(float((f.argmax(axis=0) == tgt.argmax(axis=0)).mean()), 4),
            }
        out[t] = res
    return out


def free_gb(path):
    return shutil.disk_usage(path).free / 2**30


def build_plan(heads=("goa_e13", "avp_aug", "goa_avp"), targets=None, gains=None,
               seeds=None, extra=()):
    """Build the test matrix cells. `extra` = iterable of (head, gain) pairs added
    on top of the full heads x gains grid (used for gain-matching the weaker head)."""
    targets = targets or TARGET_IDS
    gains = gains or GAINS
    seeds = seeds or SEEDS
    cells = []
    seen = set()

    # 1. Unguided baselines (gain=0)
    for pid in PROMPTS:
        for seed in seeds:
            k = ("base", "", 0, pid, seed)
            if k not in seen:
                seen.add(k)
                cells.append({
                    "head": "base", "target": "", "gain": 0,
                    "prompt_id": pid, "seed": seed, "cfg": 7.0, "steps": 50,
                    "sched": "alpha", "fn": clip_name("base", "", 0, pid, seed)
                })

    # 2. Guided cells across the heads (full grid + extra (head, gain) pairs)
    combos = [(h, g) for h in heads for g in gains] + [tuple(x) for x in extra]
    for hid, gain in combos:
        for tid in targets:
            for pid in PROMPTS:
                for seed in seeds:
                    k = (hid, tid, gain, pid, seed)
                    if k not in seen:
                        seen.add(k)
                        cells.append({
                            "head": hid, "target": tid, "gain": gain,
                            "prompt_id": pid, "seed": seed, "cfg": 7.0, "steps": 50,
                            "sched": "alpha", "fn": clip_name(hid, tid, gain, pid, seed)
                        })
    return cells


def load_cells_db():
    p = OUT / "cells.jsonl"
    db = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                db[rec["fn"]] = rec
    return db


def is_progression(tid):
    return bool(tid) and target_spec(tid)["kind"] != "static"


def record_is_current(rec):
    """Reuse a measured cell only if it was rendered with the head configured now and, for a
    chord progression, with the target fitted to the latent window (before 2026-10-30 the
    progression was stretched ~1.3x by generate()'s resample; static targets were not)."""
    head = rec["head"]
    have = rec.get("head_path", LEGACY_HEADS.get(head))
    if have is None or Path(have) != Path(HEADS["goa_e13" if head == "base" else head]):
        return False
    return not is_progression(rec.get("target")) or rec.get("target_fit") == "latent"


def resolve_head_path(hid):
    """The configured checkpoint, exactly. (The old fallback to ep12/best swapped in a
    different epoch without saying so in the results.)"""
    path = HEADS[hid]
    if path.exists():
        return path
    raise FileNotFoundError(f"Cannot resolve checkpoint for {hid} at {path} (pass --head {hid}=PATH)")


def _csv(s, cast=str):
    return [cast(x) for x in s.split(",") if x.strip()] if s else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gains", default="", help="comma list, default 512,2048")
    ap.add_argument("--targets", default="", help="comma list, default all TARGET_IDS")
    ap.add_argument("--seeds", default="", help="comma list, default 5678,1234")
    ap.add_argument("--extra", default="", help="extra head:gain pairs, e.g. avp_aug:16384")
    ap.add_argument("--head", action="append", default=[], metavar="ID=PATH",
                    help="override a head checkpoint, e.g. avp_aug=/path/latch_sa3_same_chroma_ep14.pt")
    args = ap.parse_args()
    for spec in args.head:
        hid, path = spec.split("=", 1)
        if hid not in HEADS:
            raise SystemExit(f"unknown head {hid!r}; one of {sorted(HEADS)}")
        HEADS[hid] = Path(path)

    OUT.mkdir(parents=True, exist_ok=True)
    AAC_DIR.mkdir(parents=True, exist_ok=True)

    extra = [(p.split(":")[0], int(p.split(":")[1])) for p in _csv(args.extra) or []]
    plan = build_plan(targets=_csv(args.targets), gains=_csv(args.gains, int),
                      seeds=_csv(args.seeds, int), extra=extra)
    db = {fn: rec for fn, rec in load_cells_db().items() if record_is_current(rec)}
    print(f"[matrix] Total plan: {len(plan)} cells; reusable measured cells: {len(db)}")

    todo = [c for c in plan if c["fn"] not in db]
    if args.limit > 0:
        todo = todo[:args.limit]
    print(f"[matrix] Pending execution: {len(todo)} cells")

    if args.dry_run:
        for i, c in enumerate(todo[:10]):
            print(f"  [{i+1}] {c['fn']} -> head={c['head']} target={c['target']} gain={c['gain']} pid={c['prompt_id']} s={c['seed']}")
        return

    # Every head the pending cells need must exist before the model loads (fail now, not mid-run)
    for hid in sorted({"goa_e13" if c["head"] == "base" else c["head"] for c in todo}):
        print(f"[matrix] Head {hid} -> {resolve_head_path(hid)}")

    # Load StableAudioModel with DoRA adapter
    import torch
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio

    print("[matrix] Loading StableAudioModel (medium-base)...", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    print(f"[matrix] Loading Goa DoRA adapter ({DORA_FT.name})...", flush=True)
    model.load_lora([str(DORA_FT)])
    model.set_lora_strength(1.0)
    print("[matrix] Model ready on GPU.", flush=True)

    n_frames = int(round(DURATION_SEC * FPS))
    # Targets cover the audible n_frames and hold their last frame over generate()'s padding,
    # so frame f of the target lands on latent frame f (KUANG 2026-10-30).
    n_latent = latent_frames(model, DURATION_SEC)
    print(f"[matrix] target frames: {n_frames} audible, {n_latent} in the latent window", flush=True)
    targets_raw = {
        tid: fit_to_latent(build_target(tid, n_frames), n_latent) for tid in TARGET_IDS
    }

    pt = model.model.pretransform
    dec_dtype = next(pt.parameters()).dtype

    def decode(z):
        with torch.no_grad():
            return pt.decode(z.to("cuda", dec_dtype)).float().cpu()

    # Warm-up: the FIRST GPU decode in a fresh process was unreliable (noise burst at
    # 12-14 s on avpm__base__p_goa__s5678, once a constant full-scale signal), while a
    # CPU fp32 decode of the same latent was clean. Burn two throwaway decodes.
    print("[matrix] Warm-up decodes ...", flush=True)
    for _ in range(2):
        decode(torch.randn(1, 256, 282) * 0.8)

    def checked_decode(z, wav_first):
        """Decode z again; if the two decodes disagree, decode until two agree."""
        cands = [wav_first]
        for attempt in range(3):
            w = decode(z)
            for prev in cands:
                n = min(prev.shape[-1], w.shape[-1])
                if torch.isfinite(w).all() and torch.allclose(prev[..., :n], w[..., :n], atol=5e-2, rtol=0):
                    return w, attempt
            cands.append(w)
        raise RuntimeError("VAE decode never reproduced itself in 4 attempts")

    for i, c in enumerate(todo):
        if free_gb(OUT) < MIN_FREE_GB:
            raise RuntimeError(f"Disk space below {MIN_FREE_GB} GB on {OUT}")

        fn = c["fn"]
        hid = c["head"]
        gain = c["gain"]
        tid = c["target"]
        pid = c["prompt_id"]
        seed = c["seed"]
        cfg = c["cfg"]
        steps = c["steps"]
        sched = c["sched"]
        prompt = PROMPTS[pid]

        gen = dict(
            prompt=prompt,
            duration=DURATION_SEC,
            steps=int(steps),
            cfg_scale=float(cfg),
            seed=int(seed),
            sampler_type="euler",
            apg_scale=1.0,
        )

        hpath = resolve_head_path(hid if hid != "base" else "goa_e13")
        target_name = tid if tid else "C"
        gen["latch_configs"] = [{
            "model_path": str(hpath),
            "target_raw": targets_raw[target_name],
            "weight": 1.0,
            "loss_type": "cosine",
        }]
        gen["latch_hparams"] = {
            "rho": float(gain),
            "mu": float(gain),
            "guide_schedule": sched,
        }

        sink = []
        t0 = time.time()
        print(f"[{i+1}/{len(todo)}] Render {fn} ...", end="", flush=True)

        with torch.inference_mode():
            audio = model.generate(latents_sink=sink, **gen)
        dt = time.time() - t0
        z = sink[-1].float() if sink else None

        wav, redecodes = checked_decode(z, audio[0:1].float().cpu())
        wav = wav[0]
        if redecodes:
            print(f" [decode mismatch, fixed after {redecodes + 1} re-decodes]", end="", flush=True)
        wav_tmp = OUT / fn.replace(".m4a", ".wav")
        save_audio(str(wav_tmp), wav, sc.SAME_SR)

        # AAC encode
        aac_path = AAC_DIR / fn
        cmd = [
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
            "-i", str(wav_tmp),
            "-c:a", "aac", "-b:a", "256k",
            str(aac_path),
        ]
        subprocess.run(cmd, check=True)
        wav_tmp.unlink(missing_ok=True)

        wav_np = wav.numpy()
        met = measure(wav_np, tid, n_frames)
        m_t = met[tid] if tid else met["C"]
        z_std = round(float(z.std().item()), 4) if z is not None else None

        record = {
            "fn": fn,
            "head": hid,
            "target": tid,
            "gain": gain,
            "prompt_id": pid,
            "seed": seed,
            "cfg": cfg,
            "steps": steps,
            "sched": sched,
            "fcos_bass": m_t["bass"]["fcos"],
            "fcos_mid": m_t["mid"]["fcos"],
            "hit_bass": m_t["bass"]["hit"],
            "hit_mid": m_t["mid"]["hit"],
            "z_std": z_std,
            "head_path": str(hpath),
            "target_fit": "latent",
            "target_frames": [n_frames, n_latent],
            "latency_s": round(dt, 2),
            "measured_all": met,
        }

        with open(OUT / "cells.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
        db[fn] = record
        print(f" done in {dt:.1f}s | mid_cos={m_t['mid']['fcos']:+.3f} hit={m_t['mid']['hit']:.2f} z_std={z_std}")

    print(f"[matrix] All {len(plan)} cells finished and verified.")


if __name__ == "__main__":
    main()
