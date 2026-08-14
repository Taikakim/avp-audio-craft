#!/usr/bin/env python
"""build_playlist_manifest.py — Kim direct 2026-08-15: 128-clip manifest for the 24h
YouTube "T4096 playlist" (Dadabots-metal-GAN homage). Random model x random prompt x
random per-clip DoRA weight x unique seed, deterministic given --manifest-seed so it's
reproducible/auditable before spending any LUMI GPU-hours.

Model pool = every T4096-trained checkpoint family across BOTH corpora (Kim: "use both
AVP and Goa models... different runs"):
  DoRA-adapter arms (get the 0.8-1.2 weight sweep): fp32cmp_{avp,goa}_t4096_bs{1,4}_lr*,
    fp32frames_{avp,goa}_t4096_bs{1,4}_lr1e4  (10 labels)
  Full-FT arms (weight fixed 1.0, no adapter strength knob): fullft_{avp,goa}_t4096
    (2 labels, EMA-trained -> render must load the EMA shadow)

Prompt pool = eval/kimlong_pool.json (2750 entries, Music-Flamingo-described + Granite-
revised captions over Kim's goa catalog — confirmed 2026-08-15 that's the "Flamingo AND
Granite" pipeline, not two separate caption sets).

Each of the 128 entries carries everything every downstream render stage needs, so
stages B/C/D reuse this SAME file (same seed/prompt/model/weight) and only override
frames/cfg/dist_shift/pt_medium at render time — that's what makes the length/schedule/
post-train comparisons actual matched pairs instead of last night's mismatched-prompt
mess.
"""
import argparse
import json
import random
from pathlib import Path

KIMLONG_POOL = Path("/home/kim/Projects/SAO/eval/kimlong_pool.json")

DORA_LABELS = [
    "fp32cmp_avp_t4096_bs1_lr1e4", "fp32cmp_avp_t4096_bs4_lr1e4", "fp32cmp_avp_t4096_bs4_lr5e5",
    "fp32cmp_goa_t4096_bs1_lr1e4", "fp32cmp_goa_t4096_bs4_lr1e4", "fp32cmp_goa_t4096_bs4_lr5e5",
    "fp32frames_avp_t4096_bs1_lr1e4", "fp32frames_avp_t4096_bs4_lr1e4",
    "fp32frames_goa_t4096_bs1_lr1e4", "fp32frames_goa_t4096_bs4_lr1e4",
]
FULLFT_LABELS = ["fullft_avp_t4096", "fullft_goa_t4096"]


def build(n, manifest_seed, weight_lo, weight_hi, cfg, base_render_seed):
    rng = random.Random(manifest_seed)
    pool = json.loads(KIMLONG_POOL.read_text())
    all_labels = DORA_LABELS + FULLFT_LABELS

    entries = []
    for i in range(n):
        label = rng.choice(all_labels)
        is_fullft = label in FULLFT_LABELS
        prompt_row = rng.choice(pool)
        weight = 1.0 if is_fullft else round(rng.uniform(weight_lo, weight_hi), 3)
        # unique per-clip render seed, independent stream from the manifest-composition
        # rng so re-running build() with the same manifest_seed always reproduces the
        # same (label, prompt, weight) triples even if the seed-assignment scheme changes.
        seed = base_render_seed + i
        entries.append({
            "idx": i,
            "seed": seed,
            "label": label,
            "is_fullft": is_fullft,
            "corpus": "avp" if "avp" in label else "goa",
            "weight": weight,
            "cfg": cfg,
            "prompt": prompt_row["prompt"],
            "track": prompt_row["track"],
        })
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=128)
    ap.add_argument("--manifest-seed", type=int, default=20260815)
    ap.add_argument("--base-render-seed", type=int, default=100000)
    ap.add_argument("--weight-lo", type=float, default=0.8)
    ap.add_argument("--weight-hi", type=float, default=1.2)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--out", default="/home/kim/Projects/SAO/eval/playlist_manifest_128.json")
    a = ap.parse_args()

    entries = build(a.n, a.manifest_seed, a.weight_lo, a.weight_hi, a.cfg, a.base_render_seed)
    Path(a.out).write_text(json.dumps(entries, indent=2))

    by_label = {}
    for e in entries:
        by_label[e["label"]] = by_label.get(e["label"], 0) + 1
    print(f"Wrote {len(entries)} entries -> {a.out}")
    print("Per-label counts:")
    for label in DORA_LABELS + FULLFT_LABELS:
        print(f"  {label:32s} {by_label.get(label, 0)}")
    n_avp = sum(1 for e in entries if e["corpus"] == "avp")
    print(f"avp={n_avp} goa={len(entries) - n_avp}")


if __name__ == "__main__":
    main()
