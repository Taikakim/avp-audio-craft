# June experiment prune: review list

**ON HOLD (Kim, 2026-11-03): we do not delete unaudited stuff.** 0 of these 103 runs have a `kim_feedback` in their sidecars, so nothing goes until reviewed here. Beat adapter (`onset_Fusion_opb_*`): probably old and not that good, last checkpoint of each is spared.

Data root: `/run/media/kim/Mantu/`. Eval pages open directly in a browser as `file:///home/kim/evals_aac/...`. Start at `onset_narrative.html`, `index.html`, `riffer/disentangle.html`, `riffer/onset_eval.html`, `riffer/mp.html`, `riffer/latch_sweep.html`. AAC copies there stay, so audition still works after a prune.


Owner: THE-FINN (2026-11-03). **Nothing here has been deleted yet.** Only June-dated checkpoints and audio go; sidecars, logs, scripts and folders stay.
Delete list: 10729 files, 130.3 GB (`/home/kim/sao_runs/june_prune/june_delete_manifest.tsv`). Sources for what each run is: `docs/onset-density-control-narrative.md`, run sidecars, `control/sa3_control/RIFFER_LISTENING_NOTES.md`.

## Held for your decision

**The 'longer Fusion has vibe' favourite:** `onset_FUSION_lr2e5_40epoch` and `onset_eval_lr2e5_*`, 3648 files, 22.8 GB. Their sidecars say: "By ear the most useful; dataset-relative Audiobox shows it closest to the Goa aesthetic." Goa-trained, so never releasable. Listed in `held_favourite.tsv`.

## Never in the list

`onset_Fusion_lr1e-4_randomcrop` (server's default FiLM), `onset_FUSION_lr2e5_40epoch/{soup_exppeak,riffer_final}.pt`, `soups_vibe`, everything in `sa3_lora_runs`, `latents_sa3_stem_chroma`, `evals_aac`, `riffer-evals`.

## A. Riffer (audio-reference adapter), LR/optimizer bracket: 18.0 GB

**What it is:** Riffer: an adapter meant to transfer a reference track's feel. The LR and optimizer bracket from 06-18 to 06-20.
**On record:** Your listening notes: it barely distinguishes references; a variation effect, not transfer. Line dropped.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/riffer_20pct_2048_nockpt` [page](file:///home/kim/evals_aac/control_runs/riffer_20pct_2048_nockpt/index.html) | 12 | 30 | 3.28 |  |  |
| `sa3_control_runs/riffer_400trk_lr1e-4_crop1024` | 13 | 0 | 3.02 |  |  |
| `sa3_control_runs/riffer_20pct_2048_lr1e3` [page](file:///home/kim/evals_aac/control_runs/riffer_20pct_2048_lr1e3/index.html) | 12 | 21 | 2.90 |  |  |
| `sa3_control_runs/riffer_200trk_2e-4_adamw` | 7 | 0 | 1.63 |  |  |
| `sa3_control_runs/riffer_200trk_4e-4_adamw` | 7 | 0 | 1.63 |  |  |
| `sa3_control_runs/riffer_200trk_6e-4_adamw_wu` | 7 | 0 | 1.63 |  |  |
| `sa3_control_runs/riffer_200trk_2e-4_fusion` | 5 | 0 | 1.16 |  |  |
| `sa3_control_runs/riffer_200trk_2e-4_sfadamw` | 5 | 0 | 1.16 |  |  |
| `sa3_control_runs/riffer_200trk_5e-5_fusion` | 5 | 0 | 1.16 |  |  |
| `sa3_control_runs/riffer_bf16test` | 2 | 0 | 0.46 |  |  |

## B. Riffer audition renders: 3.5 GB

**What it is:** Audition renders of those riffer models.
**On record:** Basis of the same listening notes, which stay in the repo.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/bracket6` [page](file:///home/kim/evals_aac/control_runs/bracket6/index.html) | 0 | 483 | 2.04 |  |  |
| `sa3_control_runs/bracket` [page](file:///home/kim/evals_aac/control_runs/bracket/index.html) | 0 | 116 | 0.49 |  |  |
| `sa3_control_runs/bracket6_merit` [page](file:///home/kim/evals_aac/control_runs/bracket6_merit/index.html) | 0 | 99 | 0.42 |  |  |
| `sa3_control_runs/cmp` [page](file:///home/kim/evals_aac/control_runs/cmp/index.html) | 0 | 28 | 0.28 |  |  |
| `sa3_control_runs/bracket_fine` [page](file:///home/kim/evals_aac/control_runs/bracket_fine/index.html) | 0 | 60 | 0.25 |  |  |

## C. Original onset-density heads (the first proof it steers): 3.6 GB

**What it is:** The first onset-density heads, before the full corpus.
**On record:** `400trk` is the historic proof: corr +0.90 at gain 1. The `FULL_3000` arms have no recorded verdict. Superseded.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/onset_density_400trk_crop1024` | 7 | 0 | 1.67 |  |  |
| `sa3_control_runs/onset_density_FULL_3000c_crop1024` | 4 | 0 | 0.96 |  |  |
| `sa3_control_runs/onset_density_FULL_3000_crop1024` | 2 | 0 | 0.48 |  |  |
| `sa3_control_runs/onset_density_FULL_3000b_crop1024` | 2 | 0 | 0.48 |  |  |

## D. Onset adapter, AdamW arms: 34.9 GB

**What it is:** Onset adapter trained with AdamW, with its eval clips.
**On record:** `lr1e-4` collapsed at step 43,200. `lr7.5e-5` arms stopped with outcome unknown. AdamW never came back. Some clips were in your top-100 pool, but that uses separate AAC copies.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/onset_AdamW_lr7.5e-5_randomcrop_20ep` [page](file:///home/kim/evals_aac/control_runs/onset_AdamW_lr7.5e-5_randomcrop_20ep/index.html) | 25 | 2640 | 15.29 | optimizer=adamw, lr=7.5e-05, steps=108000, scalar_field=onset_density | AdamW 20ep onset_density lr7.5e-5 randomcrop — rich-matrix prerequisite: per-layer telemetry x control authori |
| `sa3_control_runs/onset_AdamW_lr7.5e-5_randomcrop` [page](file:///home/kim/evals_aac/control_runs/onset_AdamW_lr7.5e-5_randomcrop/index.html) | 13 | 1638 | 8.89 |  |  |
| `sa3_control_runs/onset_AdamW_lr7.5e-5_continuous` [page](file:///home/kim/evals_aac/control_runs/onset_AdamW_lr7.5e-5_continuous/index.html) | 13 | 687 | 5.53 |  |  |
| `sa3_control_runs/onset_AdamW_lr1e-4` [page](file:///home/kim/evals_aac/control_runs/onset_AdamW_lr1e-4/index.html) | 12 | 12 | 2.91 |  |  |
| `sa3_control_runs/onset_AdamW_lr7.5e-5` [page](file:///home/kim/evals_aac/control_runs/onset_AdamW_lr7.5e-5/index.html) | 9 | 23 | 2.23 |  |  |

## E. Onset adapter, FusionOpt arms: 5.8 GB

**What it is:** Onset adapter FusionOpt probes and short arms: allocator-fix smoke tests, lr8e-5.
**On record:** No verdict recorded. The kept runs in this family are listed separately.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/onset_FUSION_lr8e5_10epoch` | 11 | 0 | 2.63 |  |  |
| `sa3_control_runs/onset_FUSION_lr1e4_5000_FIXED` | 6 | 0 | 1.44 |  |  |
| `sa3_control_runs/onset_FUSION_lr8e5_1p2ep` | 4 | 0 | 0.96 |  |  |
| `sa3_control_runs/onset_Fusion_lr1e-4_randomcrop_20ep` | 3 | 0 | 0.72 |  |  |

## F. Onset-per-beat adapter (Fusion): 45.3 GB

**What it is:** Onset-per-beat adapter (tempo-relative density), FusionOpt, 30 epochs. Fat checkpoints, about 1.6 GB each.
**On record:** No verdict in docs. Largest single item at 42.5 GB.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/onset_Fusion_opb_lr1.5e-4_30ep` [page](file:///home/kim/evals_aac/control_runs/onset_Fusion_opb_lr1.5e-4_30ep/index.html) | 26 | 182 | 42.51 | optimizer=fusion, lr=0.00015, steps=135000, scalar_field=onset_per_bea | opb 10ep continuation ep15->ep25, Fusion SF-NorMuon lr1.5e-4 onset_per_beat — does more training push control  |
| `sa3_control_runs/onset_Fusion_opb_10ep` [page](file:///home/kim/evals_aac/control_runs/onset_Fusion_opb_10ep/index.html) | 11 | 42 | 2.78 |  |  |

## G. Onset eval grids (clips only, no checkpoints): 14.4 GB

**What it is:** Eval grids of gain x density for the onset adapters. Clips only; `onset_eval.json` and sidecars stay.
**On record:** Numbers survive in the sidecars. The audio is what goes.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/onset_eval_clean_ep15-30` [page](file:///home/kim/evals_aac/control_runs/onset_eval_clean_ep15-30/index.html) | 0 | 1728 | 6.10 |  |  |
| `sa3_control_runs/onset_eval_soups` [page](file:///home/kim/evals_aac/control_runs/onset_eval_soups/index.html) | 0 | 864 | 3.05 |  |  |
| `sa3_control_runs/onset_eval_soups_multiprompt` [page](file:///home/kim/evals_aac/control_runs/onset_eval_soups_multiprompt/index.html) | 0 | 486 | 1.71 |  |  |
| `sa3_control_runs/onset_eval_ckpts_multiprompt` [page](file:///home/kim/evals_aac/control_runs/onset_eval_ckpts_multiprompt/index.html) | 0 | 162 | 0.57 |  |  |
| `sa3_control_runs/onset_eval_54000_g11to20` [page](file:///home/kim/evals_aac/control_runs/onset_eval_54000_g11to20/index.html) | 0 | 80 | 0.28 |  |  |
| `sa3_control_runs/onset_eval_54000_inrange` [page](file:///home/kim/evals_aac/control_runs/onset_eval_54000_inrange/index.html) | 0 | 48 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_10800` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_10800/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_16200` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_16200/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_21600` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_21600/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_27000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_27000/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_32400` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_32400/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_37800` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_37800/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_43200` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_43200/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_48600` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_48600/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_5400` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_5400/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_54000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_54000/index.html) | 0 | 49 | 0.17 |  |  |
| `sa3_control_runs/onset_eval_54000_lowgain` [page](file:///home/kim/evals_aac/control_runs/onset_eval_54000_lowgain/index.html) | 0 | 44 | 0.16 |  |  |
| `sa3_control_runs/onset_eval_FULL_s3000c` [page](file:///home/kim/evals_aac/control_runs/onset_eval_FULL_s3000c/index.html) | 0 | 30 | 0.11 |  |  |
| `sa3_control_runs/onset_eval_refined_g08-12` [page](file:///home/kim/evals_aac/control_runs/onset_eval_refined_g08-12/index.html) | 0 | 30 | 0.11 |  |  |
| `sa3_control_runs/onset_eval_s6000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_s6000/index.html) | 0 | 20 | 0.07 |  |  |
| `sa3_control_runs/onset_eval_FULL_s2000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_FULL_s2000/index.html) | 0 | 15 | 0.05 |  |  |
| `sa3_control_runs/onset_eval_fusfixed_s1000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_fusfixed_s1000/index.html) | 0 | 10 | 0.04 |  |  |
| `sa3_control_runs/onset_eval_fusfixed_s2000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_fusfixed_s2000/index.html) | 0 | 10 | 0.04 |  |  |
| `sa3_control_runs/onset_eval_fusfixed_s3000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_fusfixed_s3000/index.html) | 0 | 10 | 0.04 |  |  |
| `sa3_control_runs/onset_eval_fusfixed_s4000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_fusfixed_s4000/index.html) | 0 | 10 | 0.04 |  |  |
| `sa3_control_runs/onset_eval_fusfixed_s5000` [page](file:///home/kim/evals_aac/control_runs/onset_eval_fusfixed_s5000/index.html) | 0 | 10 | 0.04 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_final` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_final/index.html) | 0 | 10 | 0.04 |  |  |
| `sa3_control_runs/onset_eval_lr8e5_step5400` [page](file:///home/kim/evals_aac/control_runs/onset_eval_lr8e5_step5400/index.html) | 0 | 10 | 0.04 |  |  |

## H. Weight-averaged soups: 2.9 GB

**What it is:** Weight-averaged checkpoints testing whether averaging beats the best single one.
**On record:** MASTER's confirmed averaging finding is about EMA on a different head; the narrative doc says the soup blend ratio was not a real quality lever. `soups_vibe` is kept.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/soups` | 12 | 0 | 2.87 |  |  |

## L. LatCH head sweep clips (06-28/29): 1.6 GB

**What it is:** Clips from the 14-head LatCH sweep and the skewness EMA tests.
**On record:** Findings in MASTER and WORKLOG. The public page's copies are separate.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `latch_sweep/clips` | 0 | 123 | 0.56 |  |  |
| `latch_sweep/clips_g512` | 0 | 123 | 0.56 |  |  |
| `latch_sweep/skew_eval_clips` | 0 | 42 | 0.19 |  |  |
| `latch_sweep/skew_ema_eval_clips` | 0 | 30 | 0.14 |  |  |
| `latch_sweep/ladder` | 0 | 24 | 0.11 |  |  |
| `latch_sweep/(loose files)` | 0 | 8 | 0.04 |  |  |

## Z. Other: 0.5 GB

**What it is:** Small probes and a `SEND` folder.
**On record:** No verdict recorded.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `sa3_control_runs/_probe_b2` | 1 | 0 | 0.24 |  |  |
| `sa3_control_runs/_probe_b4` | 1 | 0 | 0.24 |  |  |
| `sa3_control_runs/SEND` [page](file:///home/kim/evals_aac/control_runs/SEND/index.html) | 0 | 11 | 0.05 |  |  |
| `sa3_control_runs/_collapse_test_ep25` [page](file:///home/kim/evals_aac/control_runs/_collapse_test_ep25/index.html) | 0 | 3 | 0.01 |  |  |
