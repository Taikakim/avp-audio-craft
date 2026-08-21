#!/usr/bin/env python3
"""score_d11_shuffle.py -- D11 (EXPERIMENTS.md): the frame-shuffle null on Tier-2 air.

QUESTION: is the same_chroma readout's air-band score melodic (temporal) content, or a
static per-track spectral fingerprint (mastering EQ / codec lowpass are track-constant
and land in air)? Shuffling the GT's frames IN TIME within each track preserves any
track-constant chroma shape exactly and destroys temporal (melodic) structure. So for
the per-window metrics (E2's znorm: matched 0.526 vs cross-track null 0.266 on air):

    fingerprint_fraction = (shuffled - null) / (matched - null)

~1.0 => the score is a static fingerprint (band scoping is aimed wrong);
~0.0 => the score is carried by temporal structure. NOTE the corpus-demean Tier-2
number (air 0.918) TIME-AVERAGES before cosine and is therefore shuffle-INVARIANT by
construction -- the shuffle null can only interrogate the per-window variants, which is
exactly why E2 (per-window) had to exist before D11 could run.

REUSE: imports E2's own transforms/scoring verbatim (score_e2_perwindow_norm.py loaded
as a module -- perwindow_znorm, perwindow_ranknorm, cos12_perframe_generic,
score_variant, plus tier1/tier2 helpers it re-exports). Predictions come from the
DURABLE cache eval/musicology/tier2_predicted/ (predict_head_durable.py; the 08-11 run
cached to tmpfs and lost it -- that mistake is why this file pins absolute dirs).

Run:
  /home/kim/Projects/mir/mir/bin/python score_d11_shuffle.py --self-test   # first
  /home/kim/Projects/mir/mir/bin/python score_d11_shuffle.py [--n-shuffle 5 --n-null 5]
"""
import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
E2_DIR = HERE.parent / "same_chroma_E2_perwindow_norm_2026-08-12"
TIER2_DIR = HERE.parent / "same_chroma_readout_tier2_muscriptor_2026-08-11"
PRED_DIR = HERE.parent / "tier2_predicted"          # durable (predict_head_durable.py)
FOLD12_CACHE = HERE.parent / "e2_fold12_cache"       # durable rebuild of E2's tmpfs cache


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


e2 = _load_module("e2_perwindow", E2_DIR / "score_e2_perwindow_norm.py")
BAND_NAMES, quantiles = e2.BAND_NAMES, e2.quantiles


def shuffle_gt_frames(g, rng):
    """g: (3,12,T) -> same array with the T axis permuted (one permutation shared
    across bands, since a real track's bands move through time together)."""
    perm = rng.sample(range(g.shape[-1]), g.shape[-1])
    return g[:, :, perm]


def score_shuffled(transform, pred12_list, gt12_list, ids, n_shuffle, rng_seed=777):
    """Matched pairs, but gt frame-shuffled within track. n_shuffle independent
    permutations per track; rows carry the per-track mean over permutations."""
    rows = []
    for i, fid in enumerate(ids):
        p = transform(pred12_list[i]) if transform else pred12_list[i]
        accum = np.zeros(len(BAND_NAMES))
        for rep in range(n_shuffle):
            rng = random.Random(f"{rng_seed}:{rep}:{i}")
            g = shuffle_gt_frames(gt12_list[i], rng)
            g = transform(g) if transform else g
            accum += e2.cos12_perframe_generic(p, g)
        c = accum / n_shuffle
        rows.append({"id": fid, **{b: float(c[bi]) for bi, b in enumerate(BAND_NAMES)}})
    return rows


def self_test():
    """Known-answer checks; run BEFORE trusting real numbers.
    (a) identical pred/gt with strong temporal variation: matched ~1, shuffled well
        below matched (temporal signal destroyed);
    (b) time-CONSTANT profile: shuffled == matched exactly (shuffle is a no-op on a
        fingerprint -- the property the whole test rests on);
    (c) identity permutation reproduces the matched score exactly."""
    rng = np.random.default_rng(0)
    T = 512
    # (a) pure temporal signal: INDEPENDENT frames, shared pred/gt. (Not a random
    # walk -- cumsum is autocorrelated, i.e. partially a drifting fingerprint, and
    # legitimately survives shuffling; caught by this very test's first run.)
    sig = rng.standard_normal((3, 12, T))
    m = e2.cos12_perframe_generic(e2.perwindow_znorm(sig), e2.perwindow_znorm(sig))
    assert np.allclose(m, 1.0), m
    s_rows = score_shuffled(e2.perwindow_znorm, [sig], [sig], ["a"], n_shuffle=3)
    s = np.array([s_rows[0][b] for b in BAND_NAMES])
    assert (np.abs(s) < 0.1).all(), f"(a) shuffled should collapse to ~0, got {s}"
    # (b) fingerprint: one profile tiled across time (+ tiny noise so norm != 0)
    prof = rng.standard_normal((3, 12, 1))
    fp = np.repeat(prof, T, axis=-1)
    m_fp = e2.cos12_perframe_generic(e2.perwindow_znorm(fp), e2.perwindow_znorm(fp))
    s_fp_rows = score_shuffled(e2.perwindow_znorm, [fp], [fp], ["b"], n_shuffle=3)
    s_fp = np.array([s_fp_rows[0][b] for b in BAND_NAMES])
    assert np.allclose(s_fp, m_fp, atol=1e-9), f"(b) shuffle must be no-op on fingerprint: {s_fp} vs {m_fp}"
    # (c) identity perm == matched
    class _IdRandom(random.Random):
        def sample(self, population, k):
            return list(population)
    g_id = shuffle_gt_frames(sig, _IdRandom())
    assert np.array_equal(g_id, sig)
    print("[self-test] OK: (a) temporal collapses under shuffle, (b) fingerprint "
          "invariant, (c) identity perm exact")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--n-shuffle", type=int, default=5)
    ap.add_argument("--n-null", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return

    tier2 = json.loads((TIER2_DIR / "results.json").read_text())
    ids = [r["id"] for r in tier2["primary_audio_gt"]["rows"]]
    if args.limit:
        ids = ids[: args.limit]
    missing = [f for f in ids if not (PRED_DIR / f"{f}.npy").exists()]
    if missing:
        print(f"[D11] STOP: {len(missing)}/{len(ids)} predictions not yet in {PRED_DIR} "
              f"(predict_head_durable.py still running?)")
        sys.exit(1)

    # pass1: identical to E2's, but against the durable caches.
    # SCHEMA DRIFT (found 2026-08-21): muscriptor_full's *.stats.json were regenerated
    # WITHOUT source_path/start_sample/end_sample since the 08-12 E2 run; those fields
    # now live in the co-located index.jsonl -- merge them back in per id.
    idx_path = Path(e2.tier2_mod.MUSCRIPTOR_DIR) / "index.jsonl"
    src_index = {}
    with open(idx_path) as fh:
        for line in fh:
            r = json.loads(line)
            src_index[r["id"]] = r
    print(f"[D11] index.jsonl: {len(src_index)} source rows", flush=True)
    t0 = time.time()
    FOLD12_CACHE.mkdir(exist_ok=True)
    kept_ids, pred12_list, gt12_list, dropped = [], [], [], []
    for i, fid in enumerate(ids):
        cf = FOLD12_CACHE / f"{fid}.npz"
        if cf.exists():
            d = np.load(cf)
            kept_ids.append(fid); pred12_list.append(d["pred12"]); gt12_list.append(d["gt12"])
            continue
        stats = e2.load_stats(fid)
        if stats is None:
            dropped.append((fid, "no_stats")); continue
        if "source_path" not in stats:
            stats.update({k: src_index.get(fid, {}).get(k) for k in
                          ("source_path", "start_sample", "end_sample")})
        pred = np.load(PRED_DIR / f"{fid}.npy")
        try:
            gt = e2.gt_chroma_from_source(stats)
        except Exception as ex:
            dropped.append((fid, f"audio:{ex}")); continue
        if gt is None:
            dropped.append((fid, "no_audio")); continue
        pa, ga, _T = e2.align(pred, gt)
        p12, g12 = e2.fold_to_12(pa), e2.fold_to_12(ga)
        kept_ids.append(fid); pred12_list.append(p12); gt12_list.append(g12)
        np.savez(cf, pred12=p12, gt12=g12)
        if (i + 1) % 200 == 0:
            print(f"[D11] pass1 {i+1}/{len(ids)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"[D11] pass1: kept {len(kept_ids)}, dropped {len(dropped)} ({time.time()-t0:.0f}s)", flush=True)
    if dropped:
        from collections import Counter
        print("[D11] drop reasons:", Counter(r for _, r in dropped).most_common(5), flush=True)
    if len(kept_ids) < 0.9 * len(ids):
        print(f"[D11] WARNING: kept only {len(kept_ids)}/{len(ids)} -- sample drift vs Tier-2/E2", flush=True)

    out = {"provenance": {"n_kept": len(kept_ids), "n_dropped": len(dropped),
                          "n_shuffle": args.n_shuffle, "n_null": args.n_null,
                          "note": "corpus-demean (Tier-2 air 0.918) time-averages and is "
                                  "shuffle-invariant by construction; only per-window "
                                  "variants are interrogated here"},
           "variants": {}}
    for vname, transform, plist, glist in (
            ("perwindow_znorm", e2.perwindow_znorm, pred12_list, gt12_list),):
        print(f"[D11] {vname}: matched / cross-track null / frame-shuffled ...", flush=True)
        m_rows, n_rows = e2.score_variant(vname, transform, plist, glist, kept_ids, args.n_null)
        s_rows = score_shuffled(transform, plist, glist, kept_ids, args.n_shuffle)
        v = {"matched": {b: quantiles([r[b] for r in m_rows]) for b in BAND_NAMES},
             "null": {b: quantiles([r[b] for r in n_rows]) for b in BAND_NAMES},
             "shuffled": {b: quantiles([r[b] for r in s_rows]) for b in BAND_NAMES},
             "rows_matched": m_rows, "rows_shuffled": s_rows}
        for b in BAND_NAMES:
            mm, nn, ss = (v[k][b]["median"] for k in ("matched", "null", "shuffled"))
            v.setdefault("fingerprint_fraction", {})[b] = (ss - nn) / (mm - nn) if mm != nn else None
        out["variants"][vname] = v

    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"[D11] wrote {HERE/'results.json'}", flush=True)
    for vname, v in out["variants"].items():
        print(f"\n[D11] {vname}: median matched / shuffled / null -> fingerprint fraction")
        for b in BAND_NAMES:
            print(f"  {b:>5}: {v['matched'][b]['median']:.3f} / {v['shuffled'][b]['median']:.3f} "
                  f"/ {v['null'][b]['median']:.3f}  -> ff {v['fingerprint_fraction'][b]:.3f}")


if __name__ == "__main__":
    main()
