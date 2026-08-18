#!/usr/bin/env python3
"""task_vector_gram.py — put many DoRA/LoRA checkpoints of the SAME base into one Gram matrix
and read off, without any rendering, whether a degraded family differs from a healthy one by a
SHARED direction (a spike: repairable by projecting it out) or by INDEPENDENT wandering
(diffusion: repairable only by averaging over the run).

WHY THIS AND NOT PER-WEIGHT OUTLIERS (C, 2026-08-18, Kim's eigendirection idea). A DiT's function
is invariant to rotations inside QK^T, permutations of MLP units, etc., so "this scalar weight is
an outlier" is not a coordinate-free statement — a gauge change moves the outliers around without
changing the function. Anything about a PATHOLOGY has to live in invariants: inner products of
task vectors, singular spectra, subspace angles. This tool computes the invariants.

WHY IT IS MEANINGFUL AT ALL. Independently trained networks cannot be compared in weight space
(permutation gauge). Deltas from a SHARED base at small LR stay in one basin and the base fixes
the coordinates — the exact condition under which task-vector arithmetic and model soups work.
Every checkpoint here is a fine-tune of `medium-base`, so <ΔW_i, ΔW_j> is a real number about
the two runs, not an artifact of coordinates.

WHAT IT MEASURES, per adapted matrix and summed over the model / per site / per block:
  G[i,j] = <ΔW_eff_i, ΔW_eff_j>_F      ΔW_eff = magnitude ⊙ rownorm(W_base + B·A) − W_base
                                        (dora_layer_delta_profile.py's exact formula; plain LoRA
                                        when no magnitude tensor)
  From G alone:  norms, all pairwise cosines, within-good / within-bad / cross mean cosines,
  cosine of each model to the good CONSENSUS (mean of the good set, leave-one-out for members),
  and — for a checkpoint ladder of ONE run — successive-step cosines and path efficiency
  (net / path), which is exactly checkpoint_trajectory_stats' number and is used here as the
  built-in validation: the raw-trainable Gram must reproduce it.
  Also, cheaply, per model: the DoRA magnitude vector is per-row and gauge-fixed, so THERE a
  scalar-outlier read is legitimate — |m/‖W_row‖ − 1| distribution and its extreme rows.

HOW TO READ THE VERDICT
  bad-bad cosine HIGH, bad-good LOW  -> the bad arms share a direction the good arms do not:
                                        a common pathology (spike). Eigen-repair / projection
                                        is the right tool and needs only the terminal ckpt.
  bad-bad cosine ~0, bad-good ~0     -> each bad arm wandered its own way: diffusion. No single
                                        direction to remove; the repair is a TEMPORAL soup over
                                        the run's ladder (needs the ladder pulled from LUMI).
  good-good HIGH                     -> sanity: healthy runs on one corpus learn a shared thing.

USAGE
  .venv/bin/python eval/task_vector_gram.py --out DIR \
      --ckpt good:bf16cmp_goa_ep7=/path/epoch=7-...weights.ckpt \
      --ckpt bad:adamw_goa_bs1=/path/epoch=9-step=54000.ckpt  ...
      [--ladder good:bf16cmp_goa=/dir/of/epoch=*.weights.ckpt]   (adds every epoch, in order)
Labels are '<group>:<name>'; group is 'good' | 'bad' | anything else (reported, not pooled).
CPU-only; checkpoints are mmap'd and only the adapter tensors are touched.
"""
import argparse
import collections
import glob
import json
import math
import os
import re
import sys
import time

# Thread cap BEFORE torch import: many small matmuls/QRs on 24 cores otherwise fan out to ~70
# spinning threads and the run crawls at 1300% CPU doing nothing (measured 2026-08-18; the same
# oversubscription trap as MASTER §5's control-training freeze). 4 is plenty for these shapes.
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import torch  # noqa: E402

BASE_ST = glob.glob("/home/kim/.cache/huggingface/hub/models--stabilityai--"
                    "stable-audio-3-medium-base/snapshots/*/model.safetensors")

SITE_RE = [("q", r"\.to_q\."), ("k", r"\.to_k\."), ("v", r"\.to_v\."), ("out", r"\.to_out\."),
           ("ff_in", r"\.ff\..*(0|1|in|proj_in)\.|linear_in|\.ff\.0"), ("ff_out", r"\.ff\..*(2|out|proj_out)\.|linear_out|\.ff\.2"),
           ("cross_q", r"cross_attn.*to_q"), ("cross_kv", r"cross_attn.*to_(k|v)")]


# ---------------------------------------------------------------------------------------------
# pure functions (tested)
# ---------------------------------------------------------------------------------------------

def dora_delta_eff(W, A, B, magnitude, scaling=1.0):
    """ΔW_eff for one matrix. magnitude None -> plain LoRA (ΔW = scaling·B·A)."""
    W2 = W.reshape(W.shape[0], -1)
    V = W2 + scaling * (B @ A)
    if magnitude is None:
        return V - W2
    Vh = V / (V.norm(dim=1, keepdim=True) + 1e-12)
    return Vh * magnitude.reshape(-1, 1) - W2


def gram_from_vectors(X):
    """X: (K, D) -> (K, K) Gram in float64."""
    X = X.double()
    return X @ X.T


def ladder_stats_from_gram(G, idx):
    """For checkpoints idx[0..n] of ONE run (in training order), successive-step cosines and
    path efficiency = |X_n − X_0| / Σ|X_e − X_{e−1}|, all from inner products:
        <X_a − X_b, X_c − X_d> = G[a,c] − G[a,d] − G[b,c] + G[b,d]."""
    def ip(a, b, c, d):
        return float(G[a, c] - G[a, d] - G[b, c] + G[b, d])
    steps = [(idx[e], idx[e - 1]) for e in range(1, len(idx))]
    lens = [math.sqrt(max(ip(a, b, a, b), 0.0)) for a, b in steps]
    net = math.sqrt(max(ip(idx[-1], idx[0], idx[-1], idx[0]), 0.0))
    coss = []
    for (a, b), (c, d), la, lc in zip(steps[:-1], steps[1:], lens[:-1], lens[1:]):
        coss.append(ip(a, b, c, d) / (la * lc) if la > 0 and lc > 0 else float("nan"))
    return {"path_efficiency": net / sum(lens) if sum(lens) > 0 else float("nan"),
            "step_cosines": coss, "step_lengths": lens, "net": net}


def cos_matrix(G):
    n = torch.sqrt(torch.diag(G)).clamp_min(1e-30)
    return G / (n[:, None] * n[None, :])


def group_cosines(G, good_idx, bad_idx):
    C = cos_matrix(G)
    def mean_pairs(I, J, same):
        vals = [float(C[i, j]) for i in I for j in J if (i < j if same else True)]
        return sum(vals) / len(vals) if vals else float("nan")
    return {"good_good": mean_pairs(good_idx, good_idx, True),
            "bad_bad": mean_pairs(bad_idx, bad_idx, True),
            "bad_good": mean_pairs(bad_idx, good_idx, False)}


def consensus_cosines(G, good_idx):
    """cos(model_k, mean of good set), leave-one-out when k is itself good. Model Stock's
    'angle to the center' — one number per model. From G: <x_k, mean_S> = mean_j G[k,j];
    |mean_S|² = mean over (i,j in S) G[i,j]."""
    out = {}
    for k in range(G.shape[0]):
        S = [j for j in good_idx if j != k]
        if not S:
            out[k] = float("nan"); continue
        num = sum(float(G[k, j]) for j in S) / len(S)
        den = math.sqrt(sum(float(G[i, j]) for i in S for j in S)) / len(S) * math.sqrt(float(G[k, k]))
        out[k] = num / den if den > 0 else float("nan")
    return out


# ---------------------------------------------------------------------------------------------
# checkpoint plumbing
# ---------------------------------------------------------------------------------------------

CACHE_DIR = os.environ.get("TVG_CACHE", "/home/kim/Projects/SAO/.cache/task_vector_factors")


def load_adapter(path, name):
    """Adapter factors of ONE checkpoint as on-disk fp32 memmaps on the NVMe, one memmap set per
    (A-shape, B-shape) class — the DiT adapts several: 1536-square self-attn, 768-input cross-attn
    K/V, 1536<->6144 FF — plus the ordered key list. Built once per checkpoint, reused by every later
    tool that needs ΔW_eff (SVD / consensus subspace / repair).

    Why on disk and not in RAM (2026-08-18): the in-RAM version held 23 checkpoints' factors
    (~360 MB each fp32) plus per-matrix stacks and was OOM-killed at 16 GB anon RSS on a box
    another instance had at 73 GB used. Why NOT mmap views into the .ckpt zip: every later
    per-matrix access is a random page-fault on a removable drive (measured 17 s for 6 matrices
    with 3 s of CPU). One sequential read per checkpoint into contiguous caches is both.
    Returns dict(keys=[prefix...], cfg, get=lambda i: (A_i, B_i, m_i|None) as torch tensors)."""
    import numpy as np
    d = os.path.join(CACHE_DIR, name)
    meta_p = os.path.join(d, "meta.json")
    meta = None
    if os.path.exists(meta_p):
        meta = json.load(open(meta_p))
        if not (meta.get("src") == os.path.abspath(path)
                and meta.get("src_mtime") == os.path.getmtime(path)):
            meta = None
    if meta is None:
        ck = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
        sd = ck.get("state_dict", ck)
        cfg = ck.get("lora_config") or {}
        groups = collections.defaultdict(dict)
        for k, v in sd.items():
            mm = re.match(r"(.*)\.(lora_A|lora_B|magnitude)$", k)
            if mm:
                groups[mm.group(1)][mm.group(2)] = v
        allk = sorted(p for p, parts in groups.items() if {"lora_A", "lora_B"} <= parts.keys())
        if not allk:
            sys.exit(f"[gram] no lora_A/lora_B tensors in {path}")
        classes = collections.OrderedDict()
        for k in allk:
            sig = (tuple(groups[k]["lora_A"].shape), tuple(groups[k]["lora_B"].shape),
                   "magnitude" in groups[k])
            classes.setdefault(sig, []).append(k)
        os.makedirs(d, exist_ok=True)
        cls_meta = []
        for ci, (sig, ks) in enumerate(classes.items()):
            a_shape, b_shape, has_m = sig
            A = np.lib.format.open_memmap(os.path.join(d, f"A_{ci}.npy"), mode="w+", dtype=np.float32, shape=(len(ks),) + a_shape)
            B = np.lib.format.open_memmap(os.path.join(d, f"B_{ci}.npy"), mode="w+", dtype=np.float32, shape=(len(ks),) + b_shape)
            M = (np.lib.format.open_memmap(os.path.join(d, f"m_{ci}.npy"), mode="w+", dtype=np.float32, shape=(len(ks), b_shape[0]))
                 if has_m else None)
            for i, k in enumerate(ks):
                A[i] = groups[k]["lora_A"].float().numpy()
                B[i] = groups[k]["lora_B"].float().numpy()
                if has_m:
                    M[i] = groups[k]["magnitude"].float().numpy()
            A.flush(); B.flush()
            if M is not None:
                M.flush()
            cls_meta.append({"a_shape": list(a_shape), "b_shape": list(b_shape), "has_m": has_m, "keys": ks})
        del ck, sd, groups
        meta = {"src": os.path.abspath(path), "src_mtime": os.path.getmtime(path), "cfg": cfg,
                "classes": cls_meta}
        json.dump(meta, open(meta_p, "w"))
    # open memmaps + build the flat index
    mms, keys, where = [], [], []
    for ci, c in enumerate(meta["classes"]):
        A = np.load(os.path.join(d, f"A_{ci}.npy"), mmap_mode="r")
        B = np.load(os.path.join(d, f"B_{ci}.npy"), mmap_mode="r")
        M = np.load(os.path.join(d, f"m_{ci}.npy"), mmap_mode="r") if c["has_m"] else None
        mms.append((A, B, M))
        for i, k in enumerate(c["keys"]):
            keys.append(k); where.append((ci, i))

    def get(i):
        ci, j = where[i]
        A, B, M = mms[ci]
        return (torch.from_numpy(np.array(A[j])), torch.from_numpy(np.array(B[j])),
                torch.from_numpy(np.array(M[j])) if M is not None else None)
    return {"keys": keys, "cfg": meta["cfg"], "get": get}


def base_key_for(prefix, base_keys):
    """Adapter prefix -> base safetensors key. The DiT matrices are 'model.<...>.weight'; the
    LoRA'd conditioner lives under 'conditioner.<...>' in the base (not 'model.')."""
    stem = prefix.replace(".parametrizations.weight.0", "")
    for cand in ("model." + stem + ".weight",
                 "conditioner." + stem + ".weight",
                 stem + ".weight"):
        if cand in base_keys:
            return cand
    return None


def site_of(key):
    for name, pat in SITE_RE:
        if re.search(pat, key):
            return name
    return "other"


def block_of(key):
    m = re.search(r"layers\.(\d+)\.", key)
    return int(m.group(1)) if m else -1


def parse_models(args):
    """-> list of (group, name, path) in the order given; ladders expand to every epoch."""
    models = []
    for spec in args.ckpt or []:
        lab, path = spec.split("=", 1)
        grp, name = lab.split(":", 1)
        hits = sorted(glob.glob(path))
        if len(hits) != 1:
            sys.exit(f"[gram] --ckpt {lab}: pattern must resolve to exactly one file, got "
                     f"{len(hits)}: {path}")
        models.append((grp, name, hits[0]))
    for spec in args.ladder or []:
        lab, pat = spec.split("=", 1)
        grp, name = lab.split(":", 1)
        paths = sorted(glob.glob(pat), key=lambda p: int(re.search(r"epoch=(\d+)", p).group(1)))
        if not paths:
            sys.exit(f"[gram] ladder pattern matched nothing: {pat}")
        for p in paths:
            ep = int(re.search(r"epoch=(\d+)", p).group(1))
            models.append((grp, f"{name}_ep{ep}", p))
    if not models:
        sys.exit("[gram] give at least one --ckpt or --ladder")
    return models


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", action="append", help="group:name=path")
    ap.add_argument("--ladder", action="append",
                    help="group:name=glob over epoch=*.ckpt of ONE run (adds every epoch)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--alpha", type=float, default=None,
                    help="lora_alpha; default = rank (scaling 1, our alpha=rank convention)")
    ap.add_argument("--limit-keys", type=int, default=0, help="debug: only first N matrices")
    a = ap.parse_args()
    if not BASE_ST:
        sys.exit("[gram] medium-base safetensors not in the HF cache")
    from safetensors import safe_open

    models = parse_models(a)
    K = len(models)
    names = [f"{g}:{n}" for g, n, _ in models]
    good_idx = [i for i, (g, _, _) in enumerate(models) if g == "good"]
    bad_idx = [i for i, (g, _, _) in enumerate(models) if g == "bad"]
    print(f"[gram] {K} checkpoints: {len(good_idx)} good, {len(bad_idx)} bad, "
          f"{K - len(good_idx) - len(bad_idx)} other", flush=True)

    t0 = time.time()
    adapters, cfgs = [], []
    for g, n, p in models:
        ad = load_adapter(p, f"{g}__{n}")
        adapters.append(ad); cfgs.append(ad["cfg"])
        cfg = ad["cfg"]
        print(f"  {g}:{n:<28} rank={cfg.get('rank')} alpha={cfg.get('alpha')} "
              f"type={cfg.get('adapter_type')} matrices={len(ad['keys'])}  ({time.time()-t0:.0f}s)",
              flush=True)
    keys = list(adapters[0]["keys"])
    for ad in adapters[1:]:
        if list(ad["keys"]) != keys:
            sys.exit("[gram] checkpoints do not adapt the same matrices; refusing to compare")
    kidx = list(range(len(keys)))
    if a.limit_keys:
        kidx = kidx[:a.limit_keys]
    print(f"[gram] {len(kidx)} adapted matrices common to all; loading base once per matrix",
          flush=True)

    G_eff = torch.zeros(K, K, dtype=torch.float64)      # ΔW_eff
    G_raw = torch.zeros(K, K, dtype=torch.float64)      # raw trainable (A,B,m) — validation
    G_site = collections.defaultdict(lambda: torch.zeros(K, K, dtype=torch.float64))
    G_block = collections.defaultdict(lambda: torch.zeros(K, K, dtype=torch.float64))
    mag_rel = [[] for _ in range(K)]                    # per model: (m/‖W_row‖ − 1) over rows
    ba_top1 = [[] for _ in range(K)]                    # per model: σ1²/Σσ² of B·A per matrix
    ba_erank = [[] for _ in range(K)]
    unresolved = []
    with safe_open(BASE_ST[0], framework="pt") as f:
        base_keys = set(f.keys())
        for ki in kidx:
            prefix = keys[ki]
            base_key = base_key_for(prefix, base_keys)
            if base_key is None:
                unresolved.append(prefix); continue
            W = f.get_tensor(base_key).float()
            W2 = W.reshape(W.shape[0], -1)
            wrow = W2.norm(dim=1)
            D, R = [], []
            for k in range(K):
                A, B, m = adapters[k]["get"](ki)
                sc = (a.alpha / B.shape[1]) if a.alpha else 1.0
                D.append(dora_delta_eff(W2, A, B, m, sc).reshape(-1))
                R.append(torch.cat([A.reshape(-1), B.reshape(-1)] + ([m] if m is not None else [])))
                if m is not None:
                    mag_rel[k].append((m / (wrow + 1e-12) - 1.0))
                # spectrum of B·A via the r×r problem: σ(BA) = σ(R_B R_A^T)
                Qb, Rb = torch.linalg.qr(B); Qa, Ra = torch.linalg.qr(A.T)
                s = torch.linalg.svdvals(Rb @ Ra.T)
                s2 = s * s
                if s2.sum() > 0:
                    ba_top1[k].append(float(s2[0] / s2.sum()))
                    ba_erank[k].append(float(s.sum() ** 2 / s2.sum()))
            Dm = torch.stack(D); Rm = torch.stack(R)
            g = gram_from_vectors(Dm)
            G_eff += g; G_raw += gram_from_vectors(Rm)
            G_site[site_of(prefix)] += g; G_block[block_of(prefix)] += g
            if (ki + 1) % 40 == 0:
                print(f"  {ki+1}/{len(kidx)}  {time.time()-t0:.0f}s", flush=True)
    print(f"[gram] done in {time.time()-t0:.0f}s; unresolved {len(unresolved)}", flush=True)

    os.makedirs(a.out, exist_ok=True)
    C = cos_matrix(G_eff)
    norms = torch.sqrt(torch.diag(G_eff))
    cons = consensus_cosines(G_eff, good_idx)
    grp = group_cosines(G_eff, good_idx, bad_idx)

    # ---- report -----------------------------------------------------------------------------
    L = []
    P = L.append
    P(f"task-vector Gram over {K} checkpoints, {len(kidx)} matrices, ΔW_eff (DoRA-exact)\n")
    P(f"{'model':<34} {'‖ΔW_eff‖':>9} {'cos→good-consensus':>19}  {'mag |m/‖w‖-1|: med / p99 / max':>34}  {'BA top1-frac med':>16} {'eff-rank med':>12}")
    P("-" * 132)
    for k in range(K):
        mr = torch.cat(mag_rel[k]).abs() if mag_rel[k] else None
        ms = (f"{mr.median():.4f} / {torch.quantile(mr, 0.99):.4f} / {mr.max():.4f}" if mr is not None else "-")
        t1 = sorted(ba_top1[k]); er = sorted(ba_erank[k])
        P(f"{names[k]:<34} {float(norms[k]):>9.2f} {cons[k]:>19.3f}  {ms:>34}  "
          f"{(t1[len(t1)//2] if t1 else float('nan')):>16.3f} {(er[len(er)//2] if er else float('nan')):>12.1f}")
    P("")
    P(f"mean pairwise cosine (ΔW_eff):  good-good {grp['good_good']:.3f}   bad-bad {grp['bad_bad']:.3f}   "
      f"bad-good {grp['bad_good']:.3f}")
    P("  spike hypothesis  -> bad-bad HIGH, bad-good LOW.   diffusion hypothesis -> bad-bad ≈ 0 ≈ bad-good.")
    P("")
    P("cosine matrix (ΔW_eff):")
    hdr = " " * 30 + " ".join(f"{i:>5d}" for i in range(K))
    P(hdr)
    for i in range(K):
        P(f"{i:>2d} {names[i][:26]:<26} " + " ".join(f"{float(C[i,j]):>5.2f}" for j in range(K)))
    P("")
    P("per site — mean cosines and share of total ‖ΔW_eff‖²:")
    tot = float(torch.diag(G_eff).sum())
    for s, Gs in sorted(G_site.items(), key=lambda kv: -float(torch.diag(kv[1]).sum())):
        gs = group_cosines(Gs, good_idx, bad_idx)
        share_good = (sum(float(Gs[i, i]) for i in good_idx) / max(sum(float(G_eff[i, i]) for i in good_idx), 1e-30)) if good_idx else float("nan")
        share_bad = (sum(float(Gs[i, i]) for i in bad_idx) / max(sum(float(G_eff[i, i]) for i in bad_idx), 1e-30)) if bad_idx else float("nan")
        P(f"  {s:<9} good-good {gs['good_good']:>6.3f}  bad-bad {gs['bad_bad']:>6.3f}  bad-good {gs['bad_good']:>6.3f}"
          f"   energy share: good {share_good:>6.1%}  bad {share_bad:>6.1%}")
    P("")
    P("per block — bad-good cosine and bad/good energy ratio (where does the bad delta go?):")
    for b in sorted(k for k in G_block if k >= 0):
        Gb = G_block[b]; gb = group_cosines(Gb, good_idx, bad_idx)
        eg = sum(float(Gb[i, i]) for i in good_idx) / max(len(good_idx), 1)
        eb = sum(float(Gb[i, i]) for i in bad_idx) / max(len(bad_idx), 1)
        bar = "#" * int(min(60, 20 * (eb / eg if eg > 0 else 0)))
        P(f"  L{b:02d}  bad-good cos {gb['bad_good']:>6.3f}   bad/good energy {eb/eg if eg>0 else float('nan'):>5.2f}  {bar}")
    if -1 in G_block:
        Gb = G_block[-1]; gb = group_cosines(Gb, good_idx, bad_idx)
        P(f"  non-block sites: bad-good cos {gb['bad_good']:.3f}")

    # ---- ladders: successive-step cosines + path efficiency, ΔW_eff AND raw (validation) ----
    ladders = collections.defaultdict(list)
    for i, (g, n, _) in enumerate(models):
        m = re.match(r"(.*)_ep(\d+)$", n)
        if m:
            ladders[(g, m.group(1))].append((int(m.group(2)), i))
    lad_out = {}
    if ladders:
        P("")
        P("checkpoint ladders (one run each): successive-step cosines, path efficiency")
        P("  raw-trainable eff must match checkpoint_trajectory_stats' number for the run — that is the")
        P("  built-in validation of this whole pipeline; ΔW_eff is the same trajectory seen through the base.")
        for (g, n), lst in ladders.items():
            idx = [i for _, i in sorted(lst)]
            if len(idx) < 3:
                continue
            se = ladder_stats_from_gram(G_eff, idx); sr = ladder_stats_from_gram(G_raw, idx)
            n_steps = len(idx) - 1
            P(f"  {g}:{n}  ({len(idx)} ckpts)  eff ΔW_eff {se['path_efficiency']:.3f}   eff raw {sr['path_efficiency']:.3f}"
              f"   random-walk floor 1/√{n_steps} = {1/math.sqrt(n_steps):.3f}")
            P(f"     step cos (ΔW_eff): " + " ".join(f"{c:+.2f}" for c in se["step_cosines"]))
            P(f"     step len (ΔW_eff): " + " ".join(f"{c:.1f}" for c in se["step_lengths"]))
            lad_out[f"{g}:{n}"] = {"eff_dweff": se["path_efficiency"], "eff_raw": sr["path_efficiency"],
                                    "step_cos_dweff": se["step_cosines"], "step_len_dweff": se["step_lengths"]}

    P("")
    P("These are weight-space invariants: they say HOW the runs differ, not what they sound like.")
    P("A repaired checkpoint still goes through the 20 s cfg7/W1 renders and Kim's ears.")
    report = "\n".join(L)
    print(report)
    open(os.path.join(a.out, "gram_report.txt"), "w").write(report + "\n")
    json.dump({"models": [{"group": g, "name": n, "path": p} for g, n, p in models],
               "n_matrices": len(kidx), "unresolved": unresolved,
               "G_eff": G_eff.tolist(), "G_raw": G_raw.tolist(),
               "G_site": {s: v.tolist() for s, v in G_site.items()},
               "G_block": {str(b): v.tolist() for b, v in G_block.items()},
               "norms_eff": norms.tolist(), "cos_to_good_consensus": cons,
               "group_cosines": grp, "ladders": lad_out,
               "mag_rel_stats": [{"median": float(torch.cat(m).abs().median()), "p99": float(torch.quantile(torch.cat(m).abs(), 0.99)),
                                  "max": float(torch.cat(m).abs().max())} if m else None for m in mag_rel],
               "ba_top1_median": [sorted(x)[len(x)//2] if x else None for x in ba_top1],
               "ba_erank_median": [sorted(x)[len(x)//2] if x else None for x in ba_erank]},
              open(os.path.join(a.out, "gram.json"), "w"), indent=1)
    print(f"-> {a.out}/gram_report.txt, gram.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
