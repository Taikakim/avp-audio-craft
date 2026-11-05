#!/usr/bin/env python3
"""
calibrated_melody_probe.py -- Calibrated melody probing over extracted activations.

Implements Kuang's calibrated probe architecture:
1. Gated on Clean z0: Must decode pitch from z0 before interpreting DiT block results.
2. Pitch as Place Code: 88-bin piano roll (MIDI 21 to 108) and 12-class chroma logistic probes.
3. Temporal Context: Receptive field of +/- 0.5s (+/- 2 to 5 frames at 10.76 fps).
4. Within-crop R^2 & Pearson r: Measures within-crop contour variance rather than cross-track DC offset.
5. Strict Artist-Grouped 5-Fold Cross-Validation.
6. Evaluates against clean z0, DiT blocks 0-23, and random-init control.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "latch"))
from melody_probe_map import load_crop_targets, group_folds, moving_average, FPS

DEFAULT_ACTS = os.environ.get("ACTS_DIR", "runs/melody_probe_2026-11-04/acts")
DEFAULT_RANDOM_ACTS = os.environ.get("RANDOM_ACTS_DIR", "runs/melody_probe_2026-11-04/acts_random")
DEFAULT_LATENTS = os.environ.get("LATENT_DIR", "latents/latents_sa3")
DEFAULT_OUT = os.environ.get("OUT_JSON", "eval/melody_probe_2026-11-04/calibrated_probe_results.json")

PIANO_MIN = 21 # A0
PIANO_MAX = 108 # C8
NUM_PIANO_BINS = 88

def extract_ctx(z, ctx=2):
    """
    Pad and stack context frames.
    z: [N, C, T] -> [N, T, C * (2*ctx + 1)]
    """
    N, C, T = z.shape
    zp = np.pad(z, ((0, 0), (0, 0), (ctx, ctx)), mode="edge")
    feats = [zp[:, :, i:i + T] for i in range(2 * ctx + 1)]
    return np.concatenate(feats, axis=1).transpose(0, 2, 1)

def within_crop_r2(y_true, y_pred, vmask):
    """
    Compute within-crop R^2 (de-meaned per-crop variance).
    """
    ss_tot = 0.0
    ss_res = 0.0
    for i in range(len(y_true)):
        v = vmask[i]
        if v.sum() < 5:
            continue
        yt = y_true[i, v]
        yp = y_pred[i, v]
        yt_dm = yt - yt.mean()
        yp_dm = yp - yp.mean()
        ss_tot += ((yt_dm) ** 2).sum()
        ss_res += ((yt_dm - yp_dm) ** 2).sum()
    if ss_tot <= 1e-12:
        return 0.0
    return float(1.0 - (ss_res / ss_tot))

def train_eval_place_code(X_all, targets_midi, vmask, folds, num_bins=88, epochs=25, lr=5e-3, weight_decay=1e-3, device="cuda"):
    """
    Train and evaluate a place-code multinomial logistic probe across 5 artist folds.
    """
    K = len(np.unique(folds))
    exact_accs = []
    semi1_accs = []
    expected_pitches = np.zeros_like(targets_midi, dtype=np.float32)

    dev = torch.device(device if torch.cuda.is_available() and device.startswith("cuda") else "cpu")

    for k in range(K):
        tr_idx = np.where(folds != k)[0]
        te_idx = np.where(folds == k)[0]

        X_tr = torch.tensor(X_all[tr_idx][vmask[tr_idx]], dtype=torch.float32)
        y_tr = torch.tensor(targets_midi[tr_idx][vmask[tr_idx]], dtype=torch.long)

        X_te = torch.tensor(X_all[te_idx], dtype=torch.float32) # [N_te, T, D]
        y_te = targets_midi[te_idx][vmask[te_idx]]

        # Standardize features
        mu = X_tr.mean(0)
        sd = X_tr.std(0) + 1e-6
        X_tr = ((X_tr - mu) / sd).to(dev)
        y_tr = y_tr.to(dev)

        X_te_norm = ((X_te - mu) / sd).to(dev)

        in_dim = X_tr.shape[1]
        probe = nn.Linear(in_dim, num_bins).to(dev)
        opt = torch.optim.AdamW(probe.parameters(), lr=lr, weight_decay=weight_decay)
        loss_fn = nn.CrossEntropyLoss()

        for ep in range(epochs):
            probe.train()
            opt.zero_grad()
            logits = probe(X_tr)
            loss = loss_fn(logits, y_tr)
            loss.backward()
            opt.step()

        probe.eval()
        with torch.no_grad():
            logits_te = probe(X_te_norm) # [N_te, T, num_bins]
            probs = torch.softmax(logits_te, dim=-1)
            pred_classes = logits_te.argmax(dim=-1).cpu().numpy()
            exp_p = (probs * torch.arange(num_bins, dtype=torch.float32, device=dev)).sum(dim=-1).cpu().numpy()

            expected_pitches[te_idx] = exp_p

            pred_v = pred_classes[vmask[te_idx]]
            exact = (pred_v == y_te).mean()
            semi1 = (np.abs(pred_v - y_te) <= 1).mean()
            exact_accs.append(float(exact))
            semi1_accs.append(float(semi1))

        del X_tr, y_tr, X_te_norm, probe

    return {
        "exact_acc": float(np.mean(exact_accs)),
        "within_1semi_acc": float(np.mean(semi1_accs)),
        "expected_pitches": expected_pitches
    }

def main():
    parser = argparse.ArgumentParser(description="Calibrated Melody Probe")
    parser.add_argument("--acts-dir", type=str, default=DEFAULT_ACTS)
    parser.add_argument("--random-acts-dir", type=str, default=DEFAULT_RANDOM_ACTS)
    parser.add_argument("--latent-dir", type=str, default=DEFAULT_LATENTS)
    parser.add_argument("--out-json", type=str, default=DEFAULT_OUT)
    parser.add_argument("--ctx", type=int, default=2, help="Context frames (+/-2 frames = 5 frames total)")
    parser.add_argument("--sigmas", type=str, default="0.5,0.137", help="Sigmas to analyze for DiT blocks")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    acts_dir = Path(args.acts_dir)
    latent_dir = Path(args.latent_dir)
    manifest = json.loads((acts_dir / "manifest.json").read_text())
    crops = manifest["crops"]
    W = manifest["window"]
    sigmas = [float(s) for s in args.sigmas.split(",")]

    print(f"=== Calibrated Melody Probe Map ===")
    print(f"Device: {args.device}")
    print(f"Crops: {len(crops)}, Window: {W} frames, Context: +/-{args.ctx} frames")

    # Load targets and voicing
    data = [load_crop_targets(latent_dir, c, W) for c in crops]
    groups = np.array([c["artist"] for c in crops])
    folds = group_folds(groups, k=5, seed=0)

    f0_semi = np.stack([d[0]["f0_semi"] for d in data]) # [N, W]
    f0_phrase = np.stack([d[0]["f0_phrase"] for d in data]) # [N, W]
    f0_note = np.stack([d[0]["f0_note"] for d in data]) # [N, W]
    voiced = np.stack([d[1] for d in data]) # [N, W] bool

    # 88 piano bins
    midi_bins = np.clip(np.round(f0_semi).astype(int) - PIANO_MIN, 0, NUM_PIANO_BINS - 1)
    # 12 chroma classes
    chroma_bins = np.round(f0_semi).astype(int) % 12

    results = {
        "n_crops": len(crops),
        "n_artists": len(set(groups)),
        "n_voiced_frames": int(voiced.sum()),
        "ctx_frames": args.ctx,
        "chance_88bin_exact": 1.0 / NUM_PIANO_BINS,
        "chance_12bin_exact": 1.0 / 12.0
    }

    # =========================================================================
    # STAGE 1: Mandatory Clean z0 Calibration Gate
    # =========================================================================
    print("\n--- STAGE 1: Clean z0 Calibration Gate ---")
    z0 = np.stack([np.load(acts_dir / f"{c['stem']}.z0.npy") for c in crops]) # [N, 256, W]
    X_z0 = extract_ctx(z0, ctx=args.ctx)

    print("Evaluating 88-bin Piano-Roll Place Code on clean z0...")
    res_z0_88 = train_eval_place_code(X_z0, midi_bins, voiced, folds, num_bins=88, device=args.device)
    exp_pitch_z0 = res_z0_88["expected_pitches"] + PIANO_MIN

    # Derive phrase and note from expected pitch
    pred_phrase_z0 = np.zeros_like(f0_phrase)
    pred_note_z0 = np.zeros_like(f0_note)
    for i in range(len(crops)):
        p = exp_pitch_z0[i]
        m1 = moving_average(p, 1.0 * FPS)
        m6 = moving_average(p, 6.0 * FPS)
        pred_phrase_z0[i] = m1 - m6
        pred_note_z0[i] = p - m1

    r_phrase_z0 = float(np.corrcoef(f0_phrase[voiced], pred_phrase_z0[voiced])[0, 1])
    r_note_z0 = float(np.corrcoef(f0_note[voiced], pred_note_z0[voiced])[0, 1])
    r2_within_phrase_z0 = within_crop_r2(f0_phrase, pred_phrase_z0, voiced)

    print("Evaluating 12-class Chroma Place Code on clean z0...")
    res_z0_chroma = train_eval_place_code(X_z0, chroma_bins, voiced, folds, num_bins=12, device=args.device)

    results["z0_gate"] = {
        "piano88_exact_acc": res_z0_88["exact_acc"],
        "piano88_within_1semi": res_z0_88["within_1semi_acc"],
        "chroma12_exact_acc": res_z0_chroma["exact_acc"],
        "chroma12_within_1semi": res_z0_chroma["within_1semi_acc"],
        "f0_phrase_pearson_r": r_phrase_z0,
        "f0_note_pearson_r": r_note_z0,
        "f0_phrase_within_crop_r2": r2_within_phrase_z0,
        "gate_passed": bool(res_z0_88["exact_acc"] > 0.10 and r_phrase_z0 > 0.15)
    }

    print(f"Clean z0 Results:")
    print(f"  88-bin Piano Roll: Exact Acc = {res_z0_88['exact_acc']*100:.1f}% (chance {100/88:.1f}%), +/-1 Semi = {res_z0_88['within_1semi_acc']*100:.1f}%")
    print(f"  12-class Chroma:  Exact Acc = {res_z0_chroma['exact_acc']*100:.1f}% (chance {100/12:.1f}%), +/-1 Semi = {res_z0_chroma['within_1semi_acc']*100:.1f}%")
    print(f"  Derived f0_phrase: Pearson r = {r_phrase_z0:+.3f}")
    print(f"  Derived f0_note:   Pearson r = {r_note_z0:+.3f}")
    print(f"  Gate Status: {'PASSED [OK]' if results['z0_gate']['gate_passed'] else 'FAILED'}")

    del z0, X_z0

    # =========================================================================
    # STAGE 2: DiT Residual Stream Probing across Sigmas
    # =========================================================================
    results["sigmas"] = {}

    def tag(c, s):
        return f"{c['stem']}__s{int(round(s * 1000)):04d}"

    for s in sigmas:
        print(f"\n--- STAGE 2: DiT Blocks at sigma={s} ---")
        s_tag = f"s{s}"
        results["sigmas"][s_tag] = {"blocks": []}

        first_m = acts_dir / f"{tag(crops[0], s)}.blocks.npy"
        if not first_m.exists():
            print(f"Activations not found for sigma={s}, skipping.")
            continue

        mm = [np.load(acts_dir / f"{tag(c, s)}.blocks.npy", mmap_mode="r") for c in crops]
        num_blocks = mm[0].shape[0]

        for li in range(num_blocks):
            t0 = time.time()
            blk_acts = np.stack([np.asarray(m[li], dtype=np.float32).T for m in mm]) # [N, 1536, W]
            X_blk = extract_ctx(blk_acts, ctx=args.ctx)

            res_blk = train_eval_place_code(X_blk, midi_bins, voiced, folds, num_bins=88, epochs=15, device=args.device)
            exp_p = res_blk["expected_pitches"] + PIANO_MIN

            pred_phrase = np.zeros_like(f0_phrase)
            for i in range(len(crops)):
                p = exp_p[i]
                m1 = moving_average(p, 1.0 * FPS)
                m6 = moving_average(p, 6.0 * FPS)
                pred_phrase[i] = m1 - m6

            r_phrase = float(np.corrcoef(f0_phrase[voiced], pred_phrase[voiced])[0, 1])

            # Also 12-class chroma
            res_blk_chroma = train_eval_place_code(X_blk, chroma_bins, voiced, folds, num_bins=12, epochs=15, device=args.device)

            block_stat = {
                "block": li,
                "piano88_exact_acc": res_blk["exact_acc"],
                "piano88_within_1semi": res_blk["within_1semi_acc"],
                "chroma12_exact_acc": res_blk_chroma["exact_acc"],
                "chroma12_within_1semi": res_blk_chroma["within_1semi_acc"],
                "f0_phrase_pearson_r": r_phrase,
                "eval_time_s": round(time.time() - t0, 1)
            }
            results["sigmas"][s_tag]["blocks"].append(block_stat)
            print(f"  Block {li:02d}: Piano88 = {res_blk['exact_acc']*100:.1f}% (+/-1: {res_blk['within_1semi_acc']*100:.1f}%) | Chroma12 = {res_blk_chroma['exact_acc']*100:.1f}% | f0_phrase r = {r_phrase:+.3f} ({block_stat['eval_time_s']}s)")

            del blk_acts, X_blk

    # Check random-init control at sigma 0.5
    rand_dir = Path(args.random_acts_dir)
    if rand_dir.exists() and (rand_dir / f"{tag(crops[0], 0.5)}.blocks.npy").exists():
        print("\n--- STAGE 3: Random-Init Control at sigma=0.5 ---")
        mm_rand = [np.load(rand_dir / f"{tag(c, 0.5)}.blocks.npy", mmap_mode="r") for c in crops]
        num_blocks = mm_rand[0].shape[0]
        results["random_init"] = []
        for li in [0, 6, 12, 18, 23]:
            t0 = time.time()
            blk_acts = np.stack([np.asarray(m[li], dtype=np.float32).T for m in mm_rand])
            X_blk = extract_ctx(blk_acts, ctx=args.ctx)
            res_blk = train_eval_place_code(X_blk, midi_bins, voiced, folds, num_bins=88, epochs=15, device=args.device)
            res_blk_chroma = train_eval_place_code(X_blk, chroma_bins, voiced, folds, num_bins=12, epochs=15, device=args.device)
            stat = {
                "block": li,
                "piano88_exact_acc": res_blk["exact_acc"],
                "piano88_within_1semi": res_blk["within_1semi_acc"],
                "chroma12_exact_acc": res_blk_chroma["exact_acc"],
                "eval_time_s": round(time.time() - t0, 1)
            }
            results["random_init"].append(stat)
            print(f"  Random Block {li:02d}: Piano88 = {res_blk['exact_acc']*100:.1f}% | Chroma12 = {res_blk_chroma['exact_acc']*100:.1f}% ({stat['eval_time_s']}s)")
            del blk_acts, X_blk

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved calibrated probe results to {args.out_json}")

if __name__ == "__main__":
    main()
