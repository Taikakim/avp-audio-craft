---
name: project-lora-training
description: "60s psychedelic poster art LoRA training pipeline — musubi-tuner Z-Image, v3 bucketing strategy and scripts"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6d9ae2ac-15f7-4037-bff0-4794583c973d
---

Training a LoRA on 60s psychedelic poster art using musubi-tuner on Z-Image Base model.
Hardware: RX 9070 XT 16GB / ROCm / Ryzen 9900X.

**Why:** Reduce TunableOp/MIOpen kernel compilations by consolidating from 23 naive-padding buckets down to 13 valid-dim buckets.

**Bucketing strategy (v3):**
- Valid dims: 768, 832, 896, 960, 1024, 1088, 1152, 1280, 1344 (target ~1M px ±15%)
- AR < 0.80 → portrait buckets (contain + crop ≤24px long side + pad blur)
- AR 0.80–1.22 → 1024×1024 (crop ≤24px long, scale, pad)
- AR > 1.22 → 1024×832 single landscape bucket
- MAX_DOWN=0.875, MAX_UP=1.25, border-crop solid margins, drop duplicates

**Key files:**
- `BASE/bucket_planner.py` — dry-run analysis (read-only)
- `BASE/bucket_processor.py` — writes new bucketed dirs
- `BASE/train1280px_bucketed_v3/` — fg output (236 images)
- `BASE/train_60s_new_bucketed_v3/` — ng output (~1193 images)
- musubi-tuner: `dataset_60s_combined_v3.toml`, `cache_combined_v3.sh`, `train-new.sh`
- `train_60s_poster.toml` updated to reference `dataset_60s_combined_v3.toml`

BASE = `/run/media/kim/Aitta/art/AI/00 datasets/60s poster art`
musubi-tuner = `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/comfyui/ComfyUI-2/musubi-tuner`

**How to apply:** After bucket_processor.py completes, run `bash cache_combined_v3.sh` from musubi-tuner dir (includes latent cache + text encoder cache + launches training).
