# #46 part 2 — ARC-Forcing continuation fine-tune (LUMI campaign spec)

**CONTINUITY, 2026-07-22 (Kim's greenlight pending on ONE choice, see §4).**
Goal (Kim, 07-22): "finetune it so that it learns to extend its own prior output instead
of just generating long generations out of the box."

## 1. What already exists (do not rebuild)

- `eval/arc_rollout_dataset.py` (07-13, #46 part 1): builds npz training pairs — T=1024
  windows, first `--tctx` 512 frames re-rendered through the model as latent-domain SDEdit
  (`--rollout-nl 0.5`, reuses `longform.SDEditReanchor`) = the model's own DRIFTED context;
  target = the true window; `mask` marks clamped frames. Resumable, `--dry-run` validated.
- `stable_audio_3/data/dataset.py::ArcRolloutDataset` — reads those npz.
- `training/diffusion.py` batch_inpaint branch — routes mask+context through the SAME
  conditioning keys inference uses (`inpaint_mask`/`inpaint_masked_input` → local_add_cond).
  So the learned skill is directly usable via `generate(inpaint_*)` — no new inference code.
- Base capability: SA3 base already trains with `random_inpaint_mask` → prefix-clamp
  continuation works zero-shot TODAY; this campaign trains away the drift/seam quality gap
  (exposure bias), per Live Music Diffusion (2605.22717)'s rollout-conditioning argument.

## 2. Campaign shape (two sbatches, both from proven skeletons)

**Job A — rollout dataset build** (pattern: `ctrl_matrix_hq.sbatch`, HQ, 8 GCD workers):
- Input: `$FLASH/latents_sa3` (staged from `$SCRATCH/latents_sa3.tar.gz`, muscriptor-style).
- One HQ task per shard: `python eval/arc_rollout_dataset.py --shard ... --rollout-nl 0.5
  --tctx 512 --out $SCRATCH/arc_rollout_v1` (worker must pass NOTHING extra — the builder
  already loads medium-base + does latent SDEdit itself).
- Scale: start with ~2-3k windows (enough for a DoRA-scale FT; full 5400-crop pass only if
  the pilot moves the drift metric). Non-negotiables per lumi-ops skill: ROCR-only pinning,
  `hq job wait all || true`, `j%{JOB_ID}-t%{TASK_ID}` logs, MIOpen /tmp, count-artifacts
  success line (`*.npz` count vs manifest).

**Job B — fine-tune** (pattern: `efp_fp32_compare.sbatch`, one arm per GCD):
- `scripts/train_lora.py --adapter_type dora-rows --rank 128 --lora_alpha 128` (matched to
  the fp32cmp family so results are comparable), dataset = ArcRolloutDataset over
  `$SCRATCH/arc_rollout_v1`. bf16 default (fp32 only if drift metrics look precision-bound).
- Arms (pilot, 4 GCDs): {goa data, avp data} × {rollout-nl 0.5, 0.65}. Constant: T=1024,
  tctx=512, lr 1e-4, 8 ep. The nl axis probes how much drift the context should carry.
- OPEN (§4): DoRA vs full-FT. Spec assumes DoRA.

## 3. Eval (decides ship)

- Drift-over-extensions: from one 512-frame seed, chain K=6 continuations (each conditions
  on its own prior output via inpaint API); measure per-hop DSP drift (hf_ratio, centroid,
  flatness — reuse `eval/disintegration_metrics.py`) + CLAP-to-prompt decay + seam
  discontinuity (band-RMS delta at the join). Baselines: (a) base model zero-shot inpaint
  continuation, (b) shipped SDEdit+crossfade longform on the same seeds.
- Ship bar: adapter beats BOTH baselines on seam discontinuity without losing CLAP decay,
  and stays under the disintegration gate at hop 6. Kim's ear on the survivors.
- Eval-page: follows eval-tables spec (three-audience: explainer block, params, same-playhead).

## 4. The one open decision (Kim)

Base for the FT: **(recommended) DoRA-r128 on medium-base** — composable with every
existing adapter, cheap arms, directly comparable to fp32cmp; or a fullft arm — stronger
ceiling, siloed, 10× checkpoint weight. Default = DoRA unless Kim says otherwise.

## 5. Sequencing

After the two in-flight cell reruns drain (same-cluster etiquette, and Job A wants the
latents tarball which muscriptor's rerun also stages). Rough cost: Job A ~2-4 node-h,
Job B pilot ~1 node-day. Both restart-safe (builder resumable; Lightning ckpts).
