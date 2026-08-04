#!/usr/bin/env python
"""pt_layer_shift_profile.py — which layers did ARC post-training actually rewrite?
(CONTINUITY 2026-07-21, Kim's layer-analytics night window.)

Directly tests Zach@Stability's Discord mechanism (docs/ai-research/
2026-07-21-zach-stability-discord-notes.md): "post-training to go from a flow model to a
multi-step GAN just requires changing the decoder ... the last few layers", which is his
explanation for why base-trained LoRAs transfer to the post-trained model.

Computes, per tensor common to stable-audio-3-medium (PT) and -medium-base:
    rel = ‖W_pt − W_base‖_F / ‖W_base‖_F
aggregated per DiT block and per site family, plus the OVERLAP with a DoRA's per-block
delta profile (eval/dora_layer_delta_fp32cmp_goa_t4096_bs4_ep4.json): if the adapter's
mass sits where ARC's changes are small, transplant interference is low.

Pure CPU, streams both safetensors. Run:
  ./stable-audio-3/.venv/bin/python eval/pt_layer_shift_profile.py [--json OUT]
"""
import argparse
import collections
import glob
import json
import re

from safetensors import safe_open

HUB = "/home/kim/.cache/huggingface/hub"
PT = glob.glob(f"{HUB}/models--stabilityai--stable-audio-3-medium/snapshots/*/model.safetensors")
BASE = glob.glob(f"{HUB}/models--stabilityai--stable-audio-3-medium-base/snapshots/*/model.safetensors")
DORA_JSON = "eval/dora_layer_delta_fp32cmp_goa_t4096_bs4_ep4.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="eval/pt_layer_shift_profile.json")
    a = ap.parse_args()

    per = []
    with safe_open(PT[0], framework="pt") as fpt, safe_open(BASE[0], framework="pt") as fb:
        kp, kb = set(fpt.keys()), set(fb.keys())
        common = sorted(kp & kb)
        print(f"tensors: pt={len(kp)} base={len(kb)} common={len(common)} "
              f"pt-only={len(kp-kb)} base-only={len(kb-kp)}")
        for k in sorted(kp - kb)[:6]:
            print("  pt-only:", k)
        for k in sorted(kb - kp)[:6]:
            print("  base-only:", k)
        for k in common:
            wp, wb = fpt.get_tensor(k).float(), fb.get_tensor(k).float()
            if wp.shape != wb.shape:
                print("  SHAPE MISMATCH", k, tuple(wp.shape), tuple(wb.shape))
                continue
            per.append({"key": k, "dF": (wp - wb).norm().item(), "wF": wb.norm().item()})

    blk_d = collections.defaultdict(float); blk_w = collections.defaultdict(float)
    site_d = collections.defaultdict(float); site_w = collections.defaultdict(float)
    oth_d = collections.defaultdict(float); oth_w = collections.defaultdict(float)
    for r in per:
        # DiT blocks ONLY — the pretransform (SAME) also has 'layers.N.' internally
        # (all zero-shift, ARC never touches it) and would dilute the block profile
        m = re.match(r"model\.model\.transformer\.layers\.(\d+)\.", r["key"])
        if m:
            b = int(m.group(1))
            blk_d[b] += r["dF"]; blk_w[b] += r["wF"]
            site = re.sub(r".*layers\.\d+\.", "", r["key"]).rsplit(".", 1)[0]
            site_d[site] += r["dF"]; site_w[site] += r["wF"]
        else:
            grp = re.sub(r"^model\.(model\.)?", "", r["key"]).split(".")[0]
            oth_d[grp] += r["dF"]; oth_w[grp] += r["wF"]

    rels = {b: blk_d[b] / blk_w[b] for b in sorted(blk_d)}
    print("\nper-block ARC shift: rel = Σ‖W_pt−W_base‖/Σ‖W_base‖")
    for b, v in rels.items():
        print(f"  L{b:02d} {v:.4f}  {'#' * int(60 * v / max(rels.values()))}")
    thirds = [sum(blk_d[b] for b in r) / sum(blk_w[b] for b in r)
              for r in (range(0, 8), range(8, 16), range(16, 24))]
    print(f"\nthirds: early L0-7 {thirds[0]:.4f}  mid L8-15 {thirds[1]:.4f}  late L16-23 {thirds[2]:.4f}")
    print("\nper-site (blocks):")
    for k in sorted(site_d, key=lambda k: -site_d[k] / site_w[k]):
        print(f"  {k:30s} {site_d[k]/site_w[k]:.4f}")
    print("\nnon-block groups:")
    for k in sorted(oth_d, key=lambda k: -oth_d[k] / oth_w[k]):
        print(f"  {k:30s} {oth_d[k]/oth_w[k]:.4f}")

    # overlap with the DoRA profile: correlation + interference index (Σ dora_b * arc_b)
    out = {"per_block_rel": rels, "thirds": thirds}
    try:
        dora = json.load(open(DORA_JSON))["per_block_rel"]
        import numpy as np
        db = np.array([dora[str(b)] if str(b) in dora else dora[b] for b in sorted(rels)])
        ab = np.array([rels[b] for b in sorted(rels)])
        r = float(np.corrcoef(db, ab)[0, 1])
        interf = float((db / db.sum() * ab / ab.sum()).sum() * len(db))  # 1.0 = uniform overlap
        print(f"\nDoRA-profile overlap: corr={r:+.3f}; normalized interference index={interf:.3f} "
              f"(1.0 = profiles uniform/independent, >1 = adapter mass sits WHERE ARC rewrote)")
        out["dora_overlap"] = {"corr": r, "interference_index": interf, "dora_json": DORA_JSON}
    except Exception as e:
        print("[overlap] skipped:", e)

    json.dump(out, open(a.json, "w"), indent=1)
    print(f"-> {a.json}")


if __name__ == "__main__":
    main()
