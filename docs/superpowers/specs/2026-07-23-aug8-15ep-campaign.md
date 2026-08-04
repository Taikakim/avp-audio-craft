# aug8 x 15-epoch campaign — GOA Bungee augmentation + LUMI training arms

**DRAFT (2026-07-23), spawned by CONTINUITY, subagent-authored, code + sbatch UNSUBMITTED
— for Kim's review.** Nothing here has run on GPU; all six artifacts are drafts. Renamed
from **aug10 -> aug8** partway through drafting (Kim's ruling — see Open Questions):
the GOA variant set now matches `mir/src/tools/augment_tracks.py` exactly (8 variants,
not 10). Three lanes: **aug8** (new GOA augmentation -> fresh 15-epoch arms, artifacts
1-3), **continuation** (resume the already-trained fp32_compare arms to the new
15-epoch default, artifact 4), and **DDP** (experimental: train the aug8 arms one at a
time across all 8 GCDs instead of 8-arms-in-parallel, artifact 5) — all target the same
15-epoch policy change.

## Motivation

Kim's 2026-07-23 listening verdicts (`docs/training-findings.md`, "Kim's listening
verdicts (policy-setting)") set three new defaults at once:
1. **fp32 + full-finetune sound better than bf16 / adapter-only, period** — and rank helps.
2. **15 epochs is the new training-length default**, not 8 — models "just about start to
   sound fine after ep5, and often 7 is the first really good one"; every 8-epoch-era
   verdict should be re-read with this in mind.
3. **Augmentation SEEMS to help** (not yet isolated as cleanly as #1/#2) — motivating a
   proper x8 Bungee augmentation pass on the GOA corpus, generated on LUMI (CPU-only,
   too slow to run 5400 crops x 8 variants locally without blocking the desktop GPU),
   then trained at 15 epochs so aug's effect can be read off *alongside* the
   precision/full-ft axis rather than as a separate, uncontrolled variable.

This spec + its artifacts turn that into a concrete, reviewable plan.

## The artifacts

1. **`lumi/augment_goa_bungee.py`** — CPU-only, 8-variant Bungee pitch/tempo
   augmenter for the GOA crop corpus, **variant set now IDENTICAL to
   `mir/src/tools/augment_tracks.py`**: pitch {-2,-1,+1,+2} st, tempo {-10,-5,+5,+10}%
   (BPM-capped at 155), NO combined variants (dropped per Kim's ruling — see Open
   Questions). Reuses that script's BPM-cap/peak-norm/resumable-ProcessPool
   conventions, and `Misc/augment_slice.py`'s crop-window-aware slicing (reads a WIDER
   source window so the post-transform output is trimmed back to the parent crop's
   exact sample count — every augmented crop stays duration-matched to its original,
   no extra crop/pad logic downstream). Source-path rebasing is now a repeatable
   `--source-prefix-map OLD=NEW` flag (replaces the earlier ad hoc
   `--source-root`/`--source-strip-prefix` pair) — see Logistics for the exact LUMI
   mapping. Fails loud at startup if `bungee_python` isn't importable (Open Question 2).
2. **`lumi/sbatch/aug8_encode.sbatch`** (+ companion `lumi/encode_aug_task.py`) —
   two-phase LUMI job: (A) HyperQueue-sharded CPU augmentation of the 5400 GOA crops
   via artifact 1, (B) 8-GCD SAME-L encode of the resulting FLACs to latents
   (`encode_aug_task.py`, pattern reused from `lumi/muscriptor_decode_task.py`'s
   minimal-loading + offline-HF + per-task-MIOpen preamble, via the standalone
   `AutoencoderModel.from_pretrained("same-l", ...)` path already used by
   `stable-audio-3/scripts/pre_encode_dataset.py`). Output: `$SCRATCH/latents_goa_aug8/`
   + a tarball for the training stage. Follows every lumi-ops non-negotiable (ROCR-only
   GCD pinning, `hq job wait all || true`, `j%{JOB_ID}-t%{TASK_ID}` log names, per-task
   `/tmp` MIOpen redirect, artifact-count success lines, working-tree code-refresh note).
3. **`lumi/sbatch/aug8_train.sbatch`** — 8 arms, one per GCD: {goa-aug8, avp} x
   {DoRA-r128, fullft} x {fp32, bf16}, all `--frames 512`, **15 epochs**, lr 1e-4
   (grepped convention, uniform across all four reference sbatches). AVP arms reuse
   the **existing** `latents_avp` aug set as-is — no new AVP augmentation is generated
   this round (Open Question 1, RESOLVED). Skeleton = `efp_fp32_compare.sbatch`;
   fullft plumbing = `efp_fullft_short.sbatch` / `efp_fullft_t4096.sbatch`.
4. **`lumi/sbatch/fp32cmp_continue_15e.sbatch`** (continuation lane, added on the
   coordinator's request after Kim's live checkpoint inventory) — resumes all 8
   `efp_fp32_compare.sbatch` arms from their terminal FAT checkpoints (the ones still
   carrying optimizer state, pre-prune) and trains each to the new 15-epoch total.
   **Verified, not assumed:** `train_lora.py --resume_ckpt` is a TRUE Lightning resume
   (`trainer.fit(..., ckpt_path=...)` — restores optimizer/scheduler/epoch state), distinct
   from `--warm_start_ckpt` (old-format weights-only, epoch counters restart) — this job
   uses `--resume_ckpt`, so it's a seamless continuation, not a different (fresh-optimizer)
   experiment. `--epochs 15` is passed identically to all 8 arms since it's the Lightning
   TOTAL-epoch target, not an increment — the 7 arms at `epoch=7` (8 done) run 7 more; the
   one arm at `epoch=6` (goa_t4096_bs1_lr1e4, the 47h-timeout casualty of job 19945290) runs
   8 more. Fat-ckpt paths are globbed at runtime (single non-`.weights.ckpt` per arm dir,
   post-prune). Walltime 20h (slowest arm ~99 min/epoch x 8 remaining epochs ~13.2h + headroom).
5. **`lumi/sbatch/aug8_train_ddp.sbatch`** (EXPERIMENTAL, new — Kim: "we should try
   that out", raised in response to the aug8-lane walltime risk) — instead of 8
   independent one-arm-per-GCD runs, trains the aug8 arms ONE AT A TIME using all 8
   GCDs as a single Lightning DDP group (per-arm wall-clock expected to drop ~8x).
   **Verified by reading the code, not assumed:** `train_lora.py`'s
   `pl.Trainer(devices="auto", accelerator="auto", strategy="auto", ...)` is
   HARDCODED — there is no `--devices`/`--strategy`/`--num_nodes` CLI flag. DDP is
   controlled entirely by launch-time GPU visibility + process count: under
   `srun --ntasks=8` with every rank able to see all 8 GCDs, Lightning auto-detects the
   SLURM cluster environment (`SLURM_NTASKS`/`SLURM_PROCID`/`SLURM_LOCALID`) and forms
   an 8-way DDP group, each rank binding its own device via
   `torch.cuda.set_device(local_rank)`. **This REQUIRES a deliberate exception to the
   lumi-ops "ROCR_VISIBLE_DEVICES=$SLURM_PROCID alone" rule** — that masking rule is
   what makes the one-arm-per-GCD pattern work (8 independent single-GPU processes)
   and would silently defeat DDP if applied here (every rank would see exactly 1 GPU,
   `devices="auto"` resolves to 1, Lightning falls back to `SingleDeviceStrategy`).
   The sbatch's header comment states this exception explicitly and warns future
   reviewers not to "fix" it back. Effective-batch scaling is a flag:
   `DDP_BATCH_MODE=divide` (default — per-GCD batch = proven single-GCD batch ÷ 8,
   global batch unchanged, a clean apples-to-apples wall-clock-only comparison to the
   non-DDP arms) vs `DDP_BATCH_MODE=keep` (per-GCD batch unchanged, global batch x8,
   faster convergence but NOT lr-scaled, a different experiment). Default mode is a
   SMOKE TEST of exactly one arm (`ARMS=fullft_goa_aug8_fp32`) — expand the `ARMS` list
   only after Kim confirms DDP actually scales on this stack (untested combination:
   Lightning DDP + ROCm + Singularity + LUMI SLURM). Gated on the same open item as
   artifact 2 (Open Question 2) — no real aug8 latents exist yet to smoke-test against.

## Logistics dependencies

- **bungee_python on LUMI — STILL OPEN, the #1 named risk (Open Question 2).** It's a
  compiled extension, not in the base `sa3.sif`. `aug8_encode.sbatch` checks the
  import up front and fails loud (in seconds, not after a full node spin-up) if it's
  missing; fix = build a wheel matching the container's Python/glibc, install into a
  venv overlay bound alongside the read-only SIF. Not attempted in this draft. This
  now gates BOTH the aug8-encode lane and the DDP smoke test (artifact 5), since the
  DDP smoke needs real aug8 latents to train against.
- **Source audio upload — APPROVED (Open Question 3, RESOLVED).** Upload list already
  exists: **`eval/musicology/goa_src_list.txt`** (2676 files, all under
  `/run/media/kim/Mantu`; scanned 2026-07-23 against all 5400
  `/home/kim/Projects/latents_sa3/*.json` crop records, 153.57 GB total, already
  deduped — 5400 crops average ~2.0 crops/track). **Agreed transfer/remap convention**
  (Kim): rsync `--files-from` PRESERVES THE ABSOLUTE PATH STRUCTURE under
  `$SCRATCH/goa_src/` (NOT re-rooted/flattened) — e.g.
  `/run/media/kim/Mantu/ai-music/Goa_Separated/.../full_mix.flac` lands at
  `$SCRATCH/goa_src/run/media/kim/Mantu/ai-music/Goa_Separated/.../full_mix.flac`:
  ```
  rsync -avzR -e "ssh -i ~/.ssh/id_EFP" \
    --files-from=eval/musicology/goa_src_list.txt / \
    akekim@efp.lumi.csc.fi:/scratch/project_465003186/goa_src/
  ```
  (`-R`/relative is what makes `--files-from`'s absolute entries land under `goa_src/`
  preserving their full path; dry-run first, per lumi-ops convention.) To match, `
  augment_goa_bungee.py` gained a `--source-prefix-map OLD=NEW` flag (repeatable): the
  LUMI invocation passes `--source-prefix-map /=/scratch/project_465003186/goa_src/`,
  which rewrites every crop's recorded `source_path` by re-rooting its leading `/`
  under `goa_src/` — no reconstruction of a relative path needed, just a prefix swap.
  154 GB is still a real transfer — budget time/bandwidth.
- **Crop metadata staging** — the 5400 `latents_sa3/*.json` (excl. `.TIMBRAL.json`)
  need to land at `$CODE/lumi/goa_crop_meta/` on LUMI (small, <1 GB).
- **Code refresh** — all new scripts are uncommitted/new files; verify the working-tree
  copies (not `git archive` output) are what actually ships in the code tarball.

## Arm table (`aug8_train.sbatch`)

| PROCID | dataset | adapter | precision | T | batch | lr | epochs |
|---|---|---|---|---|---|---|---|
| 0 | goa-aug8 | DoRA-r128 | fp32 | 512 | 8 (proven) | 1e-4 | 15 |
| 1 | goa-aug8 | DoRA-r128 | bf16 | 512 | 8 (proven) | 1e-4 | 15 |
| 2 | goa-aug8 | fullft | fp32 | 512 | probe 4→1 | 1e-4 | 15 |
| 3 | goa-aug8 | fullft | bf16 | 512 | 4 (proven) | 1e-4 | 15 |
| 4 | avp (existing aug) | DoRA-r128 | fp32 | 512 | 8 (proven) | 1e-4 | 15 |
| 5 | avp (existing aug) | DoRA-r128 | bf16 | 512 | 8 (proven) | 1e-4 | 15 |
| 6 | avp (existing aug) | fullft | fp32 | 512 | probe 4→1 | 1e-4 | 15 |
| 7 | avp (existing aug) | fullft | bf16 | 512 | 4 (proven) | 1e-4 | 15 |

BS=8 (DoRA T512) and BS=4 (fullft-bf16 T512) are **proven** from
`efp_fp32_compare`/`efp_bf16_twin`/`efp_fullft_short`; fullft-**fp32** T512 has no
direct precedent (fp32 fullft was only ever run at T=4096) so those two arms get the
proven batch-probe pattern instead of an assumed batch size.

**Epoch-time estimate is an ASSUMPTION**, not measured (no per-epoch T=512/aug8
timing found in a 10-minute WORKLOG/journal grep). Chain of reasoning + the one hard
number used (`~2.4 s/step` SA3 DoRA @ T~512 BS1) is written out in
`aug8_train.sbatch`'s header comment. Rough order of magnitude: DoRA arms ~15-30h
for 15 epochs (fits the 47h wall); fullft-bf16 ~30-60h; fullft-fp32 (smallest probed
batch) is the one likely to need a `--resume_ckpt` continuation beyond one job —
**or the DDP lane (artifact 5), which is exactly the response to this risk.**

## DDP lane arm registry (`aug8_train_ddp.sbatch`, EXPERIMENTAL)

Same 8 logical arms as the table above, addressed by name instead of PROCID (all 8
GCDs work on ONE arm at a time): `dora_goa_aug8_{fp32,bf16}`,
`fullft_goa_aug8_{fp32,bf16}`, `dora_avp_{fp32,bf16}`, `fullft_avp_{fp32,bf16}`.
Default `ARMS=fullft_goa_aug8_fp32` (smoke test, one arm only) — expand the list once
Kim confirms DDP actually scales. Per-arm walltime is expected to drop ~8x vs the
single-GCD estimate above (data-parallel), so a single 24h job could plausibly cover
several arms once the smoke test passes.

## Continuation lane arm table (`fp32cmp_continue_15e.sbatch`)

Resumes the ALREADY-TRAINED `efp_fp32_compare.sbatch` arms in place (same run dirs,
`--resume_ckpt` true resume) rather than starting fresh — these have real optimizer
state and 6-7 epochs of progress already, so this is the cheaper path to a 15-epoch
fp32 comparison point than the aug8 lane's from-scratch arms.

| PROCID | dataset | T | batch | lr | epoch now | epochs to run | target |
|---|---|---|---|---|---|---|---|
| 0 | avp | 4096 | 4 | 1e-4 | 7 | 7 more | 15 |
| 1 | goa | 4096 | 4 | 1e-4 | 7 | 7 more | 15 |
| 2 | avp | 4096 | 1 | 1e-4 | 7 | 7 more | 15 |
| 3 | goa | 4096 | 1 | 1e-4 | **6** (19945290 timeout) | **8 more** | 15 |
| 4 | avp | 512 | 8 | 1e-4 | 7 | 7 more | 15 |
| 5 | goa | 512 | 8 | 1e-4 | 7 | 7 more | 15 |
| 6 | avp | 4096 | 4 | 5e-5 | 7 | 7 more | 15 |
| 7 | goa | 4096 | 4 | 5e-5 | 7 | 7 more | 15 |

All 8 arms pass the identical `--epochs 15` (Lightning's total-epoch target, not an
increment) — resume + this one flag is what turns "epoch=7" into "7 more" automatically;
no per-arm epoch-count arithmetic needed in the launch command itself, only in verifying
the arm table above is right (off-by-one here wastes node-days, per the coordinator's
ask). Walltime 20h, based on the slowest arm (goa_t4096_bs1, ~99 min/epoch x 8 epochs
~13.2h) + headroom; per-epoch checkpoints mean a repeat timeout (as arm 3 already hit
once) costs only the partial epoch, and a re-submit resumes again from whatever the new
terminal fat is.

## Open questions for Kim — RULED (2026-07-23)

1. **AVP dataset choice for the aug8 arms — RESOLVED: reuse existing `latents_avp`
   as-is, no new AVP augmentation this round.** The `latents_avp_aug10` naming-collision
   risk (the 320-crop small-set control from
   `docs/superpowers/specs/2026-07-22-winning-fp32-run-plan.md`) is now MOOT — nothing
   in this campaign writes to or reads that path.
2. **Is `bungee_python` actually available/buildable inside `sa3.sif`? — STILL OPEN.**
   Blocks `aug8_encode.sbatch` entirely until confirmed one way or the other, and now
   also gates the DDP lane's smoke test (artifact 5 needs real aug8 latents).
3. **Source audio upload — APPROVED**, see Logistics: `eval/musicology/goa_src_list.txt`
   + the `rsync --files-from` / `--source-prefix-map` convention above.

**Q2 RESOLVED (2026-07-23):** bungee-python 0.2.1 pip-installs into a scratch venv overlay
(`/scratch/project_465003186/bungee_venv`, `--system-site-packages` inside sa3.sif) — Kim
ran the install live. aug8_encode.sbatch now invokes the augmenter via that venv python;
encode stage stays on container python3 (torch). Remaining pre-flight: the Bungee
CONSTRUCT one-liner (native-lib check, command in chat) + the 153.6 GB source rsync.
