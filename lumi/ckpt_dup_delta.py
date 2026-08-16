#!/usr/bin/env python
"""ckpt_dup_delta.py -- LUMI quick check (Kim direct 2026-08-17): job 21161065
(fullft_mixed_avp_goa_t4096.sbatch) ran without --devices, so its 8 srun ranks each ran an
INDEPENDENT single-GPU Trainer instead of one coordinated DDP job (see train_lora.py --devices
help text, precedent LUMI job 20413874) -- all 8 wrote to the SAME epoch=N-step=M filename,
colliding into Lightning's -v1/-v2/... auto-versioning. Rather than re-render to test
determinism, just diff the model weights ALREADY on disk across those collisions: identical
weights would mean the 8 independent trainers (same seed, same data) converged byte-for-byte;
different weights confirms real divergence (8 genuinely separate, uncoordinated training runs).

Uses mmap=True so this doesn't need to pull the full ~36GB ckpt into RAM per file -- only
touched 'state_dict' tensors get paged in.

Run (CPU is fine, no GPU needed):
  python ckpt_dup_delta.py --run /scratch/project_465003186/runs/fullft_mixed_avp_latents_sa3_t4096_wdfix
"""
import argparse
import glob
import os
import re
from collections import defaultdict


def group_by_epoch_step(run_dir):
    groups = defaultdict(list)
    for p in glob.glob(os.path.join(run_dir, "epoch=*.ckpt")):
        if p.endswith(".weights.ckpt"):
            continue
        base = os.path.basename(p)
        m = re.match(r"(epoch=\d+-step=\d+)(?:-v(\d+))?\.ckpt$", base)
        if not m:
            continue
        key = m.group(1)
        ver = int(m.group(2)) if m.group(2) else 0
        groups[key].append((ver, p))
    for key in groups:
        groups[key].sort()
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--prefix", default="diffusion.model.",
                     help="only diff keys starting with this prefix (default: online DiT weights, "
                          "skips optimizer states/EMA shadow to keep it cheap)")
    a = ap.parse_args()

    import torch

    groups = group_by_epoch_step(a.run)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    if not dup_groups:
        print(f"[dup-delta] no duplicate -vN groups found under {a.run}")
        return
    print(f"[dup-delta] {len(dup_groups)} epoch/step group(s) with duplicates\n")

    for key, versions in sorted(dup_groups.items()):
        print(f"=== {key} ({len(versions)} copies) ===")
        ref_ver, ref_path = versions[0]
        ref_ck = torch.load(ref_path, map_location="cpu", weights_only=False, mmap=True)
        ref_sd = ref_ck.get("state_dict", ref_ck)
        ref_keys = {k: v for k, v in ref_sd.items() if k.startswith(a.prefix)}
        print(f"  ref = {os.path.basename(ref_path)} ({len(ref_keys)} matching tensors)")
        del ref_ck

        for ver, path in versions[1:]:
            ck = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
            sd = ck.get("state_dict", ck)
            max_abs = 0.0
            sum_abs = 0.0
            n_diff = 0
            n_total = 0
            missing = 0
            for k, ref_t in ref_keys.items():
                if k not in sd:
                    missing += 1
                    continue
                t = sd[k]
                if t.shape != ref_t.shape:
                    missing += 1
                    continue
                d = (t.float() - ref_t.float()).abs()
                m = d.max().item()
                max_abs = max(max_abs, m)
                sum_abs += d.sum().item()
                n_total += d.numel()
                if m > 0:
                    n_diff += 1
            del ck, sd
            identical = (max_abs == 0.0 and missing == 0)
            print(f"  vs -v{ver} ({os.path.basename(path)}): "
                  f"IDENTICAL={identical} max_abs_diff={max_abs:.8g} "
                  f"mean_abs_diff={(sum_abs/max(1,n_total)):.8g} "
                  f"tensors_with_any_diff={n_diff}/{len(ref_keys)} missing_or_shape_mismatch={missing}")
        print()


if __name__ == "__main__":
    main()
