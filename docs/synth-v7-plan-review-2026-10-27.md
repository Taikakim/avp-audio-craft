# Review of the "Mixture-to-Patch Synth Inversion (V7)" implementation plan (2026-10-27)

Reviewer: CONTINUITY, at Kim's request. Plan under review: `~/.gemini/antigravity/brain/62fc5213-.../implementation_plan.md`
(written by Antigravity; not in this repo). Owner of the synth-inversion line: WINTERMUTE (OWNERSHIP.md, claimed 2026-10-07 on Kim's word).
What I read: the whole plan; the Point-and-Play paper's arXiv abstract page and HTML text (2610.19445v1, via fetch, not the PDF, so
tables are as the fetch tool reported them); `blog/2026-10-19-synth-jepa-from-day-one.md` sections 1-2, 5-6; OWNERSHIP.md; the repo for
the files the plan names. NOT read: `docs/optimiser-briefing-2026-10-26.md`, `models_v6.py` internals, the H-series entries in full,
the Point-and-Play code.

## Verdict
Worth trying, but not as written. The plan copies the paper correctly; its problems are the premise, the evaluation and the missing cheap
first test. Do not start the 7-hour build until the points marked MUST are settled.

## What is right
- The CGSP description matches the paper: sigmoid gate per token, gated mean and standard deviation, z = norm(norm(q) + R[mu; sigma]) with a
  zero-initialised last layer, 512-d code, HTSAT-base with LoRA rank 8, four losses weighted 1/1/1/0.25, tau 0.1, AdamW, batch 16, 18k steps,
  500 warmup steps. The zero-init unit test (z equals norm(q) at step 0) is the right one.
- The code it extends exists: `NoteConditionedFlow` is in `models_v6.py:24`, `FlowMatchingResMLPV4` in `models_v4.py:190`, in
  `stable-audio-tools/scripts/synth_inversion/` (commits go to the stable-audio-tools repo, not the SAO root).
- Scoring against the existing 24 real stems keeps continuity with V4-V6.

## MUST fix before building
1. **The two sides of the comparison are scored against different references.** Phrase MSS and Mel-SSIM compare the rendered patch with the
   input audio. For the Demucs baseline the reference is the separated stem; for the full-mix conditions it would be the mix, which contains
   the drums. The numbers are not comparable. Pick one common reference (the same separated stem for all three, or blinded listening on a
   fixed pairing) and write it into the plan.
2. **Pitch invariance is promised and not testable as written.** The paper's own probe leaves pitch in the code: MIDI-pitch R^2 0.263
   on extracted codes against 0.783 on raw CLAP embeddings, i.e. suppressed, not removed, and the paper does not test invariance directly.
   The plan's check ("cosine distance < 0.05 proves total pitch invariance") has an arbitrary threshold and no baseline. Replace it with the
   paper's ridge pitch probe, plus the cosine between same-patch/different-octave codes set against the cosine between different-patch
   codes. Also: Stage 2 still takes the target MIDI note as input, so invariance does not remove the need for a note.
3. **The success rule is "inspect whether V7 beats V6".** With 24 stems and a gap we already measured as small (the October 5 and October 7
   models: 7.31 against 7.84, 13 wins against 7), this needs a pre-registered test: paired per-stem comparison, a margin, seeds or a bootstrap,
   and a kill condition. Register it in `EXPERIMENTS.md` (H series) with a purpose line, as CLAUDE.md requires.
4. **The "estimated empirical probabilities" must go.** The 45-55% / 80-85% / 88-92% figures have no source: the paper reports no such
   probabilities, no electronic music and no failure cases (it lists real-world generalisation as a limitation). Delete them or label them
   as the planner's guesses.
5. **Datasets are unverified.** Slakh2100, MoisesDB and the named drum multitracks ("Acid Alien", "Black Moon", "Goddess Guerrilla", "Gate
   G3") appear nowhere in `docs/data.md`, ARCHITECTURE.md, MASTER.md or EXPERIMENTS.md. Say where they are on disk (or that they are not),
   and check licences before any of it is used for training.

## SHOULD fix
6. **Do the cheap test first (Kim's lightweight-tests-first rule).** The plan assumes source separation is the bottleneck. Our own record
   points elsewhere: the blog found a better synthetic fit did not make real stems sound closer and read it as a synthetic-to-real gap.
   Test the premise before training anything: mix Surge renders of known patches with real drum/backing stems, then run V6 on (a) the clean
   render, (b) the Demucs-separated mix, and (c) the mix directly, and score patch-parameter error and retrieval against the known patch. This
   separates separation damage from domain gap with ground truth, which the real-stem benchmark cannot give. Add held-out synthetic mixtures
   with known patches to the evaluation in any case.
7. **A cheaper first experiment exists.** Our V6 already has a temporal attentive-statistics-pooling encoder (`temporal_asp`), which is the same
   mean-and-standard-deviation pooling that CGSP adds a cue gate to. Try a cue-conditioned gate on that encoder with the mixtures, before
   bringing in CLAP and a LoRA.
8. **Keep the embedding space we already have.** The paper aligns to a frozen CLAP embedding of the isolated stem; the plan never says what the
   alignment target t is. Our Synth-JEPA audio embedding (512-d, 79% audio-to-patch retrieval) already exists. Train the cue-gated extractor
   toward the JEPA embedding of the clean Surge render, so Stage 2 and the retrieval checks stay valid, instead of building a second space and
   retraining Stage 2 on it.
9. **Check what already exists before writing it.** The paper links code and demos (github.com/User-tian/Point-and-Play); the plan writes
   the extractor from scratch. Check what the repository offers and its licence first.
10. **Optimizer line is inconsistent.** Phase 2 says AdamW with `--mod-state-dtype fp32`; that flag belongs to ModularOptimizer, not to
    plain AdamW, and Phase 3 uses ModularOptimizer with Schedule-Free. State which optimizer each stage actually uses. For a rank-8 LoRA
    keep the adapter weights in fp32 (small steps are rounded away in bf16).
11. **Time estimates are guesses.** 2.5-3.0 hours for 18k steps of HTSAT-base at batch 16 on this card is not backed by a timing; the V6
    arms (small MLPs) took 1.7-2.0 hours for 12k steps. Run a 200-step timing test, including whether the audio tower runs on ROCm with the
    attention kernels it needs.
12. **Select-by-cue cases.** The paper lists as a limitation picking one instrument when several of the same category play together. Acid
    tracks often have two or three synth parts; say how the audio cue is chosen for each of the 24 tracks and what happens when the intro has
    no solo synth.

## Housekeeping
- Point-and-Play (2610.19445) is not in `papers/knowledge.md` or `papers/`; per the papers protocol it needs a sidecar and a row.
- The plan lives only in Antigravity's directory; copy it into `docs/superpowers/specs/` once revised so it is not lost.
- Route the decision to WINTERMUTE; Kim to approve the scope.
