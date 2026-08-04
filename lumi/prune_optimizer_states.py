"""prune_optimizer_states.py — reclaim LUMI /scratch space (Kim 2026-07-19: "prune the
optimiser states from every checkpoint except the last ones; we're not resuming mid-training").

Per run dir (any dir under --root that contains *.ckpt):
  * the LAST checkpoint (max step) -> kept FULL (.ckpt, resumable) AND a slim
    <name>.weights.ckpt is written next to it (for a small download).
  * every OTHER checkpoint -> a slim <name>.weights.ckpt is written, then the fat .ckpt is
    DELETED (optimizer state gone). These stay usable for eval/inference, just not resume.

Slim = keep the loadable keys (state_dict + lora_config + hyper_parameters + epoch/step +
pytorch-lightning_version) and DROP the resume bulk (optimizer_states, lr_schedulers, loops,
callbacks). The kept state_dict is exactly what StableAudioModel.copy_state_dict loads (it runs
remap_state_dict_keys) — DoRA ckpts already had the frozen base stripped by on_save_checkpoint,
so their slim file is just the adapter; full-ft slim is the model minus the optimizer. Safe: the
.ckpt is removed only AFTER its slim file is written OK.

Run inside the container with the scratch bind:
  singularity exec --bind /scratch/project_465003186,/project/project_465003186 \
    /project/project_465003186/containers/sa3.sif \
    python /project/project_465003186/code/lumi/prune_optimizer_states.py
Add --dry-run first to see what it WOULD do (no writes, no deletes).
"""
import argparse
import gc
import glob
import os
import re
from collections import defaultdict

import torch


def step_of(path):
    m = re.search(r"step=(\d+)", path)
    return int(m.group(1)) if m else -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/scratch/project_465003186/runs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slim-all", action="store_true",
                    help="slim EVERY ckpt (keep none full) — for local copies where you never "
                         "resume (the resumable full ckpt lives on LUMI). Drops optimizer from all.")
    ap.add_argument("--keep-last-only", action="store_true",
                    help="keep ONLY the last ckpt per run (as slim weights); DELETE every other "
                         "ckpt entirely. For local copies where the mids aren't worth keeping.")
    ap.add_argument("--settle", action="store_true",
                    help="local endgame on a MIXED dir (full .ckpt + .weights.ckpt from a LUMI "
                         "prune): per run keep only the highest-epoch checkpoint of ANY extension "
                         "as slim weights, delete the rest. Considers .weights.ckpt too.")
    a = ap.parse_args()
    # a mistyped --root used to glob nothing and print "freed ~0.00 TB" like a clean
    # no-op (2026-07-23: runs/fp32_frame vs runs/fp32_frames) — fail loud instead.
    if not os.path.isdir(a.root):
        raise SystemExit(f"[prune] FATAL: --root does not exist: {a.root}")

    # keep the loadable keys; drop the resume bulk (the big part)
    KEEP = ("state_dict", "lora_config", "hyper_parameters", "epoch", "global_step",
            "pytorch-lightning_version")

    by_dir = defaultdict(list)
    for c in glob.glob(a.root + "/**/*.ckpt", recursive=True):
        if c.endswith(".weights.ckpt") and not a.settle:
            continue
        by_dir[os.path.dirname(c)].append(c)

    freed = 0
    for d, cks in sorted(by_dir.items()):
        keep = max(cks, key=step_of)
        print(f"\n[{d}]  {len(cks)} ckpt(s); "
              + ("SLIM ALL (keep none full)" if a.slim_all else f"KEEP full: {os.path.basename(keep)}"))
        for c in cks:
            sz = os.path.getsize(c)
            is_weights = c.endswith(".weights.ckpt")
            wpt = c if is_weights else c[:-5] + ".weights.ckpt"
            # modes that DELETE every non-last ckpt outright (no slim): keep-last-only, settle
            if (a.keep_last_only or a.settle) and c != keep:
                if a.dry_run:
                    print(f"  DELETE  {os.path.basename(c)} ({sz/1e9:.1f} GB)")
                else:
                    os.remove(c)
                    print(f"  deleted {os.path.basename(c)} ({sz/1e9:.1f} GB)")
                freed += sz
                continue
            # settle: the kept file is already slim weights -> leave it untouched
            if a.settle and is_weights:
                print(f"  keep (already slim): {os.path.basename(c)}")
                continue
            is_last = (c == keep) and not a.slim_all and not a.keep_last_only and not a.settle
            if a.dry_run:
                print(f"  {'slim+KEEP' if is_last else 'slim+RM'}  {os.path.basename(c)} ({sz/1e9:.1f} GB)")
                if not is_last:
                    freed += sz
                continue
            ck = slim = None
            try:
                ck = torch.load(c, map_location="cpu", weights_only=False)
                if "state_dict" not in ck:
                    print(f"  SKIP (no state_dict): {os.path.basename(c)}")
                    continue
                if "optimizer_states" not in ck:
                    # already optimizer-free (soup, export, prior slim) — nothing to strip,
                    # leave it untouched so we don't pointlessly rename .ckpt -> .weights.ckpt
                    print(f"  skip (already optimizer-free): {os.path.basename(c)}")
                    ck = None
                    continue
                slim = {k: ck[k] for k in KEEP if k in ck}     # weights + config, no optimizer
                ck = None; gc.collect()                        # free the ~30 GB optimizer state NOW,
                #                                                before torch.save — avoids 2x peak
                torch.save(slim, wpt)
                if not is_last:
                    os.remove(c)                                # drop the fat ckpt
                    freed += sz - os.path.getsize(wpt)
                    print(f"  stripped+removed {os.path.basename(c)} -> {os.path.basename(wpt)} "
                          f"({sz/1e9:.1f}->{os.path.getsize(wpt)/1e9:.2f} GB)")
                else:
                    print(f"  wrote slim, kept full: {os.path.basename(c)} "
                          f"(slim {os.path.getsize(wpt)/1e9:.2f} GB)")
            except Exception as e:
                print(f"  ERROR on {os.path.basename(c)}: {e} (left untouched)")
            finally:
                ck = slim = None; gc.collect()                 # ensure freed before the next load
    print(f"\n[prune] {'WOULD free' if a.dry_run else 'freed'} ~{freed/1e12:.2f} TB")


if __name__ == "__main__":
    main()
