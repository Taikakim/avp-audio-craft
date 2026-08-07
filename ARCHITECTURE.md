# ARCHITECTURE — what's where (1-page map)

Brief orientation. Detail lives in `MASTER.md` (cross-cutting facts) and `docs/`.

## The pipeline, end to end

```
  AUDIO (Mantu)                 MIR (mir/)                    LATENTS (NVMe)              MODELS (SAO/)
  ┌────────────┐    extract     ┌──────────────┐   encode    ┌──────────────┐   train     ┌──────────────┐
  │ Goa tracks │ ─────────────► │ .INFO + beat │ ──────────► │ .npy latents │ ──────────► │ SA3 medium   │
  │  + stems   │   features,    │ grids, 46-fld│  SAME (SA3)  │ + .json +    │  DoRA /     │ (1.5B DiT)   │
  │  + avp     │   beat grids   │ timeseries   │  64-d (SA1)  │ .TIMESERIES  │  LatCH/FiLM │ SA-Small     │
  └────────────┘                └──────────────┘             └──────────────┘             └──────────────┘
        │                                                            │                            │
        └── source of truth                          targets for ◄──┘          LatCH guidance ◄──┘
            (goa 4470 + avp own-music)                LatCH heads               steers generation
```

## Repos (see MASTER §1 for venvs)

- **`mir/`** (`/home/kim/Projects/mir`) — extracts MIR features → `.INFO` sidecars,
  beat/downbeat/onset grids, whole-track 100 Hz timeseries, Audiobox aesthetics.
  The "what does this audio contain" engine. Feeds everything downstream.
- **`SAO/stable-audio-tools/`** — the "audio-tools-AVP" **thin fork** (editable;
  `stable_audio_tools` package deltas only): **LatCH heads** (training-free guidance),
  **FusionOpt**, `rocm_env`, the FA backward patch. `LATCH_RESULTS.txt` is the LatCH lab
  notebook. The first-party *tooling* that imports it now lives in the master repo:
  LatCH head training + auditions in **`latch/`** (`train_latch`, dataset/model, probes),
  and SA3 control-adapter tooling in **`control/`** (`sa3_control/` riffer trainer on
  `latents_sa3` + timeseries; `scripts/` `sa3_flowsep`/`sa3_zerosep_rf` generative
  separation, `stem_score`). See `control/ARCHITECTURE.md`.
- **`SAO/stable-audio-3/`** — SA3 medium model (1.5 B DiT), LoRA finetune, SA3
  LatCH (phase 1). The bigger/newer generation. **Kept upstream-syncable thin fork** —
  tooling moved to the master repo (`onnx/`, `control/`, `eval/`, `latch/`); only
  SA3-side package code (LatCH, ROCm, attn/APG patches) stays here.
- **`SAO/sa3-rocm7.13-test/`** — the **ROCm 7.14 / CK flash-attn stack** (torch
  2.12+rocm7.14, `.venv` + `flash-attention` rdna branch built with CK kernels for
  gfx1201). CK FA validated for `sa3_control` **training** (2026-06-18) after the
  backward grad-count patch. Enable per `docs/flash-attn-ck-rdna4.md`
  (`FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` + §5b patch). The 2× vs Triton FA2 is
  still to be pilot-measured. See also `docs/venvs.md`.
- **`SAO/torchcodec/`**, **`SAO/my_wheels/`** — custom torch+ROCm wheel/codec builds.

## Data (drives removable; see MASTER §2 for the full table)

- **NVMe** (`/home/kim/Projects/`) — the live SA3 latents. `latents_sa3` (14 G; 5401
  `.npy`+`.json`+`.TIMESERIES.npz`, 256-d, T=4096, 10.767 Hz) + `latents_avp` (6 G, own-music).
  **Backup:** a second copy at `/run/media/kim/Mantu/sa3-latents_backup/latents_sa3/`
  (verified in parity 07-12; sync is **manual**, keep it current). `Lehto/latents_sa3`
  was removed 07-04 — do not look there.
- **Mantu** (`/run/media/kim/Mantu`) — source audio + checkpoints + the latents backup.
  `ai-music/Goa_Separated` (4470 full tracks + stems + grids),
  `sa3_lora_runs` + `sa3_control_runs` (checkpoints/eval runs, moved off Lehto 07-04).
- **Lehto** (`/run/media/kim/Lehto`) — **training data only**. `timeseries` (37 G, the
  **46-field** whole-track set), `latents` (SA-Small 64-d), `latents_stems`.
- **The eval-metrics DB** `eval/clip_metrics.db` (~43 k clips × 14 metrics incl. GPU-costly
  Audiobox CE/PQ) is NOT a latent sidecar and NOT in the latents backup — snapshotted to
  Mantu 07-19; recurring backup is a TODO (`docs/open-threads.md`).

## Reusable plumbing — the internal reuse index (check here before building)

Already built across the repos; **reuse, don't rebuild.** This is the *internal* reuse
index; `papers/knowledge.md` is the *external* prior-art index, and `docs/open-threads.md`
tracks open/dropped work. Paths are SAO-relative unless a repo is named. Last full
inventory sweep: 2026-07-20 (4 agents across mir/SAO); **top-up 2026-08-05 (doc-oversight)** — see
the block below for tools built since. Add new reusable building blocks here as they land — a stale
index is how repeat work happens.

**Built since the 07-20 sweep (doc-oversight 2026-08-05, not yet filed into A–F below):**
`eval/build_run_audit_board.py` (run-audit board) · `eval/melody_wall_analysis.py` (whitened-chroma
melodic-recurrence metric — raw chroma saturates on tonal goa) · `eval/precision_injection_ab.py` +
`stable-audio-3/stable_audio_3/training/stochastic_rounding.py` (precision A/B + SR residual writes) ·
`eval/cross_attn_mask_ab.py` (cross-attn mask A/B) · `eval/build_hf_repair_pairs.py` +
`eval/train_hf_repair.py` + `eval/eval_hf_repair.py` (HF reconstruction-filter pipeline) ·
`eval/build_clap_hyperparam_table.py` · `eval/build_clip_scores_export.py`. A full re-sweep is still owed.

### A · MIR features & audio analysis (`mir/`, `mir/bin/python`)
- **bungee time-stretch / pitch-shift** — `bungee_python` 0.2.1 (built in `mir/pitch_venv` from `mir/repos/bungee`); A/B GUI `mir/pitch_shifter_gui.py`. `bungee.Bungee(sr,ch).time_stretch/.pitch_shift`.
- **MIR base pipeline + whole-track timeseries** — `mir/src/spectral/whole_track_timeseries.py`; window consumer `stable-audio-tools/scripts/whole_track_target_source.py`. **Now 46 fields** (20 legacy @100 Hz + 26 expanded @ native rates). The expanded extractor is **`mir/src/spectral/whole_track_expanded.py`** (`FeatureExtractor`: MAEST 768-d embeds `_maest`, genre/mood/instrument curves, DEAM/emoMusic V-A, attack-transient family, stereo width/corr `_stereo_fields`, Bark/ERB, NNLS→chroma_linmap, chords, EBU-R128, dyn-complexity; TF pinned CPU-only). **Consumers must read the sidecar `field_rates` — not everything is 100 Hz.** Incremental backfill: `whole_track_timeseries.py --add-fields`.
- **Loop / longform meter** — `mir/src/tools/recurrence_meter.py` (v3 whitened-patch loopiness/novelty + `calibrate_source`, now + corr-dim + soft-DET/RQA). **The loop-metric core — import `novelty_curve(x,fps)`, don't re-derive.** Also: `tempo_iqr.py` (within-clip tempo instability), `section_extractor.py` (Foote SSM boundaries + energy arcs → `.sections.json`), `melodic_movement_ladder.py` (chroma-flux/pc-transition U-shape scorer).
- **Timbral extractors** — `mir/src/tools/extract_timbral_hdb.py` (AudioCommons hardness/depth/booming, tracks + per-crop) · `extract_reverb_depth.py` (RT60/depth, the one *safe* wrapper of the hang-prone reverb feature, SIGALRM-guarded).
- **Essentia classifier suite** — `mir/src/classification/` (`effnet_onnx` embedding backbone, `gmi_onnx` genre/mood/instrument heads, `vggish_onnx`, `essentia_features{,_optimized}`) + `src/tools/` (`crop_genre`, `classify_new_corpus` for onboarding a new corpus, `measure_genre` eval scorer, `build_feature_table` the join layer, `genre_vocab`); provision with `scripts/download_essentia_models.py`.
- **Audiobox aesthetics scorer** — `mir/src/timbral/audiobox_aesthetics.py` (single-file, mir venv).
- **Music captioning (Music Flamingo + Granite)** — `mir/src/classification/music_flamingo.py` + `granite_revision.py`, feeds `stable-audio-3/scripts/caption_tools.py`. **Check mir FIRST for any audio-understanding capability** (re-scouted the hard way 07-08).

### B · Model control, guidance & steering (`stable-audio-3/.../inference/`, `control/sa3_control/`)
- **LatCH heads + guidance** — `stable-audio-3/.../inference/latch_guided.py` `sample_flow_euler_multi_latch_guided` (Selective-TFG, **multiple guides**, `rho/mu/gamma/n_iter`, `band_hinge` + chroma/scalar/cosine/bce loss zoo). Load any head with `stable_audio_3.models.latch.load_latch_from_checkpoint(path, device)` (auto-detects arch — don't hardcode); production heads `stable-audio-3/latch_weights_sa3_medium/*_best.pt`. Phase-tolerant chroma losses: `inference/chroma_losses.py` (canonical twin `control/sa3_control/chroma_losses.py` — keep in sync).
- **Longform / loop-attractor toolchain** (`.../inference/`) — `longform.py` (`LongFormRenderer`, `SDEditReanchor`, `DriftMonitor`, `CrossfadeStitcher`, slerp + SaFa `swap_join`) · `fifo_infinite.py` (Rolling-Diffusion/Diffusion-Forcing per-token (B,T) timesteps, guarded monkey-patch) · `recurrence_potential.py` (`RecurrenceHead` anti-loop guide, band_hinge) · `rope_jitter.py` (per-head RoPE base-freq, reversible ctx-mgr) · `incantation_mask.py` (zeros text cross-attn on clamped history). Wrappers in `control/sa3_control/`: `steered_longform.py`, `development_renderer.py` (clamp/sdedit/crossfade selector, never edits longform.py), `density_schedule.py` (`ControlSchedule` + ridge_gain).
- **Guidance / sampling seams** — `.../inference/sampling.py` (`build_schedule` dist-shift-aware + sampler zoo, each exposing a per-step `callback({x,t,sigma,i,denoised})`) · `models/dit.py` native **limited-interval CFG** (`cfg_interval`, ~L479) + per-LoRA `interval`/`layer_filter` sigma-gating — **ships off by default `(0,1)`** · `models/transformer.py` `SA3_SDPA_CAST_BF16` env (fp32→bf16 attention island; the flash-attn path silently casts fp32→fp16, ~L718).
- **Control-adapter kit** (`control/sa3_control/`) — `adapters.py` (`ControlledCrossAttention`, decoupled/IP-Adapter pattern, zero-init no-op) + `inject.py` (`install_adapters`, runtime wrap+freeze) + `conditioner.py`/`es_conditioner.py` (token encoders incl. 384-ch chroma; gradient-free OpenAI-ES refiner) + `cc_probe.py` (frozen differentiable onset-density training-consistency loss) + `chroma_guided_generator.py` (chord→chroma progression driver).
- **Steering / interpretability** — `control/sa3_control/layer_patch_map.py` (**Axis-1 causal localizer** — which block/module carries an attribute; routes rank, doesn't mask) · `checkpoint_trajectory_stats.py` (**run on every finished run** — path/curvature/soup-center) · `landscape_map.py` (trajectory-PCA + planarity null) · `telemetry.py` (training telemetry → wandb) · `mert_selector.py` (best-of-N continuation scorer) · `eval/concept_directions.py` + `eval/steer_concept_direction.py` (diff-in-means SA3 activation steering, CFG-conditional-only injection rule) · **per-block weight-delta profilers** `eval/dora_layer_delta_profile.py` (where a DoRA changes the model — ‖ΔW_eff‖/‖W_base‖ per block) + `eval/pt_layer_shift_profile.py` (which layers ARC post-training rewrote) — the "where does this training actually write" tools (found style-training falls with depth + conditioning-pathway dominance; DoRA-vs-ARC per-block anticorrelation is the base→PT-transplant mechanism).
- **SA3 generative separation / riffer** — `control/scripts/` (`sa3_flowsep`, `sa3_zerosep_rf`, `stem_score`) + trainer `control/sa3_control/`. **Inference recipes** (validated param sets): `control/recipes/inference_recipes.yaml` — check before re-tuning.

### C · Eval & site tooling (`Misc/`, `eval/`)
- **Page engine** — `Misc/eval_grid.py` (rich sortable grid/table/compare renderer; the core any eval table builds on) · `Misc/build_evals.py` (site index + the shared **`WAVEFORM_CSS`/`WAVEFORM_JS`** same-playhead player — import for any player page — + `_resolve_mantu()` drive resolver).
- **Models index/matrix** — `Misc/build_model_index.py` (`collect_models()` = canonical run-label source, imported by the matrix) · `build_model_matrix.py` (manifest-driven self-populating board) · `models_index_overrides.json` (per-label recipe/note override layer — edit to annotate without code) · producer `eval/model_matrix_gen.py` + `eval/interval_schedule_bracket.py` (frac→sigma via the exact `build_schedule`) both append the shared `manifest.jsonl`.
- **Report generators (content/build split — edit the `*_data.json`, re-run the builder)** — `Misc/build_kaq.py`, `build_paper_verdicts.py`, `build_stats_page.py` (queries `clip_metrics.db`), per-page drivers `build_{goa_musicology,layer_map,e1_pilot,latch_sa3_matrix,disentangle,mp_crossmodel}_page.py`.
- **Corpus-analysis pipelines** — `eval/musicology/` (C, 2026-07-22) goa transcription musicology study: `phase1_features.py` → `phase2_clustering.py` (substyles) → `phase3_motifs.py` (motif catalog + `hook_melodic_ratio` memorability quantifier). This is CORPUS analysis, not a per-render scorer. `hook_melodic_ratio` (hook-contour repeat-count; ~0 = the measurable signature of the models' missing-melody failure) is *proposed* as a render eval-column — **G/W-owned adoption, not yet a scorer**; if it graduates it gets its own Meters entry. Report + curation subset (259 hooky-leads) + melody-contour LatCH head spec: `eval/musicology/REPORT-2026-07-22.md`.
- **Comment/feedback** — `Misc/comment_notes_block.py` (generator-side widget, clip/ckpt/model scopes) + `inject_comment_widget.py` (idempotent injector for legacy pages) + `comment_targets.json`. **`merge_comments.py` is RETIRED — the comment system is WRITE-ONLY fleet-wide** (public text = injection surface; Kim reads raw + relays).
- **Meters / scorers (`eval/`)** — `width_metric.py` (canonical stereo width; standard column) · `stereo_phase_meter.py` · `reverb_table_measure.py` · `envelope_fidelity.py` (source-vs-output envelope + pad-fill) · `structure_stability.py` (tempo-IQR/key/recurrence) · `latent_dim_feature_xcorr.py`+`latent_noise_fragility.py` (in `Misc/`, not `eval/`; CPU encodability probe — ENCODED/EMERGENT/DEGRADED) · `latent_bend.py` (deterministic latent ops) · `score_loopy_manifest.py`+`corpus_bands.py` (loop-meter validation + quantile bands) · **`control_head_disintegration_eval.py` — MANDATORY gate before any control-head "works/usable-range" claim** (Kim direct 2026-07-20; every steered clip vs its OWN baseline — dead heads pass, buzz heads can score high authority, a usable head clears both; bounds whitening/hf-blowout/noise/beat-loss/CE-drift; reads `clip_metrics.db`, no re-render; supersedes `latch_bracket_quality_gate.py`. Spec: `docs/superpowers/specs/2026-07-20-control-head-disintegration-gate.md` + MASTER control-eval §) · `drift_prediction_analysis.py` · **`clap_score.py`** (W, commit a02c46e — CLAP prompt-ADHERENCE axis, real job = genre-degeneration detector "psytrance must not collapse to drone/noise"; use the ABSOLUTE score and its DROP, NOT fine intra-genre ranking; also a cheap decode-per-iter train-side early-stop/degeneration monitor. Design + prototype numbers: `docs/superpowers/specs/2026-07-22-eval-quality-and-training-signal-design.md`).
  - ⚠ **Axis-blindness of the whole clip_metrics/CLAP/disintegration stack (structural, permanent):** these score genre-adherence + DSP-buzz + Audiobox CE/PQ — NOT fine fidelity, stereo-separation, HF-noise, or punch. Do **not** retire a training arm on a fidelity/separation axis by metric alone (e.g. "fp32≈bf16 by CLAP" does NOT overturn Kim's 07-20 fp32>bf16 *by-ear* verdict — different axes, both true). Ear owns the axes the meters can't see. Fuller treatment: the eval spec's "what these metrics cannot see" caveat.
- **Render/eval harnesses (`eval/`)** — `rarity_gen.py`+`rarity_lite_score.py` (production-invariant MERT-kNN rarity) · `chroma384_eval.py`+`chroma_steer_targets.py` (shared renderer↔page contract) · `section_boundary_validate.py` · `muscriptor_decode_gate.py` · `decoder_haze_probe.py`+`gate_a_noise_injection.py`.
- **Shared data assets** — `eval/clip_metrics.db` (~43 k clips × 14 metrics — **query it, don't re-score**) · `eval/mp_checkpoint_recipes.json` · `eval/kimlong_pool.json` (detailed-prompt pool).

### D · Inference infra (`onnx/`, `mir/`) — AMD / CPU deployment
- **SA3 → ONNX for AMD (ORT + MIGraphX)** — full text→audio, all in `onnx/`. AE `export_same_onnx.py`+`decode_onnx.py`; DiT `export_dit_onnx.py`+`dit_onnx_infer.py`+`precache_dit_cond.py`+`latent_server_dit_onnx.py`; control-adapter bake `export_dit_control_onnx.py`+`dit_control_onnx_infer.py`. **Verdict: a VRAM/deployment win, NOT speed** (eager torch ~3.3× faster/call; ONNX buys 3.8 GB + zero torch dep). Cos≈1.0 vs torch. Gotchas + writeup: `stable-audio-3/docs/onnx-amd-inference.md`.
- **CPU control-adapter eval path (the default, GPU-freeing)** — `onnx/sa3_control_onnx.py` core + `control_eval_server.py` (resident T5-Gemma + ONNX DiT/decoder, queue `SAO/control_eval_queue`) + `submit_control_job.py`. 8-step grid ≈5.4 min CPU vs ~42 min GPU. See MASTER §5.
- **CPU LatCH-guidance eval path** — `onnx/sa3_latch_onnx.py` + `latch_eval_server.py` (queue `SAO/latch_eval_queue`) + `submit_latch_job.py` + `latch_validate.py`. Autograd through the ~5-7 M head only, DiT stays ORT. **Device gotcha:** `device="cpu"` but keep GPU *visible* (do NOT set `HIP_VISIBLE_DEVICES=""`). See MASTER §5.
- **SA3 latent explorer** — `mir/plots/explorer_sa3/` (Dash viewer) + `mir/scripts/latent_server_sa3.py` (SAME-L decode/mix/steer player, port 7892). mir branch `sa3-latent-explorer`.
- **CK flash-attn (RDNA4/ROCm 7.14, faster than Triton FA2)** — built in `SAO/sa3-rocm7.13-test/`. `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before import; TRAINING needs the 1-line backward grad-count patch. Recipe: `docs/flash-attn-ck-rdna4.md`.

### E · LUMI & training toolchain (`lumi/`, project `465003186`)
- **🚨 `MIOPEN_DISABLE_CACHE=1` + `--bind …,/tmp` is MANDATORY on gfx90a** — the MIOpen kernel-cache SQLite open fails on every LUMI filesystem; without it training dies at the first conv. Also `MIOPEN_FIND_MODE=2`, `PYTORCH_TUNABLEOP_ENABLED=0`.
- **Container/env** — `lumi/sa3-env.yml` (cotainr → `.sif`; match `--index-url` ROCm to the base image; torch pinned 2.4–2.6, NOT the local 2.10/gfx1201 wheels) · `env_lumi.sh` (gfx90a profile) · `make_vendor.sh` (FusionOpt vendor shim for `--optimizer fusion`).
- **The proven deployment skeleton** = the `lumi/sbatch/efp_*` scripts (canonical body: SIF at `/project/…/containers/sa3.sif`, code from source + vendored fusion, stage latents to `/flash` once per node, multi-arm via `SLURM_PROCID` case table). **Start new jobs from `efp_fp32_compare.sbatch`, not the older `latch_*`/`dora_*`/`arc_*` templates** (those reference a never-materialized layout — their *recipes* are reusable, the wrapper isn't; `longctx_*` shows the port).
- **Job templates** — `hello_world` (day-0 gate) · `latch_parity` (campaign gate) · `latch_all_features` (`--array=0-19`) · `dora_run` (bracket = for-loop of sbatch; header has the avp-DoRA lessons) · `arc_rollout`+`arc_train` (**2-step, `--dependency=afterok`**) · `longctx_t1024/t2048` · `efp_fp32_compare`+`efp_bf16_twin` (8-arm precision matrix, fp32-SDPA + batch-size probes) · `efp_fullft_t4096` · `ctrl_matrix_hq` (HyperQueue packs a whole node — use for >20 short single-node tasks, GCD-pin via `ROCR_VISIBLE_DEVICES=$SLURM_PROCID`).
- **Data/ckpt utils** — `lumi/pack_data.sh` (tar-over-ssh staging + **doubles as latents cold backup**; target is **LUMI-O** `lumi-465003186-private`, NOT Allas) · `lumi/prune_optimizer_states.py` (fat `.ckpt` → slim `.weights.ckpt`, **keeps both for the final epoch — dedup when counting**, no optimizer state in the slim).
- **Conventions** — crops in **FRAMES = multiples of 256** (`--frames`; T512/1024/2048/4096, verify exact T) · compare ckpts **across the whole run** (stability window; prefer r128/r256 @ lr~1e-4) · 1 GCD/run, the win is parallelism (`standard-g` bills whole nodes) · **ACCESS MODEL: direct `sbatch` works now** (since 07-15; the EFP-WebUI-only banner in `lumi/README.md` is superseded — see `docs/lumi-throughput-workflow-guide.md`).

### F · Fleet comms & patrol infra (`Misc/`, `docs/`, `papers/`, `profiles/`)
- **Comms** — `Misc/agent_dialogue.py` (instance-to-instance chat/DM protocol over `osc_worklog.py` multicast; `say`/`dm-say`/`wait`/`listen`) — **protocol SPEC: `docs/superpowers/specs/2026-07-02-agent-dialogue-osc-protocol.md`** (two-layer listener/wake design, wake-arming via harness-tracked bg task, the presence/deaf gap, heartbeat upkeep) · `Misc/filelock.py` (advisory locks for shared files — **use before editing MASTER.md/specs**; **`--pid-aware` = a long-held-resource mutex** that breaks a foreign lock only when its PID is dead, not on the 15-min mtime timer — the **GPU mutex** — **canonical path `SAO/.gpu.lock` (repo root), the SAME for all instances** — so a live multi-hour job is never stolen but a crashed/rebooted one reclaims instantly. `acquire SAO/.gpu.lock --handle H --pid-aware --pid $$` (the `$$` records the wrapping shell as the persistent holder — NOT the transient CLI) before any render/train/eval, `release` after; prevents the concurrent-GPU overlap that hard-crashed the box twice 2026-07-21. **⚠️ A NON-TEAM instance shares this box and is SUPPOSED to honor `/tmp/gpu.lock`, NOT our `SAO/.gpu.lock` (Kim 2026-08-07) — but it demonstrably runs the GPU WITHOUT writing that lock (verified live 2026-08-07: foreign `grain_sim.py` held 9.7 GB with `/tmp/gpu.lock` ABSENT). A lockfile is a CLAIM; occupied VRAM is a FACT. ORDER MATTERS: (1) `rocm-smi --showpids` is GROUND TRUTH, checked FIRST — foreign VRAM present = do not start, no matter what the lockfiles say (skip our own pid + sub-512 MB idle contexts); (2) `/tmp/gpu.lock` is the FOREIGN channel — honor it (present w/ live pid = taken; reclaim only if its pid is DEAD) and MIRROR our pid into it on acquire / remove on release (only if it's ours — never delete a foreign lock) so the foreign instance sees us; (3) `SAO/.gpu.lock` (`--pid-aware`) is OURS. Don't hand-roll the order — use `Misc/gpu_guard.sh` (W, commit 2284917): `gpu_guard.sh acquire HANDLE PID` returns 0 to proceed / 1 to stand down, `release HANDLE PID` when done; it does the whole dance in the right order.** C stomped the GPU 2026-08-07 trusting only `SAO/.gpu.lock` + a sloppy rocm-smi; a lucky foreign pause saved it — a lockfile-first check would have stomped the still-running foreign job.) · `worklog_note.sh` (log+notify).
- **Site** — `Misc/build_site.py` (profiles/journals → public site) · `Misc/build_dms.py` + `mirror_dialogue.py` (DM/dialogue → redacted HTML; DMs are public-mirrored — the no-secrets rule applies).
- **Patrol ledgers (the anti-repeat-work backbone)** — `papers/knowledge.md` (external prior-art index) · this `ARCHITECTURE.md` (internal reuse index) · **`docs/open-threads.md`** (standing open/dropped-thread ledger — check before flagging, strike when fixed) · `profiles/daily/` (daily digests) · `paper_verdicts.html`/`Misc/paper_verdicts_data.json` (which papers were tested) + `docs/paper-gap-audit-2026-07-18.md` (what we under-applied).

## Doc map

| File | Purpose |
|---|---|
| `ARCHITECTURE.md` (this) | 1-page what's-where |
| `MASTER.md` | cross-cutting facts always loaded into every session |
| `WORKLOG.md` | append-only session log |
| **`docs/superpowers/specs/`** | **design specs — the running source-of-truth per subsystem** (eval-tables human-first, agent-dialogue **comms protocol**, control-head disintegration gate, eval-quality/training-signal, metrical-tree PE, reality-structured experiments, …). No per-spec index yet → a NEW spec MUST get a one-line pointer here or in the relevant §A–F entry (discoverability rule, CLAUDE.md §5). |
| `docs/venvs.md` | the venvs + the CK-flash-attn build |
| `docs/commands.md` | the commands that actually get run |
| `docs/latch.md` | what LatCH is + how heads are trained |
| `docs/training-findings.md` | recipes, params, **why latents are T=4096** |
| `docs/lessons-learned.md` | mistakes to not repeat |
| `docs/todos.md` | open work (+ IDEAS-POOL) |
| **`docs/open-threads.md`** | standing open/dropped-thread ledger + standing gotchas |
| `docs/onset-density-control-narrative.md` | the onset-density control story (§3 verdict) |
| `docs/research-synopsis-longform-continuation.md` + `docs/paper-gap-audit-2026-07-18.md` | longform loop-attractor theory + what we've under-applied from the papers |
| `docs/lumi-transition-plan.md` · `docs/lumi-throughput-workflow-guide.md` · `docs/csc-data-guidelines-guide.md` · `lumi/README.md` | LUMI: bring-up, throughput/HyperQueue, data-movement/LUMI-O backup, the bundle |
| `docs/fleet-audit-2026-07-19.md` | last dropped-thread audit (folded into open-threads) |
| `profiles/daily/` | daily digests (one page/day, Kim's catch-up) |
| `papers/knowledge.md` | the *external* prior-art reuse index (companion to this) |

- **Music captioning (Music Flamingo + Granite) — lives in mir, ALREADY BUILT.**
  `mir/MUSIC_FLAMINGO.md` + `mir/src/classification/music_flamingo.py` (GGUF Q6_K via
  llama-mtmd-cli, ~4 s/track, 5–9 GB VRAM, models in `mir/models/music_flamingo/`) +
  `granite_revision.py` (GraniteReviser, granite-4.0-h-tiny GGUF, condenses to short
  tags). Feeds `stable-audio-3/scripts/caption_tools.py` tiers (T2=Granite-compressed,
  T3=raw Flamingo). Re-discovered the hard way 2026-07-08 (scouted HF before checking
  mir) — check mir FIRST for any audio-understanding capability. (CONTINUITY)
