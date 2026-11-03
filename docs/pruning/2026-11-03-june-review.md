# June experiment prune: review list

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
| `riffer_20pct_2048_nockpt` | 12 | 30 | 3.28 |  |  |
| `riffer_400trk_lr1e-4_crop1024` | 13 | 0 | 3.02 |  |  |
| `riffer_20pct_2048_lr1e3` | 12 | 21 | 2.90 |  |  |
| `riffer_200trk_2e-4_adamw` | 7 | 0 | 1.63 |  |  |
| `riffer_200trk_4e-4_adamw` | 7 | 0 | 1.63 |  |  |
| `riffer_200trk_6e-4_adamw_wu` | 7 | 0 | 1.63 |  |  |
| `riffer_200trk_2e-4_fusion` | 5 | 0 | 1.16 |  |  |
| `riffer_200trk_2e-4_sfadamw` | 5 | 0 | 1.16 |  |  |
| `riffer_200trk_5e-5_fusion` | 5 | 0 | 1.16 |  |  |
| `riffer_bf16test` | 2 | 0 | 0.46 |  |  |

## B. Riffer audition renders: 3.5 GB

**What it is:** Audition renders of those riffer models.
**On record:** Basis of the same listening notes, which stay in the repo.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `bracket6` | 0 | 483 | 2.04 |  |  |
| `bracket` | 0 | 116 | 0.49 |  |  |
| `bracket6_merit` | 0 | 99 | 0.42 |  |  |
| `cmp` | 0 | 28 | 0.28 |  |  |
| `bracket_fine` | 0 | 60 | 0.25 |  |  |

## C. Original onset-density heads (the first proof it steers): 3.6 GB

**What it is:** The first onset-density heads, before the full corpus.
**On record:** `400trk` is the historic proof: corr +0.90 at gain 1. The `FULL_3000` arms have no recorded verdict. Superseded.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `onset_density_400trk_crop1024` | 7 | 0 | 1.67 |  |  |
| `onset_density_FULL_3000c_crop1024` | 4 | 0 | 0.96 |  |  |
| `onset_density_FULL_3000_crop1024` | 2 | 0 | 0.48 |  |  |
| `onset_density_FULL_3000b_crop1024` | 2 | 0 | 0.48 |  |  |

## D. Onset adapter, AdamW arms: 34.9 GB

**What it is:** Onset adapter trained with AdamW, with its eval clips.
**On record:** `lr1e-4` collapsed at step 43,200. `lr7.5e-5` arms stopped with outcome unknown. AdamW never came back. Some clips were in your top-100 pool, but that uses separate AAC copies.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `onset_AdamW_lr7.5e-5_randomcrop_20ep` | 25 | 2640 | 15.29 | optimizer=adamw, lr=7.5e-05, steps=108000, scalar_field=onset_density | AdamW 20ep onset_density lr7.5e-5 randomcrop — rich-matrix prerequisite: per-layer telemetry x control authori |
| `onset_AdamW_lr7.5e-5_randomcrop` | 13 | 1638 | 8.89 |  |  |
| `onset_AdamW_lr7.5e-5_continuous` | 13 | 687 | 5.53 |  |  |
| `onset_AdamW_lr1e-4` | 12 | 12 | 2.91 |  |  |
| `onset_AdamW_lr7.5e-5` | 9 | 23 | 2.23 |  |  |

## E. Onset adapter, FusionOpt arms: 5.8 GB

**What it is:** Onset adapter FusionOpt probes and short arms: allocator-fix smoke tests, lr8e-5.
**On record:** No verdict recorded. The kept runs in this family are listed separately.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `onset_FUSION_lr8e5_10epoch` | 11 | 0 | 2.63 |  |  |
| `onset_FUSION_lr1e4_5000_FIXED` | 6 | 0 | 1.44 |  |  |
| `onset_FUSION_lr8e5_1p2ep` | 4 | 0 | 0.96 |  |  |
| `onset_Fusion_lr1e-4_randomcrop_20ep` | 3 | 0 | 0.72 |  |  |

## F. Onset-per-beat adapter (Fusion): 45.3 GB

**What it is:** Onset-per-beat adapter (tempo-relative density), FusionOpt, 30 epochs. Fat checkpoints, about 1.6 GB each.
**On record:** No verdict in docs. Largest single item at 42.5 GB.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `onset_Fusion_opb_lr1.5e-4_30ep` | 26 | 182 | 42.51 | optimizer=fusion, lr=0.00015, steps=135000, scalar_field=onset_per_bea | opb 10ep continuation ep15->ep25, Fusion SF-NorMuon lr1.5e-4 onset_per_beat — does more training push control  |
| `onset_Fusion_opb_10ep` | 11 | 42 | 2.78 |  |  |

## G. Onset eval grids (clips only, no checkpoints): 14.4 GB

**What it is:** Eval grids of gain x density for the onset adapters. Clips only; `onset_eval.json` and sidecars stay.
**On record:** Numbers survive in the sidecars. The audio is what goes.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `onset_eval_clean_ep15-30` | 0 | 1728 | 6.10 |  |  |
| `onset_eval_soups` | 0 | 864 | 3.05 |  |  |
| `onset_eval_soups_multiprompt` | 0 | 486 | 1.71 |  |  |
| `onset_eval_ckpts_multiprompt` | 0 | 162 | 0.57 |  |  |
| `onset_eval_54000_g11to20` | 0 | 80 | 0.28 |  |  |
| `onset_eval_54000_inrange` | 0 | 48 | 0.17 |  |  |
| `onset_eval_lr8e5_10800` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_16200` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_21600` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_27000` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_32400` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_37800` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_43200` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_48600` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_5400` | 0 | 49 | 0.17 |  |  |
| `onset_eval_lr8e5_54000` | 0 | 49 | 0.17 |  |  |
| `onset_eval_54000_lowgain` | 0 | 44 | 0.16 |  |  |
| `onset_eval_FULL_s3000c` | 0 | 30 | 0.11 |  |  |
| `onset_eval_refined_g08-12` | 0 | 30 | 0.11 |  |  |
| `onset_eval_s6000` | 0 | 20 | 0.07 |  |  |
| `onset_eval_FULL_s2000` | 0 | 15 | 0.05 |  |  |
| `onset_eval_fusfixed_s1000` | 0 | 10 | 0.04 |  |  |
| `onset_eval_fusfixed_s2000` | 0 | 10 | 0.04 |  |  |
| `onset_eval_fusfixed_s3000` | 0 | 10 | 0.04 |  |  |
| `onset_eval_fusfixed_s4000` | 0 | 10 | 0.04 |  |  |
| `onset_eval_fusfixed_s5000` | 0 | 10 | 0.04 |  |  |
| `onset_eval_lr8e5_final` | 0 | 10 | 0.04 |  |  |
| `onset_eval_lr8e5_step5400` | 0 | 10 | 0.04 |  |  |

## H. Weight-averaged soups: 2.9 GB

**What it is:** Weight-averaged checkpoints testing whether averaging beats the best single one.
**On record:** MASTER's confirmed averaging finding is about EMA on a different head; the narrative doc says the soup blend ratio was not a real quality lever. `soups_vibe` is kept.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `soups` | 12 | 0 | 2.87 |  |  |

## L. LatCH head sweep clips (06-28/29): 1.6 GB

**What it is:** Clips from the 14-head LatCH sweep and the skewness EMA tests.
**On record:** Findings in MASTER and WORKLOG. The public page's copies are separate.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `clips` | 0 | 123 | 0.56 |  |  |
| `clips_g512` | 0 | 123 | 0.56 |  |  |
| `skew_eval_clips` | 0 | 42 | 0.19 |  |  |
| `skew_ema_eval_clips` | 0 | 30 | 0.14 |  |  |
| `ladder` | 0 | 24 | 0.11 |  |  |
| `(loose files)` | 0 | 8 | 0.04 |  |  |

## Z. Other: 0.5 GB

**What it is:** Small probes and a `SEND` folder.
**On record:** No verdict recorded.

| Run | Checkpoints | Audio | GB | Settings | Sidecar note |
|---|---:|---:|---:|---|---|
| `_probe_b2` | 1 | 0 | 0.24 |  |  |
| `_probe_b4` | 1 | 0 | 0.24 |  |  |
| `SEND` | 0 | 11 | 0.05 |  |  |
| `_collapse_test_ep25` | 0 | 3 | 0.01 |  |  |
