#!/usr/bin/env python
"""Analysis driver: extracted activation packs + TIMESERIES -> the layer x feature
map, per sigma. CPU only. Consumes extract_layer_activations.py output."""
import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from probe_layer_feature_map import (FEATURE_NAMES, load_features,
                                     pool_frames, build_feature_map)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acts-dir", type=Path, required=True)
    ap.add_argument("--latent-dir", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--out-json", type=Path, required=True)
    args = ap.parse_args()

    man = json.loads((args.acts_dir / "manifest.json").read_text())
    sigmas = man["sigmas"]
    results = {}
    for s in sigmas:
        clips, feat_pool = [], {}
        for crop in man["crops"]:
            stem, fidx = crop["stem"], np.asarray(crop["frames"])
            p = args.acts_dir / f"{stem}__s{int(s*100):02d}.npy"
            if not p.exists():
                continue
            acts = np.load(p).astype(np.float32)          # [L, F, d]
            feats = load_features(f"{args.latent_dir}/{stem}.TIMESERIES.npz")
            ok = True
            row = {}
            for nm, arr in feats.items():
                idx = fidx[fidx < len(arr)]
                if len(idx) != len(fidx):
                    ok = False
                    break
                row[nm] = arr[fidx]
            if not ok or not row:
                continue
            clips.append(acts)
            for nm, v in row.items():
                feat_pool.setdefault(nm, []).append(v)
        acts_by_layer = pool_frames(clips)
        feats = {nm: np.concatenate(v, axis=0) for nm, v in feat_pool.items()}
        m = build_feature_map(acts_by_layer, feats)
        results[str(s)] = {"r2": np.asarray(m["r2"]).round(4).tolist(),
                           "features": m["features"],
                           "best_layer": m["best_layer"],
                           "n_clips": len(clips),
                           "n_frames_pooled": int(acts_by_layer[0].shape[0])}
        print(f"[sigma {s}] {len(clips)} clips pooled; best layers:", m["best_layer"], flush=True)
    args.out_json.write_text(json.dumps(results, indent=1))
    print(f"[done] -> {args.out_json}", flush=True)


if __name__ == "__main__":
    main()
