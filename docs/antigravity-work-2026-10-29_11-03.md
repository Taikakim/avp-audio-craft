# ANTIGRAVITY's work, 2026-10-29 to 11-03: what exists, where it is, what state it is in

Inventory by CONTINUITY, 2026-11-03, because most of this was findable only through page URLs or `git log`. It lists things and their
state. Results are on the pages, not repeated here. "Checked" says who has verified what. Nothing below has been through the
disintegration gate, and none of it has been listened to for a verdict.

## Mood steering

| What | Where | State |
|---|---|---|
| LatCH `--target-source mood` / `--mood-dir` | stable-audio-3 `a18af7d`, merged with KUANG's `--target-spec` in `362d4a7` | Both routes kept, which stays is open |
| 56-d mood head, 40 epochs, with ep, online and ema0.25 variants | `Mantu/latch_sweep/mood_56d_best_40ep_20261031/C3_mood_lr8e-4_b64_cos40/` | No `run_meta.json`, so its purpose and recipe are not recorded with it |
| Choice clips under mood guidance | `eval/render_choice_clips_mood.py`, `eval/run_choice_clips_mood_eval.sh`, page `choice_clips_mood` | Published, text corrected by W |
| Reinforce vs oppose study | `eval/render_mood_oppose_reinforce.py`, page `mood_oppose` | Published, text corrected by W |
| Fine-grained gain ladder, 4 models, extreme and negative gains, inspector tab | `eval/render_mood_finegrained_matrix.py`, `eval/render_mood_extreme_weights_and_neg.py`, page `mood_finegrained` | Published, text corrected by W |
| De-confounded targets (80 clips) | `eval/render_mood_deconfounded.py`, on the same page, labelled one prompt, one seed | Reviewed: `docs/mf2-mood-deconf-review-2026-11-03.md`. W's 15-prompt run decides (E25a) |
| End-to-end pipeline | `eval/run_full_eval_and_mood_train.sh`, `eval/build_mood_eval_page.py` | Not reviewed |

## Caption mood mining and merged captions

| What | Where | State |
|---|---|---|
| Hinted vs unhinted word mining, 8 axes | Scratch only: `~/.gemini/antigravity/brain/62fc5213-…/scratch/` (`mine_mf2_long_moods.py`, `crossmodal_mf2_essentia.py`, `analyze_mf2_moods.py`, `compare_deconf_vs_naive.py`). Copy of the second in `eval/mf2_deconf_review/` | Reviewed: suppression confirmed, "more honest" and "missing from Essentia" not shown |
| **Merged captions:** cross-merge script | `eval/recover_mf2_lost_moods.py`, `eval/mf2_mood_recovery_report.json` | Report: 7,460 of 23,232 archive tracks had words stripped as contradictions; 539 of 4,461 goa_src |
| **Merged sidecars**, labelled ready to train | `lumi/goa_longform_sidecar_merged.json` (committed 6f3334a), `lumi/goa_bigset_sidecar_merged.json` (gitignored, on disk only), `goa_archive_features/goa_archive_caption_sidecar_merged_year.json` | **Hold lifted 2026-11-03:** Kim expects a noticeable quality improvement. Strip rule checked by proxy only; `industrial` rises from 31 to 6,519 archive tracks; E25b: words barely move renders by prompt, which does not judge the captions; a training comparison would |
| Merged and new Granite captions | `Kosmos/captions/goa_archive_captions_merged/granite/` (23,232), `Kosmos/captions/goa_src_captions/granite/` (4,461) | New directories. Sources appear untouched by name; I have not diffed them |

## Chroma

| What | Where | State |
|---|---|---|
| Retrained 384-d chroma head on AVP sets and gain ladder | `eval/chroma_avp_matrix_render.py`, `eval/run_chroma_avp_matrix.sh`, page `chroma_avp_matrix` (EXPERIMENTS E13) | Published, text corrected by W |
| E13 parameter matrix | `eval/chroma_e13_matrix_render.py`, `eval/run_chroma_e13_matrix.sh`, page `chroma_e13_matrix` | Published |
| Choice clips under chroma guidance | `eval/build_choice_clips_page.py`, page `choice_clips_chroma` | Published, text corrected by W |
| ep10 vs ep40 head | `eval/build_ep10_vs_ep40_page.py`, page `ep10_vs_ep40_chroma` | Published, text corrected by W |
| E22 results page | `~/evals_aac/e22_root_locked_chroma.html`, page `e22_root_locked_chroma` | Published. Kill gate passed; W corrected "overwhelming success" (8 of 14 kept the root, 4 naturally C) |

## Synth inversion

V7 published 10-28 with corrected text. **V8 held and not published:** KUANG's code review (branch `docs/v8-code-review`, not on main) found the renderer reset every 93 ms, so no V8 result counts as evidence. Specs: `docs/synth-v7-plan-review-2026-10-27.md`, `docs/synth-v8-spec-review-2026-10-28.md`.

## Traps for whoever touches this next

1. **Rebuilding undoes the corrections.** W's fixes went into the staged pages only, and the five page builders are modified and uncommitted (`eval/build_{choice_clips,ep10_vs_ep40,mood_eval,mood_finegrained,mood_oppose}_page.py`). One rebuild has already removed them once (WORKLOG 11-03 01:58).
2. **Unguided baselines on five boards come from the default sampler**, the known confound in MASTER section 5. Each board says so.
3. **Antigravity's journal and task log stop at 10-26.** Everything above is missing from them, and only the owner edits those. The next Antigravity session should catch up.
4. **Scratch scripts are the only copy** of the mining code and of much else since 10-27 (`cpu_decode.py`, `batch_audiobox_extract.py`, `batch_tonal_mood_dsp_extract.py`, and others).
