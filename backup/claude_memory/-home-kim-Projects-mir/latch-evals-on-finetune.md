---
name: latch-evals-on-finetune
description: "From 2026-10-24 LatCH head evals/renders use the biggoa DoRA finetune, not plain medium-base; per-epoch ringing check at gain 256 during training"
metadata:
  node_type: memory
  type: feedback
  originSessionId: b207d8c1-afa9-47b8-bbe0-60db9d0c4899
  modified: 2026-10-24T10:11:46.862Z
---

From 2026-10-24 on, render LatCH head evals (grids, per-epoch checks) on the **biggoa DoRA finetune** (subloss_k24_biggoa_t512_bf16_s1, epoch 63, strength 1; path in `SAO/eval/epoch_ring_hook.sh` HOOK_FT default), not plain medium-base. Kim: "use always the fine tuned checkpoint from here on".

Also standing: LatCH training runs get the per-epoch ringing check (`train_latch.py --epoch-hook "bash SAO/eval/epoch_ring_hook.sh"`, needs `--save-every-epoch`): gain 256 x 0.5–16 onsets/s, stop when a cell rings >= 0.5 (eval/ring_score.py, advisory column on pages) in two consecutive epochs at the same density. On OOM the trainer offloads head+optimizer state to CPU and retries.

**Why:** listening found overtrained heads ring at one frequency; val loss and the disintegration gate miss it; Kim wants bad runs cut early.
**How to apply:** new eval pages and training queues default to FT=biggoa and the epoch hook; pages already on medium-base (latch_opt_grid A–E) stay base for like-for-like comparison unless asked. See [[sa3-latch-head-sweep]].
