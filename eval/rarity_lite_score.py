"""rarity_lite_score.py — production-invariant rarity-lite scoring (#33, C owns).

Kim's rarity board wants per-clip rarity + delta-to-base. I flagged the confound earlier:
raw-spectral generation-vs-real-corpus similarity is dominated by the production/mastering
gap, not content. Fix = (a) LEARNED content embeddings (MERT, production-invariant) and
(b) GEN-vs-GEN scoring (all 450 clips are generations, same production domain, so kNN
rarity WITHIN the set measures content isolation, not the domain gap).

rarity_lite[clip] = percentile rank of its mean distance to the k nearest neighbours in
the standardized MERT space over ALL clips (higher = rarer / more isolated). Writes
rarity_scores.json {clip_stem: score in [0,1]} with keys == clip_index.json keys, so
G's build_rarity_page.py auto-fills the delta-to-base columns (delta = model - base per
prompt/seed). MERT is cached to mert_embeddings.npz for re-runs / the LUMI extension.

Run (mir venv, CPU): /home/kim/Projects/mir/mir/bin/python eval/rarity_lite_score.py --dir <rarity_gen_set>
"""
import argparse, glob, json, os, sys
from pathlib import Path
import numpy as np


def extract_mert(wavs, cache):
    if cache.exists():
        d = np.load(cache, allow_pickle=True)
        have = set(d["files"].tolist())
        if have >= {os.path.basename(w) for w in wavs}:
            print(f"[mert] cache hit ({len(have)} clips)", flush=True)
            return d["files"].tolist(), np.array(d["feat"])
    import soundfile as sf, torch
    torch.cuda.is_available = lambda: False
    sys.path.insert(0, "/home/kim/Projects/SAO/control")
    from sa3_control.mert_selector import MERTEmbedder
    emb = MERTEmbedder(device="cpu")
    names, feats = [], []
    for i, f in enumerate(wavs):
        y, sr = sf.read(f, dtype="float32", always_2d=True)
        y = y.mean(axis=1)[: int(24.0 * sr)]
        d = emb.embed(y, sr)
        names.append(os.path.basename(f))
        feats.append(np.concatenate([d["mid"], d["upper"]]))   # 2048-d content vector
        if (i + 1) % 25 == 0:
            print(f"  mert {i+1}/{len(wavs)}", flush=True)
    feats = np.array(feats, dtype=np.float32)
    np.savez(cache, files=np.array(names), feat=feats)
    return names, feats


def knn_rarity(feats, k=8):
    """Mean distance to k nearest neighbours -> percentile rank (production-invariant,
    gen-vs-gen). Higher = rarer/more isolated among the generations."""
    X = (feats - feats.mean(0)) / (feats.std(0) + 1e-8)
    # pairwise euclidean (450x450 fine)
    d2 = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d2, np.inf)
    knn = np.sort(d2, axis=1)[:, :k].mean(1) ** 0.5
    # percentile rank in [0,1]
    order = knn.argsort()
    pct = np.empty(len(knn))
    pct[order] = np.linspace(0, 1, len(knn))
    return pct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/run/media/kim/Mantu/sa3_lora_runs/rarity_gen_set")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()
    d = Path(args.dir)
    wavs = sorted(glob.glob(str(d / "*.wav")))
    print(f"[rarity-lite] {len(wavs)} clips in {d.name}", flush=True)
    names, feats = extract_mert(wavs, d / "mert_embeddings.npz")
    scores = knn_rarity(feats, k=args.k)
    out = {os.path.splitext(n)[0]: round(float(s), 4) for n, s in zip(names, scores)}
    (d / "rarity_scores.json").write_text(json.dumps(out, indent=0))
    # quick per-model summary (delta-to-base preview)
    from collections import defaultdict
    by_model = defaultdict(list)
    for stem, s in out.items():
        by_model[stem.split("__")[0]].append(s)
    print("[rarity-lite] median rarity by model:")
    for m in sorted(by_model):
        print(f"  {m:10s}: {np.median(by_model[m]):.3f}  (n={len(by_model[m])})")
    print(f"[rarity-lite] wrote {len(out)} scores -> {d/'rarity_scores.json'}", flush=True)


if __name__ == "__main__":
    main()
