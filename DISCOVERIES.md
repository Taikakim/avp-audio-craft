# DISCOVERIES — the "have we already figured this out / built this?" index

*The discovery-phase search target (CLAUDE.md ⛔ DISCOVERY PHASE). Regenerated
wholesale from `profiles/*.journal.md` by `Misc/build_discoveries.py` — do NOT
hand-edit below this point, it will be overwritten on the next run. To fix a
misfiled entry, edit the TOPICS keyword map in that script, not this file. To
add a finding, drop a journal line in your own journal; re-run the script.*

**Owner: THE-FINN.** Topic assignment is a keyword heuristic, not semantic
understanding — it will occasionally misfile something. `[RULED OUT]` = a
negative result (a path already tried and abandoned — first-class, not noise).

*201 entries from 4 journals.*

---

## Long-form generation · transitions · crossfade
- **tier-0 morning under Kim's lightweight-first directive: two branches resolved cheap.** — CONTINUITY, 2026-07-31
- **two Gemini theory reviews, and a prediction that failed cleanly.** — CONTINUITY, 2026-07-15
- **double-checked W's longform validation plan.** — GHOST-NOTE, 2026-07-15
- **Saturday: manifests v2, narrative review, breathing v2 design, blog week.** — CONTINUITY, 2026-07-12
- **RoPE jitter is null-by-construction on longform.py — the loop is conditioning-driven, not positional.** → `stable_audio_3/inference/rope_jitter.py`, `longform.py`, `fifo_infinite.py` — WINTERMUTE, 2026-07-12
- **overnight experiment queue — two long-form fixes null, hardness shortcut confirmed, rank-vs-weight.** → `rope_jitter.py`, `incantation_mask.py`, `hardness_spectral_diff.py`, `clip_metrics.py`, `clip_metrics_audiobox.py` — WINTERMUTE, 2026-07-12
- [research] **longform validation plan — six full-paper reads settle the port questions (Kim delegation via C).** → `docs/ai-research/validation-experiment-plan-2026-07-15.md` — WINTERMUTE, 2026-07-12
- **transitions3 verdicts: seams out, shorter windows in.** — CONTINUITY, 2026-07-08
- **Kim's ear vs the mid-noise band — ear wins, regime explains.** → `mir/src/tools/melodic_movement_ladder.py` — WINTERMUTE, 2026-07-08
- **Kim's audition findings on the prompt-style grid (on record).** — CONTINUITY, 2026-07-07
- **a2a noise-ladder ear calibration (Kim) + the 120s generate() trap.** — CONTINUITY, 2026-07-07
- **[correction] the t=0.075 "untrained tail" claim was wrong in detail.** — CONTINUITY, 2026-07-07
- **chroma-morph transitions: Kim's strongest verdict on record.** — CONTINUITY, 2026-07-07
- **the under-constraint attractor, third sighting (now doctrine).** — CONTINUITY, 2026-07-07
- **latent-explorer megabuild (ultracode) + a bug found in my own proven script.** — CONTINUITY, 2026-07-07
- **the recurring render-clipping bug, quantified (Kim: "we fix this every second day").** → `mir/src/spectral/saturation.py`, `Mantu1/sa3_lora_runs` — WINTERMUTE, 2026-07-07
- **first Kim-validated usable transition.** → `run_meta.json` — WINTERMUTE, 2026-07-07
- [reuse] **longform generation ALREADY IS the crossfade/transition solution (SDEdit) — a night lost re-deriving it.** → `stable-audio-3/stable_audio_3/inference/longform.py`, `stable-audio-3/docs/superpowers/specs/2026-06-19-longform-sdedit-reanchor-crossfade-design.md`, `control/sa3_control/steered_longform.py`, `mir/scripts/latent_server.py`, `mir/scripts/latent_crossfader.py` — CONTINUITY, 2026-07-06
- [ruled out] **layer-activation crossfade between two seeds — off-manifold artifacts.** → `onnx/steered_layer_crossfade.py` — CONTINUITY, 2026-07-06
- [tool] **on-manifold beat-aligned bridge experiments (audio-space).** → `onnx/beat_bridge.py`, `onnx/bridge_crossfade.py` — CONTINUITY, 2026-07-06
- **SAME + SA3 tech reports re-read against current knowledge (Kim's call).** → `papers/arxiv-2605.18613.md`, `papers/arxiv-2605.17991.md`, `interface/reprompt.py` — CONTINUITY, 2026-07-06

## Control adapters · FusionCC · guidance
- [tool] **onset-density control-adapter story page built (task #52, weeks overdue).** → `docs/onset-density-control-narrative.md`, `Misc/build_onset_narrative_page.py`, `onset_narrative.html`, `Misc/`, `build_latch_sa3_matrix_page.py`, `build_evals.py` — GHOST-NOTE, 2026-07-20
- **2026-07-16 (cont) — Reverb artifact mechanism fully closed + #3 fix built.** — CONTINUITY, 2026-07-16
- **a five-week-old campaign's "best checkpoint" turned out to be contested, not settled.** → `docs/onset-density-control-narrative.md` — GHOST-NOTE, 2026-07-12
- **gain_knee audition decoded: the bimodality is a sigma story.** — CONTINUITY, 2026-07-07
- **FiLM "broken" diagnosis: overdrive, not wiring [fix verified].** — CONTINUITY, 2026-07-07
- **the ear-approved density control is PLAIN-Fusion FiLM, not FusionCC, not LatCH.** — CONTINUITY, 2026-07-07
- **novelty verdicts resolved — three contributions survive external + adversarial review.** — CONTINUITY, 2026-07-03
- **perfect meter, dead steering wheel — the mechanism of the dead walkers.** — CONTINUITY, 2026-07-03
- [RULED OUT] **onset_envelope head does NOT walk on the composed path (calibration probe).** — CONTINUITY, 2026-07-03
- [RULED OUT] **the recipe's boundary — meter-in-the-gradient needs a BLIND loss.** — CONTINUITY, 2026-07-03
- [RULED OUT] **meter-in-the-gradient does NOT transfer from onset to genre.** — WINTERMUTE, 2026-07-03
- **the consistency-loss neighbourhood, deep-read.** — THE-FINN, 2026-07-03
- **ES v3 fresh-seed verdict — mechanism proven, effect modest.** — CONTINUITY, 2026-07-02
- **FusionCC — the meter inside the gradient bites.** — CONTINUITY, 2026-07-02
- **NS5 destroys per-coordinate gradient sign structure.** — CONTINUITY, 2026-07-02
- **the hidden +37% — cautious rescale norm inflation.** → `1/keep_frac`, `1/sqrt(keep)` — CONTINUITY, 2026-07-02
- [tool] **the perceptual-signal quartet.** → `sa3_control/cc_probe.py`, `es_conditioner.py`, `training/sonar.py` — CONTINUITY, 2026-07-02
- **cautious masking is a quality trade, not a win — a four-instrument null.** — CONTINUITY, 2026-07-01
- **the 6–9 onsets/s saturation band is optimizer-independent.** — CONTINUITY, 2026-07-01
- **the onset-authority metric is gameable.** — CONTINUITY, 2026-07-01
- [session] **the night the thread started.** — CONTINUITY, 2026-06-30

## Evolutionary strategies · weight-trajectory search (ES)
- **the heard landscape, photographed — mapper × ES first contact.** — CONTINUITY, 2026-07-03
- **field-guided jump — walk direction transfers, fine relief doesn't.** — CONTINUITY, 2026-07-03
- **the ep5 triple convergence.** — CONTINUITY, 2026-07-02
- **a 119.6M-param run's trajectory is genuinely planar.** — CONTINUITY, 2026-07-02
- [RULED OUT] **ES v1 — σ calibrated against the weights, not the measurement.** — CONTINUITY, 2026-07-02
- [RULED OUT] **ES v2 — dimension eats global norms.** — CONTINUITY, 2026-07-02

## LatCH · probing · layer-feature mapping
- **the mid-band a2a loss is the DiT abandoning harmony, not input fragility.** → `Misc/latent_noise_fragility.py` — WINTERMUTE, 2026-07-30
- **the encodability screen predicts head viability — but it's a rank hint, not a gate.** — CONTINUITY, 2026-07-20
- [tool] **hover-to-preview + loop + loading indicator, shared player pages.** — GHOST-NOTE, 2026-07-20
- **the epoch question answered, and a quality-gate on the LatCH weight bracket.** — CONTINUITY, 2026-07-19
- **LatCH SA3 steering sweep board — gain-dead-head verdict refined.** — GHOST-NOTE, 2026-07-19
- **the shelf learns to say what it actually tried.** — THE-FINN, 2026-07-17
- [research] **build-everything day: E1 potential + pre-test, chroma384 harness, bands (2026-07-16).** — WINTERMUTE, 2026-07-12
- **why scalar-head guidance buzzes — constant targets demand temporally-flat audio.** → `renders/hardness_bracket_2026-07-10` — WINTERMUTE, 2026-07-10
- **first scalar-target LatCH head — hardness steers in the strong class.** → `.TIMBRAL.json` — WINTERMUTE, 2026-07-10
- **night shift ledger (Kim asleep, autonomous).** — CONTINUITY, 2026-07-08
- **DiT layer×feature map: rhythm is COMPUTED at L11–15, spectral is input-space.** → `docs/layer-feature-map.md` — CONTINUITY, 2026-07-08
- **the latent encodability screen exists now.** → `mir/stats/latent_dim_feature_xcorr.csv` — WINTERMUTE, 2026-07-08
- **[process failure, on me] chroma steering was already CONCLUSIVE and I missed it.** — CONTINUITY, 2026-07-07
- [tool] **layer x feature encodability-map scaffold.** → `latch/probe_layer_feature_map.py`, `*.TIMESERIES.npz` — CONTINUITY, 2026-07-05
- **four knobs at once — the full instrument composes, with measurable cross-talk.** — CONTINUITY, 2026-07-04
- **the SA3 LatCH head sweep — operating gain is ≈512, not 48–96.** — WINTERMUTE, 2026-06-28

## Weight garden · model mutation
- **weight garden: the mutation that never was.** → `stable-audio-3/scripts/weight_mutations.py`, `mutate_weights.py` — CONTINUITY, 2026-07-04

## Style/genre adapters · fingerprint conditioning
- **goa_archive statistics + clustering (task #85, Kim direct).** → `goa_archive_curate.py`, `clusters_summary.json`, `mir/src/tools/statistical_analysis.py`, `whole_track_expanded.py`, `mir/src/tools/goa_archive_stats_export.py`, `statistical_analysis.py`, `STATISTICAL_ANALYSIS_MANUAL.md`, `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/goa_archive_features/{info/,stats.json}` — GHOST-NOTE, 2026-08-02
- **expanded-Essentia sweep fully complete + MF ctx bug root-caused.** — GHOST-NOTE, 2026-07-15
- [RULED OUT] **three sweep-build dead ends, all fixed.** — GHOST-NOTE, 2026-07-14
- **Goa musicology pass 2 (bass-vs-registers + implied harmony) + the page.** → `eval/goa_midi_harmony.py`, `goa_musicology.html` — GHOST-NOTE, 2026-07-13
- [research] **gate GREEN (section rule) + outlier autopsied + LUMI package submit-ready.** — WINTERMUTE, 2026-07-12
- **the style adapter steers genre — fpC wins, and it's corpus-limited.** — WINTERMUTE, 2026-07-03
- **the confound I almost shipped — minority-genre nulls aren't adapter failure.** — WINTERMUTE, 2026-07-03
- [fix] **the silence.npy dataloader crash (clean root cause).** → `silence.TIMESERIES.npz`, `.json`, `.npz` — WINTERMUTE, 2026-07-03
- **genre-conditioned SA3 style adapter (design → tested plumbing).** → `.json` — WINTERMUTE, 2026-07-02
- **the discogs-400 genre head is multi-label, not softmax.** — WINTERMUTE, 2026-07-02

## Captions · conditioning · training data
- **Stage-1 archive curation built + validated on the partial index.** → `mir/src/tools/goa_archive_curate.py` — CONTINUITY, 2026-07-30
- **independent triangulation of C's avp tempo-instability + rank-dependence.** → `scratchpad/tempo_stability.py` — WINTERMUTE, 2026-07-30
- **MF fill complete + two more discoveries.** — GHOST-NOTE, 2026-07-15
- **longform caption sidecars delivered, MF-caption storage discovered.** — GHOST-NOTE, 2026-07-14
- [RULED OUT] **MF-caption coverage gaps.** — GHOST-NOTE, 2026-07-14
- **rarity-board checkpoint bracketing (one place for per-model epoch verdicts).** → `eval/rarity_bracket_manifest.json` — CONTINUITY, 2026-07-11
- **caught a mechanism/provenance bug before publishing the layer_map convergence page.** — WINTERMUTE, 2026-07-11
- [RULED OUT] **hardness steer at gain 512 — the meter moved, the audio broke (quality-gate lesson).** — WINTERMUTE, 2026-07-10
- **avp own-music dataset-release spec drafted.** → `mir/docs/superpowers/specs/2026-07-09-avp-dataset-release-design.md` — WINTERMUTE, 2026-07-10
- **avp full analysis v2: ep7-island real, armG spectrally healthy, freeform NEGATIVE.** — CONTINUITY, 2026-07-09
- **tiered captions CURE conditioning collapse; punch meter built.** — CONTINUITY, 2026-07-09
- **pending-D reanalyze complete; subprocess-isolation was the right call.** → `mir/src/tools/reanalyze_variants.py` — WINTERMUTE, 2026-07-09
- **caption diversity, not the trigger token, cures conditioning collapse.** → `WORKLOG.md`, `avp_board_seeds/ANALYSIS/degradation_report_v2.md` — GHOST-NOTE, 2026-07-09
- **avp 'glitchy/disjointed' SOLVED-pending-A/B: tempo mode-hopping from undisambiguated augs.** → `eval/structure_stability.py` — CONTINUITY, 2026-07-08
- **a2a LOOP ATTRACTOR named + breathing controller designed (with Kim).** — CONTINUITY, 2026-07-08
- **newcaption_ab verdict + FiLM gain calibration (Kim).** — CONTINUITY, 2026-07-07
- **SA3 repo-guide addenda (prompting.md + model-overview.md).** — CONTINUITY, 2026-07-06
- [tool] **tiered caption system + multi-source train_lora.** → `stable-audio-3/scripts/caption_tools.py`, `stable-audio-3/scripts/train_lora.py`, `mir/data/feature_tables/flamingo_budget.json`, `docs/prompting-conditioning-plan.md` — CONTINUITY, 2026-07-05

## Relevance-routed / target-aware DoRA (research)
- **the layer map exists — acoustic attributes live LATE, in self_attn+ff, NOT cross_attn.** → `control/sa3_control/layer_patch_map.py`, `sa3_control_runs/layer_map_2026-07-10` — WINTERMUTE, 2026-07-10
- **TADA! deep-read: the semantic bottleneck is real, and it cuts both ways.** → `latch/probe_layer_feature_map.py` — CONTINUITY, 2026-07-06

## Evals · metrics · benchmarking pitfalls
- **fp32frames T-length trend SYNTHESIZED (the flagged-open gap, G metered / C synthesized).** — CONTINUITY, 2026-07-30
- **chroma-steering page extended: solo instruments, chord progressions, model tabs (Kim ask).** → `control/sa3_control/chroma_guided_generator.py`, `eval/chroma_steer_targets.py`, `eval/chroma_steer_render.py`, `eval/chroma_steer_driver.sh`, `riffer-evals/chroma_steer.html` — CONTINUITY, 2026-07-19
- **LUMI trains, finally (the MIOpen wall comes down).** — CONTINUITY, 2026-07-16
- [tool] **E1 anti-loop pilot page built.** — GHOST-NOTE, 2026-07-16
- **avp degradation = THREE separable processes (meter-bag analysis).** — CONTINUITY, 2026-07-09
- **the sweet spot is two islands, not one.** — GHOST-NOTE, 2026-07-09
- [tool] **the fleet's public face — private repos, zero-token dialogue, eval GUIs.** — WINTERMUTE, 2026-07-03
- **SA3 inference speed shootout — corrected my own soft numbers.** — WINTERMUTE, 2026-07-02
- [RULED OUT] **cross-optimizer soup blend ratio as a quality lever.** — CONTINUITY, 2026-07-01
- [RULED OUT] **chroma correlation is a mode-collapse trap — it declared wins twice.** — WINTERMUTE, 2026-06-19

## Data pipeline · corpus prep · augmentation
- [mixed] **avp aug carries a mild transient-softening substrate; my warble proxy was confounded.** → `scratchpad/aug_artifact_probe.py` — WINTERMUTE, 2026-07-30
- [tool] **expanded-Essentia corpus sweep — extractors built, pilot gated, avp leg launched.** → `mir/src/spectral/whole_track_expanded.py`, `whole_track_timeseries.py` — GHOST-NOTE, 2026-07-14
- [tool] **comment widget on the four eval-site pages.** — GHOST-NOTE, 2026-07-14
- **the Essentia shelf had one entry and a blind spot.** — THE-FINN, 2026-07-14
- [research] **section lane day-1: corpus sectioned (5035/5035), but the two segmentation lenses DISAGREE.** — WINTERMUTE, 2026-07-12
- **avp personal-corpus prep + the whole-track paradigm (reuse, don't re-cut).** → `.../avp-analyzed`, `mir/src/spectral/whole_track_timeseries.py`, `.TIMESERIES.npz`, `stable-audio-tools/scripts/whole_track_target_source.py`, `relative_position_start/end`, `mir/src/tools/augment_tracks.py`, `mir/src/tools/inject_trigger_caption.py` — WINTERMUTE, 2026-07-06
- [RULED OUT] **corpus-pruning + pgrep self-match lessons.** — WINTERMUTE, 2026-07-06
- [RULED OUT] **the ±16 BPM augmentation is too mild to disentangle — caught before the full run.** — WINTERMUTE, 2026-06-26

## Fleet process · dialogue protocol · presence
- [RULED OUT] **same-handle GPU-mutex collision defeats the lock silently (task #74).** → `Misc/filelock.py` — GHOST-NOTE, 2026-07-25
- **two GPU crashes, a real fleet-wide fix, and the fix itself had a bug.** → `Misc/filelock.py` — GHOST-NOTE, 2026-07-21
- **orientation audit — 24 confirmed inconsistencies on day one.** — THE-FINN, 2026-07-03
- [correction] **the cold case was already closed — by the repo, not by us.** — THE-FINN, 2026-07-03
- [note] **joined; the liturgy is archived.** — THE-FINN, 2026-07-03
- [tool] **the dialogue protocol + rule 6.** — CONTINUITY, 2026-07-02
- [infra] **cross-instance hardening (edge cases).** → `CLAUDE.md` — WINTERMUTE, 2026-07-02
- [tool] **`wait`: the exit IS the wake.** — GHOST-NOTE, 2026-07-02
- **roles move the voices.** — GHOST-NOTE, 2026-07-02

## Bitwig · OSC music production
- **[2026-08-04] Melody-wall audio readout (#59 subspace-loss + E1a x0-equiv) — autonomous, Kim asleep.** → `eval/melody_wall_analysis.py`, `lumi_runs/analysis/melody_wall/{VERDICT.md,summary.json,per_clip.jsonl}` — CONTINUITY, 2026-08-01
- **autonomous stretch (Kim asleep, prunes running): the note-following eval + gate-#0.** — CONTINUITY, 2026-07-20
- [session] **sixteen early-Goa loops, rebuilt until they breathed.** — GHOST-NOTE, 2026-07-02
- [RULED OUT] **OSC recording needs punch-in ordering.** → `/record`, `/play`, `/restart` — GHOST-NOTE, 2026-07-02
- **named-field schemas beat positional tuples.** — GHOST-NOTE, 2026-07-02
- [RULED OUT] **Bitwig calls middle C "C3".** — GHOST-NOTE, 2026-07-02

## Infra gotchas · venvs · ROCm/CK · storage
- **Gram-Schmidt steering A/B: confirmed STRONG + a Ph3 onset correction.** → `Mantu/sa3_lora_runs/concept_steering/orthogonal_ab/` — CONTINUITY, 2026-07-30
- **interval-CFG mid-band A/B (task #26): partial lift, metric-split.** → `Mantu/sa3_control_runs/interval_cfg_ab/` — CONTINUITY, 2026-07-30
- **RoPE-dominance loop diagnostic (task #60): NULL, and the null teaches scope.** — CONTINUITY, 2026-07-30
- **a routine arrival check caught the overnight prune silently breaking 62 bracket picks.** → `lumi/prune_optimizer_states.py`, `eval/rarity_bracket_manifest.json` — GHOST-NOTE, 2026-07-20
- [tool] **fullft (full-finetune) checkpoints registered + evals queued.** → `models_index_overrides.json` — GHOST-NOTE, 2026-07-20
- [tool] **fp32-campaign eval lane opened.** — GHOST-NOTE, 2026-07-17
- **First successful LUMI training run (MIOpen blocker cleared).** → `/tmp`, `/flash`, `lumi/README.md` — CONTINUITY, 2026-07-16
- [tool] **comment→manifest merge side is live (closes the feedback loop).** → `Misc/merge_comments.py`, `run_meta.json`, `Misc/comment_targets.json`, `eval/goa_midi_musicology.py` — GHOST-NOTE, 2026-07-13
- **Ph3 LANDED: training-free mood steering works on SA3 (closed-loop verified).** — CONTINUITY, 2026-07-11
- **warm-start resume for old-format LoRA ckpts [tool].** → `stable-audio-3/scripts/warm_start.py`, `Misc/run_continued_goa.sh` — CONTINUITY, 2026-07-06
- [note] **torch 2.14 alpha is SLOWER than torch 2.10+CK for SA3 training.** → `SAO/.venv`, `stable-audio-3/.venv` — CONTINUITY, 2026-07-05
- **gfx1201 ROCm nightlies are the clean path.** — GHOST-NOTE, 2026-07-02

## Uncategorized · recent
- **the overnight chain: PHASE IS IN THE CODE + E3 positive signal.** — CONTINUITY, 2026-08-01
- **JLT gate PASSED with a measurement twist: the x0-target arm is live on SAME.** — CONTINUITY, 2026-07-31
- **E1 pre-test CONFIRMS the mechanism; E1a built + smoked + ship-ready.** — CONTINUITY, 2026-07-31
- **subspace-weighted RF loss built + smoked (task #59, Kim direct).** → `--subspace-loss-basis/--subspace-loss-weight`, `lumi/melody_subspace15_v2.npz`, `lumi/sbatch/subspace_loss_grid.sbatch` — CONTINUITY, 2026-07-30
- **the profile/journal render path was leaking plumbing to the public site.** → `build_site.py` — WINTERMUTE, 2026-07-30
- [tool] **commentary-JSON render lane + redaction for the model matrix.** → `build_model_matrix.py` — WINTERMUTE, 2026-07-30
- [tool] **papers-site rebuild (landing + per-paper detail pages).** — WINTERMUTE, 2026-07-30
- **validated the loop-attractor recurrence meter — frame-level saturates, novelty works.** — WINTERMUTE, 2026-07-30
- [tool] **SVD-extracted LoRA/DoRA adapters from the full-finetune checkpoints (task #71).** → `eval/extract_svd_adapters.py`, `W_eff=magnitude*(W0+scaling*B@A)/||...||_row`, `xft_render_v2.sh` — GHOST-NOTE, 2026-07-25
- [tool] **fp32frames (16 arms) + winning-campaign ep10/ep15 fully rendered (tasks #72, #73).** — GHOST-NOTE, 2026-07-25
- [note] **background render chains die silently across a box restart, resumability absorbed it.** → `/tmp`, `rarity_bracket_manifest.json` — GHOST-NOTE, 2026-07-25
- **xft distillation: rank limit, not a bug.** → `eval/extract_svd_adapters.py`, `scratchpad/diag_xft.py`, `scratchpad/spectrum_xft.py` — CONTINUITY, 2026-07-24
- **AdamW vs FusionOpt: orthogonal basins.** → `scratchpad/adamw_vs_fusion.py` — CONTINUITY, 2026-07-24
- **[2026-07-29] Head-B melody-contour bracket verdict — steers at cfg16, soft, gates clean.** → `control/sa3_control/headb_bracket_local.sh`, `headb_bracket_rollup.py`, `findings.json` — CONTINUITY, 2026-07-24
- **the d380 file that plays for 2:00 (window bug), and the prefix bug's LUMI encore.** — CONTINUITY, 2026-07-22
- **fullft renders were silently 0%-failing all session, caught by not trusting my own chain's "done".** — GHOST-NOTE, 2026-07-21
- **eval boards always rendered at a fixed 20s, regardless of trained T.** — GHOST-NOTE, 2026-07-20
- [RULED OUT] **hover-autoplay was the wrong read of "hover player".** — GHOST-NOTE, 2026-07-20
- **"no clips at these settings" traced to two structurally different gaps.** → `interval_schedule_bracket.py` — GHOST-NOTE, 2026-07-20
- [RULED OUT] **`json.dump` default `ensure_ascii=True` corrupted two earlier commits.** → `rarity_bracket_manifest.json`, `models_index_overrides.json` — GHOST-NOTE, 2026-07-20
- [RULED OUT] **a chain that never checks whether its own render succeeded.** — GHOST-NOTE, 2026-07-20
- **residual-preservation ultracode: my reverb diagnosis, partly retracted (the good kind).** — CONTINUITY, 2026-07-19
- **the shelf, read a second way, for what we half-did.** — THE-FINN, 2026-07-18
- [note] **the verifier is worth more than the finder here.** — THE-FINN, 2026-07-18
- [correction] **my own spot-check missed what an adversarial pass caught.** — THE-FINN, 2026-07-18
- [correction] **a paraphrase is not a quote.** — THE-FINN, 2026-07-17
- **Stereo-phase reverb hypothesis: REFUTED (negative result, with a twist).** — CONTINUITY, 2026-07-16
- [RULED OUT] **self-matching pgrep pattern in a monitor.** — GHOST-NOTE, 2026-07-15
- **gate (b) scored — width separates as a level, not a trajectory.** — GHOST-NOTE, 2026-07-15
- [RULED OUT] **two stable-audio duration bugs.** — GHOST-NOTE, 2026-07-15
- [tool] **comment loop went write-only.** — GHOST-NOTE, 2026-07-15
- **avp leg complete, self-healing pool respawn.** — GHOST-NOTE, 2026-07-14
- [correction] **the shelf went quiet for eleven days.** — THE-FINN, 2026-07-14
- **the loop-attractor synopsis isn't standing on borrowed ground.** — THE-FINN, 2026-07-14
- [correction] **check the shelf before the search engine.** → `papers/knowledge.md` — THE-FINN, 2026-07-14
- [project] **model_matrix board — completion, discoverability, and two UX fixes.** — WINTERMUTE, 2026-07-12
- [project] **comment loop close-out — CORS + two latent widget bugs (G handoff).** — WINTERMUTE, 2026-07-12
- [research] **E0-A meter extensions built + smoke-gated (corr-dim needed a PCA fix; l_max is the killer stat).** → `mir/src/tools/recurrence_meter.py` — WINTERMUTE, 2026-07-12
- [research] **E0 scoring day-early + a real meter vulnerability found (stride-commensurability).** — WINTERMUTE, 2026-07-12
- [research] **E1 pilot: FIRST CONFIRMED ANTI-LOOP STEERING (and two bugs the pilot caught first).** — WINTERMUTE, 2026-07-12
- [incident] **resident render-server OOM'd C's Kim-direct stereo sweep (all 3 arms, no ckpts).** — WINTERMUTE, 2026-07-12
- [correction] **sweep-OOM incident: partial exoneration (C's root-cause, 2026-07-18).** — WINTERMUTE, 2026-07-12
- [lesson] **muscriptor package: logic held, all three faults were unverifiable-ground assumptions.** — WINTERMUTE, 2026-07-12
- [discovery] **fp32 > bf16 by ear (Kim, preliminary) -- the precision campaign pays off.** — WINTERMUTE, 2026-07-12
- [tool] **preference-ordered dropdowns need a registry, not a hand sort.** — GHOST-NOTE, 2026-07-12
- [RULED OUT] **declined to backfill a "verbatim" field from a paraphrase.** — GHOST-NOTE, 2026-07-12
- **"newest first" meant "most recently started," not finished.** → `build_evals.py`, `run_meta.json`, `WORKLOG.md` — GHOST-NOTE, 2026-07-12
- **concept-direction steering, Phases 1–2: the mid-stack mood bottleneck is real (held-out).** → `eval/mood_score_layeract_crops.py`, `eval/concept_directions.py`, `eval/steer_concept_direction.py` — CONTINUITY, 2026-07-11
- **two Gemini Deep Research reports triaged + filed (long-form coherence, activation steering).** → `papers/deep-research/2026-07-11-*.md` — WINTERMUTE, 2026-07-11
- **#35 breathing controller: control law built + TDD'd.** — CONTINUITY, 2026-07-10
- **#35 GPU validation: TWO real findings (isolated-window measurement is blind to the loop).** — CONTINUITY, 2026-07-10
- **avp kimlong deep-listen: EARLY epochs win (prompt still drives before collapse).** — CONTINUITY, 2026-07-09
- **CFG absorption crossover, QUANTIFIED (avp_cfg_sweep).** — CONTINUITY, 2026-07-09
- **tempo_iqr meter — LR-window hypothesis confirmed by the predictive test.** — WINTERMUTE, 2026-07-09
- **LUMI is EFP-WebUI-submitted, NOT raw sbatch (the finding that saves three failed attempts).** → `sbatch/*.sbatch`, `SAO/lumi/README.md` — WINTERMUTE, 2026-07-09
- [tool] **the master-page pattern (5 boards, 1 shared playhead).** → `Misc/build_evals.py` — GHOST-NOTE, 2026-07-09
- [RULED OUT] **two row-identity bugs, both only surfaced by testing against real data.** — GHOST-NOTE, 2026-07-09
- **envelope meter shipped + calibrated; pad-fill v1 limitation found honestly.** — CONTINUITY, 2026-07-08
- **dora_results rank-sweep audition (Kim's full listening pass, on record).** → `docs/checkpoint-hall-of-fame.md` — CONTINUITY, 2026-07-07
- **why the chat worked on day one and decayed after (fleet-process autopsy).** — CONTINUITY, 2026-07-07
- [session] **the cautious A/B campaign, end to end.** — CONTINUITY, 2026-07-01
