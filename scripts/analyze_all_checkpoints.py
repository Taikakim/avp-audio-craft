#!/usr/bin/env python3
"""
scripts/analyze_all_checkpoints.py -- Comprehensive multi-run checkpoint trajectory & norm analyzer.

Scans all checkpoint archives across storage mounts (sa3_lora_runs, lumi_runs, sa3_control_runs),
extracts tensor norms (||B||_F, ||A||_F, ||mag||_F), step-to-step interval velocities,
directional cosine alignment, cumulative path length, and trajectory efficiency.

Dynamically streams results line-by-line to /home/kim/Projects/SAO/checkpoint_analysis_catalog.jsonl
and generates periodic markdown & CSV summary reports. Fully resumable: skips already-analyzed
checkpoints on restart to conserve compute and avoid redundant I/O.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import torch

# Default search roots
DEFAULT_ROOTS = [
    "/run/media/kim/Mantu/sa3_lora_runs",
    "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs",
    "/run/media/kim/Mantu/sa3_control_runs",
    "/run/media/kim/Mantu/lumi_runs",
]

PROJECT_ROOT = Path("/home/kim/Projects/SAO")
DEFAULT_JSONL = PROJECT_ROOT / "checkpoint_analysis_catalog.jsonl"
DEFAULT_MD = PROJECT_ROOT / "checkpoint_analysis_summary.md"
DEFAULT_CSV = PROJECT_ROOT / "checkpoint_analysis_summary.csv"
OVERRIDES_JSON = PROJECT_ROOT / "Misc/models_index_overrides.json"

STEP_RE = re.compile(r"step=(\d+)|step(\d+)")
EPOCH_RE = re.compile(r"epoch=(\d+)")


def parse_step_and_epoch(filename: str) -> tuple[int | None, int | None]:
    step = None
    epoch = None
    m_step = STEP_RE.search(filename)
    if m_step:
        step = int(m_step.group(1) or m_step.group(2))
    m_epoch = EPOCH_RE.search(filename)
    if m_epoch:
        epoch = int(m_epoch.group(1))
    return step, epoch


def load_overrides(overrides_path: Path) -> dict:
    if not overrides_path.exists():
        return {}
    try:
        data = json.loads(overrides_path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        print(f"[WARN] Failed to load overrides JSON: {e}", file=sys.stderr)
        return {}


def frob_norm(tensors: dict[str, torch.Tensor]) -> float:
    if not tensors:
        return 0.0
    return math.sqrt(sum(float(t.pow(2).sum()) for t in tensors.values()))


def frob_diff(d1: dict[str, torch.Tensor], d2: dict[str, torch.Tensor]) -> float:
    keys = set(d1.keys()) & set(d2.keys())
    if not keys:
        return 0.0
    return math.sqrt(sum(float((d1[k] - d2[k]).pow(2).sum()) for k in keys))


def cos_similarity(d1: dict[str, torch.Tensor], d2: dict[str, torch.Tensor]) -> float:
    keys = set(d1.keys()) & set(d2.keys())
    if not keys:
        return 0.0
    dot = sum(float((d1[k] * d2[k]).sum()) for k in keys)
    n1 = math.sqrt(sum(float(d1[k].pow(2).sum()) for k in keys))
    n2 = math.sqrt(sum(float(d2[k].pow(2).sum()) for k in keys))
    if n1 * n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def discover_checkpoints(roots: list[str]) -> dict[str, list[dict]]:
    """Discovers all checkpoints across roots and groups them by run."""
    runs = defaultdict(list)
    seen_paths = set()

    for root_str in roots:
        root_path = Path(root_str)
        if not root_path.exists():
            continue

        print(f"[SCAN] Indexing root directory: {root_path}")
        for dirpath, _, filenames in os.walk(root_path, followlinks=True):
            ckpt_files = [f for f in filenames if f.endswith((".ckpt", ".pt", ".safetensors"))]
            if not ckpt_files:
                continue

            # Group within directory
            run_name = Path(dirpath).name
            # If enclosing folder is just "checkpoints", use parent
            if run_name in ("checkpoints", "ckpts", "weights"):
                run_name = Path(dirpath).parent.name

            for f in ckpt_files:
                full_path = str(Path(dirpath) / f)
                if full_path in seen_paths:
                    continue
                seen_paths.add(full_path)

                step, epoch = parse_step_and_epoch(f)
                is_slim = f.endswith(".weights.ckpt")
                
                runs[run_name].append({
                    "filename": f,
                    "path": full_path,
                    "dirpath": dirpath,
                    "step": step,
                    "epoch": epoch,
                    "is_slim": is_slim,
                })

    # Dedup & sort within each run
    deduped_runs = {}
    total_ckpts = 0
    for run_name, files in runs.items():
        # Dedup: If both epoch=X-step=Y.ckpt and epoch=X-step=Y.weights.ckpt exist,
        # prefer the full .ckpt (has optimizer state)
        step_map = {}
        no_step_files = []
        for item in files:
            step = item["step"]
            if step is None:
                no_step_files.append(item)
                continue
            if step not in step_map:
                step_map[step] = item
            else:
                # Prefer full .ckpt over slim .weights.ckpt
                if step_map[step]["is_slim"] and not item["is_slim"]:
                    step_map[step] = item

        sorted_items = [step_map[s] for s in sorted(step_map.keys())] + no_step_files
        deduped_runs[run_name] = sorted_items
        total_ckpts += len(sorted_items)

    print(f"[DISCOVERY] Found {len(deduped_runs)} distinct runs, {total_ckpts} total unique checkpoints.")
    return deduped_runs


def extract_checkpoint_data(item: dict) -> dict:
    """Loads checkpoint on CPU, calculates norms & statistics, frees memory."""
    ckpt_path = item["path"]
    res = {
        "path": ckpt_path,
        "filename": item["filename"],
        "step": item["step"],
        "epoch": item["epoch"],
        "file_size_mb": round(os.path.getsize(ckpt_path) / (1024 * 1024), 2),
        "is_finite": True,
        "nan_count": 0,
        "frob_norm_B": 0.0,
        "frob_norm_A": 0.0,
        "frob_norm_mag": 0.0,
        "weight_mean": 0.0,
        "weight_std": 0.0,
        "weight_min": 0.0,
        "weight_max": 0.0,
        "param_count": 0,
        "adapter_type": "unknown",
        "rank": None,
        "optimizer_type": None,
        "lr": None,
        "d_value": None,
        "sf_divergence": None,
        "b_tensors": {},  # Kept in memory only for trajectory diffing, dropped before json dump
    }

    try:
        # Load weights on CPU without allocating GPU memory
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        sd = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else {}

        # If step/epoch not in filename, check checkpoint root
        if res["step"] is None and isinstance(ckpt, dict):
            res["step"] = ckpt.get("global_step")
        if res["epoch"] is None and isinstance(ckpt, dict):
            res["epoch"] = ckpt.get("epoch")

        # Check lora config
        if isinstance(ckpt, dict) and "lora_config" in ckpt:
            cfg = ckpt["lora_config"]
            if isinstance(cfg, dict):
                res["rank"] = cfg.get("rank")
                res["adapter_type"] = cfg.get("adapter_type")

        # Partition weights
        b_dict = {}
        a_dict = {}
        mag_dict = {}
        all_vals = []
        nan_cnt = 0

        for k, v in sd.items():
            if not isinstance(v, torch.Tensor):
                continue
            
            # Check finiteness
            if not torch.isfinite(v).all():
                res["is_finite"] = False
                nan_cnt += int((~torch.isfinite(v)).sum())

            t_fp32 = v.detach().float()
            if "lora_B" in k or ".lora_b" in k:
                b_dict[k] = t_fp32
                if res["rank"] is None and len(v.shape) >= 2:
                    res["rank"] = min(v.shape)
            elif "lora_A" in k or ".lora_a" in k:
                a_dict[k] = t_fp32
                if res["rank"] is None and len(v.shape) >= 2:
                    res["rank"] = min(v.shape)
            elif "magnitude" in k:
                mag_dict[k] = t_fp32
            
            # Sample stats
            all_vals.append((float(t_fp32.sum()), float(t_fp32.pow(2).sum()), t_fp32.numel(), float(t_fp32.min()), float(t_fp32.max())))

        res["nan_count"] = nan_cnt
        res["frob_norm_B"] = frob_norm(b_dict)
        res["frob_norm_A"] = frob_norm(a_dict)
        res["frob_norm_mag"] = frob_norm(mag_dict)

        if all_vals:
            tot_sum = sum(x[0] for x in all_vals)
            tot_sq = sum(x[1] for x in all_vals)
            tot_n = sum(x[2] for x in all_vals)
            res["param_count"] = tot_n
            mean = tot_sum / tot_n
            var = max(0.0, (tot_sq / tot_n) - (mean ** 2))
            res["weight_mean"] = round(mean, 6)
            res["weight_std"] = round(math.sqrt(var), 6)
            res["weight_min"] = round(min(x[3] for x in all_vals), 6)
            res["weight_max"] = round(max(x[4] for x in all_vals), 6)

        # Inspect optimizer states if present
        if isinstance(ckpt, dict) and "optimizer_states" in ckpt:
            opt_states = ckpt.get("optimizer_states")
            if opt_states and isinstance(opt_states, list) and len(opt_states) > 0:
                ost = opt_states[0]
                if isinstance(ost, dict):
                    pgs = ost.get("param_groups", [])
                    if pgs:
                        res["lr"] = pgs[0].get("lr")
                        res["d_value"] = pgs[0].get("d")
                    # Check Schedule-Free x vs z divergence
                    st = ost.get("state", {})
                    x_sq = 0.0
                    xz_diff_sq = 0.0
                    for p_state in st.values():
                        if isinstance(p_state, dict) and "x" in p_state and "z" in p_state:
                            x_t = p_state["x"].float()
                            z_t = p_state["z"].float()
                            xz_diff_sq += float((x_t - z_t).pow(2).sum())
                            x_sq += float(x_t.pow(2).sum())
                    if x_sq > 0:
                        res["sf_divergence"] = round(math.sqrt(xz_diff_sq) / math.sqrt(x_sq), 6)

        # Store b_dict for trajectory calculation across consecutive steps
        res["b_tensors"] = b_dict

        del ckpt, sd
        gc.collect()

    except Exception as e:
        res["error"] = str(e)
        res["is_finite"] = False

    return res


def scan_associated_demos(dirpath: str, step: int | None) -> int:
    """Checks if audio demo clips exist for this checkpoint step."""
    demo_count = 0
    dp = Path(dirpath)
    
    # Check demos/step{X}
    candidates = []
    if step is not None:
        candidates.append(dp / "demos" / f"step{step}")
        candidates.append(dp / f"step{step}")
        candidates.append(dp / "standard_clips")
    candidates.append(dp / "demos")
    
    for c in candidates:
        if c.exists() and c.is_dir():
            if step is not None:
                wavs = [f for f in os.listdir(c) if f.endswith(".wav") and (f"step{step}" in f or f"_{step}_" in f or f"-{step}." in f or f"step={step}" in f)]
                demo_count += len(wavs)
            else:
                demo_count += len([f for f in os.listdir(c) if f.endswith(".wav")])
                
    return demo_count


def write_summary_reports(catalog_records: list[dict], md_path: Path, csv_path: Path):
    """Writes formatted Markdown report and flat CSV summary."""
    if not catalog_records:
        return

    # Write CSV
    csv_fields = [
        "run_name", "step", "epoch", "frob_norm_B", "velocity_per_1k",
        "directional_cosine", "efficiency", "is_finite", "nan_count",
        "rank", "adapter_type", "lr", "d_value", "sf_divergence",
        "file_size_mb", "demo_count", "family", "filename", "path"
    ]
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            for rec in catalog_records:
                writer.writerow(rec)
    except Exception as e:
        print(f"[WARN] Failed writing CSV summary: {e}", file=sys.stderr)

    # Group by run for Markdown report
    runs_map = defaultdict(list)
    for rec in catalog_records:
        runs_map[rec["run_name"]].append(rec)

    md_lines = [
        "# Stable Audio 3 Checkpoint Analysis Catalog",
        "",
        f"> **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> **Total Runs Analyzed:** {len(runs_map)}  ",
        f"> **Total Checkpoints Cataloged:** {len(catalog_records)}  ",
        "",
        "---",
        "",
        "## Executive Run Roster & Trajectory Summary",
        "",
        "| Run Name | Family | Ckpts | Step Range | Final ||B||_F | Final Vel (u/1k) | Final Dir Cos | Efficiency | Finite | Demos |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for r_name in sorted(runs_map.keys()):
        ckpts = sorted(runs_map[r_name], key=lambda x: (x["step"] is None, x["step"] or 0))
        c_count = len(ckpts)
        first_step = ckpts[0]["step"]
        last_step = ckpts[-1]["step"]
        step_range = f"{first_step}–{last_step}" if first_step is not None and last_step is not None else "N/A"
        
        last_ckpt = ckpts[-1]
        final_norm = f"{last_ckpt.get('frob_norm_B', 0.0):.2f}"
        final_vel = f"{last_ckpt.get('velocity_per_1k', 0.0):.2f}" if last_ckpt.get("velocity_per_1k") is not None else "---"
        final_cos = f"{last_ckpt.get('directional_cosine', 0.0):+.4f}" if last_ckpt.get("directional_cosine") is not None else "---"
        eff = f"{last_ckpt.get('efficiency', 0.0):.3f}" if last_ckpt.get("efficiency") is not None else "---"
        all_finite = all(c.get("is_finite", True) for c in ckpts)
        finite_str = "**YES**" if all_finite else "❌ NaN"
        total_demos = sum(c.get("demo_count", 0) for c in ckpts)
        fam = last_ckpt.get("family", "DoRA/LoRA")

        md_lines.append(
            f"| `{r_name}` | {fam} | {c_count} | {step_range} | {final_norm} | {final_vel} | {final_cos} | {eff} | {finite_str} | {total_demos} |"
        )

    md_lines.append("\n---\n")
    md_lines.append("## Detailed Per-Run Step Dynamics\n")

    for r_name in sorted(runs_map.keys()):
        ckpts = sorted(runs_map[r_name], key=lambda x: (x["step"] is None, x["step"] or 0))
        md_lines.append(f"### `{r_name}`")
        if ckpts[0].get("note"):
            md_lines.append(f"> **Verdict / Note:** {ckpts[0]['note']}\n")
        if ckpts[0].get("recipe"):
            md_lines.append(f"> **Recipe:** {ckpts[0]['recipe']}\n")

        md_lines.append("| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |")
        md_lines.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

        for c in ckpts:
            s_str = str(c.get("step", "---"))
            ep_str = str(c.get("epoch", "---"))
            nb = f"{c.get('frob_norm_B', 0.0):.2f}"
            na = f"{c.get('frob_norm_A', 0.0):.2f}"
            vel = f"{c.get('velocity_per_1k', 0.0):.2f}" if c.get("velocity_per_1k") is not None else "---"
            cos_val = f"{c.get('directional_cosine', 0.0):+.4f}" if c.get("directional_cosine") is not None else "---"
            path_len = f"{c.get('path_length', 0.0):.2f}" if c.get("path_length") is not None else "---"
            disp = f"{c.get('displacement_init', 0.0):.2f}" if c.get("displacement_init") is not None else "---"
            fin = "✓" if c.get("is_finite", True) else "❌"
            sz = f"{c.get('file_size_mb', 0.0):.1f}"
            md_lines.append(f"| {s_str} | {ep_str} | {nb} | {na} | {vel} | {cos_val} | {path_len} | {disp} | {fin} | {sz} |")

        md_lines.append("\n")

    try:
        md_path.write_text("\n".join(md_lines), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] Failed writing Markdown summary: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Analyze all SA3 checkpoints across runs.")
    parser.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS, help="Root directories to search.")
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_JSONL, help="Path to stream output JSONL.")
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD, help="Path for generated Markdown summary.")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV, help="Path for flat CSV export.")
    parser.add_argument("--max-ckpts", type=int, default=None, help="Optional max checkpoints to process.")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from existing jsonl.")
    args = parser.parse_args()

    print("=" * 85)
    print("STABLE AUDIO 3: COMPREHENSIVE MULTI-RUN CHECKPOINT ANALYZER")
    print(f"Target Roots:  {args.roots}")
    print(f"Output JSONL:  {args.output_jsonl}")
    print(f"Output MD:     {args.output_md}")
    print(f"Output CSV:    {args.output_csv}")
    print("=" * 85)

    # Load existing processed checkpoints if resuming
    processed_paths = set()
    catalog_records = []
    if not args.no_resume and args.output_jsonl.exists():
        try:
            with open(args.output_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rec = json.loads(line)
                        processed_paths.add(rec["path"])
                        catalog_records.append(rec)
            print(f"[RESUME] Loaded {len(processed_paths)} previously analyzed checkpoints from {args.output_jsonl.name}")
        except Exception as e:
            print(f"[WARN] Error reading existing JSONL: {e}", file=sys.stderr)

    # Load overrides
    overrides = load_overrides(OVERRIDES_JSON)
    print(f"[META] Loaded {len(overrides)} model commentary entries from models_index_overrides.json")

    # Discover checkpoints
    runs_dict = discover_checkpoints(args.roots)
    
    total_to_process = sum(
        1 for r_name, items in runs_dict.items() for item in items if item["path"] not in processed_paths
    )
    print(f"[QUEUE] {total_to_process} checkpoints remaining to process.\n")

    if total_to_process == 0:
        print("[DONE] All discovered checkpoints have already been analyzed!")
        write_summary_reports(catalog_records, args.output_md, args.output_csv)
        print(f"[REPORT] Summary reports updated at {args.output_md} and {args.output_csv}")
        return

    processed_count = 0
    start_time = time.time()

    # Open JSONL in append mode
    with open(args.output_jsonl, "a", encoding="utf-8") as jsonl_out:
        for r_name in sorted(runs_dict.keys()):
            items = runs_dict[r_name]
            meta = overrides.get(r_name, {})

            # Trajectory state across the run
            prev_b_dict = None
            prev_delta_b = None
            init_b_dict = None
            path_len = 0.0

            for item in items:
                ckpt_path = item["path"]

                # If already processed in an earlier run, find record to maintain trajectory state
                if ckpt_path in processed_paths:
                    existing = next((r for r in catalog_records if r["path"] == ckpt_path), None)
                    if existing:
                        # Re-read lightweight state if needed
                        pass
                    continue

                if args.max_ckpts is not None and processed_count >= args.max_ckpts:
                    print(f"\n[LIMIT] Reached max_ckpts limit ({args.max_ckpts}). Stopping.")
                    break

                t0 = time.time()
                data = extract_checkpoint_data(item)
                curr_b = data.pop("b_tensors", {})

                # Compute trajectory metrics
                data["run_name"] = r_name
                data["family"] = meta.get("family", "DoRA/LoRA adapter")
                data["note"] = meta.get("note")
                data["recipe"] = meta.get("recipe")
                data["purpose"] = meta.get("purpose")
                data["demo_count"] = scan_associated_demos(item["dirpath"], data["step"])

                if init_b_dict is None and curr_b:
                    init_b_dict = {k: v.clone() for k, v in curr_b.items()}

                if prev_b_dict is not None and curr_b:
                    # Interval displacement
                    delta_b = {k: curr_b[k] - prev_b_dict[k] for k in set(curr_b.keys()) & set(prev_b_dict.keys())}
                    disp = frob_norm(delta_b)
                    step_delta = (data["step"] - prev_step) if (data["step"] is not None and prev_step is not None) else None
                    
                    data["step_delta"] = step_delta
                    data["displacement"] = round(disp, 4)
                    if step_delta and step_delta > 0:
                        data["velocity_per_1k"] = round(disp / (step_delta / 1000.0), 2)
                    else:
                        data["velocity_per_1k"] = None

                    if prev_delta_b is not None:
                        data["directional_cosine"] = round(cos_similarity(prev_delta_b, delta_b), 4)
                    else:
                        data["directional_cosine"] = None

                    path_len += disp
                    data["path_length"] = round(path_len, 4)

                    if init_b_dict is not None:
                        disp_init = frob_diff(curr_b, init_b_dict)
                        data["displacement_init"] = round(disp_init, 4)
                        if path_len > 0:
                            data["efficiency"] = round(disp_init / path_len, 4)
                    
                    prev_delta_b = delta_b
                else:
                    data["step_delta"] = None
                    data["displacement"] = 0.0
                    data["velocity_per_1k"] = None
                    data["directional_cosine"] = None
                    data["path_length"] = 0.0
                    data["displacement_init"] = 0.0
                    data["efficiency"] = 1.0

                prev_b_dict = curr_b
                prev_step = data["step"]

                # Write line to JSONL dynamically
                json_line = json.dumps(data, ensure_ascii=False)
                jsonl_out.write(json_line + "\n")
                jsonl_out.flush()

                catalog_records.append(data)
                processed_paths.add(ckpt_path)
                processed_count += 1
                dt = time.time() - t0

                # Single-line token-conserving stdout report
                step_str = f"s={data['step']}" if data['step'] is not None else data['filename']
                vel_str = f"{data['velocity_per_1k']:.1f}u/1k" if data.get('velocity_per_1k') is not None else "init"
                cos_str = f"{data['directional_cosine']:+.3f}" if data.get('directional_cosine') is not None else "---"
                print(f"[{processed_count}/{total_to_process}] {r_name[:30]:<30} {step_str:<12} ||B||={data['frob_norm_B']:.1f} vel={vel_str:<8} cos={cos_str:<6} ({dt:.1f}s)")

                # Periodic Markdown & CSV update every 15 checkpoints
                if processed_count % 15 == 0:
                    write_summary_reports(catalog_records, args.output_md, args.output_csv)

            if args.max_ckpts is not None and processed_count >= args.max_ckpts:
                break

    # Final summary update
    write_summary_reports(catalog_records, args.output_md, args.output_csv)
    total_elapsed = time.time() - start_time
    print("\n" + "=" * 85)
    print(f"[COMPLETED] Processed {processed_count} checkpoints in {total_elapsed / 60:.1f} minutes.")
    print(f"  • JSONL Stream:   {args.output_jsonl} ({os.path.getsize(args.output_jsonl) / 1024:.1f} KB)")
    print(f"  • Markdown Table: {args.output_md} ({os.path.getsize(args.output_md) / 1024:.1f} KB)")
    print(f"  • CSV Export:     {args.output_csv} ({os.path.getsize(args.output_csv) / 1024:.1f} KB)")
    print("=" * 85)


if __name__ == "__main__":
    main()
