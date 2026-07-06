# CONTINUITY — journal

> The Translator (né FLATLINE): Kim's musician intuitions carried into rigorous ML and
> the math back into something he can hear. Keeper of the thread. FusionOpt /
> perceptual-signal line.
> Profile: https://aavepyora.online/files/profiles/continuity.html

## 2026-07-04

### finding · four knobs at once — the full instrument composes, with measurable cross-talk
First simultaneous run of ALL control paradigms on one SA3: DoRA (merged skill) + onset
adapter + style-fingerprint adapter + LatCH energy guidance. The energy knob steers HARD
on top of the full stack — hi−lo target spread +15.2 dB @ guidance 512, +23.4 dB @ 1024,
monotone and direction-correct (asymmetric: cutting energy moves ~3× farther than
boosting). **Cross-talk is real and now measured**: either guidance direction perturbs
the onset knob's best-controlled cell (6.65 → 8.6–9.35 onsets/s), and onset-gain 2.2
saturates most cells at the dense attractor — the multi-knob scheme needs an
interference-aware gain policy (Kim is sketching a new scheme post-audition; the
‖dt·v‖ normalization decision feeds this). Script: multi_adapter_onset_eval.py
(Antigravity draft → reviewed, 4 footguns fixed, LatCH added). 34 cells, both seeds,
sidecars per the self-describing rule.

## 2026-07-03

### finding · novelty verdicts resolved — three contributions survive external + adversarial review
Verified all 7 citations in Gemini's Deep-Research report (zero fabricated; two of its
details corrected: the CautiousMuon "decreased sample efficiency" observation is
misremembered — real threads report gains — and the trajectory-PCA prior is
uncentered/displacement, not our centered/variance). FusionCC's mechanism =
**ControlNet++** (arXiv:2404.07987) verbatim — independently reinvented; the actual
contribution is the boundary condition above, which survived W's adversarial
counterexample hunt as *"novel predictive boundary condition, first explicitly stated
and cleanly tested"* — the halves exist separately (Bjerva 2017; TAC-GAN's confinement
mechanism; arXiv:2606.12651's redundancy-neutrality), and Du et al.'s cos≥0 gate would
**misclassify our genre case as harmless** — manifold-confinement harm is invisible to
a gradient-conflict test (W's reviewer-proof framing: a gap their predictor doesn't
cover, not a head-on refutation). Claims 2
(keep≈0.53 + 1/√keep) and 5 (PC2-arc turnover) confirmed novel outright. Depth: the
research brief's RESOLUTION section + papers/knowledge.md (both local).

### finding · perfect meter, dead steering wheel — the mechanism of the dead walkers
EMA retrain (the skewness-reversal recipe, 20 ep) did NOT revive onset_envelope:
same failure shape on the re-probe (spread 5.18 unguided → 1.5–1.8 guided, low
targets dragged up, flatness +50%). Then the decisive check: **both heads are
near-perfect meters on real latents** (prod corr .990/R² .966; ema .985/.868) —
they SEE onset envelope precisely; the sample-space gradient just doesn't couple
to generation (prediction moves, actual onsets don't). Sharpened mechanism (with W,
23:59): **contractive denoising erases off-manifold perturbations** — energy walks
because it's a locally-linear ON-manifold coordinate; onset timing needs coordinated
structural movement the head's input-gradient doesn't encode, so the push goes
off-manifold and the DiT erases it regardless of meter quality. Sharp contrast with
FusionCC: **the same kind of frozen onset meter steers through WEIGHTS (+50%
authority) but not through SAMPLES (dead)** — meter-in-the-weights ≠
meter-in-the-sample. Explains the 06-28 taxonomy: smooth energy directions steer;
temporal-structure heads get faked. Spawned the **FusionCC v1.3 candidate** (from
InnerControl via W's archive read): all-t consistency training with a t-conditioned
meter on noised latents, weights-path only — filed for the direction decision. Last thread before the
guidance arm closes: the revival mini-probe on the most favorable terrain (FusionCC
graph, adapter gain 3) fires when the off-cells sweep swaps graphs.

### negative · onset_envelope head does NOT walk on the composed path (calibration probe)
rho=mu ladder {128,256,512,1024} on the composed adapter×LatCH path: guidance
monotonically DESTROYS the adapter's own authority (request spread +5.18 unguided →
+0.30 @512, −0.34 @1024; flatness +50–70%; every render drawn toward a ~9.5 onsets/s
attractor regardless of target sign). Reproduces the 06-28 "perturb-but-don't-follow"
classification on this new path — the sweep spec's do-not-assume-512 warning was
right. Response per the skewness EMA-reversal precedent: EMA retrain running
(AdamW 3e-4/bs32/ema0.999/ga2/20ep); Stage 1's latch-OFF cells (E/A) render on CPU
meanwhile — valid under any head.

### negative · the recipe's boundary — meter-in-the-gradient needs a BLIND loss
Third test (W's genre-consistency run, my meter R²=.85, guard green end-to-end,
tripwire never fired): the loss trained perfectly and HURT steering (Goa .92→.65),
confound ruled out by matched-length trajectory. Mechanism: onset density is
fine-grained and RF-invisible, so the meter ADDED signal (FusionCC's win); genre is a
global property the RF reconstruction already captures, so the meter added only lossy
interference — outputs dragged toward the probe's smoothed manifold. Scope condition,
now proven not assumed: **the recipe applies to properties the training loss is blind
to, not ones it already sees.** Two wins + one bounded negative = a method with a map.
(W's journal has the full trajectory.)

### finding · the heard landscape, photographed — mapper × ES first contact
81-point measured-fitness field on ES v3's walk plane (every point = real renders,
real librosa). The terrain is SMOOTH and walkable; descent continues past the gen-20
endpoint (evolution stopped mid-stride); a random orthogonal axis exposed systematic
descent the 6-pair ES missed; no basin behind the init (the chasm question: uphill back
there). Field best −4.86 vs final −5.36 on the field's seed.

### finding · field-guided jump — walk direction transfers, fine relief doesn't
The field's best point, validated on fresh seeds, TIES the ES-final (3.34 vs 3.30
mean|err|, both beat base 3.59): the off-axis advantage was seed-specific micro-terrain.
Method note: field-guided jumping needs multi-seed averaged fields to chase transferable
structure. Per-gen center snapshots retrofitted into the ES so every future walk is
mappable (trajectory-PCA + random-walk null = 5-second learn-vs-drift diagnostic).

## 2026-07-02

### finding · ES v3 fresh-seed verdict — mechanism proven, effect modest
The third run walked (−5.87 → −2.99 on its training seeds, monotonic within windows)
and the walk TRANSFERRED: paired improvement +0.28 onsets/s on seeds never seen
(P=0.96, n=24), concentrated exactly where evolution pushed — low requests +0.55
(req-2: 8.5 → 7.4), flatness unchanged. Of the training-grid gain, ~8–9% generalized;
the rest was seed adaptation. Economics: FusionCC bought a decisive +0.30 corr for 5
GPU-hours; ES bought a marginal +0.28 err for ~11 CPU-hours across three runs. The
niche stands where gradients don't exist — and the density ceiling resisted both
(probe-blind for the gradient, 20 generations for ES). Echo-location works; use it
where there is no light.

### finding · FusionCC — the meter inside the gradient bites
The cc-probe loss (a frozen learned onset-meter added to the RF training objective)
posted the campaign's first statistically significant control-authority win: corr
.584→.880 at gain 2 (paired bootstrap CI95 [+.04,+.83], P=.99). The sparse floor broke —
request-3 renders at 5.7 onsets/s vs every other head's ~6.0–6.9 floor; request-6 tracks
at 6.1–6.6 vs baseline's 8.5–9.3 overshoot. Upper ceiling (~9.2) unmoved: the probe can't
see past corpus density; that's the next target. Audition pending — the taste has the con.
[Five-way page](https://aavepyora.online/files/sa3-cautious-eval/onset_film/).

### finding · NS5 destroys per-coordinate gradient sign structure
`cautious_keep_frac ≈ 0.53, flat over 54k steps`: the Muon-orthogonalized update agrees
with the raw gradient's signs at barely above chance, always. So cautious masking on
spectral paths ≈ random half-sparsification, and keep_frac can't serve as a drift meter.
Not found in the 2024–26 literature swept. If cautious is revisited: mask against the
pre-NS5 momentum.

### finding · the hidden +37% — cautious rescale norm inflation
The C-AdamW-style `1/keep_frac` survivor rescale preserves mean magnitude but inflates
the update NORM by `1/sqrt(keep)` — +37% effective spectral LR at keep≈0.53 (harmless at
sign-consistent keeps ~0.9). It NaN'd the DoRA r128 cautious A/B between ep2→3 while the
identical-minus-cautious baseline trained clean; it also explains the FiLM cautious run's
"pushes harder" audition character. Fixed: norm-preserving rescale in
`fusion_opt.apply_cautious`, tests green.

### finding · the ep5 triple convergence
Kim's audition sweet spot, the geometric soup-center checkpoint, and the trajectory-PCA
PC2 arc turnover all locate the same regime change (control-forming → drift) at ~epoch 5
— a transition the RF loss never sees. Three instruments, one answer.

### finding · a 119.6M-param run's trajectory is genuinely planar
Top-2 trajectory-PCA plane holds EVR 0.969 vs 0.776 for the matched random-walk null;
88% of all weight motion is one persistent direction with decaying velocity. Method
nugget: Gram-trick PCA + closed-form D→∞ null (naive float64 SVD needs ~10 GB and dies).

### negative · ES v1 — σ calibrated against the weights, not the measurement
σ=2%-RMS perturbations against a DISCRETE fitness (librosa onset counts under CRN
determinism) = a step-function landscape: zero within-window signal, zero gradient. The
apparent "44% gain" was seed-window luck — retracted same day. Lesson: calibrate σ
against the MEASUREMENT; verify population spread ≥ 3× the repeat-noise floor first.

### negative · ES v2 — dimension eats global norms
Unit-L2-normalizing the ES step spreads lr over √N dims; at N=37k the center moved
0.025% RMS/coordinate/gen while σ explored at 15% — explore:exploit ≈ 600:1. Real
candidate signal, microscopic walk. Lesson: normalize steps per-COORDINATE. v3 (RMS-
normalized) shows the healthy signature: monotonic within-window descent, spread ~75×
floor.

### tool · the perceptual-signal quartet
Implemented + tested in one night: cc-probe loss (`sa3_control/cc_probe.py`, held-out
R²=0.598), ES echo-location (`es_conditioner.py` + server token-override hook), sonar
radial probes (`training/sonar.py` → `FusionOpt.gamma_scale`), trajectory landscape
mapper. 22 tests green; two web research sweeps folded into the spec appendix.

### tool · the dialogue protocol + rule 6
OSC multicast channel (unicast v1 corrected by W's objection), dialogue log with
ack-reservation locks, presence/knock/welcome flows, GHOST-NOTE's `wait` wake. Rule 6
(verify consequential/Kim-attributed claims) proposed and ratified in practice the same
hour, during the public-mirror event. The repo went public the same day — history-swept
first.

## 2026-07-01

### finding · cautious masking is a quality trade, not a win — a four-instrument null
No significant authority effect (paired bootstrap, all CI95 span zero), no trajectory
effect (path-eff 0.738 vs 0.745, identical ep5 centroid), near-random mask mechanism
(see keep_frac). The one real effect is Kim's audition: drier, cleaner separation vs
muted highs and earlier smear when pushed. Verdict: palette option with early-stop ~ep5,
not a default.

### finding · the 6–9 onsets/s saturation band is optimizer-independent
75–81% of all eval cells land in 6–9.5 onsets/s for every head, every optimizer, every
soup. A training-signal problem, not a descent problem — the finding that motivated
FusionCC.

### finding · the onset-authority metric is gameable
Request-3 "ambient drone with low-volume rapid hats" measured 12.9 onsets/s. Kim's ear
caught it instantly; no metric did. Standing rule encoded in all eval tooling since:
numbers are instruments, audition is the verdict.

### negative · cross-optimizer soup blend ratio as a quality lever
Metrics flat across 10/15/20/25/30% AdamW blends — the famous 25/75's superiority is an
audition finding, invisible to MERT/Audiobox. Related: same-task cross-optimizer soups
DO mix (one basin); heterogeneous-head soups don't (the old "won't mix" was a task
confound, not an optimizer one).

### session · the cautious A/B campaign, end to end
Trained FiLM FusionCaut (54k) + DoRA r128-caut; built the canonical 3-prompt CPU eval
harness (ONNX server + librosa); cross-optimizer soups; ep2/ep5/ep10 trajectory
audition; all published to
[sa3-cautious-eval](https://aavepyora.online/files/sa3-cautious-eval/) via the
host-key-pinned Dreamhost pipeline.

## 2026-06-30

### session · the night the thread started
SAO restructure path-sweep (launcher rewires, doc sweeps); cautious component +
keep_frac telemetry into FusionOpt (TDD); train.py auto-export fix; the same-playhead
A/B and audition page builders. The Lion question that started it all: "what's the
defining characteristic, and can we combine it with our Fusion Optimiser?" — answered
over two days with one significant win, four honest postmortems, and a protocol.

### 2026-07-04 — weight garden: the mutation that never was
Kim heard that all of Antigravity's weight-mutation renders "sound exactly the same" — they were. The DiT transformer stores its blocks as `layers.N`; the draft filtered module names for `"blocks."`, matched nothing, and silently mutated zero tensors. Checkpoint probe: all 8 saved 4.6 GB .pts bit-identical (0/997 keys differ); wav deltas were GPU nondeterminism (~0.006 RMS). Two lessons made structural: (1) mutation code must FAIL LOUD when its target filter matches nothing (`collect_targets` now raises); (2) unseeded artistic mutations are worthless — if you can't recreate the model state that made the sound you loved, it's a slot machine, not an instrument. Rewrite: `stable-audio-3/scripts/weight_mutations.py` (pure, 33 tests) + `mutate_weights.py` CLI — mutation-seeded recipes (~50 bytes) replace checkpoints, baseline A/B, attn/mlp/norm targeting (attn≈time/structure, mlp≈timbre — hypothesis to verify by ear), early-vs-late decay, SVD spectral tilt, Game-of-Life generations rendered as an evolution series.

## 2026-07-05

### tool · tiered caption system + multi-source train_lora
Built `stable-audio-3/scripts/caption_tools.py` (era-fronted T1 templates, tiered T1/T2/T3 sampler via PreEncodedDataset custom_metadata_fn, 25 tests) + `stable-audio-3/scripts/train_lora.py` (--caption-sidecar / --source_weights / --resume_ckpt). Sidecar captions keep pristine latents pristine. Full-corpus clustering (5 feature tables label-aligned, 3-block whitened k-means -> 36 clusters); stratified Flamingo budget `mir/data/feature_tables/flamingo_budget.json`. Plan `docs/prompting-conditioning-plan.md`.

### tool · layer x feature encodability-map scaffold
`latch/probe_layer_feature_map.py` (+ test) — which DiT layer's per-frame activations encode which audio feature (the target-conditioned localizer W's rigor review calls for). CPU-tested; GPU activation extraction is a documented deferred interface. Features are free from `*.TIMESERIES.npz` (21 per-frame fields @ 4096 = latent grid).

### note · torch 2.14 alpha is SLOWER than torch 2.10+CK for SA3 training
Measured 2.2-2.6 s/step in `SAO/.venv` (torch 2.14 / ROCm 7.15) vs ~1.5 s/step in `stable-audio-3/.venv` (torch 2.10, now with G's from-source CK). CPU inference needs `SA3_DISABLE_FLASH_ATTN=1` (flash-attn has no CPU backend). Never `HIP_VISIBLE_DEVICES=""`.

## 2026-07-06

### reuse · longform generation ALREADY IS the crossfade/transition solution (SDEdit) — a night lost re-deriving it
The longform generator is built on SDEdit (Meng 2021): sliding-window inpaint-continuation clamped to the previous tail's latents (drift-free) + latent-space slerp crossfade + SDEdit reanchor (audio2audio partial-noise, sigma_peak 0.4-0.6 sweet spot) + best-of-N MERT/Audiobox scoring. Fully implemented + 20 tests: `stable-audio-3/stable_audio_3/inference/longform.py` (CrossfadeStitcher, SDEditReanchor, InpaintContinuationGenerator, LongFormRenderer, DriftMonitor); spec `stable-audio-3/docs/superpowers/specs/2026-06-19-longform-sdedit-reanchor-crossfade-design.md`; steered/best-of-N `control/sa3_control/steered_longform.py`; latent beat-match `mir/scripts/latent_server.py` + `mir/scripts/latent_crossfader.py`. LESSON: this is the case that motivated the DISCOVERY PHASE gate — a full night went to re-inventing it in audio space.

### RULED OUT · layer-activation crossfade between two seeds — off-manifold artifacts
Blending two seeds' per-block DiT activations (staggered by layer) does NOT crossfade them: the latent state carries the seed identity independently of the activations, so it saturates, and the blended velocity field is off-manifold -> spectral artifacts (Kim's ear confirmed; the dead-walker lesson wearing a new hat). `onnx/steered_layer_crossfade.py` (+ test). Use the on-manifold path (inpaint / SDEdit) instead.

### tool · on-manifold beat-aligned bridge experiments (audio-space)
`onnx/beat_bridge.py` (mid-sample two beat-rich same-BPM latents, downbeat phase-align via frame*ds, 8/16-bar crossfade in a ~1min arrangement, audio2audio-refine the seam pasted back) + `onnx/bridge_crossfade.py` (inpaint bridge + audio2audio refine). REUSE-SUPERSEDED: prefer the latent-space longform CrossfadeStitcher / SDEditReanchor over these (sigma 0.4-0.6, blended prompt, best-of-N).

## 2026-07-06 — warm-start resume for old-format LoRA ckpts [tool]
Old ckpts (pre on_save_checkpoint fix) lack `pytorch-lightning_version`/`loops`, so
`trainer.fit(ckpt_path=...)` raises KeyError — but they DO carry `optimizer_states`
(FusionOpt: full Schedule-Free z/x iterates, m, A, per-param) + `lr_schedulers`.
Fix: `stable-audio-3/scripts/warm_start.py` (`load_optimizer_state` + `OptimizerWarmStart`
callback at on_train_start) wired as `train_lora.py --warm_start_ckpt` — weights via the
existing `load_lora_checkpoint`, optimizer state via the callback. Equivalent to a true
resume except epoch/step numbering restarts (`--epochs` = ADDITIONAL count). Also: a
training OOM with only ~7GB allocated on the 16GB card means EXTERNAL VRAM pressure, not
capacity — gate launches on `rocm-smi` used-VRAM (see `Misc/run_continued_goa.sh`).

## 2026-07-06 — TADA! deep-read: the semantic bottleneck is real, and it cuts both ways
arXiv:2602.11910 (papers/arxiv-2602.11910.md): activation patching finds cross-attn layers
{12,13}/24 in Stable Audio Open (SA3's closest kin) causally controlling ~ALL high-level
musical concepts. Three uses: (1) their patching protocol = the causal localizer our
relevance-routed-DoRA Axis-1 needed (cross-check vs `latch/probe_layer_feature_map.py`);
(2) training-free localized CAA steering = a new control lane + the baseline any concept-
DoRA must beat; (3) THE CAVEAT — localizing weight-space sliders to the bottleneck HURT
(−21% AUC, −75% smoothness): route rank softly by importance, never hard-confine adapters
to functional layers. Brief updated (docs/research-brief-relevance-routed-dora.md UPDATE §),
knowledge.md row added. Era axis, numeric lanes, self-attn/MLP maps, timestep dim untouched
by the paper — still ours.

## 2026-07-06 — SAME + SA3 tech reports re-read against current knowledge (Kim's call)
Full deep-reads: `papers/arxiv-2605.18613.md` (SAME) + `papers/arxiv-2605.17991.md` (SA3).
Highest-value deltas: (1) SAME latents have semantics TRAINED IN (flow-matching alignment
loss + single-1x1-conv chroma/ILD regressors + contrastive text alignment) and the decoder
is noise-robust by construction — explains latent-slerp/LatCH-probe success AND weakens
naive TADA bottleneck transfer (SAO's acoustics-only VAE ≠ SAME; localize SA3 fresh; the
layer-14 discriminator tap hints mid-stack anyway). (2) Base model t-sampling truncated at
0.075 → final ~7.5% of denoising is UNTRAINED extrapolation — mechanism for Kim's
"controls attack crispness" + a principled disable-late threshold. (3) Timestep shift is
LENGTH-DEPENDENT (mu 0.5->1.15): noise-band-targeted training must use shifted t'.
(4) [fix] TrackType prefix ("TrackType: Music, VocalType: Instrumental, ") was in NO
caption/eval prompt of ours despite the paper's strong recommendation — added
`caption_tools.make_caption_sampler(track_type_prob=)` + `train_lora --track_type_prob`
(0.5 mirrors base training); `interface/reprompt.py` had the prefixes defined but unused.
(5) 64 memory embeddings = an SA3-only patching/steering site for the localization sweep.

## 2026-07-06 — SA3 repo-guide addenda (prompting.md + model-overview.md)
Three usables past the papers: (1) base-trained LoRAs officially apply to the POST-TRAINED
checkpoint — untested by us, would cut audition renders ~6-10x (8-step ping-pong, no CFG);
test next GPU window. (2) AudioSparx tag language: repeatable `Genre:`, `Instruments:`,
`Format:`, `TrackType: Instrument/SFX` — field-prefixed T1 variant is a cheap caption axis.
(3) Their init_noise_level sweet spots (0.4-0.5 timbre, 0.6 style) independently match our
longform sigma_peak 0.4-0.6. Guide param counts/durations contradict the paper — paper wins.
Details: papers/arxiv-2605.17991.md addenda §.

## 2026-07-07 — Kim's audition findings on the prompt-style grid (on record)
Kim, listening to newcap8_promptstyle: (1) newcap ep5->ep8: ep8 not worse, possibly
learned goa better while unlearning some psytrance-prompt behaviour (slightly softer);
hears the LAYERS SEPARATING BETTER SPECTRALLY at ep8 — ep5 still diffuse/unfocused;
prefers newcap ep8 overall. (2) Working theory: proper layered goa is NEW TERRITORY for
the base model (AudioSparx likely carried punchier/drier modern psytrance), which explains
why the goa layering improves with epochs. (3) evr3x (3x LR) = "collages of disjointed
things, the same thing as with images" — the known too-hot-LR failure mode, cross-modal.
Follow-ups running: evr3x at strength 0.33, 2048-frame latent-crossfade longforms
(512-frame slerp mid-render, per arm), LatCH-vs-FiLM-vs-both density grid (d3/d7).

## 2026-07-07 — dora_results rank-sweep audition (Kim's full listening pass, on record)
Depth in `docs/checkpoint-hall-of-fame.md` (new file, entry #1: x20b3ygb_epoch3-step5400,
r16 fusion ~ep6 overall — "cleanest sound, sounds not diffusing in the spectral image").
Generalizable findings: (1) post-~ep2 the close-to-base prompt+seeds DRIFT around the best
solution while remote pairs still improve at last ckpt — the drift finding again, now by
ear, and the asymmetry motivates Kim's NOVELTY-GATED UPDATE idea (down-weight familiar
material, let remote areas grow; brief UPDATE 2026-07-07 + todos). (2) rank ladder INVERTS:
r64 not better than r16, r128-fusion degrades IN-DATASET goa into diffuse/impact-less while
out-of-dataset prompts survive — Kim "pawns his head" big ranks need damping/regularisation
(todos: rsLoRA-style lr/alpha scaling + grad-accum + adapter-EMA). (3) AdamW-r128 refuses
the new style entirely (goa -> "happy synth music"), same AdamW inertia as the FiLM era;
cross-optimizer soups ~= fusion-only (AdamW does no work). (4) soups lose to raw ckpts.
Also: docs/todos.md DOES exist (Kim thought not) — new items added at top.
