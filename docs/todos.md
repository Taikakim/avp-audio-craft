# TODOs — open work across the pipeline

## ASK-KIM (2026-07-22 triage)

- LatCH LR-knee retest at 3e-3 — obsolete now that EMA-retrain won for weak heads (WORKLOG.md:1782)? Kill?
- Short-form adequacy ruling (multi-length Phase-2 LoRA item) — your-ear decision, still undecided (training-findings.md:51); the 579-dropped-sources item lives or dies with it.
- CLAUDE.md `@import` confirmation — almost certainly moot (fallback in place; everyone reads MASTER explicitly); one-word kill?
- [POOL] Muon high-LR — self-downgraded 07-17 (parlance's numbers are pretraining-from-scratch only, zero fine-tune evidence); kill, or keep the gentle 1e-4→3e-4 sweep as a #3-stereo-loss rider?
- APT (style-specialized adversarial post-training, LUMI-G) — never started; LUMI now proven; priority call vs #46/#53 (multi-day implementation).

Keep this honest and current. Move done items to `WORKLOG.md`. Newest concerns near top.

## Now / next

- [ ] **LUMI training runs must auto-render our standard clip grid on finish** (Kim's standing
      directive, resurfaced 2026-08-05 after the aug8 clip gap turned out to be exactly this —
      verified the plan was NEVER actually implemented for the DoRA/fullFT training path: grepped
      `scripts/train_lora.py`, zero post-training render/subprocess hook. The only precedent is
      `control/sa3_control/train.py --export-onnx-on-finish` (MASTER §5, 2026-06-27) — and that's
      ONNX export, not a clip render. Every LUMI training run currently needs a SEPARATE,
      manually-submitted render job (checked `lumi/sbatch/*.sbatch` — no `--dependency=afterok`
      chaining anywhere), which is exactly how runs like `aug8_train_ddp` end up with checkpoints
      and zero clips for weeks. Fix: either (a) an sbatch `--dependency=afterok:$TRAIN_JOBID` render
      job auto-submitted at the end of the training sbatch, or (b) a finish-hook subprocess call in
      `train_lora.py` itself (mirroring the control-adapter pattern) that launches the standard-grid
      renderer on the terminal checkpoint. Owner TBD — natural fit for whoever's touching
      `aug8_train_ddp`'s sbatch next (C owns that lane) since it's the run that surfaced the gap.
      GHOST-NOTE, docs/todos.md.)
- [x] **Chroma-morph transitions** (Kim 2026-07-07; CORRECTED after Kim surfaced — DONE 07-07/08 (chroma head + morph targets shipped through transitions3 + explorer a2a tab)
      riffer/chroma_steer.html — the tooling already exists, WORKLOG 2026-06-25):
      steer harmony across the transition window with a time-varying chroma target
      (A's measured tail chroma -> B's head chroma). USE THE TRAINED STEM-CHROMA HEAD
      `latch_sa3_chroma_other_best.pt` (now Mantu/sa3_lora_runs/cu_reward_renders/
      analysis/chroma_heads/ — promote to a weights dir), cosine loss, gain ~1536-2048
      (the proven pitch-steering band); targets from `compute_same_chroma` sidecars
      (Lehto/latents_sa3_stem_chroma, 4907/5400) or computed on the fly (mir-same-chroma,
      pure numpy). NOT the essentia hpcp_ts (wrong recipe = garbage) and NOT the hpcp
      LatCH head. transition_lab v4. Tier-2 (d384 chroma ADAPTER, forward-conditioned):
      same_chroma data mostly exists; adapter training still to do.
- [ ] **Style-specialized adversarial post-training on LUMI-G** (Kim 2026-07-07,
      feasibility confirmed): start from the RELEASED post-trained medium (skips
      distillation), generator updates at ADAPTER scale (DoRA), discriminator = base
      ckpt + fresh conv head, relativistic + contrastive losses per paper eqs 6-11,
      DROP the latent-CLAP loss (not released; single-style trigger prompts lower the
      need) or use decoded LAION-CLAP as a monitor only. Small-data GAN risk mitigated
      by: pretrained both nets + augmentation variants + short run + eval-stack
      collapse watch. Memory ~40GB (fits half an MI250X); compute ~1-few node-days at
      10-20k steps. REAL COST = implementing the APT loop (~days, paper eqs are
      complete). Would give a punchy 8-step no-CFG model in Kim's/goa style — the
      "trained finisher" for our fine-tunes.

- [ ] **Training-free rhythm/pitch preservation for a2a** (Kim 2026-07-07), three tiers:
      (a) FEASIBLE NOW — per-step K-candidate selection in ping-pong sampling, scored in
      LATENT space by LatCH heads (onset_envelope/HPCP predicted from the noisy latent)
      against the SOURCE's envelopes; selection sidesteps the dead-gradient problem AND
      the decode cost; stop after ~50% of denoising (structure locks mid-trajectory);
      MERT stays as the final whole-clip reranker (longform best-of-N harness exists).
      — (a) DONE 07-08 (renoise_hook K-candidate selection in the ping-pong sampler,
      LatCH-scored vs source onset envelope, first 50% of steps, live-verified, WORKLOG.md:1709).
      (b) MERT gradient guidance through SAME-decode — heavy, LUMI-class.
      (c) ACTIVATION PRESERVATION — cache the source pass's activations at the layers
      where rhythm/pitch live, clamp/blend toward them for the first 50% of steps;
      needs the layer×feature map extraction (pending) + TADA-style localization —
      the strongest motivation yet to finish that work.
- [ ] (2026-07-22 triage) a2a activation-preservation tier (c) — layer map exists now
      (docs/layer-feature-map.md); tier (b) MERT-gradient stays LUMI-class.

- [ ] **Pad-fill detection stack** (Kim 2026-07-07, from the a2a ladder droning-pads
      observation): (a) timbral extractor runs w/ `dev_output=True` — reverb returns
      (mean_RT60, probability) CONTINUOUS, not the true/false; + timbral_depth — over
      goa/avp/avp-aug corpora for baselines (W's lane, DM'd) — (a) DONE 07-08 (WORKLOG.md:1711); (b) envelope-fidelity
      meter — SHIPPED 07-08 (eval/envelope_fidelity.py, 4 tests; first calibration:
      fidelity axes track Kim's ear exactly, nl35 onset .97/bands .95 vs nl50
      .93/.84) BUT the pad-fill detector v1 only catches pads-in-SILENCE; Kim's
      pads are LAYERED BEHIND active content -> v2 = per-band sustained-floor
      delta (slow-envelope floor of output vs source, no quiet-zone dependency) (source-vs-output onset+band-RMS correlation,
      excess-sustained-energy = pad-fill signature — Kim's "envelope timings stay
      close to the example", zero new models) — (b) DONE 07-08 (iterated to v3
      floor-to-peak-ratio, ear-calibrated, continuity.journal.md:493); (c) RT60/depth deltas as eval columns
      + best-of-N rerank penalty in longform — W's meter finding 2026-07-07: RT60
      SATURATES at ~1.1s (Loellmann ceiling, 24% of tracks peg; prob collapses with
      it) exactly where pad-fill is strongest -> DEPTH-primary (clean 49-69 spread),
      RT60 secondary/dry-side-only; heavy-tail rerank needs a longer-range estimator
      or the envelope meter carries it; (d) later: LatCH head on RT60/depth
      (energy-family scalar = the steerable kind). NOT a training-loss meter (scope
      law: RF already reconstructs reverb; the failure is generation-time).
- [ ] (2026-07-22 triage) pad-fill eval columns/rerank — re-scope post reverb_bigpicture
      (eval/reverb_bigpicture.md reframed the "reverb" as mono spectral haze).

- [x] **avp r128-adjusted + familiarity runs (chain stages C+D, postponed 2026-07-07)** — DONE 07-07/08 (C 8/8 WORKLOG.md:1574, D 8/8 WORKLOG.md:1713; verdicts: r128adj best / familiarity worst, continuity.journal.md:527):
      C = avp r128 dora-rows fusion, alpha 45 (rsLoRA sqrt-scaling), lr 2e-4, 8ep,
      grad-accum 2 — NB: actually ran to epoch 6/8 before Kim's reprioritization (ckpts in dora128adj_avp_8ep, warm-startable for the last 2 eps via --warm_start_ckpt); D = avp r16 + `--familiarity_beta 1.0` (smoke-tested, gate PASSED,
      implementation ready). Both fully specced in `Misc/run_overnight_20260707.sh`
      (stages C/D). Candidate for **LUMI-G** if Kim's setup lands (MI250X/ROCm — our
      stack should port; venv + CK flash-attn story needs checking there), else the
      next local GPU night.

- [x] **Transitions round 2** (Kim 2026-07-07, first round sounded weak/noisy even — DONE 07-07 (newcap8_transitions_r2 + superseded by transitions3 recipe)
      pre-transition — possibly seeds, possibly the LENGTH effect: 2-min segments get
      the timestep shift pushed toward high noise): arms hof(x20b3ygb ep3-5400) /
      newcap8 / evr1x(ep3-6108) / newstack(ep3-5400), aggr prompt, seeds 1234+42,
      totals 512 AND 1024 frames (xfade = total/4), v1/v2/v3. transition_lab.py is
      parametrized + arms registered; run in the first GPU gap (post-chain ~18:30)
      or CPU when the newstack eval frees it. QUEUED — executes automatically.

- [x] **avp DoRA run WITH the augmentations** (Kim 2026-07-07) — SUPERSEDED 2026-07-22 triage (originals-only arm ran + augs exonerated, continuity.tasks.md:28 + WORKLOG.md:1744; tiered-caption arms settled conditioning, WORKLOG 07-09; residue = the #28/#29/#36/#37/#39 avp arm ruling on Kim's Lane-4 list): tonight's avp runs
      (r16 / r128adj / familiarity) train on the 2393 full-mix original crops only —
      rerun including G's Bungee augmentation variants (pitch ±1/2, tempo ±5/10%,
      ~1035 crops, parent-ratio downbeats, same trigger captions) once they're
      confirmed landed in `latents_avp` (as of 07-07 morning the dir holds originals
      only — check G's encode delta status first). CORRECTED 2026-07-08 (G's manifest
      re-read): latents_avp ALREADY contains the augs — 288 originals + 2105 aug crops
      (tempo ±5/±10, pitch ±1/±2). Every avp DoRA so far trained 88% on stretched/shifted
      audio. The MISSING arm is ORIGINALS-ONLY (288 crops) — train it as the clean
      comparison; prime suspect for Kim's 'glitchy/disjointed' avp verdict (adapter may
      have learned stretch/shift artifact texture as the house sound).
      PLUS (Kim 2026-07-08, weird-prompt finding): current avp prompts are ONE
      trigger word in two spellings — zero compositional handles; the rerun should
      sample trigger + descriptive tiers (caption-sampler infra) so the adapter
      learns to compose with English prompts.

- [ ] **Outro/empty-space cheating in onset-density training** (Kim 2026-07-07, gain_knee
      audition): the model can hit a low density request by rendering an outro/track-ending
      with empty space — the scalar target counts silence. Fixes to try: (a) compute the
      training scalar over ACTIVE frames only (RMS-gated onset density) — (a) DONE 07-08
      (window_onset_density_active, 109/109 tests, continuity.journal.md:501), (b) downweight or
      exclude end-of-track crops (high `relative_position_end` + low-RMS tail), (c) eval
      side: measure density over the active region only so the cheat stops scoring.
- [ ] (2026-07-22 triage) retrain density control on active-frame scalar — #53 rider.
- [x] **Re-render the density-control grid at calibrated FiLM gains** (~1.5-2.75, or the — DONE 07-07 (newcap8_density_control_g175, FiLM verified steering)
      ridge schedule): the 2026-07-07 432-clip grid used gain 6 (steered_longform default),
      but the gain_knee audition puts the style-flip knee at ~1.4-1.5 for the June adapter —
      if the new grid sounds style-flipped rather than density-modulated, gain was too hot.
      Verify where FusionCC's knee sits (it may differ) before re-rendering.

- [x] **Rank-16 Fusion comparison rerun with the improved dataset stack** (Kim 2026-07-07, — DONE 07-07 (dora16_goa_newstack_8ep + A-vs-HoF board)
      from the dora_results audition): same recipe as `sa3-goa-dora-47s-b4-cont/x20b3ygb`
      (the Hall-of-Fame run) but with everything we've built since: tiered captions
      (T1 era-fronted / T2 Granite / T3 raw via `--caption-sidecar`), curated tag vocab,
      `--track_type_prob 0.5`, multi-source weighting. Direct A/B against the HoF ckpt.
- [x] **Big-rank damping experiment** — DONE/ANSWERED (rsLoRA-α arm ran and won: r128adj, WORKLOG.md:1574; root cause = linear s=α/r damping, docs/dora-alpha-audit-2026-07-12.md + continuity.journal.md:692; Kim's "w1.5 better" = manual un-damping, WORKLOG.md:1774) (Kim's rank-128 "pawn my head" hypothesis: r64 ≤ r16,
      r128 degrades in-dataset goa into diffuse/impact-less while out-of-dataset prompts
      survive): try (a) LR scaled by rank — rsLoRA-style `alpha ∝ sqrt(rank)` or lr×~0.35
      for r128-vs-r16, (b) grad accumulation, (c) EMA over adapter weights (our proven
      drift fix from the LatCH ES work). Context: `docs/checkpoint-hall-of-fame.md`.
- [x] **Novelty-gated update weighting** — DONE 07-08 as `familiarity_beta`, NEGATIVE result (worst arm by meter + Kim's ear: WORKLOG.md:1713, continuity.journal.md:531) (Kim's idea, same audition): down-weight updates
      for material the model already renders well, let "remote areas grow" — cheapest
      testable form is per-crop focal-style loss reweighting by an EMA of that crop's own
      RF loss (low loss = familiar = down-weight). Folded into
      `docs/research-brief-relevance-routed-dora.md` (UPDATE 2026-07-07) as the data-axis
      sibling of the two existing axes.
- [x] **Export the *control-adapted* DiT to ONNX** — DONE (2026-06-27). Adapters
      (`to_k`/`to_v`/`to_out` + conditioner) fold into the DiT graph as forward inputs:
      `onnx/export_dit_control_onnx.py` + `onnx/dit_control_onnx_infer.py`,
      fp16 fixed (PE moved host-side, 3.1 GB), GPU MIGraphX cos=1.0/100%-on-EP. The all-CPU
      eval path is now canonical: `sa3_control_onnx.py` (shared gen-core) +
      `control_eval_server.py` + `submit_control_job.py` (file-drop queue
      `SAO/control_eval_queue`) — 8-step grid ≈5.4 min CPU vs ~42 min GPU-with-compile, so
      CPU is the default eval path, not a fallback. (MASTER §5; move to WORKLOG.)
- [x] **SA3 LoRA retrain** on the new `latents_sa3` (5400 T=4096 beat-aligned crops). Caches — DONE (superseded by the dora sweep + newstack runs)
      warm. rank 16 dora-rows bf16 `--compile`, `MIOPEN_FIND_MODE=2`. Decide step budget +
      `--demo_every ≥1500`. Watch that step time drops to ~2-3 s now T is fixed.
- [x] **Validate the CK flash-attn build** — SUPERSEDED (CK FA rebuilt + precision-validated in the PROD venv 07-05, ghost-note.tasks.md:52; prod stack now ships CK, MASTER.md:453; archaeology called moot, the-finn.tasks.md:203) (`sa3-rocm7.13-test`, scripts 02-05): numerical
      correctness + benchmark vs Triton-AMD backend. BUILT but unproven; on the experimental
      7.14 stack. If it's correct AND faster, plan a path to the production stack.
- [x] **`relative_position_ts` LatCH head** — INVALIDATED (probe R²=0.03 local / 0.08 pooled, "don't ship the position slider": docs/latch.md:95, WORKLOG.md:1168) — train a head on the new structural-position
      ramp; test as an inference knob (0=intro, 0.5=mid, 1=outro). Novel control.

## LatCH

- [x] Promote the whole-track **per-stem heads** — SUPERSEDED (SAO-latent-era premise; SAME probe re-ranked the menu, rms_other/onset_other now weak 0.14-0.24, docs/latch.md:87-94; chroma_other per-stem head shipped via chroma-morph) (onset_envelope_drums etc.) to full-data
      production runs — smoke-validated, not shipped. `rms_other`/`onset_envelope_other`
      looked strongest; vocals weakest (sparse in Goa).
- [ ] Re-test LatCH LR knee at **lr 3e-3** (1e-3 won at every batch in the 10ep/50% sweep —
      the knee may not have been reached).
- [x] SA3 LatCH **Phase 2** — SUPERSEDED (renoise-hook ping-pong LatCH guidance shipped, WORKLOG.md:1709; heads EMA-retrained, WORKLOG.md:1782; residual scope folds into the #53 LatCH+FiLM LUMI campaign, plan-2026-07-22-worklist.md Lane 2.5): ping-pong guidance for post-trained small/medium, SAME-L/medium
      heads, σ-relative-window transfer. (SA3 memory `latch-sa3-phase1.md`.)

## SA3 training (beyond LoRA)

- [ ] Decide if short-form (<T=1024) inference quality from the T=4096-only LoRA is adequate;
      if not, a **multi-length** Phase-2 LoRA with quantised T buckets (`training-findings.md`).
- [x] Per-epoch **prompt re-randomisation** — SUPERSEDED (caption-sidecar tier sampler resamples captions at dataloader time via custom_metadata_fn, WORKLOG.md:1471) — current SA3 crop prompts bake one §3.5 sample
      into the `.json` at encode time; for training variety, regenerate at dataloader time.
- [ ] Recover the **579 dropped sources** (<380 s or no downbeats) if short-form matters —
      currently excluded from `latents_sa3`.

## Infra / docs

- [ ] Confirm CLAUDE.md **`@import`** of an absolute cross-tree path actually inlines in a
      fresh session (fallback instruction is in place regardless).
- [x] mir + SAT + SA3 have **uncommitted working-tree changes** — SUPERSEDED (that session's changes committed+pushed in the 07-10 sweep, WORKLOG.md:1766; TODAY's uncommitted files are tracked in docs/open-threads.md) from this session's scripts
      (timeseries, encoders, train_latch/train_lora flags). Decide what to commit where.
- [x] Push branches that are local-only — DONE 07-10 (all 4 repos pushed to the private remotes, WORKLOG.md:1766) (`mir/whole-track-timeseries`, etc.) if you want
      off-machine backup.

- **LUMI: FULL FINETUNE of SA3-medium on Kim's corpus** (Kim 2026-07-09, priority when
  LUMI online): "for out-of-knowledge styles that's the only way to get the information
  in" (his image-world experience; the avp adapter arms' mush supports it — adapter
  capacity + frozen text pathway can't absorb a genuinely OOD style). Design notes:
  MI250X fits 1.4B full-FT easily; use the FIXED caption stack (Flamingo tiers + bpm
  disambiguation), per-alias data splits (Summamutikka goa-coherent vs Aavepyörä
  eclectic), low-LR + early ckpt ladder (the phase-window lesson transfers), and the
  underfit one-style-per-dataset doctrine. W owns LUMI scaffolding — encode when specing.
  — RAN as #52/#54 + fullft 10-arm campaign (ckpts on $SCRATCH, evals rendering 07-22);
  bullet superseded, see plan-2026-07-22-worklist.md.

- **avp board render convention (Kim 2026-07-09):** every future avp board render does
  BOTH DoRA strength 1.0 AND 0.6 — `model.set_lora_strength(0.6)` is a live knob (no
  reload; LoRA is unmerged parametrization), so it's ~free. At reduced strength the
  collapsed attractor pulls less and the prompt/base-prior cooperate = direct test of
  the conditioning-collapse cure. Filename tag __st10 / __st06. Applies to the
  caption-tier arm renders + all subsequent boards. Sidecar:
  Mantu/sa3_lora_runs/_conventions/avp_board_render.json.
  → relocate to MASTER conventions/§5 (not a completable task) — flagged 2026-07-22 triage.

- **arm H (r256 DoRA) DOES NOT FIT on 16GB — LUMI-only (2026-07-09).** Tried FusionOpt
  batch4/2/1 (all OOM — Shampoo preconditioners ~1536x1536 per layer) and AdamW batch2
  (wedged at startup, 0 steps, held VRAM). Max local adapter rank = 128 (arm G ran fine).
  r256+ is a LUMI experiment. Do NOT re-attempt locally.
  → relocate to MASTER conventions/§5 (not a completable task) — flagged 2026-07-22 triage.

- **build_dms.py should redact at build time, not just at publish (W finding 2026-07-13,
  pool):** the on-disk `site/dm/` pages are RAW — path/secret redaction happens only in
  `mirror_dialogue.py`'s `redact()` at rsync time. Safe as long as DMs are published
  exclusively via mirror_dialogue.py (never wholesale-rsync site/dm/), but one wrong
  transfer command away from a leak. Fix: move/duplicate the redact pass into
  build_dms.py so the built artifact is already clean.

- **No persistent matrix clip-shipper (W root-cause 2026-07-14, pool):** the Mantu->staging->
  server sync loop for model_matrix clips was harness-reaped (same lesson as the eval servers)
  — Kim saw a "board missing clips" gap because renders landed but nothing shipped them. W
  ships manually on render-completion for now; the proper fix is a setsid-daemonized shipper
  (or a systemd user timer like comment-merge.timer). Until then: whoever finishes a matrix
  render pings W for the ship.

- [POOL, G] (2026-07-15, C's gate-(b) follow-ups) Width T-sweep: stereo-width LEVEL vs context
  length (T=512/1024/2048/4096, few seeds, base model) — if width narrows monotonically with T
  that's a clean law and width graduates to a standard metric. Card-gap filler. Companion:
  2-3 more seeds on the 4096 single-shot/windowed pair to firm the n=1 level gap.
  Tooling ready: eval/width_metric.py (merges width stats into run_meta.width_metrics;
  same meter as the corpus sidecars, so numbers are band-comparable).
- [x] [POOL, W→C] (2026-07-15; DONE C 2026-07-22) model.py generate() silent 120s sample_size
  clamp — after it also cost the LUMI native campaign 103 renders: sample_size default is now
  None = auto-GROW the window to fit seconds_total+pad (loud [generate] notice); explicit
  sample_size = hard cap with the existing warning (old behavior). 4-case mock test passed;
  W to review (was his POOL item). NB our render workers pass sample_size explicitly ->
  they run in cap mode and print the clamp warning when pad exceeds the cap: expected, benign.

- [POOL, C] (2026-07-22, StemGen 2312.08723 export; checked against train.py:675) Multi-source
  CFG for sa3_control: training currently drops ONLY the control signal (per-item p=0.1,
  ctrl.masked_fill) while text is never dropped in the control loop (cfg_dropout_prob=0.0) —
  so states {uncond, text-only} are never seen with the adapter active, and per-source guidance
  scales (λ_text, λ_ctrl) can't be calibrated jointly. Cheap change: add --text-dropout 0.1
  (independent draw) + a 3-pass compositional sampler at eval (StemGen ablation: both λ=3.0
  best, FAD 4.30→3.17 unguided→guided; guiding on the NON-text source mattered as much).
  Candidate arm for the next control training round (#53 rider?), not a standalone campaign.
- [x] [POOL, C] (2026-07-16, parlance/Discord + Kim) Stereo-phase reverb test — DONE 07-16 (RESULT + RESULT-2 below: hypothesis refuted, mechanism = mono spectral haze; tools eval/{stereo_phase_meter,reverb_table_measure,decoder_haze_probe}.py shipped; successor = #3 stereo-loss sweep, tracked OPEN in docs/open-threads.md): chase the "unfitting
  reverb / short bathroom-impulse" artifact Kim + parlance both hear on DoRA outputs. Hypothesis:
  inter-channel phase / stereo image is a low-energy, RF-loss-invisible component that fine-tuning
  perturbs (Kim's hunch: stereo info in SAME latents drifts under FT; rhymes with the known T=4096
  single-shot stereo-COLLAPSE, MASTER §5). NB parlance's exact PSD-VAE mechanism does NOT map —
  SAME is waveform-domain, not PSD — but the fragile-inter-channel-phase lesson does. Test: render
  a reverb-exhibiting DoRA vs medium-base, matched prompt+seed, and compare inter-channel coherence
  + mid/side energy ratio + stereo-width-over-time + spectral comb-notch signature (the "room
  impulse" = early-reflection comb). If DoRA separates from base on L/R coherence or combing, the
  artifact is localized to stereo-phase degradation and becomes a regularization target. Depends on
  F's Essentia Panning/stereo-width meter (the stereo axis I prioritized first) + a coherence meter;
  companion to [POOL,G] width T-sweep + eval/width_metric.py (band-comparable numbers). Second lens
  worth noting in writeup: SAME's near-deterministic decoder averages an FT-perturbed ambiguous
  latent -> smear (parlance's "diffusion-decoder-or-bust" argument), a compatible mechanism.

  RESULT (2026-07-16, ultracode test, meter=eval/stereo_phase_meter.py): HYPOTHESIS REFUTED
  IN STATED DIRECTION. True DoRA-vs-base A/B (same prompt+seed+base, adapter-only), 189 clips,
  7 prompts x 3 seeds x 8 epochs. Every stereo axis moves OPPOSITE to the phase-decorrelation/comb
  prediction: L/R coherence RISES (+0.13), side energy DROPS (-0.06), width NARROWS (-0.02), comb
  detector flat. DoRA does not decorrelate stereo -> it COLLAPSES the image toward MONO/center
  (6/7 prompts). Effect strongest EARLY (ep7-31), washes out by ep47-63 (backwards from overtrain
  prediction). ONE real exception: kimlong shows genuine L/R decorrelation (coh 0.33->0.09) matching
  Kim's ear ("ringing bands after ep31") -> prompt-specific, not general. Mechanism (latent-perturb
  vs decoder-averaging) NOT isolated (only final audio on disk). Fix REVERSED: an L/R-coherence
  regularizer is WRONG (coherence already rises); the warranted objective is stereo-WIDTH/side-energy
  PRESERVATION + prompt-conditional handling for kimlong-type. Next: (a) cheap per-prompt + mono-domain
  reverb/decay meter (the "reverb" may BE width-collapse, or a mono smear the L/R meter can't see);
  (b) optional GPU latent-isolation render to settle decoder-vs-sampler.

- [POOL, C] (2026-07-16, parlance/Discord Muon intel) High-LR Muon schedule for DoRA: parlance
  (g-diffuser) reports Muon+EDM2-forced-weight-norm unlocks stable LR up to 0.5 with 1/step decay
  (early high-LR steps hyper-efficient -> ~50k-step convergence). We can't retrofit forced weight-norm
  onto frozen SA3, BUT DoRA IS weight-norm on the adapter (magnitude x normalized direction), and
  FusionOpt already routes magnitudes->AdamW / lora_A,B directions->Muon(NorMuon) (confirmed in the
  LUMI smoke log param groups). So his regime is unusually transferable to our DoRA path. TEST: sweep
  FusionOpt Muon-group LR upward (toward 0.5, carefully) with 1/step decay on a DoRA r128 run; measure
  (a) stability, (b) convergence speed vs lr1e-4, (c) whether it changes the EARLY-epoch reverb/stereo-
  collapse (which is an early-optimization-phase transient per the 2026-07-16 reverb test). Candidate:
  a local r128 bracket (fits on 16GB) or an extra LUMI arm alongside task #52. Caveat: 0.5 is a
  from-scratch number; fine-tuning a pretrained model, too-hot can erase learned structure -> sweep up.

  RESULT-2 (2026-07-16, mechanism fully localized): the DoRA "reverb" = a MONO SPECTRAL HAZE
  (flatness 2-3x real goa), NOT stereo-phase/tail (round1), NOT sampler (48 vs 24 steps unchanged:
  Δflat~0, Δcoh~0 over 275 matched pairs), NOT the decoder (dry real-goa encode->decode roundtrips
  clean at ~9e-5, ~200x below gen level; decoder doesn't collapse stereo either). By elimination +
  theory it's the DiT LATENT TARGET = conditional-mean generation: model renders E[latent|prompt],
  keeping predictable high-energy structure and dropping high-entropy detail -> spectral fine-structure
  becomes haze, stereo residual collapses (two faces of one effect). Base has it (inherent); DoRA
  modulates (higher strength -> more tonal -> less haze; but collapses stereo more, lacking the
  data x capacity the base used to hold stereo). ONLY lever = training objective/conditioning:
  #3 side-channel loss (built, validated) + an analogous spectral-detail loss + parlance's mid/side
  conditioning. Tools: eval/{stereo_phase_meter,reverb_table_measure,decoder_haze_probe}.py;
  data reverb_{matrix,goa,st48}.jsonl; write-up eval/reverb_bigpicture.md. #3 sweep = the payoff run.

  CORRECTION (2026-07-17, parlance via Kim): his LR-0.5 / 1-per-step-decay numbers are
  PRETRAINING-FROM-SCRATCH ONLY -- he has NEVER fine-tuned an existing model, so zero transfer
  evidence to our DoRA regime. From-scratch tolerates hot LR (no learned prior to protect);
  fine-tuning must stay gentle or it overwrites the base (catastrophic forgetting) -- and DOUBLY
  so for us: the reverb/stereo finding shows DoRA already tramples the base's fragile structure at
  lr1e-4, so a HIGHER LR worsens exactly the collapse we're trying to fix. => "toward 0.5" is OFF.
  DOWNGRADED to: (a) a gentle LR sweep 1e-4->3e-4 to test if Muon+DoRA-normalization tolerates
  somewhat hotter than naive AdamW; (b) the 1/step decay idea tested separately at fine-tuning LRs.
  Both low-priority behind #3 stereo-loss + longctx (the experiments that actually target our problem).
