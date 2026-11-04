#!/usr/bin/env python
"""melody_probe_map.py -- where does melody live inside the SA3 DiT? (KUANG 2026-11-04)

Extends the 2026-07-08 layer x feature map (docs/layer-feature-map.md) to MELODY, with the protocol of
"Does Physics Live in the Activations?" (2610.03154, papers/): ridge probes on every block's residual
stream at six noise levels, against controls the July map lacked.

The question it is built to answer: the lead f0 LatCH head (reads the noisy latent z_t) sets the pitch
DIRECTION over a whole clip (E4/E4b) but does not follow contours with periods of 5 s or less (D16). Is
phrase-rate contour readable somewhere inside the DiT where it is not readable from z_t? If so, an f0
head read from that block band is the fix, as the July map already recommended for rhythm.

Targets (per latent frame, 10.77 fps; f0 targets on voiced frames only, from the crop's TIMESERIES
companion: f0_other_ts = Melodia lead f0 on the separated stem, f0_other_voiced_ts):
  f0_semi    lead pitch in semitones (MIDI scale)
  f0_slow    10 s moving average (register drift; what E4b steers)
  f0_phrase  1 s average minus 6 s average (about 1-6 s periods: the band D16 fails on)
  f0_note    pitch minus its 1 s average (note-level detail)
  f0_delta   slope of the 0.5 s average over about 0.55 s (melodic direction)
  beat       beat_activation_ts, all frames: POSITIVE CONTROL (July map: 0.80 at block 14, sigma 0.5)
Readouts compared per sigma (all ridge, grouped 5-fold by artist, alpha picked on an inner split):
  blocks 0-23        the residual stream after each block (memory tokens stripped)
  x_t (ctx +-2)      the noisy input latent with +-2 frames of context: the linear input baseline
  z0 (ctx +-2)       the clean latent: the input ceiling
  f0 head            the existing lead f0 LatCH head on x_t (--f0-head), linearly calibrated per fold:
                     the NONLINEAR input baseline, the one that matters
  hpcp oracle        the crop's own 12-d HPCP: how much of each target pitch class alone explains
  random-init DiT    the same extraction on moment-matched random weights (--random-init run)
  permutation null   targets shuffled across crops, best block per sigma
Memory tokens: the mean over the 64 memory tokens per block is saved too, and probed for the window's
mean register (one value per crop: exploratory, n = crops).

Stages:
  extract  (GPU) --latent-dir --out-dir [--n-crops 160 --window 320 --f0-head CKPT --random-init]
  analyze  (CPU) --acts-dir [--random-acts-dir] --out-json
Sizes: 160 crops x 6 sigmas x 24 blocks x 320 frames x 1536 x fp16 = about 23 GB.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import numpy as np

FPS = 44100 / 4096
SIGMAS = (0.99, 0.909, 0.715, 0.5, 0.285, 0.137)       # the paper's grid, -40 .. +16 dB
F0_TARGETS = ("f0_semi", "f0_slow", "f0_phrase", "f0_note", "f0_delta")
CTX = 2


# ------------------------------------------------------------------------------------- targets

def hz_to_semitone(f):
    f = np.asarray(f, dtype=np.float64)
    return np.where(f > 0, 69.0 + 12.0 * np.log2(np.maximum(f, 1e-6) / 440.0), np.nan)


def moving_average(x, n):
    """Centered moving average with edge-normalized weights (no zero padding bias)."""
    n = max(1, int(round(n)))
    k = np.ones(n)
    num = np.convolve(x, k, mode="same")
    den = np.convolve(np.ones_like(x), k, mode="same")
    return num / den


def fill_unvoiced(semi):
    """Linear interpolation across unvoiced (nan) frames; edges hold the nearest voiced value."""
    s = np.asarray(semi, dtype=np.float64)
    ok = np.isfinite(s)
    if ok.sum() == 0:
        return np.zeros_like(s)
    idx = np.arange(len(s))
    return np.interp(idx, idx[ok], s[ok])


def f0_targets(f0_hz, voiced=None, fps=FPS):
    """Per-frame melodic targets for one window, and the voiced mask they are scored on."""
    semi = hz_to_semitone(f0_hz)
    v = np.isfinite(semi) if voiced is None else (np.asarray(voiced) > 0.5) & np.isfinite(semi)
    s = fill_unvoiced(np.where(v, semi, np.nan))
    ma = lambda sec: moving_average(s, sec * fps)
    m05, m1, m6, m10 = ma(0.5), ma(1.0), ma(6.0), ma(10.0)
    lag = max(1, int(round(0.275 * fps)))
    delta = np.zeros_like(s)
    delta[lag:-lag] = m05[2 * lag:] - m05[:-2 * lag]
    out = {"f0_semi": s, "f0_slow": m10, "f0_phrase": m1 - m6, "f0_note": s - m1, "f0_delta": delta}
    return out, v


def best_window(voiced, window, step=32):
    """Start of the window with the most voiced frames (deterministic)."""
    voiced = np.asarray(voiced, dtype=np.float64)
    if len(voiced) <= window:
        return 0
    c = np.concatenate([[0.0], np.cumsum(voiced)])
    starts = np.arange(0, len(voiced) - window + 1, step)
    return int(starts[np.argmax(c[starts + window] - c[starts])])


def with_context(z, ctx=CTX):
    """[C, T] -> [T, C*(2ctx+1)] by stacking shifted copies (edge-padded)."""
    z = np.asarray(z, dtype=np.float32)
    zp = np.pad(z, ((0, 0), (ctx, ctx)), mode="edge")
    T = z.shape[1]
    return np.concatenate([zp[:, i:i + T] for i in range(2 * ctx + 1)], axis=0).T


def artist_of(meta: dict) -> str:
    tn = meta.get("source_track", "") or meta.get("path", "")
    tn = os.path.basename(str(tn))
    return (tn.split(" - ")[0] if " - " in tn else tn).strip().lower() or "unknown"


# ---------------------------------------------------------------------------------------- ridge

def _standardize(Xtr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1.0
    return (Xtr - mu) / sd, (Xte - mu) / sd


def ridge_path(Xtr, Ytr, Xte, alphas):
    """Predictions for every alpha from one eigendecomposition. Y is centered on train."""
    Xtr, Xte = _standardize(np.asarray(Xtr, np.float64), np.asarray(Xte, np.float64))
    ym = Ytr.mean(0)
    Yc = Ytr - ym
    if Xtr.shape[0] >= Xtr.shape[1]:
        w, V = np.linalg.eigh(Xtr.T @ Xtr)
        XtY = V.T @ (Xtr.T @ Yc)
        P = Xte @ V
        return {a: P @ (XtY / (w + a)[:, None]) + ym for a in alphas}
    w, U = np.linalg.eigh(Xtr @ Xtr.T)                    # dual form when n < d
    UtY = U.T @ Yc
    K = Xte @ Xtr.T @ U
    return {a: K @ (UtY / (w + a)[:, None]) + ym for a in alphas}


def r2(y, p):
    y, p = np.asarray(y, np.float64), np.asarray(p, np.float64)
    if y.ndim == 1:
        y, p = y[:, None], p[:, None]
    ss = ((y - y.mean(0)) ** 2).sum(0)
    ok = ss > 1e-12
    if not ok.any():
        return 0.0
    return float(np.mean(1 - ((y - p) ** 2).sum(0)[ok] / ss[ok]))


def group_folds(groups, k=5, seed=0):
    """Assign whole groups to k folds, balancing sample counts (largest groups first)."""
    groups = np.asarray(groups)
    uniq, counts = np.unique(groups, return_counts=True)
    rng = np.random.default_rng(seed)
    order = np.lexsort((rng.random(len(uniq)), -counts))
    load = np.zeros(k)
    fold_of = {}
    for i in order:
        f = int(np.argmin(load))
        fold_of[uniq[i]] = f
        load[f] += counts[i]
    return np.array([fold_of[g] for g in groups])


ALPHAS = (1.0, 10.0, 100.0, 1e3, 1e4, 1e5)


def grouped_ridge_r2_multi(X, Y, groups, k=5, alphas=ALPHAS, seed=0):
    """Held-out R^2 per column of Y, whole groups held out. Alpha is chosen per column on an inner
    group split of each training fold; all columns share each fold's decomposition."""
    X, Y = np.asarray(X, np.float64), np.asarray(Y, np.float64)
    if Y.ndim == 1:
        Y = Y[:, None]
    groups = np.asarray(groups)
    folds = group_folds(groups, k, seed)
    preds = np.zeros_like(Y)
    for f in range(k):
        te, tr = folds == f, folds != f
        if te.sum() == 0 or tr.sum() == 0:
            continue
        inner = group_folds(groups[tr], 4, seed + 1 + f)
        itr, iva = inner != 0, inner == 0
        if iva.sum() and itr.sum():
            path = ridge_path(X[tr][itr], Y[tr][itr], X[tr][iva], alphas)
            best = [max(alphas, key=lambda a: r2(Y[tr][iva][:, j], path[a][:, j])) for j in range(Y.shape[1])]
        else:
            best = [alphas[len(alphas) // 2]] * Y.shape[1]
        outer = ridge_path(X[tr], Y[tr], X[te], sorted(set(best)))
        for j, a in enumerate(best):
            preds[te, j] = outer[a][:, j]
    return [r2(Y[:, j], preds[:, j]) for j in range(Y.shape[1])]


def grouped_ridge_r2(X, y, groups, k=5, alphas=ALPHAS, seed=0):
    return grouped_ridge_r2_multi(X, y, groups, k, alphas, seed)[0]


# --------------------------------------------------------------------------------------- extract

def get_blocks(cdm):
    for name, mod in cdm.model.named_modules():
        if name.endswith("transformer") and hasattr(mod, "layers"):
            return list(mod.layers)
    raise RuntimeError("could not locate the ContinuousTransformer with .layers")


def randomize_weights(module, seed=0):
    """Moment-matched random weights: every >=2-D tensor redrawn N(mean, std) of itself; 1-D tensors
    set to their own mean (gains stay about 1, biases about 0). The architecture and scales stay,
    the learned structure goes."""
    import torch
    g = torch.Generator(device="cpu").manual_seed(seed)
    with torch.no_grad():
        for p in module.parameters():
            if p.ndim >= 2:
                r = torch.randn(p.shape, generator=g) * p.float().std().cpu() + p.float().mean().cpu()
                p.copy_(r.to(p.device, p.dtype))
            else:
                p.fill_(float(p.float().mean()))


def extract_window(cdm, z, prompt, seconds_total, sigmas, eps_seed=7, f0_head=None):
    """One crop window through the DiT at each sigma. Returns per sigma: blocks [L, T, d] fp16,
    memory-token means [L, d] fp16, x_t [256, T] fp16, and the f0 head's prediction [T] (Hz) or None."""
    import torch
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    T = z.shape[-1]
    tensors = cdm.conditioner([{"prompt": prompt, "seconds_total": seconds_total}], str(device))
    tensors["inpaint_mask"] = [torch.zeros((1, 1, T), device=device)]
    tensors["inpaint_masked_input"] = [torch.zeros_like(z, device=device)]
    cond = {k: (v.type(mdtype) if torch.is_tensor(v) else v)
            for k, v in cdm.get_conditioning_inputs(tensors).items()}
    blocks = get_blocks(cdm)
    grabbed = {}

    def mk(i):
        def hook(_m, _inp, out):
            o = out[0] if isinstance(out, tuple) else out
            o = o[0]
            grabbed[i] = (o[-T:].detach().to(torch.float16).cpu(),
                          o[:-T].float().mean(0).to(torch.float16).cpu() if o.shape[0] > T
                          else torch.zeros(o.shape[-1], dtype=torch.float16))
        return hook

    hooks = [b.register_forward_hook(mk(i)) for i, b in enumerate(blocks)]
    out = {}
    try:
        g = torch.Generator(device="cpu").manual_seed(eps_seed)
        eps = torch.randn(z.shape, generator=g)
        for s in sigmas:
            x_t = ((1 - s) * z.float() + s * eps).to(device, mdtype)
            t = torch.full((1,), float(s), device=device, dtype=mdtype)
            grabbed.clear()
            with torch.no_grad():
                cdm.model(x_t, t, **cond)
                head = None
                if f0_head is not None:
                    hp = next(f0_head.parameters())
                    head = f0_head(x_t.to(hp.dtype), t.to(hp.dtype)).float()[0, 0].cpu().numpy()
            out[s] = {"blocks": torch.stack([grabbed[i][0] for i in range(len(blocks))]).numpy(),
                      "memory": torch.stack([grabbed[i][1] for i in range(len(blocks))]).numpy(),
                      "x_t": x_t[0].to(torch.float16).cpu().numpy(), "head": head}
    finally:
        for h in hooks:
            h.remove()
    return out


def pick_crops(latent_dir, n_crops, window, per_artist=3, min_voiced=0.3, seed=0):
    """Crops with a lead f0 companion, at most per_artist per artist, the window with the most voicing."""
    rng = np.random.default_rng(seed)
    by_artist = {}
    for jp in sorted(Path(latent_dir).glob("*.json")):
        stem = jp.stem
        npz = jp.with_name(stem + ".TIMESERIES.npz")
        if not npz.exists() or not jp.with_name(stem + ".npy").exists():
            continue
        by_artist.setdefault(artist_of(json.loads(jp.read_text())), []).append(stem)
    artists = sorted(by_artist)
    rng.shuffle(artists)
    picks = []
    for a in artists:
        stems = list(by_artist[a])
        rng.shuffle(stems)
        took = 0
        for stem in stems:
            if took >= per_artist or len(picks) >= n_crops:
                break
            with np.load(Path(latent_dir) / f"{stem}.TIMESERIES.npz") as d:
                if "f0_other_ts" not in d.files:
                    continue
                f0 = np.asarray(d["f0_other_ts"], dtype=np.float64)
                v = (np.asarray(d["f0_other_voiced_ts"]) > 0.5) if "f0_other_voiced_ts" in d.files else f0 > 0
            n = min(len(v), np.load(Path(latent_dir) / f"{stem}.npy", mmap_mode="r").shape[-1])
            if n < window:
                continue
            st = best_window(v[:n], window)
            if v[st:st + window].mean() < min_voiced:
                continue
            picks.append({"stem": stem, "artist": a, "start": st})
            took += 1
        if len(picks) >= n_crops:
            break
    return picks


def run_extract(args):
    import torch
    from stable_audio_3 import StableAudioModel
    args.out_dir.mkdir(parents=True, exist_ok=True)
    picks = pick_crops(args.latent_dir, args.n_crops, args.window, args.per_artist, args.min_voiced, args.seed)
    if not picks:
        raise SystemExit("no crops with f0_other_ts and enough voicing")
    print(f"[extract] {len(picks)} crops from {len({p['artist'] for p in picks})} artists", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device=args.device)
    cdm = model.model
    if args.random_init:
        randomize_weights(cdm.model, seed=args.seed)
        print("[extract] DiT weights randomized (moment-matched control)", flush=True)
    head = None
    if args.f0_head:
        from stable_audio_3.models.latch import load_latch_from_checkpoint
        head = load_latch_from_checkpoint(str(args.f0_head), device=args.device).eval()
    sigmas = [float(s) for s in args.sigmas.split(",")]
    man = {"sigmas": sigmas, "window": args.window, "fps": FPS, "random_init": args.random_init,
           "eps_seed": "seed * 100003 + 7 + crop index (one draw per crop, shared across sigmas)",
           "f0_head": str(args.f0_head) if args.f0_head else None, "crops": []}
    t_all = time.time()
    for ci, p in enumerate(picks):
        stem, st = p["stem"], p["start"]
        z = np.load(Path(args.latent_dir) / f"{stem}.npy")
        z = z[0] if z.ndim == 3 else z
        zw = torch.tensor(z[:, st:st + args.window], dtype=torch.float32)[None]
        meta = json.loads((Path(args.latent_dir) / f"{stem}.json").read_text())
        # one noise draw per crop: a draw shared by every crop is identical at each frame position, and a
        # probe can see through it (the July extractor shared seed 7 across crops)
        res = extract_window(cdm, zw, meta.get("prompt", ""), args.window / FPS, sigmas,
                             eps_seed=args.seed * 100003 + 7 + ci, f0_head=head)
        for s, r in res.items():
            tag = f"{stem}__s{int(round(s * 1000)):04d}"
            np.save(args.out_dir / f"{tag}.blocks.npy", r["blocks"])
            np.save(args.out_dir / f"{tag}.memory.npy", r["memory"])
            np.save(args.out_dir / f"{tag}.xt.npy", r["x_t"])
            if r["head"] is not None:
                np.save(args.out_dir / f"{tag}.head.npy", r["head"].astype(np.float32))
        np.save(args.out_dir / f"{stem}.z0.npy", zw[0].numpy().astype(np.float16))
        man["crops"].append(p)
        if ci % 10 == 0:
            print(f"[extract] {ci + 1}/{len(picks)} {stem} ({time.time() - t_all:.0f} s)", flush=True)
        (args.out_dir / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"[extract] done in {(time.time() - t_all) / 60:.1f} min -> {args.out_dir}", flush=True)


# --------------------------------------------------------------------------------------- analyze

def load_crop_targets(latent_dir, crop, window):
    with np.load(Path(latent_dir) / f"{crop['stem']}.TIMESERIES.npz") as d:
        sl = slice(crop["start"], crop["start"] + window)
        f0 = np.asarray(d["f0_other_ts"], dtype=np.float64)[sl]
        v = np.asarray(d["f0_other_voiced_ts"])[sl] if "f0_other_voiced_ts" in d.files else (f0 > 0)
        beat = np.asarray(d["beat_activation_ts"], dtype=np.float64)[sl] if "beat_activation_ts" in d.files else None
        hpcp = np.asarray(d["hpcp_ts"], dtype=np.float64)[sl] if "hpcp_ts" in d.files else None
    tg, voiced = f0_targets(f0, v)
    return tg, voiced, beat, hpcp


def analyze(acts_dir, latent_dir, sigmas=None, random_dir=None, n_null=3, stride=1, log=print):
    man = json.loads((Path(acts_dir) / "manifest.json").read_text())
    sigmas = sigmas or man["sigmas"]
    W = man["window"]
    crops = man["crops"]
    data = [load_crop_targets(latent_dir, c, W) for c in crops]
    fr = np.arange(0, W, stride)
    vmask = np.concatenate([d[1][fr] for d in data])
    groups_all = np.concatenate([[c["artist"]] * len(fr) for c in crops])
    crop_id = np.concatenate([[i] * len(fr) for i in range(len(crops))])
    Yf0 = np.stack([np.concatenate([d[0][k][fr] for d in data]) for k in F0_TARGETS], 1)
    has_beat = all(d[2] is not None for d in data)
    beat = np.concatenate([d[2][fr] for d in data]) if has_beat else None
    has_hpcp = all(d[3] is not None for d in data)
    hpcp = np.concatenate([d[3][fr] for d in data]) if has_hpcp else None
    gv = groups_all[vmask]
    Yv = Yf0[vmask]

    def score_f0(X):
        return dict(zip(F0_TARGETS, grouped_ridge_r2_multi(X[vmask], Yv, gv)))

    def score_all(X):
        out = score_f0(X)
        if beat is not None:
            out["beat"] = grouped_ridge_r2(X, beat, groups_all)
        return out

    def tag(c, s):
        return f"{c['stem']}__s{int(round(s * 1000)):04d}"

    res = {"n_crops": len(crops), "n_artists": len(set(c["artist"] for c in crops)),
           "n_voiced_frames": int(vmask.sum()), "window": W, "stride": stride, "sigmas": {}}
    if hpcp is not None:
        res["hpcp_oracle"] = score_f0(hpcp)
    z0 = np.concatenate([with_context(np.load(Path(acts_dir) / f"{c['stem']}.z0.npy"))[fr] for c in crops])
    res["z0_ctx"] = score_all(z0)
    del z0
    reg = np.array([np.nanmean(np.where(d[1], d[0]["f0_semi"], np.nan)) for d in data])
    for s in sigmas:
        t0 = time.time()
        row = {}
        xt = np.concatenate([with_context(np.load(Path(acts_dir) / f"{tag(c, s)}.xt.npy"))[fr] for c in crops])
        row["x_t_ctx"] = score_all(xt)
        del xt
        hp = [Path(acts_dir) / f"{tag(c, s)}.head.npy" for c in crops]
        if all(p.exists() for p in hp):
            # the head's own semitone curve and its 1/6/10 s averages, per crop, so a linear
            # calibration can rebuild every contour band from what the head predicts
            feats = []
            for p in hp:
                hs = np.nan_to_num(hz_to_semitone(np.maximum(np.load(p), 1e-3)))
                feats.append(np.stack([hs] + [moving_average(hs, sec * FPS) for sec in (1.0, 6.0, 10.0)], 1)[fr])
            row["f0_head"] = score_f0(np.concatenate(feats))
        mm = [np.load(Path(acts_dir) / f"{tag(c, s)}.blocks.npy", mmap_mode="r") for c in crops]
        L = mm[0].shape[0]
        per_block = []
        for li in range(L):
            X = np.concatenate([np.asarray(m[li], dtype=np.float32)[fr] for m in mm])
            per_block.append(score_all(X))
            del X
        row["blocks"] = per_block
        keys = list(per_block[0])
        row["best_block"] = {k: int(np.argmax([b[k] for b in per_block])) for k in keys}
        if n_null:
            # whole-window targets permuted across crops, scored on each activation crop's own
            # voiced frames: what the best block "explains" when the pairing is broken
            nulls = {}
            rng = np.random.default_rng(0)
            for k in ("f0_phrase", "f0_slow"):
                X = np.concatenate([np.asarray(m[row["best_block"][k]], dtype=np.float32)[fr] for m in mm])
                vals = []
                for _ in range(n_null):
                    perm = rng.permutation(len(crops))
                    Yp = np.concatenate([data[j][0][k][fr] for j in perm])
                    vals.append(grouped_ridge_r2(X[vmask], Yp[vmask], gv))
                nulls[k] = float(np.mean(vals))
            row["null"] = nulls
        mem = np.stack([np.load(Path(acts_dir) / f"{tag(c, s)}.memory.npy").astype(np.float32) for c in crops])
        fmean = np.stack([np.asarray(m, dtype=np.float32).mean(1) for m in mm])     # [crops, L, d]
        cg = np.array([c["artist"] for c in crops])
        ok = np.isfinite(reg)
        row["register_per_crop"] = {
            "memory_tokens": [grouped_ridge_r2(mem[ok, li], reg[ok], cg[ok]) for li in range(L)],
            "frame_mean": [grouped_ridge_r2(fmean[ok, li], reg[ok], cg[ok]) for li in range(L)]}
        res["sigmas"][str(s)] = row
        log(f"[analyze] sigma {s}: best blocks {row['best_block']}  ({time.time() - t0:.0f} s)")
    if random_dir is not None:
        rman = json.loads((Path(random_dir) / "manifest.json").read_text())
        if [c["stem"] for c in rman["crops"]] == [c["stem"] for c in crops]:
            rnd = {}
            for s in sigmas:
                if not any(abs(s - r) < 1e-9 for r in rman["sigmas"]):
                    continue                                    # the control may cover fewer sigmas
                mm = [np.load(Path(random_dir) / f"{tag(c, s)}.blocks.npy", mmap_mode="r") for c in crops]
                rnd[str(s)] = [score_f0(np.concatenate([np.asarray(m[li], dtype=np.float32)[fr] for m in mm]))
                               for li in range(mm[0].shape[0])]
            res["random_init"] = rnd
        else:
            res["random_init"] = "skipped: the random-init run used different crops"
    return res


def summary_markdown(res) -> str:
    lines = ["# Melody probe map", "",
             f"{res['n_crops']} crops, {res['n_artists']} artists, {res['n_voiced_frames']} voiced frames, "
             f"window {res['window']} frames; ridge R^2, folds grouped by artist.", "",
             "| sigma | target | best block (R^2) | x_t ctx | f0 head | z0 ctx | hpcp oracle | random-init best | null |",
             "|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.3f}"
    for s, row in res["sigmas"].items():
        for k in list(F0_TARGETS) + (["beat"] if "beat" in row["best_block"] else []):
            b = row["best_block"][k]
            rnd = res.get("random_init")
            rb = (max(x[k] for x in rnd[s]) if isinstance(rnd, dict) and s in rnd and k in rnd[s][0] else None)
            lines.append(f"| {s} | {k} | {b} ({f(row['blocks'][b][k])}) | {f(row['x_t_ctx'].get(k))} | "
                         f"{f(row.get('f0_head', {}).get(k))} | {f(res['z0_ctx'].get(k))} | "
                         f"{f(res.get('hpcp_oracle', {}).get(k))} | {f(rb)} | {f(row.get('null', {}).get(k))} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--latent-dir", type=Path, required=True)
    e.add_argument("--out-dir", type=Path, required=True)
    e.add_argument("--n-crops", type=int, default=160)
    e.add_argument("--window", type=int, default=320, help="contiguous latent frames per crop (320 = 29.7 s)")
    e.add_argument("--per-artist", type=int, default=3)
    e.add_argument("--min-voiced", type=float, default=0.3)
    e.add_argument("--sigmas", default=",".join(map(str, SIGMAS)))
    e.add_argument("--f0-head", type=Path, default=None, help="lead f0 LatCH head checkpoint (baseline)")
    e.add_argument("--random-init", action="store_true", help="moment-matched random DiT weights (control)")
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--device", default="cuda")
    a = sub.add_parser("analyze")
    a.add_argument("--acts-dir", type=Path, required=True)
    a.add_argument("--latent-dir", type=Path, required=True)
    a.add_argument("--random-acts-dir", type=Path, default=None)
    a.add_argument("--out-json", type=Path, required=True)
    a.add_argument("--stride", type=int, default=1, help="frame stride for the probes (2 halves the CPU time)")
    a.add_argument("--n-null", type=int, default=3)
    args = ap.parse_args()
    os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
    if args.cmd == "extract":
        run_extract(args)
    else:
        res = analyze(args.acts_dir, args.latent_dir, random_dir=args.random_acts_dir,
                      n_null=args.n_null, stride=args.stride, log=lambda m: print(m, flush=True))
        args.out_json.write_text(json.dumps(res, indent=1))
        args.out_json.with_suffix(".md").write_text(summary_markdown(res))
        print(f"[analyze] -> {args.out_json} and {args.out_json.with_suffix('.md')}")


if __name__ == "__main__":
    main()
