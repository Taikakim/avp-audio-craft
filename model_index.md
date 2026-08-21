# SA3 Model Index

> [!NOTE]
> **Generated 2026-08-17 — re-run `python3 Misc/build_model_index_page.py`.**
> Auto-built from the live eval-board manifest (`~/.cache/evals_aac/model_matrix/manifest_live.jsonl`) joined to the maintained per-model source `Misc/models_index_overrides.json` (real recipes extracted from each checkpoint + plain-language why + comparison targets + hand-added by-ear verdicts). This replaces the old hand-compiled snapshot; the July-4 body is kept verbatim as a **Legacy snapshot** at the foot of this file.
>
> **Roster:** 245 board labels → **177 distinct trained models** across **27 families** (`_ptm` = same checkpoint re-rendered on medium-base, collapsed onto its parent). 153 carry a recipe/verdict override; 24 are on the board but not yet annotated; 148 carry a hand-added by-ear or board-metered verdict.
>
> **To change a verdict or recipe:** edit `Misc/models_index_overrides.json` (verdicts live there so they survive regeneration — this generator only reads them) and re-run the script. Off-board control-head notes live in `Misc/model_index_legacy.md`.

---

## base — 1 model(s)

#### `base`
- **ID `M-XD7Y0P`** · also known as: `base_ptm`
- 1 ckpt tag(s) on board (base) · 514 clips
- **Training data:** n/a (base post-trained model)
- **Recipe:** stabilityai stable-audio-3-medium POST-TRAINED (ARC few-step), NO adapter -- steps 8, cfg 1 (native). The control row for the *_ptm adapter rows: if an adapter-on-PT row sounds like THIS row, the adapter is not expressing on the post-trained model.
- *(also on board as base-render variant: `base_ptm`)*


## xft_distillation — 60 model(s), 60 with a verdict

#### `xftdora128_fullft_avp_t1024`
- **ID `M-2TQEAC`**
- **SVD-extracted DoRA r128 from the avp t1024 whole-DiT fullft (fullft_avp_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_avp_t1024.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_avp_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** NO — a full fine-tune does NOT distill to a small adapter: the weight-delta is <b>near-full-rank</b>, not low-rank like a style LoRA's. Uniform-rank energy captured (extracted ranks measured across ALL 10 fullft parents — INVARIANT ±0.2pp across both corpora and every context length T256–T4096; higher-rank spectrum shape from the goa_t256 reference): 4.5% @r16, 14.8% @r64, 25.7% @r128, and it takes r512/r1024 for 65%/89.5%. Per-module median rank for 90% energy runs 49–72% of the 1536 hidden dim — nothing 'small'. The invariance is itself a finding: the delta's spectral shape is TRAINING-REGIME-determined (same optimizer/lr/epochs → same spectrum), not data-determined — the rank-side sibling of the ‖dW‖∝LR magnitude law. ~57 of the 60 extracted adapters are glitch/noise at these ranks and were never shipped; a 3-pair matched-rank A/B (r16/r128, avp+goa) on xft_distillation.html makes the contrast audible. A finding, not a shippable model family (credit: task #71 GHOST-NOTE extraction + CONTINUITY SV-spectrum reframe + per-arm invariance sweep, task #77).
- *status: finding-not-shippable*

#### `xftdora128_fullft_avp_t2048`
- **ID `M-2WX6JC`**
- **SVD-extracted DoRA r128 from the avp t2048 whole-DiT fullft (fullft_avp_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_avp_t2048.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_avp_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_avp_t256`
- **ID `M-1ZPS08`**
- **SVD-extracted DoRA r128 from the avp t256 whole-DiT fullft (fullft_avp_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_avp_t256.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_avp_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_avp_t4096`
- **ID `M-42GVV9`**
- **SVD-extracted DoRA r128 from the avp t4096 whole-DiT fullft (fullft_avp_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_avp_t4096.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_avp_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_avp_t512`
- **ID `M-PW7P82`**
- **SVD-extracted DoRA r128 from the avp t512 whole-DiT fullft (fullft_avp_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_avp_t512.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_avp_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_goa_t1024`
- **ID `M-71CJS9`**
- **SVD-extracted DoRA r128 from the goa t1024 whole-DiT fullft (fullft_goa_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_goa_t1024.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_goa_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_goa_t2048`
- **ID `M-XNASVX`**
- **SVD-extracted DoRA r128 from the goa t2048 whole-DiT fullft (fullft_goa_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_goa_t2048.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_goa_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_goa_t256`
- **ID `M-QM51Y4`**
- **SVD-extracted DoRA r128 from the goa t256 whole-DiT fullft (fullft_goa_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_goa_t256.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_goa_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_goa_t4096`
- **ID `M-M12HPC`**
- **SVD-extracted DoRA r128 from the goa t4096 whole-DiT fullft (fullft_goa_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_goa_t4096.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_goa_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora128_fullft_goa_t512`
- **ID `M-YH4699`**
- **SVD-extracted DoRA r128 from the goa t512 whole-DiT fullft (fullft_goa_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r128 extraction from fullft_goa_t512.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftlora128_fullft_goa_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_avp_t1024`
- **ID `M-YTZHZX`**
- **SVD-extracted DoRA r16 from the avp t1024 whole-DiT fullft (fullft_avp_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_avp_t1024.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_avp_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_avp_t2048`
- **ID `M-VZZCCD`**
- **SVD-extracted DoRA r16 from the avp t2048 whole-DiT fullft (fullft_avp_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_avp_t2048.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_avp_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_avp_t256`
- **ID `M-YZ7DTD`**
- **SVD-extracted DoRA r16 from the avp t256 whole-DiT fullft (fullft_avp_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_avp_t256.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_avp_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_avp_t4096`
- **ID `M-0CCMFB`**
- **SVD-extracted DoRA r16 from the avp t4096 whole-DiT fullft (fullft_avp_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_avp_t4096.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_avp_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_avp_t512`
- **ID `M-VBEFEZ`**
- **SVD-extracted DoRA r16 from the avp t512 whole-DiT fullft (fullft_avp_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_avp_t512.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_avp_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_goa_t1024`
- **ID `M-6RY2J9`**
- **SVD-extracted DoRA r16 from the goa t1024 whole-DiT fullft (fullft_goa_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_goa_t1024.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_goa_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_goa_t2048`
- **ID `M-XWWKGA`**
- **SVD-extracted DoRA r16 from the goa t2048 whole-DiT fullft (fullft_goa_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_goa_t2048.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_goa_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_goa_t256`
- **ID `M-1YS280`**
- **SVD-extracted DoRA r16 from the goa t256 whole-DiT fullft (fullft_goa_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_goa_t256.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_goa_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_goa_t4096`
- **ID `M-WG7FNA`**
- **SVD-extracted DoRA r16 from the goa t4096 whole-DiT fullft (fullft_goa_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_goa_t4096.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_goa_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora16_fullft_goa_t512`
- **ID `M-7QA1HJ`**
- **SVD-extracted DoRA r16 from the goa t512 whole-DiT fullft (fullft_goa_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r16 extraction from fullft_goa_t512.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftlora16_fullft_goa_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_avp_t1024`
- **ID `M-37J37M`**
- **SVD-extracted DoRA r64 from the avp t1024 whole-DiT fullft (fullft_avp_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_avp_t1024.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_avp_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_avp_t2048`
- **ID `M-VA1GSR`**
- **SVD-extracted DoRA r64 from the avp t2048 whole-DiT fullft (fullft_avp_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_avp_t2048.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_avp_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_avp_t256`
- **ID `M-CGN1WA`**
- **SVD-extracted DoRA r64 from the avp t256 whole-DiT fullft (fullft_avp_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_avp_t256.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_avp_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_avp_t4096`
- **ID `M-4PVNVG`**
- **SVD-extracted DoRA r64 from the avp t4096 whole-DiT fullft (fullft_avp_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_avp_t4096.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_avp_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_avp_t512`
- **ID `M-HBWP7D`**
- **SVD-extracted DoRA r64 from the avp t512 whole-DiT fullft (fullft_avp_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_avp_t512.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_avp_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_goa_t1024`
- **ID `M-HBJAKC`**
- **SVD-extracted DoRA r64 from the goa t1024 whole-DiT fullft (fullft_goa_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_goa_t1024.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_goa_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_goa_t2048`
- **ID `M-G6XN3N`**
- **SVD-extracted DoRA r64 from the goa t2048 whole-DiT fullft (fullft_goa_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_goa_t2048.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_goa_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_goa_t256`
- **ID `M-532WGJ`**
- **SVD-extracted DoRA r64 from the goa t256 whole-DiT fullft (fullft_goa_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_goa_t256.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_goa_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_goa_t4096`
- **ID `M-0011A9`**
- **SVD-extracted DoRA r64 from the goa t4096 whole-DiT fullft (fullft_goa_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_goa_t4096.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_goa_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftdora64_fullft_goa_t512`
- **ID `M-8DR1J1`**
- **SVD-extracted DoRA r64 from the goa t512 whole-DiT fullft (fullft_goa_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: dora-rows
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the DoRA r64 extraction from fullft_goa_t512.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftlora64_fullft_goa_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_avp_t1024`
- **ID `M-4KFA7P`**
- **SVD-extracted LoRA r128 from the avp t1024 whole-DiT fullft (fullft_avp_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_avp_t1024.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_avp_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_avp_t2048`
- **ID `M-90WKHH`**
- **SVD-extracted LoRA r128 from the avp t2048 whole-DiT fullft (fullft_avp_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_avp_t2048.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_avp_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_avp_t256`
- **ID `M-JN16NW`**
- **SVD-extracted LoRA r128 from the avp t256 whole-DiT fullft (fullft_avp_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_avp_t256.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_avp_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_avp_t4096`
- **ID `M-WY1QMQ`**
- **SVD-extracted LoRA r128 from the avp t4096 whole-DiT fullft (fullft_avp_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_avp_t4096.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_avp_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_avp_t512`
- **ID `M-RS6VDE`**
- **SVD-extracted LoRA r128 from the avp t512 whole-DiT fullft (fullft_avp_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_avp_t512.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_avp_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_goa_t1024`
- **ID `M-XF6HGD`**
- **SVD-extracted LoRA r128 from the goa t1024 whole-DiT fullft (fullft_goa_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_goa_t1024.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_goa_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_goa_t2048`
- **ID `M-7PV649`**
- **SVD-extracted LoRA r128 from the goa t2048 whole-DiT fullft (fullft_goa_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_goa_t2048.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_goa_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_goa_t256`
- **ID `M-NXMRAM`**
- **SVD-extracted LoRA r128 from the goa t256 whole-DiT fullft (fullft_goa_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_goa_t256.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_goa_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_goa_t4096`
- **ID `M-EASZSW`**
- **SVD-extracted LoRA r128 from the goa t4096 whole-DiT fullft (fullft_goa_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_goa_t4096.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_goa_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora128_fullft_goa_t512`
- **ID `M-PAEAQV`**
- **SVD-extracted LoRA r128 from the goa t512 whole-DiT fullft (fullft_goa_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r128 recovers only ~25.7% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r128 extraction from fullft_goa_t512.
- **Compare against:**
  - `family:dora128_* (straight-trained DoRA at matched rank 128, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-128 approximation of it
  - `xftdora128_fullft_goa_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora128_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r128-extracted carries only ~25.7% of the fullft delta's energy while a trained dora128 spends its full rank-128 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_avp_t1024`
- **ID `M-A4QAY6`**
- **SVD-extracted LoRA r16 from the avp t1024 whole-DiT fullft (fullft_avp_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_avp_t1024.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_avp_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_avp_t2048`
- **ID `M-M6HRK3`**
- **SVD-extracted LoRA r16 from the avp t2048 whole-DiT fullft (fullft_avp_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_avp_t2048.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_avp_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_avp_t256`
- **ID `M-FPMWV8`**
- **SVD-extracted LoRA r16 from the avp t256 whole-DiT fullft (fullft_avp_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_avp_t256.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_avp_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_avp_t4096`
- **ID `M-JKYYM6`**
- **SVD-extracted LoRA r16 from the avp t4096 whole-DiT fullft (fullft_avp_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_avp_t4096.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_avp_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_avp_t512`
- **ID `M-8F3R00`**
- **SVD-extracted LoRA r16 from the avp t512 whole-DiT fullft (fullft_avp_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_avp_t512.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_avp_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_goa_t1024`
- **ID `M-HGAW35`**
- **SVD-extracted LoRA r16 from the goa t1024 whole-DiT fullft (fullft_goa_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_goa_t1024.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_goa_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_goa_t2048`
- **ID `M-3QZSXY`**
- **SVD-extracted LoRA r16 from the goa t2048 whole-DiT fullft (fullft_goa_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_goa_t2048.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_goa_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_goa_t256`
- **ID `M-04436Q`**
- **SVD-extracted LoRA r16 from the goa t256 whole-DiT fullft (fullft_goa_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_goa_t256.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_goa_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_goa_t4096`
- **ID `M-ZP33XZ`**
- **SVD-extracted LoRA r16 from the goa t4096 whole-DiT fullft (fullft_goa_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_goa_t4096.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_goa_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora16_fullft_goa_t512`
- **ID `M-VKYH5P`**
- **SVD-extracted LoRA r16 from the goa t512 whole-DiT fullft (fullft_goa_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r16 recovers only ~4.5% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r16 extraction from fullft_goa_t512.
- **Compare against:**
  - `family:dora16_* (straight-trained DoRA at matched rank 16, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-16 approximation of it
  - `xftdora16_fullft_goa_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora16_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r16-extracted carries only ~4.5% of the fullft delta's energy while a trained dora16 spends its full rank-16 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_avp_t1024`
- **ID `M-8BSVTB`**
- **SVD-extracted LoRA r64 from the avp t1024 whole-DiT fullft (fullft_avp_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_avp_t1024.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_avp_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_avp_t2048`
- **ID `M-NVN7P2`**
- **SVD-extracted LoRA r64 from the avp t2048 whole-DiT fullft (fullft_avp_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_avp_t2048.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_avp_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_avp_t256`
- **ID `M-HC1MRT`**
- **SVD-extracted LoRA r64 from the avp t256 whole-DiT fullft (fullft_avp_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_avp_t256.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_avp_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_avp_t4096`
- **ID `M-N694TE`**
- **SVD-extracted LoRA r64 from the avp t4096 whole-DiT fullft (fullft_avp_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_avp_t4096.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_avp_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_avp_t512`
- **ID `M-0AYE92`**
- **SVD-extracted LoRA r64 from the avp t512 whole-DiT fullft (fullft_avp_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_avp_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_avp_t512.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, avp)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_avp_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_avp_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_avp at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_goa_t1024`
- **ID `M-XJ3ANY`**
- **SVD-extracted LoRA r64 from the goa t1024 whole-DiT fullft (fullft_goa_t1024) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t1024 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_goa_t1024.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t1024 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_goa_t1024` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_goa_t2048`
- **ID `M-1KSQAB`**
- **SVD-extracted LoRA r64 from the goa t2048 whole-DiT fullft (fullft_goa_t2048) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t2048 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_goa_t2048.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t2048 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_goa_t2048` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_goa_t256`
- **ID `M-NSBXX4`**
- **SVD-extracted LoRA r64 from the goa t256 whole-DiT fullft (fullft_goa_t256) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t256 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_goa_t256.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t256 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_goa_t256` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_goa_t4096`
- **ID `M-CNSBQF`**
- **SVD-extracted LoRA r64 from the goa t4096 whole-DiT fullft (fullft_goa_t4096) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t4096 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_goa_t4096.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t4096 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_goa_t4096` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*

#### `xftlora64_fullft_goa_t512`
- **ID `M-2SRNX4`**
- **SVD-extracted LoRA r64 from the goa t512 whole-DiT fullft (fullft_goa_t512) — task-#71 distillation test. Finding: the fullft delta is near-full-rank, so r64 recovers only ~14.8% of its energy (measured across all 10 fullft parents — invariant ±0.2pp); kept as A/B evidence, NOT a shippable model.**
- 1 ckpt tag(s) on board (adapter) · 162 clips
- **Recipe:**
  - kind: safetensors adapter (svd-extracted)
  - method: lora
  - rank/alpha: rank 64, alpha 64.0
  - optimizer: N/A (SVD-extracted adapter — no training optimizer state)
  - extracted from: fullft_goa_t512 (svd-fullft-delta)
- **Why it was made:** Kim's hypothesis (task #71, 2026-07-23/24): a full-DiT fine-tune (fullft) is empirically 'just better' than a matched-rank trained adapter — can that quality be shipped cheaply by <b>SVD-truncating the weight delta</b> (deltaW = W_fullft &minus; W_base) down to a small adapter? Tested by extracting LoRA/DoRA adapters at ranks {16,64,128} from each of 10 fullft arms (avp/goa &times; t256/512/1024/2048/4096) via truncated SVD (Eckart-Young best rank-r approximation of deltaW), then auditioning and measuring the singular-value energy spectrum of the delta itself. The DoRA variant additionally stores magnitude = row_norm(W_fullft). This member is the LoRA r64 extraction from fullft_goa_t512.
- **Compare against:**
  - `family:dora64_* (straight-trained DoRA at matched rank 64, goa)` — extraction (SVD-truncated from a fullft) vs training directly at that rank — the xft_distillation.html A/B
  - `fullft_goa_t512 (the parent fullft checkpoint)` — full near-full-rank weight delta vs this rank-64 approximation of it
  - `xftdora64_fullft_goa_t512` — DoRA magnitude term (row_norm of W_fullft) vs plain LoRA on the IDENTICAL SVD basis
  - the same dora64_goa at MATCHED ENERGY (not just matched rank) — matched-energy view: r64-extracted carries only ~14.8% of the fullft delta's energy while a trained dora64 spends its full rank-64 budget on-task — that asymmetry is WHY extraction loses at equal rank
- **Verdict:** (same as `xftdora128_fullft_avp_t1024`)
- *status: finding-not-shippable*


## fp32cmp_bf16cmp — 17 model(s), 17 with a verdict

#### `bf16cmp_avp_t512_bs8_lr1e4`
- **ID `M-3DKQR8`** · also known as: `bf16cmp_avp_t512_bs8_lr1e4_ptm`, `bf16cmp_avp_t512_bs8_lr1e4_repr`, `bf16cmp_avp_t512_bs8_lr1e4_repr_ptm`
- **fp32-vs-bf16 precision A/B: bf16 attention, DoRA-r128 FusionOpt, avp, T512 (47.6s), bs8, lr1e-4.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1856 clips
- **Training data:** latents_avp — 2393 crops incl. augmentation variants, trigger + longform-caption sidecar
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 2392
- **Why it was made:** Precision A/B on RDNA4: does fp32 attention (vs bf16 throughout) actually improve quality, and is the improvement worth the ~compute cost? Kim's preliminary listening verdict (2026-07-20, recorded in run_meta kim_feedback + WORKLOG): fp32 beats bf16 by ear in most ways (better sound separation, less noisy high end), worse in very few (occasional less punch, likely source-faithfulness not a defect) -- not a comprehensive audit. Two questions flagged as undecided then: bs1-vs-bs4, and whether the fp32 edge holds at longer training context (fixed-20s eval grids can't show trained-context effects) -- the second question is what the fp32frames family (T512-T4096, fp32 only) actually answers, since fp32cmp itself only has T512+T4096, no T2048.
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** Kim's preliminary ear verdict (fp32 > bf16 in most ways) stands, not comprehensively audited. Native-length (T4096, 380s) DSP+CLAP metering completed 2026-07-30 (task #79) after finding + fixing a stale-duration bug affecting several of these arms' native cells -- see WORKLOG 2026-07-29/30. bs1-vs-bs4 still undecided; no dedicated side-by-side listening pass has been done on it.
- *status: in-progress*
- *(also on board as base-render variant: `bf16cmp_avp_t512_bs8_lr1e4_ptm`)*

#### `bf16cmp_avp_t512_bs8_lr1e4_repr`
- **ID `M-3DKQR8`**
- **fp32-vs-bf16 precision A/B: bf16 attention, DoRA-r128 FusionOpt, avp, T512 (47.6s), bs8, lr1e-4. (representative-epoch re-pull)**
- 1 ckpt tag(s) on board (ep7) · 208 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 2392
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `bf16cmp_avp_t512_bs8_lr1e4_repr_ptm`)*

#### `bf16cmp_goa_t512_bs8_lr1e4`
- **ID `M-B5EW7K`** · also known as: `bf16cmp_goa_t512_bs8_lr1e4_ptm`
- **fp32-vs-bf16 precision A/B: bf16 attention, DoRA-r128 FusionOpt, goa, T512 (47.6s), bs8, lr1e-4.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1856 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 5400
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `bf16cmp_goa_t512_bs8_lr1e4_ptm`)*

#### `fp32cmp_avp_t4096_bs1_lr1e4`
- **ID `M-CDY4BY`** · also known as: `fp32cmp_avp_t4096_bs1_lr1e4_ptm`, `fp32cmp_avp_t4096_bs1_lr1e4_repr`, `fp32cmp_avp_t4096_bs1_lr1e4_repr_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs1, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep17, ep18, ep2, ep3, ep4, ep5, ep6, ep7) · 1692 clips
- **Training data:** latents_avp — 2393 crops incl. augmentation variants, trigger + longform-caption sidecar
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 19144
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t4096_bs1_lr1e4_ptm`)*

#### `fp32cmp_avp_t4096_bs1_lr1e4_repr`
- **ID `M-CDY4BY`**
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs1, lr1e-4. (representative-epoch re-pull)**
- 2 ckpt tag(s) on board (ep4, ep7) · 303 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 19144
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t4096_bs1_lr1e4_repr_ptm`)*

#### `fp32cmp_avp_t4096_bs4_lr1e4`
- **ID `M-VGZMYK`** · also known as: `fp32cmp_avp_t4096_bs4_lr1e4_ptm`, `fp32cmp_avp_t4096_bs4_lr1e4_repr`, `fp32cmp_avp_t4096_bs4_lr1e4_repr_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs4, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep2, ep25, ep26, ep3, ep4, ep5, ep6, ep7) · 1692 clips
- **Training data:** latents_avp — 2393 crops incl. augmentation variants, trigger + longform-caption sidecar
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 4784
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t4096_bs4_lr1e4_ptm`)*

#### `fp32cmp_avp_t4096_bs4_lr1e4_repr`
- **ID `M-VGZMYK`**
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs4, lr1e-4. (representative-epoch re-pull)**
- 2 ckpt tag(s) on board (ep4, ep7) · 357 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 4784
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t4096_bs4_lr1e4_repr_ptm`)*

#### `fp32cmp_avp_t4096_bs4_lr5e5`
- **ID `M-SVC9JF`** · also known as: `fp32cmp_avp_t4096_bs4_lr5e5_ptm`, `fp32cmp_avp_t4096_bs4_lr5e5_repr`, `fp32cmp_avp_t4096_bs4_lr5e5_repr_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs4, lr5e-5.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1650 clips
- **Training data:** latents_avp — 2393 crops incl. augmentation variants, trigger + longform-caption sidecar
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 5e-05, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 4784
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t4096_bs4_lr5e5_ptm`)*

#### `fp32cmp_avp_t4096_bs4_lr5e5_repr`
- **ID `M-SVC9JF`**
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs4, lr5e-5. (representative-epoch re-pull)**
- 2 ckpt tag(s) on board (ep4, ep7) · 357 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 5e-05, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 4784
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t4096_bs4_lr5e5_repr_ptm`)*

#### `fp32cmp_avp_t512_bs8_lr1e4`
- **ID `M-5VNP3R`** · also known as: `fp32cmp_avp_t512_bs8_lr1e4_ptm`, `fp32cmp_avp_t512_bs8_lr1e4_repr`, `fp32cmp_avp_t512_bs8_lr1e4_repr_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T512 (47.6s), bs8, lr1e-4.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1856 clips
- **Training data:** latents_avp — 2393 crops incl. augmentation variants, trigger + longform-caption sidecar
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 2392
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t512_bs8_lr1e4_ptm`)*

#### `fp32cmp_avp_t512_bs8_lr1e4_repr`
- **ID `M-5VNP3R`**
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, avp, T512 (47.6s), bs8, lr1e-4. (representative-epoch re-pull)**
- 2 ckpt tag(s) on board (ep4, ep7) · 449 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 2392
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_avp_t512_bs8_lr1e4_repr_ptm`)*

#### `fp32cmp_goa_t4096_bs1_lr1e4`
- **ID `M-VFNDP4`** · also known as: `fp32cmp_goa_t4096_bs1_lr1e4_ptm`, `fp32cmp_goa_t4096_bs1_lr1e4_repr`, `fp32cmp_goa_t4096_bs1_lr1e4_repr_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs1, lr1e-4.**
- 9 ckpt tag(s) on board (ep0, ep1, ep13, ep14, ep2, ep3, ep4, ep5, ep6) · 867 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 3 (0-indexed), step 21600
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_goa_t4096_bs1_lr1e4_ptm`)*

#### `fp32cmp_goa_t4096_bs1_lr1e4_repr`
- **ID `M-VFNDP4`**
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs1, lr1e-4. (representative-epoch re-pull)**
- 3 ckpt tag(s) on board (ep4, ep5, ep6) · 504 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 6 (0-indexed), step 37800
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_goa_t4096_bs1_lr1e4_repr_ptm`)*

#### `fp32cmp_goa_t4096_bs4_lr1e4`
- **ID `M-6Z77DB`** · also known as: `fp32cmp_goa_t4096_bs4_lr1e4_ptm`, `fp32cmp_goa_t4096_bs4_lr1e4_repr`, `fp32cmp_goa_t4096_bs4_lr1e4_repr_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs4, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep15, ep16, ep2, ep3, ep4, ep5, ep6, ep7) · 2231 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 6750
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_goa_t4096_bs4_lr1e4_ptm`)*

#### `fp32cmp_goa_t4096_bs4_lr1e4_repr`
- **ID `M-6Z77DB`**
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs4, lr1e-4. (representative-epoch re-pull)**
- 4 ckpt tag(s) on board (ep4, ep5, ep6, ep7) · 627 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 10800
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_goa_t4096_bs4_lr1e4_repr_ptm`)*

#### `fp32cmp_goa_t4096_bs4_lr5e5`
- **ID `M-GPBY1E`** · also known as: `fp32cmp_goa_t4096_bs4_lr5e5_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs4, lr5e-5.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1032 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 5e-05, weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 6750
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_goa_t4096_bs4_lr5e5_ptm`)*

#### `fp32cmp_goa_t512_bs8_lr1e4`
- **ID `M-N7B91H`** · also known as: `fp32cmp_goa_t512_bs8_lr1e4_ptm`
- **fp32-vs-bf16 precision A/B: fp32 attention, DoRA-r128 FusionOpt, goa, T512 (47.6s), bs8, lr1e-4.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1856 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 5400
- **Why it was made:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- **Compare against:**
  - `bf16cmp_<corpus>_t512_bs8_lr1e4` — precision (fp32 attention vs bf16 throughout) -- the matched corpus/bs/lr sibling, the primary A/B
  - `family:fp32frames` — training context length (T512/1024/2048/4096) at fp32 -- does the precision edge hold as context grows
- **Verdict:** (same as `bf16cmp_avp_t512_bs8_lr1e4`)
- *status: in-progress*
- *(also on board as base-render variant: `fp32cmp_goa_t512_bs8_lr1e4_ptm`)*


## fp32frames — 16 model(s), 16 with a verdict

#### `fp32frames_avp_t1024_bs1_lr1e4`
- **ID `M-CN8QRQ`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T1024 (95.1s), bs1, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 23930
- **Why it was made:** Kim direct, 2026-07-21: 'does the fp32 benefit hold up at longer training context?' The fp32cmp family only compares T512 vs T4096 at fp32 (no T2048), so this sweep fills the T-length axis in full (512/1024/2048/4096) at both batch sizes, both corpora, fp32 only (no bf16 variant here -- that axis is fp32cmp's job). This is the family that actually answers the T4096-vs-T2048 half of Kim's 07-20 open question.
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** T-trend synthesized (CONTINUITY, 2026-07-30, from the audiobox+clap backfill -- task #83): (1) SHORT-render quality is training-length-INVARIANT -- grid-20s PQ spread <=0.2 across T512-T4096, direction inconsistent; mechanically sensible since a 20s render is ~T215 regardless of the checkpoint's trained context. (2) Long-form IS where T matters, but the current data is DURATION-CONFOUNDED: native T4096@380s beats native T2048@190s on PQ in 6/8 cells (biggest: goa bs1 cfg7 6.21->7.14), but render length varies WITH training length in this comparison -- the decisive test (both checkpoints rendering the SAME duration) hasn't been run yet, and it's the same missing comparison the longctx family needs; one render design would settle both. (3) Anomaly flagged for Kim's ear: goa_t2048_bs1 dips on both PQ and CLAP in both length buckets -- possible weak arm or bad epoch, not yet investigated further.
- *status: done*

#### `fp32frames_avp_t1024_bs4_lr1e4`
- **ID `M-M7G2Z8`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T1024 (95.1s), bs4, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 5980
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_avp_t2048_bs1_lr1e4`
- **ID `M-6XJ8KR`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T2048 (190.2s), bs1, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7, ep8, ep9) · 252 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 23930
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_avp_t2048_bs4_lr1e4`
- **ID `M-G45Y4Q`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T2048 (190.2s), bs4, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7, ep8, ep9) · 252 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 5980
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_avp_t4096_bs1_lr1e4`
- **ID `M-YVDAP4`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs1, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7, ep8, ep9) · 243 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 23930
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_avp_t4096_bs4_lr1e4`
- **ID `M-CW4REX`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T4096 (380.4s), bs4, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7, ep8, ep9) · 252 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 5980
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_avp_t512_bs1_lr1e4`
- **ID `M-BE4VF8`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T512 (47.6s), bs1, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 23930
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_avp_t512_bs4_lr1e4`
- **ID `M-VMKVYV`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, avp, T512 (47.6s), bs4, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 5980
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t1024_bs1_lr1e4`
- **ID `M-2MCYD1`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T1024 (95.1s), bs1, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 54000
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t1024_bs4_lr1e4`
- **ID `M-JXANKH`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T1024 (95.1s), bs4, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 13500
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t2048_bs1_lr1e4`
- **ID `M-65JTW2`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T2048 (190.2s), bs1, lr1e-4.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep9) · 225 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 54000
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t2048_bs4_lr1e4`
- **ID `M-6281TM`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T2048 (190.2s), bs4, lr1e-4.**
- 10 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7, ep8, ep9) · 252 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 13500
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t4096_bs1_lr1e4`
- **ID `M-753J0X`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs1, lr1e-4.**
- 4 ckpt tag(s) on board (ep0, ep1, ep2, ep6) · 189 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 6 (0-indexed), step 37800
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t4096_bs4_lr1e4`
- **ID `M-091S2H`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T4096 (380.4s), bs4, lr1e-4.**
- 6 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep8) · 207 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 8 (0-indexed), step 12150
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t512_bs1_lr1e4`
- **ID `M-B2ZRMA`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T512 (47.6s), bs1, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 54000
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*

#### `fp32frames_goa_t512_bs4_lr1e4`
- **ID `M-WX9EB1`**
- **fp32 context-length sweep: DoRA-r128 FusionOpt, goa, T512 (47.6s), bs4, lr1e-4.**
- 1 ckpt tag(s) on board (ep9) · 162 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 9 (0-indexed), step 13500
- **Why it was made:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- **Compare against:**
  - `family:fp32frames (own T ladder)` — training context length T512->T4096 at matched bs -- the primary axis this sweep isolates
  - `fp32cmp_<corpus>_t512_bs8_lr1e4 / fp32cmp_<corpus>_t4096_bs<N>_lr1e4` — cross-check against the fp32cmp family's own T512/T4096 arms (same precision, different bs/lr grid)
- **Verdict:** (same as `fp32frames_avp_t1024_bs1_lr1e4`)
- *status: done*


## fullft — 10 model(s), 10 with a verdict

#### `fullft_avp_t1024`
- **ID `M-PKCKYJ`** · also known as: `fullft_avp_t1024_ptm`
- **Whole-1.4B-DiT FULL fine-tune on avp at T=1024 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 1 ckpt tag(s) on board (ep7) · 88 clips
- **Training data:** latents_avp -- avp own-music crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=1024 latent frames
  - corpus: avp
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on avp-only crops at T=1024 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_avp_t1024) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on avp (dora16_avp*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_avp_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** Kim's 2026-07-23 policy verdict covers this family: full fine-tunes rated above adapter-only by ear, period (the ruling bundles 'fp32 + fullft'; note this campaign trained bf16 — the precision half of that ruling comes from the fp32cmp sibling campaign). Two structural caveats: (1) 8-epoch-era terminal — Kim's same ruling made 15 epochs the new default ('ep7 is often the first really good one'), so this ep7 checkpoint stops at the threshold of good; the winning-arms +40ep continuation exists because of exactly this. (2) NO low-rank distillation path: the delta is near-full-rank — r128 SVD extraction keeps only ~25.7% of its energy, and that fraction is INVARIANT across all 10 parents (±0.2pp over both corpora and T256-T4096; the rank structure is training-regime-determined, not data-determined) — so this model ships/continues as full weights or not at all. Per-T quality trend within THIS family is not separately measured; the fp32frames sibling family (different precision/optimizer) shows T4096>=T2048 production quality at native lengths — indicative only. Corpus: Kim's own avp material — publishable-lineage candidate once the CC dataset path lands, still internal for now.
- *status: done*
- *(also on board as base-render variant: `fullft_avp_t1024_ptm`)*

#### `fullft_avp_t2048`
- **ID `M-37WTQA`** · also known as: `fullft_avp_t2048_ptm`
- **Whole-1.4B-DiT FULL fine-tune on avp at T=2048 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 108 clips
- **Training data:** latents_avp -- avp own-music crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=2048 latent frames
  - corpus: avp
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on avp-only crops at T=2048 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_avp_t2048) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on avp (dora16_avp*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_avp_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_avp_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_avp_t2048_ptm`)*

#### `fullft_avp_t256`
- **ID `M-ARV23Y`** · also known as: `fullft_avp_t256_ptm`
- **Whole-1.4B-DiT FULL fine-tune on avp at T=256 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 3 ckpt tag(s) on board (ep46, ep47, ep7) · 124 clips
- **Training data:** latents_avp -- avp own-music crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=256 latent frames
  - corpus: avp
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on avp-only crops at T=256 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_avp_t256) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on avp (dora16_avp*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_avp_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_avp_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_avp_t256_ptm`)*

#### `fullft_avp_t4096`
- **ID `M-M6M020`** · also known as: `fullft_avp_t4096_ptm`
- **Whole-1.4B-DiT FULL fine-tune on avp at T=4096 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 108 clips
- **Training data:** latents_avp -- avp own-music crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=4096 latent frames
  - corpus: avp
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on avp-only crops at T=4096 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_avp_t4096) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on avp (dora16_avp*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_avp_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_avp_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_avp_t4096_ptm`)*

#### `fullft_avp_t512`
- **ID `M-6C5CYY`** · also known as: `fullft_avp_t512_ptm`
- **Whole-1.4B-DiT FULL fine-tune on avp at T=512 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 1 ckpt tag(s) on board (ep7) · 88 clips
- **Training data:** latents_avp -- avp own-music crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=512 latent frames
  - corpus: avp
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on avp-only crops at T=512 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_avp_t512) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on avp (dora16_avp*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_avp_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_avp_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_avp_t512_ptm`)*

#### `fullft_goa_t1024`
- **ID `M-YGC603`** · also known as: `fullft_goa_t1024_ptm`
- **Whole-1.4B-DiT FULL fine-tune on goa at T=1024 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 1 ckpt tag(s) on board (ep7) · 88 clips
- **Training data:** latents_sa3 -- goa crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=1024 latent frames
  - corpus: goa
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on goa-only crops at T=1024 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_goa_t1024) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on goa (dora16_goa*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_goa_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** Kim's 2026-07-23 policy verdict covers this family: full fine-tunes rated above adapter-only by ear, period (the ruling bundles 'fp32 + fullft'; note this campaign trained bf16 — the precision half of that ruling comes from the fp32cmp sibling campaign). Two structural caveats: (1) 8-epoch-era terminal — Kim's same ruling made 15 epochs the new default ('ep7 is often the first really good one'), so this ep7 checkpoint stops at the threshold of good; the winning-arms +40ep continuation exists because of exactly this. (2) NO low-rank distillation path: the delta is near-full-rank — r128 SVD extraction keeps only ~25.7% of its energy, and that fraction is INVARIANT across all 10 parents (±0.2pp over both corpora and T256-T4096; the rank structure is training-regime-determined, not data-determined) — so this model ships/continues as full weights or not at all. Per-T quality trend within THIS family is not separately measured; the fp32frames sibling family (different precision/optimizer) shows T4096>=T2048 production quality at native lengths — indicative only. Corpus rule: goa-trained weights are never published (commercial-music tier 2) — internal research artifact.
- *status: done*
- *(also on board as base-render variant: `fullft_goa_t1024_ptm`)*

#### `fullft_goa_t2048`
- **ID `M-D26FMK`** · also known as: `fullft_goa_t2048_ptm`
- **Whole-1.4B-DiT FULL fine-tune on goa at T=2048 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 108 clips
- **Training data:** latents_sa3 -- goa crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=2048 latent frames
  - corpus: goa
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on goa-only crops at T=2048 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_goa_t2048) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on goa (dora16_goa*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_goa_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_goa_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_goa_t2048_ptm`)*

#### `fullft_goa_t256`
- **ID `M-MCN7MN`** · also known as: `fullft_goa_t256_ptm`
- **Whole-1.4B-DiT FULL fine-tune on goa at T=256 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 3 ckpt tag(s) on board (ep19, ep20, ep7) · 124 clips
- **Training data:** latents_sa3 -- goa crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=256 latent frames
  - corpus: goa
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on goa-only crops at T=256 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_goa_t256) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on goa (dora16_goa*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_goa_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_goa_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_goa_t256_ptm`)*

#### `fullft_goa_t4096`
- **ID `M-6626NW`** · also known as: `fullft_goa_t4096_ptm`
- **Whole-1.4B-DiT FULL fine-tune on goa at T=4096 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 108 clips
- **Training data:** latents_sa3 -- goa crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=4096 latent frames
  - corpus: goa
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on goa-only crops at T=4096 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_goa_t4096) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on goa (dora16_goa*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_goa_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_goa_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_goa_t4096_ptm`)*

#### `fullft_goa_t512`
- **ID `M-Y2NFWH`** · also known as: `fullft_goa_t512_ptm`
- **Whole-1.4B-DiT FULL fine-tune on goa at T=512 latent frames (LUMI, bf16, FusionOpt lr 1e-4, 8 epochs; epoch=7 final synced). The 'just better, period' baseline that the xft_distillation grid tried — and failed — to compress into a small adapter.**
- 1 ckpt tag(s) on board (ep7) · 88 clips
- **Training data:** latents_sa3 -- goa crops, LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: non-lora (control/latch/other)
  - method: whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)
  - base_model: SA3 medium-base
  - optimizer: FusionOpt, lr 1e-4
  - precision: bf16
  - context_len: T=512 latent frames
  - corpus: goa
  - epochs: 8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)
- **Why it was made:** LUMI FULL fine-tune campaign (Kim direct, 2026-07-17/20): the entire 1.4B-parameter DiT is fine-tuned (not a low-rank adapter) on goa-only crops at T=512 latent frames, bf16, FusionOpt optimizer at lr 1e-4 for 8 epochs. Selective sync: a checkpoint is written every epoch but only epoch=7 (the final) is pulled to local eval storage — Kim 2026-07-20 standardized on last-checkpoint-only ('universally been the best'; full multi-epoch pulls are too slow to eval). This is the high-water-mark run the fp32/adapter comparisons and the xft SVD-extraction grid all measure against. Judgment/verdict on this arm is CONTINUITY's lane (per manifest).
- **Compare against:**
  - the xft_distillation adapters SVD-extracted from THIS run (xft*_fullft_goa_t512) — full fine-tune vs its own rank-16/64/128 SVD compressions — task #71's near-full-rank 'doesn't distill' finding
  - `straight-trained DoRA/LoRA on goa (dora16_goa*/dora128*) at matched corpus` — whole-DiT full fine-tune vs low-rank adapter — the 'fullft is just better, period' baseline claim
  - the other fullft context-length arms (fullft_goa_t256..t4096) — context-length T sweep at full-finetune capacity (same corpus, same recipe, only T differs)
- **Verdict:** (same as `fullft_goa_t1024`)
- *status: done*
- *(also on board as base-render variant: `fullft_goa_t512_ptm`)*


## adamw_bf16_sweep — 8 model(s), 8 with a verdict

#### `adamw_avp_t512_bs1_lr1e4`
- **ID `M-PXNTVF`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on avp, bf16, lr 1e-4, batch 1, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: avp corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** AdamW and FusionOpt were found to land in nearly-orthogonal weight-space basins (dir cos ~0.1, Fusion moves ~2x farther for the same steps -- CONTINUITY's weight-space read, WORKLOG 2026-07-24) -- so the weight delta alone proves the optimizers are DIFFERENT, not which is BETTER. This sweep answers that with metrics: same DoRA-rows r128 arch/rank/target-modules/corpus as the fp32frames family, only the optimizer (AdamW vs FusionOpt) and precision (bf16 vs fp32) differ, so any metric gap traces to the optimizer/precision choice, not a confound.
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** Ep5->ep9 CE mostly improves with more training as expected, but adamw_goa_t512_bs1_lr1e4 shows a striking CLAP collapse (0.261->-0.008 matched-cos) alongside a CE drop from ep5->ep9 -- looks like a possible degeneration case, flagged for a listen, not yet confirmed by ear. No A/B-vs-Fusion verdict yet -- metrics landed on both boards (dora_table.html/model_matrix.html) 2026-07-29/30 but the side-by-side listening comparison Kim/CONTINUITY asked for has not been done.
- *status: done*

#### `adamw_avp_t512_bs4_lr1e4`
- **ID `M-SAYDMG`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on avp, bf16, lr 1e-4, batch 4, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: avp corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*

#### `adamw_avp_t512_bs4_lr2e4`
- **ID `M-CVDH8H`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on avp, bf16, lr 2e-4, batch 4, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=2e-4 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 2e-4 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: avp corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*

#### `adamw_avp_t512_bs4_lr5e5`
- **ID `M-8KYW4J`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on avp, bf16, lr 5e-5, batch 4, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=5e-5 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 5e-5 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: avp corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*

#### `adamw_goa_t512_bs1_lr1e4`
- **ID `M-JC1JNJ`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on goa, bf16, lr 1e-4, batch 1, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: goa corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*

#### `adamw_goa_t512_bs4_lr1e4`
- **ID `M-BM3T1E`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on goa, bf16, lr 1e-4, batch 4, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: goa corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*

#### `adamw_goa_t512_bs4_lr2e4`
- **ID `M-V38DK6`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on goa, bf16, lr 2e-4, batch 4, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=2e-4 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 2e-4 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: goa corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*

#### `adamw_goa_t512_bs4_lr5e5`
- **ID `M-2H5GC4`**
- **AdamW-vs-FusionOpt A/B: DoRA-r128 on goa, bf16, lr 5e-5, batch 4, T512 (47.6s).**
- 2 ckpt tag(s) on board (ep5, ep9) · 216 clips
- **Recipe:**
  - method: DoRA (dora-rows)
  - rank/alpha: rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict
  - base_model: SA3 medium (SAME latent, 10.77 Hz)
  - optimizer: AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=5e-5 -- verified from checkpoint optimizer_states param_groups
  - lr_schedule: constant, peak lr 5e-5 (checkpoint lr_schedulers list is empty -- no scheduler)
  - precision: bf16
  - context_len: T=512 frames, 47.55s (10.7666 fps)
  - corpus: goa corpus (generic name; scale redacted per spec)
  - objective: rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)
  - steps: epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts
- **Why it was made:** (same as `adamw_avp_t512_bs1_lr1e4`)
- **Compare against:**
  - `fp32frames_<corpus>_t512_bs<N>_lr1e4` — optimizer (AdamW here vs FusionOpt) + precision (bf16 vs fp32) -- the matched-config Fusion sibling, same rank/corpus/T/bs/lr
  - `family:adamw_bf16_sweep` — learning rate (1e-4/2e-4/5e-5) and batch size (1/4) within the sweep itself
- **Verdict:** (same as `adamw_avp_t512_bs1_lr1e4`)
- *status: done*


## dronesweep — 8 model(s), 8 with a verdict

#### `dronesweep_adamw_fair_s1`
- **ID `M-K0W9FZ`**
- **LATENT RUNAWAY - 18/54 cells over bound**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- **Why it was made:** Drone-recipe fp32 full-FT sweep (LUMI, 4 recipes x 2 seeds, T1024/bs4/20ep, one arm per GCD): which recipe survives fp32 full-FT WITHOUT the latent runaway that produces the spectral drone.
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** LATENT RUNAWAY - 18/54 clips exceed the sanity bound (median z0 std 1.583, healthy ~1.0). Degraded/droning output; metrics withheld for the bad cells. 36 cells are within bound.
- *status: failed-runaway*

#### `dronesweep_adamw_fair_s2`
- **ID `M-ZHC1GP`**
- **DIVERGED - NaN latents, output is a square wave**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** DIVERGED TO NaN - all 54 clips have entirely non-finite latents. The audio decodes to a FULL-SCALE SQUARE WAVE (peak = rms = 1.0). Do not audition; do not read any metric from it. A training failure, NOT a sound-quality result.
- *status: failed-diverged*

#### `dronesweep_bf16_plain_s1`
- **ID `M-SE16AE`**
- **clean - median z0 std 0.83**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** CLEAN on this seed - all 54 clips within the latent-sanity bound (median z0 std 0.83, healthy ~1.0). Fully scored. One of the two recipes that survives fp32 full-FT.
- *status: clean*

#### `dronesweep_bf16_plain_s2`
- **ID `M-FFSW62`**
- **clean - median z0 std 0.736**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** CLEAN on this seed - all 54 clips within the latent-sanity bound (median z0 std 0.736, healthy ~1.0). Fully scored. One of the two recipes that survives fp32 full-FT.
- *status: clean*

#### `dronesweep_force_scalar_s1`
- **ID `M-ZTY4XG`**
- **LATENT RUNAWAY - 54/54 cells over bound**
- 1 ckpt tag(s) on board (ep7) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** LATENT RUNAWAY - 54/54 clips exceed the sanity bound (median z0 std 3.121, healthy ~1.0). Degraded/droning output; metrics withheld for the bad cells. 0 cells are within bound.
- *status: failed-runaway*

#### `dronesweep_force_scalar_s2`
- **ID `M-1R2M22`**
- **LATENT RUNAWAY - 51/54 cells over bound**
- 1 ckpt tag(s) on board (ep7) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** LATENT RUNAWAY - 51/54 clips exceed the sanity bound (median z0 std 2.958, healthy ~1.0). Degraded/droning output; metrics withheld for the bad cells. 3 cells are within bound.
- *status: failed-runaway*

#### `dronesweep_plain_s1`
- **ID `M-HZPMZF`**
- **clean - median z0 std 0.768**
- 1 ckpt tag(s) on board (ep7) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** CLEAN on this seed - all 54 clips within the latent-sanity bound (median z0 std 0.768, healthy ~1.0). Fully scored. One of the two recipes that survives fp32 full-FT.
- *status: clean*

#### `dronesweep_plain_s2`
- **ID `M-A6SE5S`**
- **clean - median z0 std 0.675**
- 1 ckpt tag(s) on board (ep7) · 54 clips
- **Why it was made:** (same as `dronesweep_adamw_fair_s1`)
- **Compare against:**
  - t
  - h
  - e
  -  
  - o
  - t
  - h
  - e
  - r
  -  
  - t
  - h
  - r
  - e
  - e
  -  
  - d
  - r
  - o
  - n
  - e
  - s
  - w
  - e
  - e
  - p
  -  
  - r
  - e
  - c
  - i
  - p
  - e
  - s
  -  
  - a
  - t
  -  
  - t
  - h
  - e
  -  
  - s
  - a
  - m
  - e
  -  
  - s
  - e
  - e
  - d
- **Verdict:** CLEAN on this seed - all 54 clips within the latent-sanity bound (median z0 std 0.675, healthy ~1.0). Fully scored. One of the two recipes that survives fp32 full-FT.
- *status: clean*


## fp32_winning — 8 model(s), 8 with a verdict

#### `winning_avp_t1024_a45_fp32`
- **ID `M-7D0YTD`** · also known as: `winning_avp_t1024_a45_fp32_ptm`
- **frames control: winning recipe at T1024 (the analysis' context-length optimum).**
- 5 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59) · 656 clips
- **Training data:** latents_avp -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 11960
- **Why it was made:** Isolates context length within the winning recipe — the analysis suggested T1024 as optimal; everything else matches the avp flagship. Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_avp_t512_a45_fp32` — training context length (T1024 vs T512, the analysis' proposed optimum)
- **Verdict:** 20 epochs trained; +40-EPOCH CONTINUATION IN FLIGHT (Kim direct 2026-07-29, resumed toward epoch 60 — the ep7-threshold lesson says these arms were likely still under-trained at ep20; per-epoch ckpts keep every point auditable). The question this arm exists to isolate is OPEN until the continuation lands and the arms are compared per-cell + by ear. No per-arm ear verdict yet.
- *status: in-progress*
- *(also on board as base-render variant: `winning_avp_t1024_a45_fp32_ptm`)*

#### `winning_avp_t512_a128_fp32`
- **ID `M-HB4KK5`** · also known as: `winning_avp_t512_a128_fp32_ptm`
- **alpha control (avp): alpha128 (s=1, undamped) vs the flagship's alpha45.**
- 7 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59, ep94, ep95) · 692 clips
- **Training data:** latents_avp -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 5980
- **Why it was made:** Isolates the alpha-damping lever: identical to the avp flagship except alpha=rank. If the flagship wins, 'adj' damping is real; if this wins, the alpha-audit's damping story needs revision. Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_avp_t512_a45_fp32` — alpha damping — this arm is the a128 control isolating the 'adj' benefit
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_avp_t512_a128_fp32_ptm`)*

#### `winning_avp_t512_a45_bf16`
- **ID `M-R705ZX`** · also known as: `winning_avp_t512_a45_bf16_ptm`
- **precision control (avp): bf16 on the identical winning recipe.**
- 5 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59) · 656 clips
- **Training data:** latents_avp -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 5980
- **Why it was made:** Isolates fp32-vs-bf16 at fixed everything-else — the direct precision A/B on the winning recipe (Kim's 07-23 'fp32 just better' came from the fp32cmp family; this pair retests it inside the winning stack). Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_avp_t512_a45_fp32` — precision — bf16 control on the identical winning recipe
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_avp_t512_a45_bf16_ptm`)*

#### `winning_avp_t512_a45_fp32`
- **ID `M-XWGFWR`** · also known as: `winning_avp_t512_a45_fp32_ptm`
- **FLAGSHIP (avp): the winning recipe — r128 alpha45 fp32 T512 on the full avp corpus.**
- 5 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59) · 656 clips
- **Training data:** latents_avp -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 5980
- **Why it was made:** W's 2026-07-22 DoRA hyperparameter x metric analysis found the top-CLAP levers = alpha<rank ('adj', the rsLoRA-schedule alpha~4*sqrt(r)=45 our linear s=alpha/r scaling turns into deliberate damping), augmentation, and fp32; this arm runs all winning levers together on the full corpus (escaping the 320-crop small-set confound Kim caught). Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_avp_t512_a128_fp32` — alpha damping (a45 'adj' vs a128 s=1) — the flagship's headline lever
  - `winning_avp_t512_a45_bf16` — precision (fp32 vs bf16) at fixed winning recipe
  - `winning_avp_t1024_a45_fp32` — training context length (T512 vs T1024)
  - `winning_avpaug10_t512_a45_fp32` — augmentation (plain full corpus vs aug10)
  - `winning_goa_t512_a45_fp32` — corpus generality (avp vs goa, identical recipe)
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_avp_t512_a45_fp32_ptm`)*

#### `winning_avpaug10_t512_a45_fp32`
- **ID `M-GG6KT8`** · also known as: `winning_avpaug10_t512_a45_fp32_ptm`
- **small-set control: aug10 corpus under the winning recipe.**
- 5 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59) · 656 clips
- **Training data:** latents_avp -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 800
- **Why it was made:** Does fp32 + the winning levers rescue the 320-crop augmented-set result, or was that gain a small-set artifact? Isolates augmentation from corpus size. Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_avp_t512_a45_fp32` — augmentation / small-set rescue (aug10 vs plain full corpus)
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_avpaug10_t512_a45_fp32_ptm`)*

#### `winning_goa_t512_a128_fp32`
- **ID `M-HZC05J`** · also known as: `winning_goa_t512_a128_fp32_ptm`
- **alpha control (goa).**
- 7 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59, ep74, ep75) · 692 clips
- **Training data:** latents_sa3 -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 13500
- **Why it was made:** Same alpha isolation on goa. Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_goa_t512_a45_fp32` — alpha damping (goa control)
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_goa_t512_a128_fp32_ptm`)*

#### `winning_goa_t512_a45_bf16`
- **ID `M-QNBW1R`** · also known as: `winning_goa_t512_a45_bf16_ptm`
- **precision control (goa).**
- 5 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59) · 656 clips
- **Training data:** latents_sa3 -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 13500
- **Why it was made:** Same precision isolation on goa. Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_goa_t512_a45_fp32` — precision (goa control)
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_goa_t512_a45_bf16_ptm`)*

#### `winning_goa_t512_a45_fp32`
- **ID `M-TVC6VF`** · also known as: `winning_goa_t512_a45_fp32_ptm`
- **FLAGSHIP (goa): the winning recipe on the goa corpus.**
- 5 ckpt tag(s) on board (ep10, ep15, ep19, ep50, ep59) · 656 clips
- **Training data:** latents_sa3 -- LUMI-side per-epoch checkpointing
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 19 (0-indexed), step 13500
- **Why it was made:** Same winning-lever stack as the avp flagship, on goa — tests whether the recipe is corpus-general. Campaign design: W 2026-07-22 (winning-fp32 plan); continuation: efp_fp32_winning_continue40 (C, Kim direct).
- **Compare against:**
  - `winning_goa_t512_a128_fp32` — alpha damping (a45 vs a128)
  - `winning_goa_t512_a45_bf16` — precision (fp32 vs bf16)
  - `winning_avp_t512_a45_fp32` — corpus generality (goa vs avp)
- **Verdict:** (same as `winning_avp_t1024_a45_fp32`)
- *status: in-progress*
- *(also on board as base-render variant: `winning_goa_t512_a45_fp32_ptm`)*


## dora16_avp_exploration — 7 model(s), 7 with a verdict

#### `dora16_avp_8ep`
- **ID `M-REHGMB`** · also known as: `dora16_avp_8ep_ptm`
- **DoRA r16 on avp, 8ep — the avp knee at ep4-6, but the deep-listen finding is EARLY epochs win (punch + dorian at ep2/ep6); conditioning collapses late.**
- 3 ckpt tag(s) on board (ep0, ep2, ep6) · 838 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 6 (0-indexed), step 2093
- **Why it was made:** The core r16 avp run. Board verdict put the knee at ep4-6, but Kim's deep-listen found EARLY epochs win (ep2 punch + dorian, ep6 the fine winner) with conditioning collapsing in later epochs — the 'early epochs win' finding that the originals runs also carry.
- **Compare against:**
  - `dora16_avp_originals_* (earlyeps/densewin/win7/64ep)` — same early-epochs-win finding across the originals (no-aug) variants
  - `dora64_avp_tiered_* / dora128adj_avp` — rank — r16 early-win vs larger-rank behavior on avp
- **Note (by-ear):** Early AVP DoRA arm (rank 16) — completed cleanly overnight; superseded as the tempo/quality reference by the later rank/LR comparison arms (r128adj, arm G).
- *(also on board as base-render variant: `dora16_avp_8ep_ptm`)*

#### `dora16_avp_familiarity_8ep`
- **ID `M-K84MRS`** · also known as: `dora16_avp_familiarity_8ep_ptm`
- **DoRA r16 avp 'familiarity' arm — judged the WORST of the avp arms; a minimal bracket kept for completeness.**
- 2 ckpt tag(s) on board (ep0, ep4) · 592 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 4 (0-indexed), step 1495
- **Why it was made:** The 'familiarity' caption arm, rated worst of the avp board arms — kept with a minimal bracket for board completeness rather than for use.
- **Compare against:**
  - `dora16_avp_8ep / freeform` — caption-arm comparison — why familiarity lost
- **Note (by-ear):** Novelty-gating (familiarity_beta) mechanism verified working end-to-end (weight spread 0.87-1.13 after the ep-1 warmup, loss 0.726) — musical-quality impact not yet separately assessed.
- *(also on board as base-render variant: `dora16_avp_familiarity_8ep_ptm`)*

#### `dora16_avp_freeform_8ep`
- **ID `M-8TDAYZ`** · also known as: `dora16_avp_freeform_8ep_ptm`
- **DoRA r16 avp 'freeform' — a NEGATIVE result: a single descriptive caption does NOT fix conditioning collapse (it was never the trigger token's fault).**
- 2 ckpt tag(s) on board (ep31, ep7) · 592 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 31 (0-indexed), step 1152
- **Why it was made:** Analysis-v2 negative result: a single descriptive caption does NOT fix conditioning collapse — prompt/seed ratio 0.22, WORSE than the trigger arm's 0.92. The lesson: it was never the trigger token's fault; ANY single caption reused per crop collapses conditioning. Two picks kept just to show the failure on the board.
- **Compare against:**
  - the tiered/diverse-caption runs (dora64 tiered, newcaptions) — single-caption-per-crop (collapses) vs tiered/diverse captions (fixes it) — the actual cause of conditioning collapse
- **Note (by-ear):** Freeform-caption arm — a single descriptive caption did NOT fix conditioning collapse (prompt/seed ratio 0.22, same as the trigger-token baseline's 0.92); showed caption diversity, not caption quality, is what matters.
- *(also on board as base-render variant: `dora16_avp_freeform_8ep_ptm`)*

#### `dora16_avp_originals_64ep`
- **ID `M-J77CKP`** · also known as: `dora16_avp_originals_64ep_ptm`
- **DoRA r16 avp originals, long 64-epoch ladder (save-every-8) — early wins; Kim HoF points near ep15/ep31; later saves post-collapse, omitted.**
- 3 ckpt tag(s) on board (ep15, ep31, ep7) · 838 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 31 (0-indexed), step 1152
- **Why it was made:** The longer originals ladder (saved every 8 epochs). Early saves win; Kim's hall-of-fame points fall near the ep15/ep31 saves; the ep47-63 saves are post-collapse and omitted — reinforcing early-epochs-win over a long horizon.
- **Compare against:**
  - the shorter originals windows (earlyeps/win7/densewin) — long ladder vs short windows — does the early-win hold over 64 epochs (it does)
- **Note (by-ear):** "D'" — the aug-theory control arm (originals only, no augmentation). Turned out to be the LEAST tempo-stable arm (38% locked), refuting data-multimodality as the tempo-instability driver; instability is optimization-phase/LR-window-driven instead.
- *(also on board as base-render variant: `dora16_avp_originals_64ep_ptm`)*

#### `dora16_avp_originals_densewin`
- **ID `M-KFMENN`** · also known as: `dora16_avp_originals_densewin_ptm`
- **DoRA r16 avp originals — a dense re-run window carrying the fine variants Kim HoF'd (ep2/ep6 fine); ep10 the one late witness.**
- 3 ckpt tag(s) on board (ep10, ep2, ep6) · 838 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 10 (0-indexed), step 396
- **Why it was made:** A dense re-run window of the originals, kept because it carries the fine variants Kim hall-of-famed (ep2/ep6 fine); ep2/ep6 are the winners, ep10 kept as the single late witness.
- **Compare against:**
  - `dora16_avp_originals_win7 / earlyeps` — the fine-variant winners across originals windows
- **Note (by-ear):** One of the fine epoch-window renders that fed the ep7-9 vs. ep31 dual-sweet-spot analysis — see dora128adj_avp_aug10_lr1e4 / the degradation-report findings for the consolidated verdict.
- *(also on board as base-render variant: `dora16_avp_originals_densewin_ptm`)*

#### `dora16_avp_originals_earlyeps`
- **ID `M-BX8E1M`** · also known as: `dora16_avp_originals_earlyeps_ptm`
- **DoRA r16 avp 'originals' (no augs), ep0-4 — spans only the early epochs by design, where the 'early epochs win' finding lives.**
- 3 ckpt tag(s) on board (ep0, ep2, ep4) · 883 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 180
- **Why it was made:** 'Originals' = no augmentations; the deep-listen 'early epochs win' finding lives on these runs. This one spans only ep0-4 by design (all early) — the whole usable spread.
- **Compare against:**
  - `dora16_avp_originals_win7/densewin/64ep` — the originals ladder — early-epoch spread vs longer ladders
- **Note (by-ear):** One of the fine epoch-window renders that fed the ep7-9 vs. ep31 dual-sweet-spot analysis (ep31 = narrow, ringing-adjacent island; ep7-9 later found spectrally healthier).
- *(also on board as base-render variant: `dora16_avp_originals_earlyeps_ptm`)*

#### `dora16_avp_originals_win7`
- **ID `M-PRNEEH`** · also known as: `dora16_avp_originals_win7_ptm`
- **DoRA r16 avp originals — early-win: ep2 and ep6(fine) are Kim's favourites, ep0 anchor; ep10+ omitted as post-collapse.**
- 3 ckpt tag(s) on board (ep0, ep2, ep6) · 838 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 6 (0-indexed), step 252
- **Why it was made:** An 'originals' (no-aug) early-win run: Kim's favourites are ep2 and the ep6 fine variant, ep0 the pre-learning anchor; the late epoch is collapse and omitted.
- **Compare against:**
  - `dora16_avp_originals_densewin / earlyeps` — same early-win finding across the originals re-run windows
- **Note (by-ear):** One of the fine epoch-window renders that fed the ep7-9 vs. ep31 dual-sweet-spot analysis — see dora128adj_avp_aug10_lr1e4 / the degradation-report findings for the consolidated verdict.
- *(also on board as base-render variant: `dora16_avp_originals_win7_ptm`)*


## sa3_goa_dora_47s (original July DoRA) — 7 model(s)

#### `sa3-goa-dora-47s`
- **ID `M-9C6SDV`** · also known as: `sa3-goa-dora-47s_ptm`
- 1 ckpt tag(s) on board (ep0) · 349 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s_ptm`)*

#### `sa3-goa-dora-47s-b4`
- **ID `M-NZZBK2`** · also known as: `sa3-goa-dora-47s-b4_ptm`
- 2 ckpt tag(s) on board (ep0, ep2) · 568 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s-b4_ptm`)*

#### `sa3-goa-dora-47s-b4-cont`
- **ID `M-SWQ8TA`** · also known as: `sa3-goa-dora-47s-b4-cont_ptm`
- 3 ckpt tag(s) on board (ep0, ep3, ep4) · 847 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s-b4-cont_ptm`)*

#### `sa3-goa-dora-47s-r128-adamw`
- **ID `M-57AWDN`** · also known as: `sa3-goa-dora-47s-r128-adamw_ptm`
- 2 ckpt tag(s) on board (ep0, ep7) · 598 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s-r128-adamw_ptm`)*

#### `sa3-goa-dora-47s-r128-fusion`
- **ID `M-PM6MZY`** · also known as: `sa3-goa-dora-47s-r128-fusion_ptm`
- 3 ckpt tag(s) on board (ep0, ep2, ep4) · 802 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s-r128-fusion_ptm`)*

#### `sa3-goa-dora-47s-r128-fusion-caut`
- **ID `M-AHPZR0`** · also known as: `sa3-goa-dora-47s-r128-fusion-caut_ptm`
- 2 ckpt tag(s) on board (ep0, ep2) · 568 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s-r128-fusion-caut_ptm`)*

#### `sa3-goa-dora-47s-r64`
- **ID `M-TVXDBK`** · also known as: `sa3-goa-dora-47s-r64_ptm`
- 3 ckpt tag(s) on board (ep0, ep3, ep7) · 802 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*
- *(also on board as base-render variant: `sa3-goa-dora-47s-r64_ptm`)*


## dora_everything_lr_sweep — 4 model(s), 2 with a verdict

#### `dora128_everything_8ep_lr0.5x`
- **ID `M-HQ1ZXT`** · also known as: `dora128_everything_8ep_lr0.5x_ptm`
- **DoRA r128 on 'everything', 8ep, 0.5x LR — the low-LR arm of the sweep, rendered across all 8 checkpoints on the standard grid.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1972 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 12216
- **Why it was made:** The 0.5x-LR arm of the everything sweep (Kim direct 2026-07-13): saved but never rendered, now rendered across all 8 checkpoints on the standard grid to complete the LR comparison.
- **Compare against:**
  - `dora128_everything_8ep_lr1x / lr3x` — low-LR vs baseline/high — undercooking vs overcooking across the sweep
  - `dora128_everything_8ep_lr0.5x_cont5` — the 8ep run vs its 5-epoch warm-start continuation (length trajectory)
- *(also on board as base-render variant: `dora128_everything_8ep_lr0.5x_ptm`)*

#### `dora128_everything_8ep_lr0.5x_cont5`
- **ID `M-ESHQQR`** · also known as: `dora128_everything_8ep_lr0.5x_cont5_ptm`
- **DoRA r128 'everything' 0.5x-LR — a 5-epoch warm-start continuation (epochs 9-13) so the length trajectory reads contiguously against the original 8ep 0.5x run.**
- 5 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4) · 1126 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 7635
- **Why it was made:** Warm-started (adapter weights + FusionOpt state restored from the 8ep run's final epoch) for 5 more epochs (training epochs 9-13), rendered on the standard grid so the length trajectory continues contiguously from the original 0.5x run.
- **Compare against:**
  - `dora128_everything_8ep_lr0.5x` — the continuation vs its 8-epoch parent — does more training past ep8 help or overcook
- *(also on board as base-render variant: `dora128_everything_8ep_lr0.5x_cont5_ptm`)*

#### `dora128_everything_8ep_lr1x`
- **ID `M-T6H97J`** · also known as: `dora128_everything_8ep_lr1x_ptm`
- **DoRA r128 on 'everything', 8ep, 1x LR — the CANONICAL sweep checkpoint (ep7): the 72-clip weight×length sweep + steps-24 lock-in all used this.**
- 3 ckpt tag(s) on board (ep0, ep4, ep7) · 802 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 12216
- **Why it was made:** The baseline arm of the 'everything'-corpus LR sweep. ep7 is the established-good checkpoint that the 72-clip weight×length sweep and the steps-24 lock-in were all run against — the reference the 0.5x/3x arms are compared to.
- **Compare against:**
  - `dora128_everything_8ep_lr0.5x / lr3x` — learning-rate effect at equal epochs (0.5x vs 1x vs 3x)
- **Note (by-ear):** One of two full-corpus 8-epoch DoRA runs (2e-4) that fed the later avp analysis boards — no distinct standalone listening verdict recorded for this run vs its lr3x sibling.
- *(also on board as base-render variant: `dora128_everything_8ep_lr1x_ptm`)*

#### `dora128_everything_8ep_lr3x`
- **ID `M-654EBM`** · also known as: `dora128_everything_8ep_lr3x_ptm`
- **DoRA r128 on 'everything', 8ep, 3x LR — the high-LR twin of the 1x baseline; likely overcooked late, and that contrast is the point.**
- 3 ckpt tag(s) on board (ep0, ep4, ep7) · 802 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0006, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 12216
- **Why it was made:** The 3x-LR twin of the everything_8ep baseline, rendered at the matching bracket so the board shows the LR effect at equal epochs — expected to overcook in later epochs; the comparison is the deliverable.
- **Compare against:**
  - `dora128_everything_8ep_lr1x` — 3x vs 1x LR at equal epochs — the overcooking onset
- **Note (by-ear):** One of two full-corpus 8-epoch DoRA runs (6e-4) that fed the later avp analysis boards — no distinct standalone listening verdict recorded for this run vs its lr1x sibling.
- *(also on board as base-render variant: `dora128_everything_8ep_lr3x_ptm`)*


## dora128adj_avp — 3 model(s), 3 with a verdict

#### `dora128adj_avp_8ep`
- **ID `M-Q0ZRTD`** · also known as: `dora128adj_avp_8ep_ptm`
- **DoRA r128 α45 on avp, 8ep — the 'best of the avp board arms' (2026-07-08 verdict); the pre-final run before the warm-started final.**
- 3 ckpt tag(s) on board (ep0, ep3, ep6) · 838 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 6 (0-indexed), step 2093
- **Why it was made:** The r128adj (α=45, not α=rank) arm that the 2026-07-08 avp board judged best. This is the pre-final 8-epoch run; its warm-started successor (dora128adj_avp_8ep_final) is the shipped tip.
- **Compare against:**
  - `dora128adj_avp_8ep_final` — pre-final vs the warm-started final checkpoint of the same arm
  - the other avp board arms (dora16_avp_* / dora64_*) — rank/alpha choice — why r128@α45 won the 07-08 board
- **Note (by-ear):** Rank-128-adjusted AVP arm — completed via a warm-started continuation from an accidental partial run; later confirmed among the more tempo-stable ranks (86% stable) in WINTERMUTE's tempo-IQR triangulation.
- *(also on board as base-render variant: `dora128adj_avp_8ep_ptm`)*

#### `dora128adj_avp_8ep_final`
- **ID `M-TJ25R9`** · also known as: `dora128adj_avp_8ep_final_ptm`
- **DoRA r128 α45 on avp — the warm-started FINAL of the winning avp arm; a single checkpoint that IS the deliverable.**
- 1 ckpt tag(s) on board (ep0) · 346 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 0 (0-indexed), step 299
- **Why it was made:** Warm-started from the dora128adj 8ep run's late epoch; only one checkpoint exists and it is the deliverable of the arm the 07-08 avp board rated best.
- **Compare against:**
  - `dora128adj_avp_8ep` — the final vs its pre-final parent run
- **Note (by-ear):** The finished 8/8-epoch rank-128-adjusted AVP run (warm-started from epoch 6) — see dora128adj_avp_8ep for its tempo-stability verdict.
- *(also on board as base-render variant: `dora128adj_avp_8ep_final_ptm`)*

#### `dora128adj_avp_aug10_lr1e4`
- **ID `M-2TN31W`** · also known as: `dora128adj_avp_aug10_lr1e4_ptm`
- **DoRA r128 α45 on avp, aug10, lr1e-4 — 'arm G', the BROADLY SHIPPABLE recipe: escapes both tempo AND spectral collapse, healthy centroid across 300-3000 steps.**
- 28 ckpt tag(s) on board (ep37, ep7, ep74, ep74_iv0.0-0.6, ep74_iv0.0-0.7, ep74_iv0.0-0.8, ep74_iv0.0-0.9, ep74_iv0.0-1.0, ep74_iv0.1-0.6, ep74_iv0.1-0.7, ep74_iv0.1-0.8, ep74_iv0.1-0.9, ep74_iv0.1-1.0, ep74_iv0.2-0.6, ep74_iv0.2-0.7, ep74_iv0.2-0.8, ep74_iv0.2-0.9, ep74_iv0.2-1.0, ep74_iv0.3-0.6, ep74_iv0.3-0.7, ep74_iv0.3-0.8, ep74_iv0.3-0.9, ep74_iv0.3-1.0, ep74_iv0.4-0.6, ep74_iv0.4-0.7, ep74_iv0.4-0.8, ep74_iv0.4-0.9, ep74_iv0.4-1.0) · 1333 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 45.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 74 (0-indexed), step 3000
- **Why it was made:** The recipe flagged 'broadly shippable' in analysis v2 (+tempo_iqr): r128 at lr1e-4 escapes BOTH tempo and spectral collapse — centroid stays healthy from 300-3000 steps and tempo is flat/stable across the whole run (mean IQR 0.94, never collapses). Any epoch is valid, unusually for this board.
- **Compare against:**
  - the everything-8ep LR sweep (lr0.5x/1x/3x) — lr1e-4 as the collapse-free operating point vs the LR extremes that overcook or undercook
  - `dora16/dora64 avp arms` — rank — r128 escaping collapse where smaller ranks don't
- **Note (by-ear):** "Arm G" — tempo-stable across its ENTIRE 3000-step run (mean IQR 0.94, never collapses), the strongest confirmation of the lower-LR/higher-rank stability hypothesis.
- *(also on board as base-render variant: `dora128adj_avp_aug10_lr1e4_ptm`)*


## dora_caption_stack — 3 model(s), 2 with a verdict

#### `dora128_47s_cont_from5`
- **ID `M-P68RVX`** · also known as: `dora128_47s_cont_from5_ptm`
- **DoRA r128 47s new-caption lineage — a fresh warm-start from the 5ep base's last checkpoint, 5 more epochs (lineage epochs 6-10).**
- 28 ckpt tag(s) on board (ep0, ep10_iv0.0-0.6, ep10_iv0.0-0.7, ep10_iv0.0-0.8, ep10_iv0.0-0.9, ep10_iv0.0-1.0, ep10_iv0.1-0.6, ep10_iv0.1-0.7, ep10_iv0.1-0.8, ep10_iv0.1-0.9, ep10_iv0.1-1.0, ep10_iv0.2-0.6, ep10_iv0.2-0.7, ep10_iv0.2-0.8, ep10_iv0.2-0.9, ep10_iv0.2-1.0, ep10_iv0.3-0.6, ep10_iv0.3-0.7, ep10_iv0.3-0.8, ep10_iv0.3-0.9, ep10_iv0.3-1.0, ep10_iv0.4-0.6, ep10_iv0.4-0.7, ep10_iv0.4-0.8, ep10_iv0.4-0.9, ep10_iv0.4-1.0, ep2, ep4) · 1252 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 6750
- **Why it was made:** Kim's direct ask (2026-07-12) to continue from ep5: a fresh warm-start from the newcaptions_5ep last checkpoint for 5 more epochs (lineage epochs 6-10). Kim's remembered preference for this lineage is the mid-continuation point (≈ep8 total).
- **Compare against:**
  - `dora128_47s_newcaptions_5ep` — continuation vs its 5ep base — the ep6-10 trajectory
  - `dora128_newcap_continued_3more` — two different continuation branches from the same caption base
- *(also on board as base-render variant: `dora128_47s_cont_from5_ptm`)*

#### `dora128_47s_newcaptions_5ep`
- **ID `M-PKAFWK`** · also known as: `dora128_47s_newcaptions_5ep_ptm`
- **DoRA r128 on 47s crops, new caption stack, 5ep — the base run; Kim preferred a later (ep8-equiv) point reached via the continuation.**
- 3 ckpt tag(s) on board (ep0, ep2, ep4) · 802 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 6750
- **Why it was made:** The new-caption-stack base run (5 epochs). Kim's listen preferred a later point (≈ep8-equiv, reached through the warm-start continuation); this base's last epoch is the tip before that warm-start.
- **Compare against:**
  - `dora128_47s_cont_from5 / dora128_newcap_continued_3more` — the base vs its warm-start continuations — where Kim's preferred ep8 point lives
- **Note (by-ear):** First tiered-caption A/B (5 epochs) — the new caption system made outputs noticeably more consistent (tighter range) than the old baked-in prompts; an initial "era-steering" read was retracted as seed noise at n=2 seeds.
- *(also on board as base-render variant: `dora128_47s_newcaptions_5ep_ptm`)*

#### `dora128_newcap_continued_3more`
- **ID `M-RP4H8M`** · also known as: `dora128_newcap_continued_3more_ptm`
- **DoRA r128 new-caption — a 3-epoch warm-start continuation (≈ep7-8 overall); its tip is Kim's preferred 'newcap ep8' checkpoint.**
- 2 ckpt tag(s) on board (ep0, ep2) · 568 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 2 (0-indexed), step 4050
- **Why it was made:** A 3-epoch continuation warm-started from the newcaptions ep4 checkpoint (≈ep7-8 overall). Kim prefers the newcap ep8 point, which is this continuation's tip — the wanted checkpoint of the caption-stack lineage.
- **Compare against:**
  - `dora128_47s_cont_from5` — two continuation branches from the same caption base — which reaches Kim's ep8 preference
- **Note (by-ear):** 3-epoch warm-started continuation of the newcaptions run (loss 0.766→0.747), producing the "ep7-equivalent" newcaptions checkpoint referenced in later caption-system comparisons.
- *(also on board as base-render variant: `dora128_newcap_continued_3more_ptm`)*


## lreq_goa — 3 model(s)

#### `lreq_goa_lr1e4`
- **ID `M-HFN3YE`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 360 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `lreq_goa_lr2e4`
- **ID `M-QJW67W`**
- 7 ckpt tag(s) on board (ep1, ep11, ep13, ep3, ep5, ep7, ep9) · 504 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `lreq_goa_lr5e5`
- **ID `M-PB0YZ9`**
- 10 ckpt tag(s) on board (ep11, ep15, ep19, ep23, ep27, ep3, ep31, ep35, ep39, ep7) · 720 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## precision_ladder — 3 model(s)

#### `precision_ladder_t256_bf16mixed`
- **ID `M-2RFDS7`**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `precision_ladder_t256_fp16mixed`
- **ID `M-XPPZT1`**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `precision_ladder_t256_fp32`
- **ID `M-JQ8ZVG`**
- 1 ckpt tag(s) on board (ep9) · 54 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## subloss — 3 model(s)

#### `subloss_v3sel_k12`
- **ID `M-F7W1YX`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 360 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `subloss_v3sel_k2`
- **ID `M-ZV8Y2G`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 360 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `subloss_v3sel_k5`
- **ID `M-SY1HZC`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 360 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## subloss_goa — 3 model(s)

#### `subloss_goa_k12`
- **ID `M-SR1K2Q`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 378 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `subloss_goa_k2`
- **ID `M-NEZ3A4`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 378 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*

#### `subloss_goa_k5`
- **ID `M-2AZX4C`**
- 5 ckpt tag(s) on board (ep11, ep15, ep19, ep3, ep7) · 378 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## dora16_special — 2 model(s), 2 with a verdict

#### `dora16_glitchheal_5ep_2xlr`
- **ID `M-KY1781`** · also known as: `dora16_glitchheal_5ep_2xlr_ptm`
- **DoRA r16 'glitch-heal' at 2x LR — a NEGATIVE result: the heal adapter OVERWRITES rather than heals; its own learned voice dominates.**
- 2 ckpt tag(s) on board (ep0, ep4) · 598 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: lr 0.0002, betas [0.9, 0.95], weight_decay 0.01, eps 1e-08
  - epochs: epoch 4 (0-indexed), step 25
- **Why it was made:** Negative result (2026-07-04): the glitch-heal adapter OVERWRITES rather than heals — at 2x LR its own learned voice dominates, the glitch becomes a minor accent, and the final adapter is near-identical on a clean vs glitched base. Two picks kept to show start-vs-end.
- **Compare against:**
  - the base checkpoint it was meant to heal — heal-vs-overwrite: the adapter imposing its voice instead of correcting the target
- **Note (by-ear):** Weight-mutation "healing" experiment — a 5-epoch LoRA trained on a glitched base neither heals nor compensates; the adapter simply dominates (~5x more shift than the glitch itself), and the glitch survives underneath as an accent.
- *(also on board as base-render variant: `dora16_glitchheal_5ep_2xlr_ptm`)*

#### `dora16_goa_newstack_8ep`
- **ID `M-HKNGKS`** · also known as: `dora16_goa_newstack_8ep_ptm`
- **DoRA r16 on goa, new caption stack, 8ep — Kim's HEADLINE A/B: new caption stack vs the old hall-of-fame best; full bracket.**
- 3 ckpt tag(s) on board (ep0, ep3, ep7) · 802 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 16, alpha 16.0
  - optimizer: lr 0.0002, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 10800
- **Why it was made:** Kim's headline A/B: the new caption stack vs the old hall-of-fame best on goa. Full bracket; a mid checkpoint mirrors the HoF pick's step count as a natural comparison point.
- **Compare against:**
  - the prior goa hall-of-fame best checkpoint — new caption stack vs the old HoF best — the headline caption-stack A/B
- **Note (by-ear):** New caption-stack vs. old Hall-of-Fame checkpoint, epoch-by-epoch A/B rendered (30 clips) for Kim's direct listening — no recorded verdict yet on which stack won.
- *(also on board as base-render variant: `dora16_goa_newstack_8ep_ptm`)*


## dora64_tiered_lr — 2 model(s), 2 with a verdict

#### `dora64_avp_tiered_lr1e4`
- **ID `M-GJWNVK`** · also known as: `dora64_avp_tiered_lr1e4_ptm`
- **DoRA r64 avp tiered captions, lr1e-4 — UNDER-cooked: never reaches the sweet spot 2e-4 hits at ep0; usable band ep3-7.**
- 3 ckpt tag(s) on board (ep0, ep3, ep7) · 883 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 64, alpha 32.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 7 (0-indexed), step 288
- **Why it was made:** The lr1e-4 arm of the r64 tiered-caption pair. It is under-cooked — it never reaches the sweet spot that the 2e-4 arm hits at ep0 — but its usable band is broad (ep3-7, esp ep7); ep0 is the pre-learning anchor.
- **Compare against:**
  - `dora64_avp_tiered_lr2e4` — lr1e-4 (under-cooked, broad usable band) vs lr2e-4 (overshoots by ep0) — the LR sweet-spot on r64 tiered
- **Note (by-ear):** r64 tiered-caption arm (1e-4) — same caption-diversity-fixes-collapse result as its lr2e4 sibling; part of the recipe validation (r64 + tiered captions + early-stop ~ep7-9).
- *(also on board as base-render variant: `dora64_avp_tiered_lr1e4_ptm`)*

#### `dora64_avp_tiered_lr2e4`
- **ID `M-MSB20T`** · also known as: `dora64_avp_tiered_lr2e4_ptm`
- **DoRA r64 avp tiered captions, lr2e-4 — OVERSHOOTS: ep0 is the single usable checkpoint (caught at the edge of breakdown); every later epoch useless.**
- 1 ckpt tag(s) on board (ep0) · 361 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 64, alpha 32.0
  - optimizer: PRUNED (slim .weights.ckpt — no optimizer_states)
  - epochs: epoch 0 (0-indexed), step 36
- **Why it was made:** The lr2e-4 arm: ep0 is the SINGLE usable checkpoint, caught right at the edge of breakdown ('vertical movement + pitches, solid beat'). 2e-4 overshoots the sweet spot by ep0 and every later epoch is useless even as an effect; ep1 optional as the cliff witness.
- **Compare against:**
  - `dora64_avp_tiered_lr1e4` — lr2e-4 (overshoots, ep0-only) vs lr1e-4 (under-cooked, broad band) — how sharp the LR sweet-spot is on r64
- **Note (by-ear):** r64 tiered-caption arm (2e-4) — tiered/diverse captions DID fix conditioning collapse where freeform failed (prompt/seed ratio 1.5-2.65 vs freeform's 0.22); later superseded as the leading recipe by the prompt-arc finding.
- *(also on board as base-render variant: `dora64_avp_tiered_lr2e4_ptm`)*


## longctx — 2 model(s), 2 with a verdict

#### `longctx_t1024_r128`
- **ID `M-505NWG`** · also known as: `longctx_t1024_r128_ptm`
- **DoRA r128 trained at T=1024 context (task-50 long-context arm) — the training-length-mismatch fix arm (train at the length you generate at). Verdict: C's lane.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1856 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 2696
- **Why it was made:** task-50 long-context arm: a r128 DoRA trained at T=1024 latent frames to test the training-length-mismatch fix — train at the same context length you generate at, rather than training short and extrapolating. The regime-comparison flagship of task-50; judgment is CONTINUITY's lane.
- **Compare against:**
  - `longctx_t2048_r128` — training context length T=1024 vs T=2048 in the long-context regime
  - the fullft / dora arms trained at shorter T then generating long — train-at-generation-length vs train-short-extrapolate-long — the mismatch this arm addresses
- **Verdict:** Board-metered at NATIVE generation length — the datapoint the length-mismatch hypothesis needs: cfg7 w1.0 95s: PQ 7.46, CLAP 0.30 (n=32). Strong for a native-length render (the fp32frames native cells span ~6.2-7.8 PQ), which supports train-at-the-length-you-generate — but the decisive matched A/B (this model at native length vs a T512-trained sibling generating the SAME length) has not been assembled yet, and no ear verdict exists. Promising, unsynthesized; graduates when the cross-model native-length comparison and Kim's listen land.
- *status: in-progress*
- *(also on board as base-render variant: `longctx_t1024_r128_ptm`)*

#### `longctx_t2048_r128`
- **ID `M-J08YRH`** · also known as: `longctx_t2048_r128_ptm`
- **DoRA r128 trained at T=2048 context (task-50 long-context arm) — the training-length-mismatch fix arm (train at the length you generate at). Verdict: C's lane.**
- 8 ckpt tag(s) on board (ep0, ep1, ep2, ep3, ep4, ep5, ep6, ep7) · 1608 clips
- **Training data:** latents_sa3 — 5400 goa crops, longform-caption sidecar (t3 100% coverage)
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 128, alpha 128.0
  - optimizer: lr 0.0001, weight_decay 0.01, eps 1e-08
  - epochs: epoch 7 (0-indexed), step 5400
- **Why it was made:** task-50 long-context arm: a r128 DoRA trained at T=2048 latent frames to test the training-length-mismatch fix — train at the same context length you generate at, rather than training short and extrapolating. The regime-comparison flagship of task-50; judgment is CONTINUITY's lane.
- **Compare against:**
  - `longctx_t1024_r128` — training context length T=1024 vs T=2048 in the long-context regime
  - the fullft / dora arms trained at shorter T then generating long — train-at-generation-length vs train-short-extrapolate-long — the mismatch this arm addresses
- **Verdict:** Board-metered at NATIVE generation length — the datapoint the length-mismatch hypothesis needs: cfg16 w1.0 190s: PQ 7.95, CLAP 0.40 (n=8). Strong for a native-length render (the fp32frames native cells span ~6.2-7.8 PQ), which supports train-at-the-length-you-generate — but the decisive matched A/B (this model at native length vs a T512-trained sibling generating the SAME length) has not been assembled yet, and no ear verdict exists. Promising, unsynthesized; graduates when the cross-model native-length comparison and Kim's listen land.
- *status: in-progress*
- *(also on board as base-render variant: `longctx_t2048_r128_ptm`)*


## dora_rank_extreme — 1 model(s), 1 with a verdict

#### `dora256_avp_aug10_lr7e5`
- **ID `M-S9QYKX`** · also known as: `dora256_avp_aug10_lr7e5_ptm`
- **DoRA r256 on avp, aug10, lr7.5e-5 — the rank-256 data point; a single checkpoint (the run only fits on the cluster, not locally).**
- 1 ckpt tag(s) on board (ep3) · 346 clips
- **Recipe:**
  - kind: dora/lora
  - method: dora-rows
  - rank/alpha: rank 256, alpha 64.0
  - optimizer: lr 7e-05, betas [0.9, 0.95], weight_decay 0.01, eps 1e-08
  - epochs: epoch 3 (0-indexed), step 300
- **Why it was made:** The r256 data point on the rank axis. A rank this large does not fit for local training (four attempts), so it is a cluster-only run; the single surviving checkpoint is included as the r256 anchor for the rank sweep.
- **Compare against:**
  - `dora16 / dora64 / dora128 avp arms` — rank axis — does r256 buy anything over r128, or just cost more
- **Note (by-ear):** "Arm H" (rank 256) — ruled out after repeated OOM/hang failures on the 16GB card across 4 attempts; this is the lone surviving checkpoint from a run that never completed. Max viable local rank stays 128.
- *(also on board as base-render variant: `dora256_avp_aug10_lr7e5_ptm`)*


## fullft_bigset — 1 model(s)

#### `fullft_bigset`
- **ID `M-FAGVCW`**
- 2 ckpt tag(s) on board (ep3, ep7) · 49 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## fullft_mixed_avp_goa — 1 model(s)

#### `fullft_mixed_avp_goa_t4096`
- **ID `M-6WMGSK`**
- 1 ckpt tag(s) on board (ep0) · 54 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## fullft_mixed_wdfix_ddpbug — 1 model(s)

#### `fullft_mixed_wdfix_ddpbug`
- **ID `M-13C8RA`**
- 1 ckpt tag(s) on board (ep7) · 18 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## smoke — 1 model(s)

#### `smoke_r256_a256_lr1e4_f512_bs8`
- **ID `M-9VQNRH`** · also known as: `smoke_r256_a256_lr1e4_f512_bs8_ptm`
- **Pipeline smoke-test run (r256/a256, LUMI) — rendered for sanity confirmation only, NOT a model candidate.**
- 2 ckpt tag(s) on board (ep2, ep5) · 464 clips
- **Training data:** latents_sa3 subset (smoke)
- **Recipe:** LUMI pipeline smoke run: DoRA r256 α256, T=512 crops, batch 8, lr 1e-4 — sanity artifact, not a model candidate.
- *status: not-a-model-candidate*
- *(also on board as base-render variant: `smoke_r256_a256_lr1e4_f512_bs8_ptm`)*


## x0eq — 1 model(s)

#### `x0eq_sub5_goa`
- **ID `M-W9VXDJ`**
- 6 ckpt tag(s) on board (ep0, ep11, ep15, ep19, ep3, ep7) · 432 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


## x0eq_goa — 1 model(s)

#### `x0eq_goa`
- **ID `M-6PJZEZ`**
- 6 ckpt tag(s) on board (ep0, ep11, ep15, ep19, ep3, ep7) · 432 clips
- *No override entry — recipe/verdict not yet recorded. Add one to `Misc/models_index_overrides.json` (or see the Legacy snapshot below for July by-ear notes) and re-run.*


---

# Legacy hand-compiled snapshot (2026-07-04)

> [!NOTE]
> Below is the original hand-authored index, kept verbatim for its by-ear verdicts. It covers the July DoRA runs **and** the control-head families (onset FiLM / style fingerprint / LatCH guidance / ES conditioners / mutated bases / adapter soups) that are **not on the live text-to-audio board above**, so the generator cannot reach them. Source: `Misc/model_index_legacy.md`.

## ⭐ Top-Tier Models (Ship / Use)

| Role | Model | Path | Why |
|------|-------|------|-----|
| **DoRA** | r128f exponential-ascending soup | `Mantu/sa3_lora_runs/soups_dora/r128f_expasc.ckpt` | Best DoRA soup; base run fréchet **0.0750** |
| **Onset** | FusionCC (CC-loss) | `Mantu/sa3_control_runs/onset_FusionCC_lr1e-4_randomcrop/riffer_final.pt` | Best onset steering: corr g2 **.880** (vs .584 baseline) |
| **Onset (ONNX)** | FUSION lr2e-5 40ep exppeak soup | `Mantu/sa3_control_runs/onset_FUSION_lr2e5_40epoch/soup_exppeak.pt` | Baked into ONNX DiT; monotonic 3→11 onsets/sec |
| **Style** | fpC AdamW | `Mantu/sa3_control_runs/style_fpC_adamw/riffer_final.pt` | Ship this — genre-CC variant **hurt** steering |
| **ES cond** | v3 field-best | `Mantu/sa3_control_runs/es_conditioner_v3/cond_fieldbest.npz` | Best grid point (a=1.17, b=−0.38) |

> [!WARNING]
> **Earlier in this session I recommended `style_fpC_genrecc`** — that was wrong! WORKLOG says genre-CC **HURT** steering (Goa 0.92→0.65, Psy 0.46→0.03). Use `style_fpC_adamw` instead.

---

## 1. DoRA Finetunes

All under `Mantu/sa3_lora_runs/`.

### sa3-goa-dora-47s-r128-adamw ⭐ Best clean run
- **Type:** DoRA rank-128, AdamW, 8 epochs, 47s crops
- **Checkpoints:** `epoch={0-7}-step={1350-10800}.ckpt` (2.0 GB each)
- **Quality:** Fréchet distance **0.0750** — the baseline winner in cautious A/B
- **Params:** Use as-is or via soups

### sa3-goa-dora-47s-r128-fusion
- **Type:** DoRA rank-128, FusionOpt (SF-NorMuon), 8 epochs
- **Checkpoints:** `epoch={0-7}-step={1350-10800}.ckpt` (4.0 GB each)
- **Quality:** Clean run, feeds into `r128f_*` soups

### sa3-goa-dora-47s-r128-fusion-caut ⚠️ DIVERGED
- **Type:** DoRA rank-128, FusionOpt + Cautious masking
- **Checkpoints:** 8 epochs (4.0 GB each) — **NaN after ep2**
- **Quality:** Healthy ep0–2 fréchet 0.0785 (competitive), then **full collapse**
- **Root cause:** Cautious rescale inflates effective LR by +37% (keep_frac ≈ 0.53)
- **Verdict:** ep0–2 usable as palette option; ep3+ garbage

### sa3-goa-dora-47s-r64
- **Type:** DoRA rank-64, 8 epochs
- **Checkpoints:** 8 × 1.0 GB

### sa3-goa-dora-47s-b4 / b4-cont
- **Type:** DoRA default rank, batch-4 variants
- **Checkpoints:** 3–5 epochs (260 MB each)

### dora128_300trk
- **Type:** DoRA rank-128, 300-track/607-crop subset, T=4096
- **Notes:** First full run. "Lightning tqdm SILENT in non-TTY"

### DoRA Soups (`soups_dora/`)

| Soup | File | Size | Notes |
|------|------|------|-------|
| **r128f expasc** ⭐ | `r128f_expasc.ckpt` | 667 MB | Exponential ascending blend of r128-fusion epochs |
| r128f expdesc | `r128f_expdesc.ckpt` | 667 MB | Exponential descending (more early-epoch weight) |
| r128f goodearly | `r128f_goodearly.ckpt` | 667 MB | Hand-picked early-epoch blend |
| r64 expasc/desc/goodearly | `r64_*.ckpt` | 335 MB | Rank-64 equivalents |
| r16 expasc/desc/goodearly | `r16_*.ckpt` | 87 MB | Rank-16 equivalents |
| cross 10A90F–30A70F | `cross_*A*F.ckpt` | 667 MB | AdamW × Fusion cross-optimizer blends |

### DoRA Cautious Soups (`soups_dora_caut/`)

| Soup | File | Notes |
|------|------|-------|
| r128caut expasc | `r128caut_expasc.ckpt` | Only ep0–2 are healthy |
| r128caut expdesc | `r128caut_expdesc.ckpt` | Use with caution |
| r128caut goodearly | `r128caut_goodearly.ckpt` | |

---

## 2. Onset FiLM Heads

All under `Mantu/sa3_control_runs/`.

### onset_FusionCC_lr1e-4_randomcrop ⭐ Best onset head
- **Type:** FusionOpt + Control-Consistency loss, lr1e-4, random crop
- **Checkpoints:** `riffer_final.pt` (1.9 GB) + 10 intermediates + ONNX exports
- **Quality:** **First significant win of the campaign.**
  - Corr/gain: g1 .558→**.752**, g2 .584→**.880** (P=.99 significant), g3 .702→**.889**
  - Tracks mid-range beautifully: req 5/6/7 → meas 6.0/6.8/7.6 (vs baseline's 8.5–8.7 overshoot)
- **Params:** onset_gain 1.0–3.0; density 3–12

### onset_FUSION_lr2e5_40epoch ⭐ ONNX reference
- **Type:** FusionOpt, lr2e-5, 40 epochs
- **Checkpoints:** `riffer_final.pt`, **`soup_exppeak.pt`** (239 MB), `soup_expasc.pt` + 40 intermediates
- **Quality:** Monotonic, calibrated steering: density 3→4.88, 11→11.15 onsets/sec
- **Notes:** `soup_exppeak.pt` is baked into the ONNX DiT control graph (Kevin Griffing VST handoff)
- **Params:** onset_gain 1.0–3.0; full density range

### onset_FusionCaut_lr1e-4_randomcrop — Palette option
- **Type:** FusionOpt + Cautious masking
- **Checkpoints:** `riffer_final.pt` (1.9 GB) + ONNX exports + `landscape/`
- **Quality:** "Quality TRADE not win — drier/cleaner separation, muted highs, smears when pushed. Over-trains: **ep5 sweet spot**, ep10 over-injects at low density."
- **Verdict:** Keep as palette option with early-stop; **not default**
- **Params:** onset_gain ≤ 2.0; ep5 checkpoint preferred

### onset_Fusion_lr1e-4_randomcrop — FusionCC baseline
- **Type:** FusionOpt, lr1e-4, random crop, 10 epochs
- **Checkpoints:** `riffer_final.pt` (239 MB) + `soup_exppeak.pt` + ONNX exports
- **Quality:** Corr/gain: g1 .582, g2 .657, g3 .793 — the "E_fusion" baseline

### onset_density_400trk_crop1024 — Original scalar head
- **Type:** Onset density scalar, 400 tracks, crop 1024
- **Checkpoints:** `riffer_final.pt` (232 MB) + 12 intermediates
- **Quality:** "Steers SA3 output onset density at corr **+0.90** (gain 1): sparse→dense = 4.3→8.3 onsets/sec"

### onset_FUSION_lr8e5_* (10ep, 1ep, 1.2ep)
- **Type:** Higher-LR FusionOpt variants (quick experiments)
- **Checkpoints:** `riffer_final.pt` + intermediates

### onset_FUSION_lr1e4_5000_* (FIXED, ckpt, crop1024, crop512)
- **Type:** lr1e-4 / 5000-step variants with different crop sizes
- **Checkpoints:** Various `riffer_step*.pt`

### onset_AdamW_lr7.5e-5_randomcrop_20ep
- **Type:** AdamW baseline, lr7.5e-5, 20 epochs, random crop
- **Checkpoints:** `riffer_final.pt` + 19 eval subdirs
- **Notes:** Part of optimizer bracket (AdamW vs FusionOpt)

### onset_Fusion_opb_* (10ep, 30ep, lr1.5e-4_30ep)
- **Type:** Onset-per-beat mode (onsets aligned to beat grid)
- **Notes:** `opb_30ep` aborted (only train.log). `opb_lr1.5e-4_30ep` has 29 steps + evals.

---

## 3. Style Fingerprint Heads

All under `Mantu/sa3_control_runs/`.

### style_fpC_adamw ⭐ Ship this
- **Type:** Fingerprint variant C (genre k+1 + year = 13 dims), AdamW
- **Checkpoints:** `riffer_final.pt` (957 MB) + 7 intermediates
- **Quality:** Best genre steering. Goa confidence **0.92**, Psy **0.46**
- **Params:** style_gain 0.25–1.0; `fp_in_dim=13`, `fp_variant="C"`

### style_fpC_genrecc ⚠️ Don't use
- **Type:** Fingerprint C + Genre-Consistency loss
- **Checkpoints:** `riffer_final.pt` (957 MB) + 7 intermediates
- **Quality:** Genre-CC **HURT** steering: Goa 0.92→**0.65**, Psy 0.46→**0.03**
- **Verdict:** "Meter-in-the-gradient does NOT transfer onset to genre — adds interference not signal"

### style_fpA_adamw
- **Type:** Fingerprint variant A (genre + year + bpm + sync = 15 dims), AdamW
- **Checkpoints:** `riffer_final.pt` (957 MB), `riffer_step5400.pt`

### style_fpB_adamw ❌ Empty
- **Type:** Never trained (0 files)

---

## 3b. SA3 LatCH Guidance Heads (gradient guidance — NOT a FiLM adapter)

> [!IMPORTANT]
> **This whole family is missing from the tables above because it does not live under `Mantu/` —**
> it lives in the SA3 repo: `stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt`.
> These are a **different control mechanism** from §2/§3. §2/§3 are **forward FiLM adapters** baked
> into the DiT (a pure forward mod; gains **1.0–3.0** / **0.25–1.0**). LatCH heads are a **gradient
> guidance** method — the DiT runs forward-only, autograd flows through the ~5–7 M-param head only
> (fp32 head, fp16 CK-FA DiT). **Do not cross the gains:** LatCH energy heads operate at **gain ≈512**,
> ~170× the adapter gains — feeding 3.0 to a LatCH head does nothing; feeding 512 to a FiLM adapter blows up.

**14 medium heads** (`adaln_zero`, `standardized`, **depth 4**): `beat_activation`, `downbeat_activation`,
`hpcp`, `onset_envelope`, `onset_envelope_drums`, `rms_drums`, `rms_energy_air`, `rms_energy_bass`,
`rms_energy_body`, `rms_energy_mid`, `spectral_flatness`, `spectral_flux`, `spectral_kurtosis`,
`spectral_skewness`.

- **Load via the canonical loader, never hardcode arch:** `stable_audio_3.models.latch.load_latch_from_checkpoint(path, device)`
  auto-detects in/out ch, dim, depth, num_heads, t_injection and attaches `std_mean`/`std_std` as `head.metadata`.
  Constructing `LatCH(dim=256, depth=6, …)` **silently fails** to load these (state-dict mismatch).
- **Sibling `latch_weights_sa3/` (no `_medium`) = epoch-numbered snapshots** (`_ep<N>.pt`, simpler `concat`
  keys, **no `_best.pt`**). Not the production heads — don't load them as medium heads.
- **Operating gain ≈ 512 for energy heads** (NOT 48–96, NOT 128 — **gain 128 is a dead zone**). Ladder
  128→1024 monotonic (~40–47× MERT-Δ growth). At gain 8, `corr=1.0` is a **mirage** (rank-corr ≠ magnitude) — judge by spread.
- **Steering verdict (14-head sweep, 2026-06-28):**
  - **Strong:** `rms_energy_bass` (+5.1 dB @512), `rms_energy_mid` (+6.0 dB @512)
  - **Moderate:** `rms_energy_body`, `spectral_skewness`, `rms_energy_air`
  - **Dead at any weight:** `beat/downbeat/onset` activation heads, `hpcp`, `spectral_kurtosis` (perturb CE without steering)
- **`spectral_skewness` was re-trained with EMA (2026-06-29) and reversed its "architecture-limited" verdict** —
  the ceiling was **damping-limited**, fixed by EMA 0.999 + grad-accum + early-stop, not a lower LR.
- **Eval energy/timbre heads with the MERT _mid_ layer** — the upper layer is melody/harmony and blind to a
  bass-RMS change (it mislabeled the two best heads "dead" on the first pass).
- **CPU eval path exists:** `onnx/latch_eval_server.py` + `submit_latch_job.py` (plain DiT on ORT CPU, torch
  autograd through the head only). Provenance/results: riffer-evals `latch_sweep.html`, mir memory `sa3-latch-head-sweep`.

---

## 4. ES Conditioners

All under `Mantu/sa3_control_runs/`.

### es_conditioner_v3 ⭐ Best ES
- **Files:** `cond_es_best.npz`, **`cond_fieldbest.npz`**, `cond_final.npz`, `es_state.npz`, `es_history.json`
- **Quality:** "Real but modest transfer. Paired improvement +0.28 onsets/s mean error."
  - Field-guided jump found best grid point OFF the walk line (a=1.17, b=−0.38)
  - Terrain is SMOOTH and walkable; descent continues past gen-20 endpoint
- **Notes:** These are raw FiLM layer weights (`.npz`), not standard adapter `.pt` files

### es_conditioner_v2 ⚠️ Failed
- **Quality:** Per-coordinate norm issue — no real learning

### es_conditioner_pilot ⚠️ Failed
- **Quality:** No real learning — seed-window luck only

---

## 5. Riffer / Audio-Reference Adapters

All under `Mantu/sa3_control_runs/`.

### riffer_400trk_lr1e-4_crop1024
- **Checkpoints:** `riffer_final.pt` (239 MB) + 10 intermediates
- **Quality:** "Retrained full-effect at 400trk/lr1e-4 to test if more-data/lower-LR smooths"

### riffer_200trk_* (6 optimizer variants)
- **Type:** 200-track riff adapter optimizer bracket (AdamW/Fusion/SF-AdamW, various LRs)
- **Quality:** "Riffer works, but only reference-specific at lr1e-4 (peaks step ~6000, then elbow-declines); heavier LR mode-collapses"

---

## 6. Onset Adapter Soups

Under `Mantu/sa3_control_runs/soups/` (12 profiles for onset_FUSION_lr2e5_40epoch):

| Soup | Profile | Size |
|------|---------|------|
| soup_expasc_ep10-40 | Exponential ascending | 239 MB |
| soup_exppeak20_ep10-40 | Exponential peak at ep20 | 239 MB |
| soup_exppeak25_ep10-40 | Exponential peak at ep25 | 239 MB |
| soup_asc_ep10-40 | Linear ascending | 239 MB |
| soup_desc_ep10-40 | Linear descending | 239 MB |
| soup_cosasc_ep10-40 | Cosine ascending | 239 MB |
| soup_cosdesc_ep10-40 | Cosine descending | 239 MB |
| soup_sine_ep10-40 | Sine | 239 MB |
| soup_tri_ep10-40 | Triangle | 239 MB |
| soup_valley_ep10-40 | Valley | 239 MB |
| soup_A_ep10_ep40 | Simple average ep10+ep40 | 239 MB |
| soup_ep20_ep40 | Simple average ep20+ep40 | 239 MB |

Under `Mantu/sa3_control_runs/soups_vibe/` (cross-optimizer soups):

| Soup | Notes |
|------|-------|
| `cross_25A75F.pt` | 25% AdamW + 75% Fusion |
| `cross_25A75F_caut.pt` | + Cautious variant |
| `cross_25A75F_caut_ep2.pt` / `_ep5.pt` | Cautious early-stop variants |
| `best_of_runs.pt` | Cherry-picked best |
| `AdamW_peak_mix.pt` / `Fusion_peak_mix.pt` | Per-optimizer peak blends |
| + 4 ONNX export subdirs | |

---

## 7. Mutated Base Models

Under `Mantu/sa3_mutated_checkpoints/` (each ~4.6 GB + .wav preview).
Created by [mutate_weights.py](file:///home/kim/Projects/SAO/stable-audio-3/scripts/mutate_weights.py).

| Variant | Drift | Shuffle | Blur | Contraction |
|---------|-------|---------|------|-------------|
| Pure drift (gentle) | **0.01** | 0 | 0 | 0 |
| Pure drift (moderate) | **0.05** | 0 | 0 | 0 |
| Pure shuffle (gentle) | 0 | **0.01** | 0 | 0 |
| Pure shuffle (moderate) | 0 | **0.05** | 0 | 0 |
| Pure blur | 0 | 0 | **0.1** | 0 |
| Pure contraction | 0 | 0 | 0 | **0.1** |
| Drift + shuffle + blur | **0.02** | **0.01** | **0.05** | 0 |
| Drift + blur + contraction | **0.02** | 0 | **0.05** | **0.1** |

---

## 8. Composition Evaluations

### composed_sweep
- **Location:** `Mantu/sa3_control_runs/composed_sweep/`
- **Contents:** `E_fusion/` (162 cells), `A_cc/` (162 cells), `E_fusion_v2/`
- **Verdict:** Stage1 complete (324 cells, 2 seeds). FusionCC advantage **replicates**.

### sa3_multihead_bracket ⭐ 4-knob validated
- **Location:** `Mantu/sa3_lora_runs/sa3_multihead_bracket/`
- **Contents:** 12 WAV renders + `manifest.json` + `run_meta.json`
- **Verdict:** "4-knob composition VERIFIED: energy guidance steers hard ON TOP of the full stack — hi-lo spread +15.2 dB @512, +23.4 dB @1024, monotone, direction correct"

> [!CAUTION]
> All server-rendered evals since 2026-06-27 had a clipping bug. Re-render before final ear verdicts.

---

## Quick Reference: Recommended Run Command

```bash
python control/sa3_control/multi_adapter_onset_eval.py \
    --dora-ckpt  /run/media/kim/Mantu/sa3_lora_runs/soups_dora/r128f_expasc.ckpt \
    --onset-ckpt /run/media/kim/Mantu/sa3_control_runs/onset_FusionCC_lr1e-4_randomcrop/riffer_final.pt \
    --style-ckpt /run/media/kim/Mantu/sa3_control_runs/style_fpC_adamw/riffer_final.pt \
    --reference-latent /home/kim/Projects/latents_sa3/003231.npy \
    --densities "5,6,7,8,9,10" \
    --onset-gains "1.0,2.0,3.0" \
    --style-gains "0.25,0.5,1.0" \
    --out-dir /run/media/kim/Mantu/sa3_lora_runs/sa3_multihead_bracket
```
