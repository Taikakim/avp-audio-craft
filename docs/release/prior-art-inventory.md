# Prior-art inventory: what to disclose with the first release

Owner: THE-FINN (created 2026-11-02). Purpose: a checklist for a dated, public methods write-up published alongside the
release. **Not legal advice, and novelty is NOT established for these rows.** Only the first novelty check
(`docs/research-brief-2026-07-03-novelty-check.md`) has searched the literature, and it downgraded our claims. That is
fine for the purpose: a disclosure blocks later patents whether or not we invented the idea first. It does change how we
word things, so credit the ancestor and say what is ours.

**To block a claim, each entry must let a skilled reader reproduce the method, and should state it broadly:** any rectified-flow
audio model, any differentiable feature head, any instrument. Pointers below were checked to exist; their contents were
not re-audited.

Readiness: **A** written up with evidence, needs rewriting for outsiders. **B** results exist, method needs writing out.
**C** provisional, wait for a check.

## Steering and guidance (the core)

| # | Method | What is ours | Builds on | Evidence and pointer | Ready |
|---|---|---|---|---|---|
| 1 | LatCH feature guidance on a rectified-flow music model at full scale | Port to SAME-L; operating gain ladder; the DiT forward stays fp16 with only the head in fp32 and autograd, so it runs at about base speed | LatCH paper 2603.04366, TFG | MASTER section 5, `stable-audio-tools/LATCH_RESULTS.txt` | A |
| 2 | Why guidance is back-loaded, and the fixes: flat step schedule, latent-std anchor per sigma | Diagnosis (first 20% of steps get about 0.2% of budget); `guide_schedule`, `guide_anchor` | TFG step weight | MASTER section 5, EXPERIMENTS E5 | A |
| 3 | Guiding with a measured per-frame curve (`target_raw`), with phase-locked transfer shown by an antiphase control | The target pathway and the antiphase test; arrangement-level structure transfers, note-level does not | Pons et al. | MASTER section 5 | A |
| 4 | Forward adapter plus gradient guidance together, and the time-varying hand-off: FiLM early, crossfade into LatCH, exponential fade to unguided | The combination and the schedule, which removes the audible switch-off | FiLM, LatCH | EXPERIMENTS E7/E8, E18 | A |
| 5 | Chroma steering in the codec's 3-band space, tested for transposition equivariance | Head recipe (E13); transposition probe as an evaluation method; the HPCP reference-bin trap | SAME chroma | EXPERIMENTS E13, E13b, E21; MASTER section 5 | A |
| 6 | Root-locked chroma: steer a chord SHAPE in whatever key the render is in, via a soft-min over the 12 target transpositions | **Strongest candidate here,** needs a novelty look | Transposition-invariant losses generally | EXPERIMENTS E22, `control/sa3_control/chroma_losses.py` | B |
| 7 | Sharpened or exaggerated chroma targets | Trades overall match for strongest-note landing | E13 | EXPERIMENTS E13x | C, measured only |
| 8 | Evaluating control with two screens: dead and disintegrating | Baseline-relative gate; effect size against a reference control, since a head rendering buzz still moves the feature meter | | MASTER section 4, `docs/superpowers/specs/2026-07-20-control-head-disintegration-gate.md` | A |
| 9 | Meter-in-the-gradient and when it helps | **Mechanism is ControlNet++ (prior art).** Ours is only the boundary condition: helps where the base loss is blind, hurts where it is redundant, with a harm mechanism | ControlNet++ 2404.07987, InnerControl 2507.02321 | MASTER section 4, novelty brief | A |
| 10 | Melody-subspace loss in fine-tuning | A training loss targeting melody; first listen favoured it, at some cost to kick and bass | | `docs/training-findings.md` 2026-09-27, W39 synopsis | B |

## The workspace (what the GUI embodies)

| # | Method | What is ours | Pointer | Ready |
|---|---|---|---|---|
| 11 | Multi-lane latent arrangement: each lane encoded and steered through its own chain (LatCH, FiLM, LoRA, time-stretch), overlaps inpainted, lanes mixed in latent space, master chain, one decode | The whole workflow. **Most product-shaped, so most worth disclosing in detail** | `docs/superpowers/specs/2026-09-15-latent-forge-design.md`, `latent-forge/README.md` | A |
| 12 | Long-form generation with a timed prompt arc and steering | Arc grammar, steered longform | `control/sa3_control/steered_longform.py`, WORKLOG 2026-06-21 | B |
| 13 | Inversion-based text-prompted separation with a faithfulness controller (eta), on a rectified-flow music model | FlowEdit is AUDEDIT's; separation as the use, and the RF-Solver eta controller, are ours | MASTER section 4 | A |
| 14 | Beat-matched generative DJ transitions: staged per-stem hand-over, placement timeline, masked inpainting, latent-std control | The pipeline and audits | EXPERIMENTS F7, `docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md` | B |
| 15 | Control adapters baked into an exported graph; gradient guidance over a forward-only exported model with autograd on the head alone | Deployment architecture for low-VRAM and CPU | MASTER section 5, `onnx/` | A |

## Stability and training

| # | Method | What is ours | Pointer | Ready |
|---|---|---|---|---|
| 16 | Clamping generated latent std before decode to prevent decoder discontinuities | Cause and fix. **Found independently by ANTIGRAVITY and GHOST-NOTE, about 99% fewer bad samples on the checked clip.** Credit both | W39 synopsis, WORKLOG 2026-09 | B |
| 17 | Optimizer routing per parameter type for orthogonalised updates on 2-D audio DiTs | **Already public** in the Muon guide (2026-10-27), with negative results; ModularOptimizer itself is ANTIGRAVITY's | `blog/2026-10-21-muon-survival-guide-DRAFT.md`, live on the site | Done, add a dated archive |
| 18 | FusionOpt | **Already public,** CC0, `fusion-optimiser` | repo | Done |

## Synth inversion (ANTIGRAVITY and KUANG lines, W for earlier versions)

| # | Method | What is ours | Pointer | Ready |
|---|---|---|---|---|
| 19 | Mixture to synth patch plus automation: cue-driven extraction, static patch with dynamic 10 Hz lanes, export of preset and MIDI CC | A strong product idea, so **disclose the idea early even if the numbers wait** | `docs/superpowers/specs/2026-10-28-synth-inversion-v8-dynamic-tse-spec.md` | C: benchmarks are self-reported, and KUANG's review fixes landed afterwards, so re-run first |
| 20 | Synth knob directions in a codec latent space | Which knobs have shared directions | EXPERIMENTS H4 | B |

## Deliberately left out

- Negative or null results (morph contour following, preference optimization on real stems): worth publishing, but they block nothing. They belong in the post.
- Bug postmortems with no reusable method.
- Anything that needs goa-corpus specifics to explain.

## How to publish it

1. One document, sections as above, each entry with the method stated, a broad statement of scope, and a pointer to code in the public repo.
2. Deposit on **Zenodo** for a dated DOI, connected to the GitHub repo so each release is archived; trigger **Software Heritage** on the public repo.
3. arXiv optionally, later. Do not wait for it.
4. Worth noting: `WORKLOG` and the dialogue have mirrored publicly and with dates since July, as have eval pages. That may already help for some rows, but it is scattered, and not written so someone could reproduce a method. Do not rely on it alone. An archive.org snapshot is cheap insurance.
5. Credit: ANTIGRAVITY and KUANG contributions under their own names; Kim decides how the human authorship reads.
6. Rights: the write-up can describe training on the project's music without naming the commercial corpus.

## Next step

Rows 6, 11, 4 and 19 are the most worth a targeted literature check, since those are where a company would most plausibly file. Patent databases were never searched; if that matters, it is a separate job.
