#!/usr/bin/env python3
"""gen_length_variant_tasks.py — emit the LUMI HyperQueue task list for the 2026-08-02
length-variant eval run (LUMI leg = the 55 LUMI-resident terminal checkpoints).

Run LOCALLY (needs eval/render_jobs_lumi.txt from partition_render_jobs.py + ~/lumi_ckpt_inventory.txt);
writes lumi/length_variant_tasks.txt with LUMI-ABSOLUTE paths. Commit that file; the sbatch fans it
out across 8 GCDs on LUMI. One render_matrix_cells.py invocation per line.

Per terminal (label, tag, T): FOUR passes (only the genuinely-new cells — the 8 kept prompts' 20s
already exist locally, so LUMI renders only goa_organic at 20s + native for all 9 + ptm cfg1/w1):
  1. native medium       : 9 prompts x {1,7,16} x strengths, --frames T
  2. goa_organic 20s      : goa_organic x {1,7,16} x strengths
  3. ptm native (cfg1/w1) : 9 prompts x cfg1 x w1, --frames T, --steps 8
  4. ptm 20s   (cfg1/w1)  : 9 prompts x cfg1 x w1, --steps 8
DoRA adapters sweep --strengths 0.6,1.0,1.5,2.0; fullft/base collapse to w1 (worker default).
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS = HERE.parent / "eval" / "render_jobs_lumi.txt"
INV = Path.home() / "lumi_ckpt_inventory.txt"
OUT = HERE / "length_variant_tasks.txt"

# LUMI-absolute paths (standard project tree; see lumi/sbatch/ctrl_matrix_hq.sbatch)
CODE = "/project/project_465003186/code"
RENDER_OUT = "/scratch/project_465003186/renders/length_variant"
WORKER = f"{CODE}/lumi/render_matrix_cells.py"
SNAP9 = f"{CODE}/lumi/matrix_prompts_lenvar9.json"
SNAP_GOA = f"{CODE}/lumi/matrix_prompts_lenvar_goa.json"
DORA_STRENGTHS = "0.6,1.0,1.5,2.0"


def ckpt_stem(p):
    return re.sub(r"\.(weights\.ckpt|ckpt|safetensors)$", "", Path(str(p)).name)


def main():
    if not JOBS.exists():
        raise SystemExit(f"missing {JOBS} -- run eval/partition_render_jobs.py first")
    if not INV.exists():
        raise SystemExit(f"missing {INV} -- run the LUMI inventory command first")

    # LUMI inventory: ckpt stem -> full LUMI paths
    lumi_by_stem = {}
    for ln in INV.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        path = ln.split(" ", 1)[1] if " " in ln else ln
        lumi_by_stem.setdefault(ckpt_stem(path), []).append(path)

    lines, unresolved = [], []
    for row in JOBS.read_text().splitlines():
        row = row.strip()
        if not row:
            continue
        label, tag, tstr, local_ckpt = (row.split("\t") + ["", "", "", ""])[:4]
        T = int(tstr[1:]) if tstr.startswith("T") else 512
        # resolve the LUMI-side checkpoint path (same stem + label is a path component)
        stem = ckpt_stem(local_ckpt)
        lumi_ck = next((p for p in lumi_by_stem.get(stem, []) if label in Path(p).parts), None)
        if lumi_ck is None:
            unresolved.append(f"{label} {tag} ({stem})")
            continue
        is_fullft = label.startswith("fullft_") or label == "base"
        sw = "" if is_fullft else f" --strengths {DORA_STRENGTHS}"
        base = f"python {WORKER} --label {label} --tag {tag} --ckpt {lumi_ck} --out {RENDER_OUT}"
        # 1 native medium, 2 goa 20s medium, 3 ptm native cfg1/w1, 4 ptm 20s cfg1/w1
        lines.append(f"{base} --prompts {SNAP9} --frames {T}{sw}")
        lines.append(f"{base} --prompts {SNAP_GOA}{sw}")
        lines.append(f"{base} --prompts {SNAP9} --pt-medium --only-cfgs 1 --steps 8 --frames {T}")
        lines.append(f"{base} --prompts {SNAP9} --pt-medium --only-cfgs 1 --steps 8")

    OUT.write_text("\n".join(lines) + "\n")
    n_labels = len(lines) // 4
    print(f"wrote {OUT}: {len(lines)} task lines ({n_labels} terminals x 4 passes)")
    if unresolved:
        print(f"!! {len(unresolved)} labels had NO LUMI checkpoint match (skipped) -- investigate:")
        for u in unresolved:
            print("    ", u)


if __name__ == "__main__":
    main()
