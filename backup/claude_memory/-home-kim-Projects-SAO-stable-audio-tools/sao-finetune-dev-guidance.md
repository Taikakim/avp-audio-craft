---
name: sao-finetune-dev-guidance
description: "Stable Audio devs' (Zach/Fauno15) Discord guidance on finetuning SAO-small — LR, batch, demos VRAM, ARC, overfitting"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

Guidance from Zach (Fauno15, SA dev) + others, Discord Oct 2025, on finetuning Stable Audio Open Small from the base model. Relevant to the Goa two-stage finetune ([[latch-overview]] sibling work; configs under `configs/finetune/`).

- **LR:** 5e-5 is the "normal" diffusion LR. Zach trains at 1e-4/2e-4 but at **global batch ~512**; smaller batch → stay at/below 5e-5. Our stage1 is already 5e-5 at batch 8.
- **Instability/NaN:** "LR too high and/or no gradient clipping" is the usual cause (adax). We have grad clip 1.0; our NaN was instead the randomly-initialized resized `to_global_embed.0` projection (added conditioners). Fix in train.py = **PARTIAL** zero-init: preserve the pretrained `seconds_total` block (it's `global_cond_ids[0]` = first 768 input cols), zero ONLY the appended new-conditioner cols. NOTE: a FULL zero-init is wrong — it also strips the base's always-on `seconds_total` global signal, and Zach says seconds_total is in global cond (no CFG dropout) *specifically* so the model doesn't cheese the loss with silence → full-zero collapsed demos to silence.
- **Loss shape:** initial fast dip (model adapting, esp. to a changed length) then **flat plateau ≈ normal**. Loss dropping *after* the plateau = overfitting.
- **Demo VRAM** (demos can use more VRAM than training): set `"chunked": true` in the pretransform config, and/or fewer demos. We use chunked:true + iterate_batch:true.
- **Dataset size:** aim ≥5k audio files (10k+ better) to avoid overfitting full finetunes; "tens of thousands" of steps less likely to overfit. LoRA needs orders of magnitude less.
- **ARC (stage 2) is hard:** ~2× VRAM (generator + discriminator), many model passes per step, "not a solved problem, may not work without changes." Make the base model as good as possible first. Same `train.py`.
- **AdamW8bit:** ~30–40% VRAM savings, no quality loss reported (CZ-84) — but needs bitsandbytes (ROCm support is the catch on AMD).
- **Terminology:** our `rectified_flow` objective == 1-rectified flow == flow matching; "reflow"/2-rectified-flow (synthetic flow-path pairs) is a separate later step we are NOT doing.
