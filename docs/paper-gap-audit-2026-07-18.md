# Paper Gap Audit — 2026-07-18

**Author:** THE-FINN (overseer)
**Scope:** SAO music-ML stack (SA3 rectified-flow model, SAME latent).

## What this is

This is a **gap-hunt**, not the verdict page. Where `paper_verdicts_data.json`
asks "did the paper's central claim replicate on our stack?", this audit asks a
different question: for every reviewed paper, is there a useful mechanism the
team **missed**, a method it applied only in **part** (skipping a load-bearing
companion), or something it applied **wrong**?

**Method.** A fan-out of deep-read agents examined each reviewed paper against
the paper PDF *and* the team's actual code, proposing candidate gaps. Every
candidate was then adversarially verified — re-checked against the PDF text and
the live code paths — and refuted candidates were dropped. 20 gaps survived,
each carrying its verifier verdict:

- **confirmed** — both the paper claim and the code fact hold, and the transfer
  argument stands.
- **overstated → corrected** — the kernel is real but the finder's framing
  over-reached; the narrower true claim is stated inline.

Every item is a **lead for the team to weigh**, not a directive. Read the
verdict and value before acting. Values: `high` / `medium` / `low`.

**Note on the brief:** the tasking asked me to lead with the Kynkäänniemi
interval-CFG and an "InfiniteAudio buffer-zone" item. Kynkäänniemi survived and
leads below. No InfiniteAudio buffer-zone gap survived verification, so it does
not appear.

---

## Top actionable

The cleanest wins: gaps the verifier left **confirmed** (not narrowed), on
infrastructure the team already runs. Highest-value first.

### 1. TADA — adopt the alignment–preservation AUC + smoothness steering eval
*Paper 2602.11910 · type: MISSED · verdict: **confirmed** · value: **HIGH***

**Gap.** The team adopted TADA's layer localization and its training-free
CAA/diff-in-means steering lane, but not TADA's steering **eval protocol**. Its
steering "wins" are single-point Essentia alignment deltas with no preservation
axis.

**Paper evidence.** TADA §4 defines: an alignment–preservation **AUC**
(trapezoid of sign-corrected MuQ/CLAP alignment delta over an LPAPS-preservation
axis), a **Smoothness** metric (std of consecutive alignment gaps along the α
ladder), and Audiobox Aesthetics — all methods calibrated to the **same max
perceptual distortion**. This is exactly how TADA shows localization *helps*
activation steering (+46–49% CAA AUC) but *hurts* weight-space sliders (−21%
AUC, −75% smoothness) — a trade-off invisible on raw alignment gain. The
protocol is model-agnostic (measured on Ace-Step, but it is a measurement
recipe). `papers/knowledge.md:30` already lists it as "worth adopting."

**Our evidence.** `eval/steer_concept_direction.py` renders the α ladder
{0,+2,−2,+6,−6} but only saves audio; nothing computes preservation vs
alignment. The headline is a single point — `mt_dark` Essentia dark 0.018→0.341
at α=+2 (19×) — with the journal itself noting "|α|=6 breaks structure
everywhere" qualitatively but never quantifying it. Audiobox/MERT scorers exist
in the stack but are wired to DoRA eval, not to the concept-steering renders.

**Why it matters.** A 19× "dark" gain cannot be distinguished from off-manifold
distortion that merely *reads* dark to the Essentia classifier without a
preservation axis. Adding LPAPS-preservation-vs-delta AUC + smoothness turns the
steering result into a real scorecard and lets diff-in-means / ReFT-r1 /
orthogonalized directions be compared on one scale.

**Smallest test.** Run a denser, distortion-calibrated α sweep on one mood; for
each α compute an in-stack perceptual distance (MERT / Audiobox) from the α=0
render as the preservation axis and the signed Essentia delta as alignment;
report trapezoid AUC + smoothness. **Caveat (narrows cost, not existence):** the
current 5-render ladder is too sparse and uncalibrated to reuse post-hoc — TADA
uses 15+15 strengths calibrated to equal max distortion, so this needs a fresh
sweep, not just re-scoring existing renders.

### 2. Kynkäänniemi — limited-interval CFG ships OFF by default, never A/B'd
*Paper kynkaanniemi2024 · type: PARTIAL · verdict: **confirmed** · value: **MEDIUM***

**Gap.** SA3 natively supports limited-interval CFG and adopted the companion
APG combine, but ships the interval OFF: `cfg_interval=(0,1)` = guidance
everywhere = plain CFG. The paper's central claim — narrowing the interval
improves quality / prevents mode collapse — has **never been A/B'd**.

**Paper evidence.** CFG at all noise levels is "clearly harmful toward the
beginning of the chain (high noise), largely unnecessary toward the end, only
beneficial in the middle"; "most of the drift is caused at high noise levels."
Table 1: limiting the interval improves EDM2-S FID 2.23→1.68 and sets the
EDM2-XXL record 1.40, with guidance at only 6 of 32 steps — which also *lowers*
sampling cost. Demonstrated to transfer to large-scale latent diffusion (SDXL).
Recommendation: "expose the guidance interval as a hyperparameter in all
diffusion models."

**Our evidence.** `cfg_interval` defaults to `(0,1)` at `dit.py:363` /
`model.py:412`; UI sliders default 0.0/1.0. For rectified flow, `dit.py:456`
sets `sigma=t`, and the gate `dit.py:479` is
`cfg_interval[0] <= sigma[0] <= cfg_interval[1]` — so `(0,1)` never excludes a
step. APG adopted (`apg_scale=1.0`), interval left un-narrowed. Verified
compute-saving: when the gate is false, `dit.py:627` falls to a single
`self._forward` (no doubled pass), so narrowing genuinely skips work. The team's
own record confirms the headline "has never been directly A/B'd" and the one
supporting datum (WINTERMUTE melodic-movement mid-band U-shape collapse) is
co-attributed to three mechanisms at once — confounded, not isolated.

**Why it matters.** The team already *observed* the exact failure the paper
blames on guidance-everywhere: a mid-noise-band mode-collapse U-shape in
melodic-movement metrics. Shutting guidance off at the high-noise early-t steps
is the paper's direct remedy, with a near-free inference speedup on the
now-unguided steps.

**Smallest test.** A/B narrowed `cfg_interval` vs `(0,1)`, holding
APG/steps/cfg_scale fixed; read the `melodic_movement_ladder` mid-band U-shape +
FAD. **Critical porting caveat:** do **not** paste the paper's EDM sigma numbers
(0.19, 1.61) into this gate — here `sigma=t∈[0,1]`, so 1.61 never gates the
high-noise end and 0.19 only disables the last ~19% (low-noise) steps, i.e. the
*less* important half. Re-derive in flow-t units and sweep the **upper**
(high-noise/early) bound first, e.g. `(0.0,0.7)` / `(0.1,0.8)`.

### 3. DirectAudioEdit — dynamic (weak→strong) target-CFG schedule for FlowEdit
*Paper 2606.07356 · type: MISSED · verdict: **confirmed** · value: **MEDIUM***

**Gap.** The team's FlowEdit port uses a single constant target-CFG for every
edit step. DirectAudioEdit's ablated dynamic target-guidance schedule — cheap,
separable from the paper's DDPM-specific machinery — was never adopted.

**Paper evidence.** Source-branch CFG stays fixed (`w_src=3`); the **target**
CFG follows a monotonic cosine ramp 8→12 across edit steps, because early on
"weaker target guidance helps avoid abrupt deviations from edit-irrelevant
source structure" while later "stronger target guidance encourages more complete
target-semantic injection." Table 3 ("w/o Dynamic CFG" = fixed target scale):
dynamic guidance "consistently improves FAD, KL, SSIM" — load-bearing. The
CFG-ramp piece is separable: it only modulates the standard classifier-free
guidance scale inside the target reverse update, independent of the shared-noise
re-noising that makes the rest of the paper DDPM-specific.

**Our evidence.** `control/scripts/sa3_flowsep.py` passes one scalar `cfg_tar`
(default 13.5); inside `make_flowedit_euler` the target branch reuses it
unchanged every edit step. No cfg schedule/ramp anywhere. The team instead
hand-rolled a self-described "crude" `anchor_eta` fidelity dial (blends `z_edit`
back toward source `x0` at high-noise steps) — an ad-hoc attack on the same
source-preservation problem. flowsep already runs on medium-base with **live**
CFG, so the "CFG inert on APT-distilled checkpoints" objection (the recorded
verdict's basis for rejecting the rest of the paper) does not apply here.

**Why it matters.** A principled, tunable alternative to the ad-hoc `anchor_eta`
blend for the recurring FlowEdit failure mode (over-editing / loss of source
note-timing during separation), on the checkpoint flowsep already requires.

**Smallest test.** Replace the scalar `cfg_tar` in `make_flowedit_euler` with a
per-edit-step cosine ramp (~6→13.5) and A/B separation faithfulness (same
notes/timing vs `original.wav`) against the current fixed-CFG + `anchor_eta`
baseline on the existing goa-mix test. **Caveats on magnitude:** only the ramp
*shape* transfers, not the absolute 8→12 range (flowsep already runs cfg 13.5
robustly); and the paper's own Table 3 discussion notes the benefit is
backbone-dependent, so the size of the win on RF/SA3 is unproven.

---

## Missed

Mechanisms with no engagement (or engagement that stopped short of building) on
our stack. All verdicts below are **overstated → corrected** unless noted; the
narrower true claim is given.

### SAME — refit the built-in ILD stereo readout
*Paper 2605.18613 · value: **MEDIUM** · overstated→corrected*

SAME ships an ILD regressor (single 1×1 conv, 32-band mel L−R log-mag
difference) — the exact stereo twin of the three chroma regressors — and it is
documented in `SAME_CHROMA_FINDINGS.md` but never refit. The team already
exploits the chroma twin this way (`scripts/latch/extract_same_chroma_targets.py`
→ `chroma_heads_real.npz`); ILD was never built. **Narrower claim:** refitting
it gives a cheap latent-native stereo-width term for `stereo_loss.py`, but (a)
`z0_hat` is biased at high t, so the t-gate stays — the win is **full-batch at
low t**, not full-schedule supervision; (b) ILD is a *level*/panning meter only,
so it can replace the panning/width meter (`todos.md:222`) but **not** the
inter-channel phase-coherence/combing meter, and is narrower than the current
audio-space `side=(L−R)/2` loss. **Test:** refit `W_ild,b_ild`, add an ILD term
matching `readout(z0_hat)` to `readout(x1)`, A/B against the decode-based side
loss on a stereo-collapse DoRA arm.

### Latent Space Disentanglement (symbolic) — Gram-Schmidt orthogonalization
*Paper 2605.31295 · value: **MEDIUM** · overstated→corrected*

The steering code adds raw diff-in-means directions with no orthogonalization
(`grep` for orthogonal/gram-schmidt across `eval/` is clean). Gram-Schmidt
projection of two direction vectors is architecture-agnostic linear algebra that
transfers cleanly to the audio DiT and will be needed once 2–3 correlated
concepts are composed. **Narrower claim:** this is **not a missed insight** — the
team's own deep-research brief (`papers/deep-research/2026-07-11-activation-steering-dit-audio.md`,
same day as the code) already cites the paper by arXiv ID and explicitly
prescribes Gram-Schmidt as the fix. It is an unimplemented, already-recognized
TODO gated on steering still being at the single-attribute phase; the gap TYPE
("missed") is wrong. The only stale artifact is the verdicts-JSON line calling
it "unrelated MIDI methods." The claim's attribution of `mt_uplifting`'s
negative-only failure to entanglement is unsupported — the team diagnosed it as
feature-steerability, not confound.

### UltraViCo — attention-concentration decay + RoPE-harmonic diagnostic
*Paper 2511.20123 · value: **MEDIUM** · overstated→corrected*

SA3 is a bidirectional flow-matching RoPE DiT (same class UltraViCo validates
on), with a live non-causal `flex_attention_score_mod` hook that makes both the
decay (Eq 5/6) and the offline Prop-1 harmonic diagnostic a ~10-line change, and
the paper's OOM obstacle is gone (~2K audio tokens vs ~200K video). Neither has
been applied. **Value:** (a) a cheap first-principles test of whether SA3's loops
are RoPE-harmonic-induced vs the statistic-blindness cause the team already
measured; (b) a possible lift to the single-pass beyond-native quality ceiling.
**Narrower claim:** single-pass only reaches ~4× (not arbitrary length, so it
does **not** replace windowing wholesale), does **not** address the
within-length a2a loop-attractor, and the team *does* already run naive
single-pass beyond-native renders (fixed long render T=2048/4096). So "removes
seams/drift/loops wholesale" and "single-pass never run" are both wrong.
**Test:** (1) offline, no GPU — compute SA3 `inv_freq` and test Prop-1 harmonic
alignment; (2) add an Eq-5 `score_mod` (constant α≈0.5–0.8 on out-of-window
positive logits) and A/B a single-pass 2×-native render decay ON vs OFF on the
loopiness/HF-variance/drift metrics.

### SaFa — global reference-trajectory latent swap (operator-2)
*Paper 2502.05130 · value: **MEDIUM** · overstated→corrected*

SaFa's operator-2 (a shared global reference trajectory swapped into each
window's non-overlap region during early high-noise steps only, `r_guide≈0.3`)
is not implemented; the team Markov-chains each window to its predecessor's tail
(`longform.py:245`). A global anchor could bound cross-window timbre/level
**drift** better than Markov chaining. **Narrower claim:** it is a documented
pending item (verdict flags operator-2 unported), **not** a loop-attractor fix —
the team's corpus diagnoses looping as flow-matching posterior-mean collapse and
explicitly notes "SaFa fixes the join, not the attractor," and the default
renderer has no re-anchor to be "too strong/late." A faithful Eq-11 port still
needs a hooked/parallel per-step renderer (`sampling.py` exposes per-step
callbacks, so cheaper than the verdict implied but not a free drop-in); the only
true on-infra approximation (SDEdit from a shared reference) is a different
whole-window operator that risks the very repetition SaFa warns of at high
`r_guide`. **Test:** early-steps-only shared-reference clamp on the sequential
renderer; sweep `r_guide` 0.2–0.4 vs 0.6+, measure drift AND loopiness.

### SimDPS — soft "pull-toward-anchor" z0_hat DPS head
*Paper 2509.16342 · value: **MEDIUM** · overstated→corrected*

The team's bridges use hard inpaint-clamp + crossfade; the recurrence head only
pushes *away* from over-recurrence. SimDPS's uncertainty-weighted z0_hat-space
gradient `‖(I−M)(z_anchor − z0_hat)‖²` (a soft "pull-toward-anchor" term) is not
implemented, and the guide-list framework
(`sample_flow_euler_multi_latch_guided`, `rf_z0_hat = noised − t·v`) already has
everything needed. **Narrower claim:** the *idea* is not missed — the team runs an
active retrieval/reference-conditioning thread (synopsis S7, SimDPS on the
reading list, planned as SaFa-style **hard** injection E4/task#27). What is
un-instantiated is the specific **soft** z0_hat-gradient form as a guide-list
head — a cheap complement to the push-away head and a softer alternative to the
planned hard injection. (The paper is a time-domain model, but the aux term needs
only `x̂0` + a mask, so it is domain-agnostic.) **Test:** `SimAnchorHead` —
retrieve an earlier SAME-latent segment by cosine similarity, add an ω-weighted
`‖(I−M)(anchor − z0_hat)‖²` term over the bridge window, A/B a thematic-return
bridge vs crossfade + hard-clamp.

### TC-LoRA — sigma-dependent control-adapter gain
*Paper 2510.09561 · value: **MEDIUM** · overstated→corrected*

Control-adapter gain is constant across denoising steps (`adapters.py:158`, set
once per `generate()`; `density_schedule.py` varies gain over song-time and
onset-density, never sigma). Making control authority sigma-dependent —
front-loaded at high-sigma structure-forming steps, tapered at low sigma — is a
cheap experiment supported by the coarse-to-fine principle TC-LoRA's intro cites
and by SA3's own LoRA-Interval knob. **Narrower claim:** this is a time-varying
**scalar-gain** schedule — i.e. the T-LoRA approach TC-LoRA explicitly frames as
**insufficient** — NOT TC-LoRA's actual method (per-step hypernetwork weight
regeneration in weight space vs the team's activation-space adapter). TC-LoRA's
Table 2 (1.06 vs 1.56) confounds weight-vs-activation-space and dynamic-vs-static
and does **not** isolate time-modulation, so it is not evidence a gain schedule
beats a fixed gain. Also mildly in tension with the team's own finding that
rhythm is a noise-*invariant* emergent (beat R² 0.80 flat across sigma).
**Test:** make `ControlContext.gain` a function of sampler sigma; A/B a
high-sigma-weighted schedule vs constant gain on onset-density adherence + CE.
Cheaper: reuse the native LoRA sigma-interval to gate the control adapter to the
structure-forming band.

### NA-RFM — gradient-free offline activation-direction steering
*Paper 2602.11395 · value: **LOW** · overstated→corrected*

For the **global/scalar** MIR-attribute subset only (e.g. hardness/"buzz"), the
team has not tried NA-RFM's offline-learned, gradient-free activation-direction
add plus a distributional PCA coarse correction at high noise. **Narrower
claim:** the headline framing over-reaches — the window-restriction insight is
already deployed (LatCH `start_pct=0.4` excludes the high-noise front) and is an
active research thread; NA-RFM is not clearly cheaper than LatCH (LatCH backprops
a tiny head; NA-RFM adds a second full DiT forward per window step, and its 16×
is vs full-model-backprop TFG, not LatCH); LatCH is not the paper's benchmarked
baseline; and a fixed single direction cannot represent the team's time-varying
per-frame targets (chroma/onset/beat). **Test:** pilot on one global target
(hardness) — learn a linear/RFM direction offline, inject over a mid/late window,
compare accuracy + FAD + wall-clock against the existing LatCH guide.

### STAS — massive-activation diagnostic + Detail-Guidance amplification
*Paper 2603.17825 · value: **LOW** · overstated→corrected*

The team has never measured whether SA3's DiT has fixed-channel massive
activations (dumps store frame-mean over tokens, so they *cannot* detect MAs).
Since MAs appear even in image DiTs, a ~30-min diagnostic + a quality-lever
amplification is worth running. **Narrower claim:** STAS's pitched application
(boundary-token amplification for cross-window drift) does **not** transfer —
STAS's boundary-MA structure is an artifact of the video VAE's chunk-wise
compression with an independently-encoded first frame, which SA3's uniform
continuous SAME autoencoder lacks (STAS shows uniform image encoders have no such
pattern); and STAS fixes intra-clip cross-chunk seams within one forward pass,
not the cross-generation drift SA3 faces — that axis is SaFa's latent swap,
already queued as E4. **Test:** compute per-channel activation magnitude vs token
position and sigma on existing dumps; only if fixed MA channels appear, prototype
a mask-and-replace lever.

### SegTune — concat-then-shared-MLP lane fusion
*Paper 2606.02638 · value: **LOW** · overstated→corrected*

`modular_local_cond` fuses lanes by summing per-lane MLP outputs; because the
SiLU is applied per-lane before the sum, it cannot model cross-lane nonlinear
interactions the way `local_add_cond`'s concat-then-shared-MLP (already
implemented) can. The team recorded SegTune's concat>mix result as landscape
awareness but never connected it to their own sum-fusion. **Narrower claim:**
modest architectural nuance, **not** "the exact fusion SegTune's ablation beats"
— SegTune's losing "Mixed" is a naive 0.2/0.8 raw-embedding blend, not a
per-lane learned-projection sum, so the paper is weak direct evidence; the cited
WORKLOG "interference" line is about a genre-consistency loss, not lane fusion;
and modular-sum is a deliberate tradeoff for independently CFG-droppable lanes
that concat-shared-MLP would sacrifice. **Test:** route a 2-lane setup
(onset_density + brightness) through `local_add_cond` vs `modular_local_cond`,
measure per-lane steering accuracy and cross-lane interference.

### UNISON — depth-matched multi-layer text conditioning
*Paper 2605.31530 · value: **LOW** · overstated→corrected*

SA3 conditions every DiT block on a single final-layer T5Gemma embedding
(`conditioners.py:259` `last_hidden_state`, reused for all blocks) — the
single-layer status quo UNISON's Table 8 improves on (FD 22.71→20.46).
**Narrower claim:** this is a team-**known, explicitly-deferred** future ablation
(`papers/arxiv-2605.31530 - UNISON: A Unified Sound Generation and Editing Framework via Deep LLM Fusion.md:16` calls it "not a gap being missed"), so the
"missed" type is wrong; the benefit is modest and shown only on UNISON's 7B-Qwen
double-stream MM-DiT with a param-count/mechanism-confounded baseline; transfer
to depth-matched injection over T5Gemma's bidirectional-encoder last_hidden_state
in SA3's single-latent RF model is plausible but unproven, and it needs a
cross-attn/backbone fine-tune (costlier than usual adapter experiments).
**Test:** extract several T5Gemma encoder layers, add per-depth projectors, route
shallow→deep to shallow→deep DiT cross-attn, A/B CLAP prompt-adherence.

### Diffusion Warm Init — sweep the SDEdit re-anchor decay constants
*Paper 2606.18968 · value: **LOW** · overstated→corrected*

The two `init_noise` decay constants (0.85→0.55) in the opt-in, non-default
`development_renderer` SDEdit re-anchor are hand-set and never swept; a
faithfulness+realism metric sweep could validate them. **Narrower claim:** this
was **not missed** — the sourcebook surfaced it and consciously parked it ("not
an action item now") — and the paper's melodic-faithfulness-to-external-guide vs
realism tradeoff does not map cleanly to longform self-continuation, where the
decay is a variation-vs-prefix-coherence knob and there is no external melody to
score. Only the bare sweep *methodology* transfers. **Test:** if ever revisited,
sweep `sigma_peak` ~0.4–0.9 scoring faithfulness by LatCH chroma/onset probe
distance and realism by the FAD-analog; pick from the knee.

### Cautious Weight Decay — mask the decay term, not the update
*Paper 2510.12402 · value: **LOW** · overstated→corrected*

FusionOpt masks the *update* (`update×grad`) and applies weight decay **unmasked**
at all four sites (`fusion_opt.py:620/625/681/685`), so it never implemented
CWD's actual proposal — masking the *decay* by `update×parameter` sign — a valid
~one-line change. **Narrower claim:** **not a missed insight** — the team already
documented that CWD is weight-decay-only, distinct from their update-mask
finding, and would "plausibly sidestep" their DoRA-divergence bug. CWD is not a
substitute for what the cautious-*update* experiment targeted (taming LMO
wandering in the flat control landscape) — different mechanism. And CWD's Muon
benefit is validated only as pretraining-scale regularization (338M–2B LM /
ImageNet), not in SA3's LoRA/DoRA finetuning regime at `wd=0.01`, where the gain
is unvalidated and likely marginal. **Test:** add a `cautious_wd` flag replacing
`(1 − γ·wd)` with `(1 − γ·wd·I(U·p≥0))` at the four decay sites (leave U
untouched, no rescale), A/B vs plain decay on a goa DoRA run.

---

## Partial

Papers the team **applied** but only in part — a load-bearing companion piece was
skipped. (Kynkäänniemi and DirectAudioEdit, both partial-flavored, are in Top
actionable above.)

### LatCH — the paper's best variant (LatCH-B) is unimplemented
*Paper 2603.04366 · value: **MEDIUM** · overstated→corrected*

The team implements LatCH-F only; LatCH-B (rollout/trajectory-trained heads),
which the paper reports as its best variant (up to 6× lower control error, +2.3
MOS), is unimplemented — and this is already a documented follow-up
(`LATCH_README.md:163`, verdict caveat), not an unrecognized gap. **Narrower
claim:** the headline margins were on SAO's **acoustic conv-VAE**; do not expect
them on SA3's SAME latent, whose diffusion-alignment loss is explicitly designed
to shrink the forward/reverse marginal mismatch LatCH-B closes, and whose single
biggest LatCH-B win (Intensity, 6×) is on a feature that is **dead** on SAME
anyway. For the live SAME feature (beats) the B-vs-F gap is a modest ~15% BCE,
not 6×. The "out-of-domain latents" framing is also overstated — the F head is
noise-conditioned across all t, so it is in-domain by noise level; only the
second-order trajectory-vs-forward marginal differs. **Test:** retrain one head
(onset/beat) LatCH-B-style from short SA3 sampler trajectories; A/B
control-alignment + FD in the [0.4,1.0] window.

> **Correction 2026-07-19** (GHOST-NOTE's direct-measurement LatCH sweep, MASTER
> §5): the "live SAME feature (beats)" phrasing above is now wrong — direct
> raw-feature measurement (not the old MERT-proxy) **confirms beat/downbeat
> activation heads are genuinely dead at any gain**, consistent with this doc's own
> note that rhythm is a noise-invariant emergent (the model rebuilds the beat grid
> regardless, so the head can read it but not push it). Pick the LatCH-B retrain
> target from a head with proven unsaturated authority instead — **onset_envelope**,
> whose old "dead" verdict that same sweep *refuted* (0.7→2.5 on direct measurement,
> target 2.1), is the right choice; do NOT use beat/downbeat. Also relevant to the
> value estimate: that sweep found no continuous head plateaus by gain 512 (bass/
> body/mid/air/hardness/flatness/flux/skewness all climb monotonically past 8192),
> so LatCH-F authority is larger than the old operating-gain guidance implied — which
> weakens, not strengthens, the marginal case for LatCH-B on the heads that already
> steer well.

### AxBench — learn the rank-1 steering direction (ReFT-r1)
*Paper 2501.17148 · value: **MEDIUM** · overstated→corrected*

The team shipped only closed-form diff-in-means for concept steering; AxBench
shows a **learned** rank-1 direction (ReFT-r1) roughly doubles it on steering
(0.543 vs 0.239), and the team's 1/3 mood hit-rate matches AxBench's weak-DiffMean
profile. **Narrower claim:** the finder's mechanism and cost are **wrong** — the
paper states "detection and steering is identical to DiffMean" for ReFT-r1; its
ReLU/TopK gate lives only in the *training objective* and at steer time it
injects the same ungated `α·w`. So there is no gated "inject-only-where-active"
DiT benefit. ReFT-r1's sole edge is that `w` is *learned* via a generation-loss
training loop — which cannot be computed from the static dumps and, on SA3's
flow-matching model, needs the objective re-derived and a real training loop, not
"tens of minutes on existing dumps." The SAE-skip decision itself is **validated,
not a gap** (DiffMean > SAE on steering too). **Test:** fit a flow-matching
adaptation of ReFT-r1's joint objective per mood, A/B its injection against raw
diff-in-means on `mt_dark`/`mt_uplifting`/`mt_relaxing`.

### SA3 (self) — align the adapter t-sampler to the inference schedule
*Paper 2605.17991 · value: **LOW** · overstated→corrected*

The control-adapter trainer's default t-sampler (plain `logit_normal`, centered
~0.5, length-blind) under-weights the high-noise band emphasized by the model's
length-invariant logSNR-uniform inference schedule; defaulting the adapter
t-sampler to the already-implemented `log_snr_uniform` would better match train
to inference t. **Narrower claim:** the length-dependent-shift mechanism is
**refuted** — per the SA3 paper (lines 1308–1309) and the medium-base config (no
`sampling_distribution_shift_options` → `LogSNRShift(rate=0)`), inference uses a
length-**invariant** schedule, so there is no larger mismatch at T=4096 and
applying the base's length-dependent shift to adapter training would actually
*mismatch* inference. What survives is a modest, length-invariant t-distribution
alignment tweak using tooling that already exists. **Test:** default the adapter
t-sampler to `log_snr_uniform`; A/B a chroma384/onset adapter at T=4096.

### SHIFT — per-step classifier-gated steering strength
*Paper 2604.09213 · value: **LOW** · overstated→corrected*

`eval/steer_concept_direction.py` holds α constant across all timesteps (only the
*direction* is sigma-bucket-matched); SHIFT's per-step concept-presence-gated
strength (eqs 13–14) is unimplemented, and could raise the usable-α ceiling and
cut high-α (|α|=6) structure-breaking. **Narrower claim:** already a documented
open item in the verdicts file, not overlooked; **not** a small hook tweak (needs
a new per-step activation classifier **and** regime inversion — SHIFT's gate is
for concept *erasure*, amplifying while the concept is present, whereas the team
does mood *addition*, so a literal port amplifies the wrong way); and it would
**not** recover the "dead"/one-sided moods, which are direction-quality failures
a strength gate cannot fix — only the high-α degradation. **Test:** projection-gated
α (scale by activation's projection onto the unit direction, reusing existing
diff-in-means directions), A/B vs static-α ladder.

### ARC-Forcing (LMDM) — the adversarial rollout objective is absent
*Paper 2605.22717 · value: **LOW** · overstated→corrected*

`eval/arc_rollout_dataset.py` builds exposure-bias/DAgger regression data
(drifted single-block context → true continuation) — still single-block-level
supervision, which the paper explicitly names as the disease. The load-bearing
pieces (adversarial full-rollout objective L_R + caption-contrastive L_C, and a
base-model discriminator warm-started on ~30s segments) are absent. **Narrower
claim:** this is an explicitly-labeled incomplete "part 1" of an unsubmitted task
the team already files as UNTESTED and documents as an adversarial-rollout
mechanism — not a wrong objective being silently baked in. (Contra the finder,
the team **does** ship `stable_audio_tools/models/arc.py` + `training/arc.py`,
byte-identical to upstream single-block ARC.) And transfer to SA3's
bidirectional-window (non-AR) Longform — where the observed failure is loopiness,
not AR compounding drift, and the prerequisite LMDM KV-cache architecture is
unbuilt — is itself unproven (same mismatch that nulled the rope_jitter/LoL
port). **Action:** before submitting the LUMI job, either rescope the pipeline as
honest "exposure-bias scheduled-sampling," or extend to the real recipe
(multi-block rollouts + base-init discriminator with L_R+L_C + ~30s warm-start)
and measure the ARC-vs-regression delta.

---

## Counts

| Type | Count | Confirmed | Overstated→corrected |
|---|---|---|---|
| Missed | 14 | 2 (TADA, DirectAudioEdit) | 12 |
| Partial | 6 | 1 (Kynkäänniemi) | 5 |
| Wrong | 0 | — | — |
| **Total** | **20** | **3** | **17** |

By value: **HIGH** 1 (TADA) · **MEDIUM** 9 · **LOW** 10.

The three **confirmed** gaps (TADA eval protocol, Kynkäänniemi interval-CFG,
DirectAudioEdit dynamic target-CFG) are the cleanest actionable wins — all on
infrastructure the team already runs, all cheap. The 17 overstated items were
each narrowed by the verifier; act on the corrected claim, not the finder's
original framing. Several "missed" items (Gram-Schmidt, SimDPS, UNISON, CWD,
warm-init) turned out to be team-*known* deferred TODOs whose only defect is a
stale line in `paper_verdicts_data.json` — worth a cleanup pass on that file.
