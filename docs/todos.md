# TODOs — open work across the pipeline

Keep this honest and current. Move done items to `WORKLOG.md`. Newest concerns near top.

## Now / next

- [x] **Chroma-morph transitions** (Kim 2026-07-07; CORRECTED after Kim surfaced — DONE 07-07/08 (chroma head + morph targets shipped through transitions3 + explorer a2a tab)
      riffer/chroma_steer.html — the tooling already exists, WORKLOG 2026-06-25):
      steer harmony across the transition window with a time-varying chroma target
      (A's measured tail chroma -> B's head chroma). USE THE TRAINED STEM-CHROMA HEAD
      `latch_sa3_chroma_other_best.pt` (now Mantu1/sa3_lora_runs/cu_reward_renders/
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
      (b) MERT gradient guidance through SAME-decode — heavy, LUMI-class.
      (c) ACTIVATION PRESERVATION — cache the source pass's activations at the layers
      where rhythm/pitch live, clamp/blend toward them for the first 50% of steps;
      needs the layer×feature map extraction (pending) + TADA-style localization —
      the strongest motivation yet to finish that work.

- [ ] **Pad-fill detection stack** (Kim 2026-07-07, from the a2a ladder droning-pads
      observation): (a) timbral extractor runs w/ `dev_output=True` — reverb returns
      (mean_RT60, probability) CONTINUOUS, not the true/false; + timbral_depth — over
      goa/avp/avp-aug corpora for baselines (W's lane, DM'd); (b) envelope-fidelity
      meter — SHIPPED 07-08 (eval/envelope_fidelity.py, 4 tests; first calibration:
      fidelity axes track Kim's ear exactly, nl35 onset .97/bands .95 vs nl50
      .93/.84) BUT the pad-fill detector v1 only catches pads-in-SILENCE; Kim's
      pads are LAYERED BEHIND active content -> v2 = per-band sustained-floor
      delta (slow-envelope floor of output vs source, no quiet-zone dependency) (source-vs-output onset+band-RMS correlation,
      excess-sustained-energy = pad-fill signature — Kim's "envelope timings stay
      close to the example", zero new models); (c) RT60/depth deltas as eval columns
      + best-of-N rerank penalty in longform — W's meter finding 2026-07-07: RT60
      SATURATES at ~1.1s (Loellmann ceiling, 24% of tracks peg; prob collapses with
      it) exactly where pad-fill is strongest -> DEPTH-primary (clean 49-69 spread),
      RT60 secondary/dry-side-only; heavy-tail rerank needs a longer-range estimator
      or the envelope meter carries it; (d) later: LatCH head on RT60/depth
      (energy-family scalar = the steerable kind). NOT a training-loss meter (scope
      law: RF already reconstructs reverb; the failure is generation-time).

- [ ] **avp r128-adjusted + familiarity runs (chain stages C+D, postponed 2026-07-07)**:
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

- [ ] **avp DoRA run WITH the augmentations** (Kim 2026-07-07): tonight's avp runs
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
      training scalar over ACTIVE frames only (RMS-gated onset density), (b) downweight or
      exclude end-of-track crops (high `relative_position_end` + low-RMS tail), (c) eval
      side: measure density over the active region only so the cheat stops scoring.
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
- [ ] **Big-rank damping experiment** (Kim's rank-128 "pawn my head" hypothesis: r64 ≤ r16,
      r128 degrades in-dataset goa into diffuse/impact-less while out-of-dataset prompts
      survive): try (a) LR scaled by rank — rsLoRA-style `alpha ∝ sqrt(rank)` or lr×~0.35
      for r128-vs-r16, (b) grad accumulation, (c) EMA over adapter weights (our proven
      drift fix from the LatCH ES work). Context: `docs/checkpoint-hall-of-fame.md`.
- [ ] **Novelty-gated update weighting** (Kim's idea, same audition): down-weight updates
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
- [ ] **Validate the CK flash-attn build** (`sa3-rocm7.13-test`, scripts 02-05): numerical
      correctness + benchmark vs Triton-AMD backend. BUILT but unproven; on the experimental
      7.14 stack. If it's correct AND faster, plan a path to the production stack.
- [ ] **`relative_position_ts` LatCH head** — train a head on the new structural-position
      ramp; test as an inference knob (0=intro, 0.5=mid, 1=outro). Novel control.

## LatCH

- [ ] Promote the whole-track **per-stem heads** (onset_envelope_drums etc.) to full-data
      production runs — smoke-validated, not shipped. `rms_other`/`onset_envelope_other`
      looked strongest; vocals weakest (sparse in Goa).
- [ ] Re-test LatCH LR knee at **lr 3e-3** (1e-3 won at every batch in the 10ep/50% sweep —
      the knee may not have been reached).
- [ ] SA3 LatCH **Phase 2**: ping-pong guidance for post-trained small/medium, SAME-L/medium
      heads, σ-relative-window transfer. (SA3 memory `latch-sa3-phase1.md`.)

## SA3 training (beyond LoRA)

- [ ] Decide if short-form (<T=1024) inference quality from the T=4096-only LoRA is adequate;
      if not, a **multi-length** Phase-2 LoRA with quantised T buckets (`training-findings.md`).
- [ ] Per-epoch **prompt re-randomisation** — current SA3 crop prompts bake one §3.5 sample
      into the `.json` at encode time; for training variety, regenerate at dataloader time.
- [ ] Recover the **579 dropped sources** (<380 s or no downbeats) if short-form matters —
      currently excluded from `latents_sa3`.

## Infra / docs

- [ ] Confirm CLAUDE.md **`@import`** of an absolute cross-tree path actually inlines in a
      fresh session (fallback instruction is in place regardless).
- [ ] mir + SAT + SA3 have **uncommitted working-tree changes** from this session's scripts
      (timeseries, encoders, train_latch/train_lora flags). Decide what to commit where.
- [ ] Push branches that are local-only (`mir/whole-track-timeseries`, etc.) if you want
      off-machine backup.
