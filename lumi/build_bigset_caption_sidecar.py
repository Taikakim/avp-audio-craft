#!/usr/bin/env python3
"""build_bigset_caption_sidecar.py — re-key a relpath-keyed goa caption sidecar onto the
SYNTHETIC latent ids that pre_encode_dataset.py writes, so train_lora.py's
--caption_sidecar actually resolves for ${SCRATCH}/latents_goa_bigset.

WHY THIS IS NEEDED (2026-08-17, C):
  pre_encode_dataset.py names each latent `{shard:02d}{batch:06d}{i:04d}` (e.g. 000000000000)
  -- a synthetic id with no track name in it. PreEncodedDataset.__getitem__ sets
  info["latent_filename"], and caption_tools.make_caption_sampler's DEFAULT key resolver takes
  the basename-stem of the first present of (latent_filename, path, relpath, ...) -- so it keys
  on "000000000000" and misses every entry of a sidecar keyed by track relpath. With
  --no_caption_check there is also no stored prompt to fall back on, so training would silently
  use EMPTY prompts. Rather than patch the key resolver (and risk changing behavior for the
  other corpora that rely on the current default), re-key the sidecar itself: each latent's
  sibling .json carries `relpath` (and `path`), which IS what the goa sidecars are keyed by.

  Match is attempted in order: exact relpath -> exact path -> relpath without extension ->
  basename -> basename without extension. Every fallback is COUNTED and reported separately so
  a low exact-match rate cannot hide behind a loose fallback.

USAGE (login node is fine -- pure json, no torch, no GPU, no container):
  python3 lumi/build_bigset_caption_sidecar.py \
      --latents-dir /scratch/project_465003186/latents_goa_bigset \
      --source-sidecar /project/project_465003186/code/lumi/goa_bigset_sidecar.json \
      --out /project/project_465003186/code/lumi/goa_bigset_relkeyed_sidecar.json

  Add --report-only to measure coverage WITHOUT writing (do this first).
"""
import argparse
import json
import os
from collections import Counter
from glob import glob


def _variants(relpath, path):
    """Lookup keys to try, most-exact first. Yields (kind, key)."""
    if relpath:
        yield "relpath", relpath
        yield "relpath_noext", os.path.splitext(relpath)[0]
    if path:
        yield "path", path
        yield "path_noext", os.path.splitext(path)[0]
    for src in (relpath, path):
        if src:
            base = os.path.basename(src)
            yield "basename", base
            yield "basename_noext", os.path.splitext(base)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents-dir", required=True,
                    help="dir of <latent_id>.npy + <latent_id>.json from pre_encode_dataset.py")
    ap.add_argument("--source-sidecar", required=True,
                    help="existing caption sidecar keyed by track relpath/path (e.g. the granite output)")
    ap.add_argument("--out", default=None, help="output sidecar path (omit with --report-only)")
    ap.add_argument("--report-only", action="store_true",
                    help="measure coverage and write nothing (run this FIRST)")
    ap.add_argument("--show-misses", type=int, default=5,
                    help="how many unmatched relpaths to print for diagnosis")
    a = ap.parse_args()

    if not a.report_only and not a.out:
        ap.error("--out is required unless --report-only")

    with open(a.source_sidecar) as f:
        src = json.load(f)
    print(f"[sidecar] source: {len(src)} keys <- {a.source_sidecar}", flush=True)

    jsons = sorted(glob(os.path.join(a.latents_dir, "*.json")))
    print(f"[sidecar] latents: {len(jsons)} .json sidecars <- {a.latents_dir}", flush=True)

    out = {}
    kinds = Counter()
    misses = []
    no_relpath = 0
    for jp in jsons:
        latent_id = os.path.splitext(os.path.basename(jp))[0]
        try:
            with open(jp) as f:
                md = json.load(f)
        except Exception as e:
            misses.append((latent_id, f"<unreadable: {e}>"))
            continue
        relpath, path = md.get("relpath"), md.get("path")
        if not relpath and not path:
            no_relpath += 1
            continue
        for kind, key in _variants(relpath, path):
            if key in src:
                out[latent_id] = src[key]
                kinds[kind] += 1
                break
        else:
            misses.append((latent_id, relpath or path))

    total = len(jsons)
    matched = len(out)
    print(f"\n[sidecar] MATCHED {matched}/{total} ({matched/max(1,total):.1%})")
    for kind, n in kinds.most_common():
        print(f"           via {kind}: {n}")
    if no_relpath:
        print(f"           .json with neither relpath nor path: {no_relpath}")
    print(f"[sidecar] UNMATCHED: {len(misses)}")
    for lid, rp in misses[: a.show_misses]:
        print(f"           {lid}  <-  {rp}")

    # a caption sidecar that only covers part of the corpus trains the rest on empty prompts --
    # surface that loudly rather than writing a quietly-partial file.
    if matched < total:
        print(f"\n[sidecar] WARNING: {total - matched} latents would train with NO caption "
              f"(empty prompt). Fix the source sidecar's coverage before training, or accept "
              f"it deliberately.")

    if a.report_only:
        print("\n[sidecar] --report-only: nothing written")
        return
    with open(a.out, "w") as f:
        json.dump(out, f)
    print(f"\n[sidecar] wrote {matched} entries -> {a.out}")
    print(f"[sidecar] use with: --caption_sidecar ,{a.out}  (parallel to --encoded_dir order)")


if __name__ == "__main__":
    main()
