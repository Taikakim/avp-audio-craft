# WINTERMUTE — journal
> the rigor — the adversary who makes the work true, not merely beautiful.

## 2026-07-08

### finding · the mid-band a2a loss is the DiT abandoning harmony, not input fragility
Composed my latent-dim×feature xcorr with C's DiT layer×feature map, via a noise-matched
input probe (`Misc/latent_noise_fragility.py`, RF noising matched to C's extraction). This
**overturned my own prior**: I'd hypothesised mid-band energy was uniquely fragile at the
input. It isn't — at the raw noised latent *every* feature collapses uniformly toward R²≈0 by
σ0.8. The asymmetry lives entirely in the DiT rebuild. beat_activation is rebuilt to R² 0.80 at
L14 **identically across σ 0.2/0.5/0.8** (noise-invariant emergent — synthesised from
conditioning+coarse periodicity, not read off the collapsed latent). rms_energy_mid (gain
+0.01, peak 0.19→0.08) and hpcp (gain +0.07, peak 0.50→0.41) are barely rebuilt and fade with
noise = degraded-and-abandoned. **Mechanism for Kim's ear-finding:** under a2a mid-noising the
model keeps rhythm locked but can't reconstruct harmony/melody, so the melodic slot gets
corpus-mean filler (the U-shape posterior-average). Beat survives, melody goes generic.
Actionable: chroma-morph guidance is now *justified* (harmony must be re-supplied); C's block-13
rhythm heads get a noise guarantee (target invariant at any nl). docs/layer-feature-noise-invariance.md.
Good reminder that measuring beats a clean-sounding prior — my "uniquely fragile" story was wrong.

### finding · validated the loop-attractor recurrence meter — frame-level saturates, novelty works
C+Kim found the a2a loop attractor (nl .55+ full tracks: generated regions loop one phrase
for minutes; docs/a2a-loop-attractor.md) and designed a breathing-noise controller driven by
a recurrence meter. I validated that primitive on the real renders (kaikkialla/vapausvoima
evr1x ladders + sources). NEGATIVE: the naive FRAME-cosine recurrence rate SATURATES (0.99
for source AND every nl — tonal music trivially recurs frame-wise), so the sketched trigger
fires on everything — don't build on it. POSITIVE: a PATCH-level (4s) meter works —
loop_strength rises + novelty (1−max sim to preceding 8–40s) collapses at nl .55–.60
(kaikkialla novelty .059→.029 −50%; vapausvoima .044→.013 −70%), matching Kim's ear, and
RECOVERS at .70 = the same overshoot band as my earlier movement U-shape (two meters, same
window). Design steers for #35: drive by the NOVELTY floor not raw recurrence; per-track
self-calibration is NECESSARY (0.968 loop = looping for one track, ~source for another — no
global threshold), vindicating C's R_src design. scratchpad/recurrence_meter{,2}.py. Pattern
worth keeping: validate the meter on real data before anyone builds the controller on it.
UPDATE (v3, Kim's feature correction): chroma is tonality-biased (breaks on non-tonal
psytrance) and rhythm is constant (saturates) — the loop is the whole SPECTRAL IMAGE. Switched
to per-band-whitened log-mel patches (z-score each band so the steady kick flattens, only
varying content drives similarity) → dramatically cleaner: kaikkialla novelty 0.659→0.471 at
nl.55 (~8× the chroma separation) and the .70 overshoot now jumps ABOVE source (0.765 vs 0.659).
Translation for C's latent controller: whiten each 256-d SAME channel over the window before
cosine, else constant-energy channels bias it to 'always looping'. recurrence_meter3.py.

### finding · independent triangulation of C's avp tempo-instability + rank-dependence
C (with Kim's "self-similarity" wager) found avp adapters generate tempo-unstable music
(multimodal conditioning: 7 tempo variants under one caption → mode-hops mid-clip). I
triangulated with a DIFFERENT algorithm (autocorr tempogram, per-5s-window folded
dominant-tempo, within-clip IQR): CONFIRMED. Frac stable (IQR≤2bpm): goa-ep7 control 100%
(my meter ceiling, reproduces C's locked baseline), r16_plain 54%, r16_familiarity 46%
(worst), **r128adj 86%**. NEW reusable fact: the instability is **rank-dependent** — r128
nearly recovers stability, so if a rerun can't drop/caption tempo augs, higher LoRA rank
alone substantially mitigates. Honest caveat: real avp full-tracks measure 80% stable in my
meter (not C's 100%) — my per-window librosa tempo is noisier on organic/ambient material
(C's folded method is the cleaner headline instrument), and avp source genuinely isn't
metronomic. Bracket: goa 100% > real-avp 80% > r16 ~50% → r16 adapters sit below their own
source's stability = they genuinely ADD instability. `scratchpad/tempo_stability.py`.

### mixed · avp aug carries a mild transient-softening substrate; my warble proxy was confounded
Tested C's "stretch-artifact-texture" hypothesis at the source (15 tracks × 8 Bungee variants,
drums+full_mix). POSITIVE, clean on the pitch axis (duration-preserving): pitch shifts genuinely
soften transients (onset-kurtosis −0.14…−1.02) + dull HF (−0.18pp). So 88% of the avp training
data carries a mild "softer/duller" texture, uniformly worse-direction → plausible substrate for
C's glitchy-DoRA verdict. NEGATIVE/dead-end worth logging: my sustained-frame spectral-flux
"warble" proxy is **confounded by tempo→events-per-frame** (tempo+10 +12.9, tempo−10 −13.6, symmetric
sign-flip = density artifact, not phase-vocoder warble) — do NOT use sustained-flux as a glitch meter
across time-stretched pairs. Couldn't objectively confirm "glitchy/disjointed", only "softer/duller".
C's originals-only A/B stays decisive. `scratchpad/aug_artifact_probe.py`.

## 2026-07-03

### negative · meter-in-the-gradient does NOT transfer from onset to genre
Wired CONTINUITY's latent genre meter (R²=0.85) into the fpC trainer as a genre-consistency loss
(the FusionCC recipe: probe(z0_hat) → match the requested genre, t-gated, held-out-dim guard).
Trained clean overnight — the probe-hack guard stayed green end-to-end, tripwire never fired. But
it made steering **worse**: Goa authority 0.92→0.65, Psy 0.46→0.03 (collapsed). Disentangled the
over-training confound with a checkpoint trajectory: at *matched* length (ep5) gcc=0.41 vs
baseline=0.92, and gcc *improves* ep5→ep12 (0.41→0.69) — so it's the fp loss itself, not drift.
The tell is the null-fingerprint output: baseline sits on a committed trance blend (0.23), gcc
collapses to genre-ambiguous (Experimental 0.01). **Mechanism: onset is fine-grained and
RF-invisible, so its meter ADDS signal (why FusionCC won); genre is a GLOBAL property already
present in the real crop's reconstruction, so its meter adds no new information — only lossy
interference, dragging the output toward the probe's smoothed genre manifold (blander, less
genre-committed).** Recipe scope now known: it helps for fine-grained properties RF-loss can't see,
not global ones it already captures. Ship the original fpC; the perfectly-held guard means this is
an honest "method doesn't help here," not a broken run.

### finding · the style adapter steers genre — fpC wins, and it's corpus-limited
Ran the eval RF val loss can't do: hold the text prompt constant, vary *only* the fingerprint's
genre, then measure the output genre with the discogs-400 head. Result — conditioning on **Goa
drives the measured output to Goa at 0.92** (fpC) vs ~0 baseline: real, strong steering. **fpC
(style-only, genre+year) beats fpA (style+groove) decisively** — the bpm/sync groove dims *dilute*
the genre signal. Steering strength tracks corpus frequency (Goa≫Psy>Trance≫tail): the adapter
learned a Goa↔Psy dial; the sparse tail is **data-limited, not architecture-limited**. The
benchmark's RF-loss tie (0.7865 vs 0.7870) was blind to all of this — the whole point of building
the genre eval. Published as a same-playhead eval GUI on the site.

### finding · the confound I almost shipped — minority-genre nulls aren't adapter failure
First eval pass picked Techno/Ambient/Downtempo as targets; all steered to nothing. Nearly wrote
"adapter only makes Goa." Caught it: those are 5–15% of a Goa/Psy corpus — a null there means the
model *never learned them*, not that steering fails. Re-ran on genres with real support. The rigor's
job is to not let a rigged test masquerade as a verdict.

### fix · the silence.npy dataloader crash (clean root cause)
Variant B crashed at step ~1180 on `silence.TIMESERIES.npz` missing. Root cause: `silence.npy`
(1 of 5401, a junk crop, no `.json`/`.npz`) — the scalar-mode filter dropped it, but fingerprint
mode has `scalar_field=None` so it survived, and B is the only variant that loads the timeseries.
Fixed at the source: drop crops with no `.json` companion in every mode (`b0153f0`).

### tool · the fleet's public face — private repos, zero-token dialogue, eval GUIs
Kim's call: all SA repos private (can't police injected text in a public repo), served content on
aavepyora is the public surface. Built the pieces: a **deterministic dialogue colorizer** (systemd
file-watch → styled, colored log every round, no LLM in the loop), the **FusionOpt explainer**, the
**eval landing + browsable audio tree**, and the **genre-steering eval GUI** (same-playhead cells).
`fusion-optimiser` stays public — the one repo with no agent-coordination text to inject into.

## 2026-07-02

### finding · genre-conditioned SA3 style adapter (design → tested plumbing)
Designed and half-built a **genre-conditioned FiLM style adapter** for SA3. Thesis: the
`sa3_control` adapters already made better Goa than the DoRA finetune *because* they condition on
audio-derived MIR, not the broken text prompt — which turned out to be a Spotify/MB metadata genre
dump (`genre: psytrance, title:…, bpm:…`), never a sonic description. Shipped & tested: the genre
vocab (K=11, ≥303-crop min-support), per-crop genre-vector plumbing, the `FingerprintEncoder`, and
the dataset fingerprint + the **window-scalar alignment fix** (volatile onset/energy from the sliced
timeseries, not the crop-level `.json` scalar — a bug that also affects the existing onset/energy
heads). Discogs genre vectors written to all 5400 crops (100% coverage).

### finding · the discogs-400 genre head is multi-label, not softmax
Caught on verifying the scan: a crop reads Goa 0.61 *and* Psy 0.75; the K values sum >1. So the
spec's "raw softmax + `other = 1−Σ` simplex" premise was wrong — `other` is vestigial (clamps to 0).
Upside: multi-label is a *richer* signal and **moots the normalization-distortion worry that drove
the whole raw+other design**. No re-scan needed; spec corrected.

### finding · SA3 inference speed shootout — corrected my own soft numbers
Built the torch/ONNX × CPU/GPU speed matrix, then the rigor turned on its own output: (a) RTF is vs
**realtime**, not vs CPU; (b) the "5 min CPU vs 42 min GPU" line conflated a one-time ~40-min
MIGraphX AOT *compile* with generation; (c) "adapters only ~3× faster on GPU" was **two
mis-measurements** (LATCH on the fp32 *verify* path; control on ONNX-MIGraphX not torch) — remeasured
both at ≈ base speed, **RTF ~24×**. Corrected the stale MASTER §5 "LatCH must run fp32" — the DiT
forward is under `no_grad`, so only the head needs fp32.

### infra · cross-instance hardening (edge cases)
The rigor's job on the shared plumbing was catching what breaks: the original **unicast OSC channel
couldn't fan out** — a co-listener would *steal* the night-board's packets (SO_REUSEPORT
load-balances, doesn't duplicate) → drove the multicast v2. The public dialogue-log mirror had a
**`mktemp` → 0600 perm trap** (Apache can't read 0600 → 403); its 404s were a **stale cached
WordPress 404** (the file was fine) — diagnosed server-side, fixed with a scoped `no-cache`
`.htaccess`. Audited the public log for leaked secrets (**clean**), then wrote the "logs are PUBLIC,
no secrets" rule into MASTER §4 + the OSC spec + all four `CLAUDE.md`. Adopted GHOST-NOTE's
`agent_dialogue.py wait` over my hand-rolled wake trigger — one tested wake path beats five drifting
copies.

## 2026-06-28

### finding · the SA3 LatCH head sweep — operating gain is ≈512, not 48–96
Swept all 14 SA3-medium LatCH guidance heads × {low,mid,high} target × 3 prompts, measured with MERT
(magnitude) + Audiobox (quality). **Gain 128 is a dead zone** (feature moves <1 dB); the real
operating point is **≈512** — ~10× the documented figure, a monotonic ladder 128→1024. The energy
heads (rms_bass/mid) steer strongly; the **activation heads (beat/downbeat/onset), hpcp, kurtosis are
dead at any weight**. And the first pass mislabeled the two *best* heads "dead" because I read them
with the upper MERT layer (melody/harmony), blind to a bass-RMS change — fixed by using the mid layer.

## 2026-06-26

### negative · the ±16 BPM augmentation is too mild to disentangle — caught before the full run
Kim's disentanglement-by-augmentation idea (pitch+stretch aug × onset_per_beat target) was sound in
principle, but before committing the run I checked the numbers: training corr(onset_per_beat, bpm) =
−0.81; augmenting 25% at ±10–16 BPM only moved it to −0.805 — a rounding error against Goa's ~60-BPM
span. Meaningful decorrelation needs ±30+ BPM at ~100% coverage (heavy stretch → quality cost, doubled
dataset). Pivoted: test the tempo-invariant *target* alone first (it blocks the forward shortcut with
no aug at all); widen aug only if the inverse shortcut shows. A weak helper dressed as a fix.

## 2026-06-19

### negative · chroma correlation is a mode-collapse trap — it declared wins twice
Training the SA3 riffer control-adapter, I used chroma correlation to a reference as the match metric.
It fooled me into declaring success *twice*: a **collapsed** adapter (same output for every reference)
still scores chroma ≈0.9 against any Goa reference, because they share keys. The metric literally
cannot see mode collapse. The fix is a **cross-reference audio difference** — generate with ref A vs
ref B (same seed/prompt), RMS-diff the outputs; low diff = collapsed. The most expensive kind of wrong
is the metric that agrees with you.

## 2026-07-06

### finding · avp personal-corpus prep + the whole-track paradigm (reuse, don't re-cut)

Prepping Kim's own music (Aavepyörä/Summamutikka) as a LoRA/DoRA conditioning corpus on the
UUID drive (`.../avp-analyzed`). Key paradigm correction worth writing down so nobody re-cuts
short crops again: **for SA3 LoRA/DoRA training we do NOT pre-cut fixed crops.** Store
**full-length latents + whole-track 100 Hz timeseries**, and sample a random beat-aligned
window per step — the consumer slices `[start,end]` and resamples to the latent's `n_frames`,
so any training length works.
- Producer: `mir/src/spectral/whole_track_timeseries.py` (100 Hz `.TIMESERIES.npz`, per-stem too).
- Consumer/slicer: `stable-audio-tools/scripts/whole_track_target_source.py`
  (`WholeTrackTargetSource.get(key, feature, start, end, n_frames)` → `resample_axis0`).
- Encode unit = **4096-frame (≈380 s) crops at begin/mid/end**, ~2/track, overlapping for tracks
  under 8192 frames (verified against `latents_sa3` companion `relative_position_start/end`).
- I mistakenly ran the OLD 11.9 s crop pipeline first (config default) — deleted those; separation
  + augmentation were paradigm-independent so they were reused, not wasted.

Tools built (reusable):
- `mir/src/tools/augment_tracks.py` — **Bungee** pitch/tempo augmenter (129× RT), runs under
  **mir/.venv** (bungee_python lives there, NOT mir/bin/python). Spec: pitch ±1/±2 st; tempo
  ±5/±10 % rounded to integer BPM **capped at 155**, deduped; augments the **4 stems too**
  (bungee-shift the clean stems — faster + higher quality than re-separating), per-variant track
  folders; ProcessPool parallel, resumable.
- `mir/src/tools/inject_trigger_caption.py` — writes the aavepyora/aavepyörä trigger caption
  (deterministic per track) in place of Flamingo, for the personal-style LoRA.

### negative · corpus-pruning + pgrep self-match lessons

(1) orphan-pruning an analyzed corpus by matching **only `.flac`** source
files wrongly trashed folders for `.wav`-source keepers (3 of mine) — match **all audio extensions**.
(2) `pgrep -f 'script.py'` inside a shell whose own command line contains that string self-matches —
use `ps | grep '[s]cript'`. Reversible-delete (move to trash dir) caught the .flac bug harmlessly.

## 2026-07-07

### finding · the recurring render-clipping bug, quantified (Kim: "we fix this every second day")

Ran mir's saturation/clipping calc (`mir/src/spectral/saturation.py` + a peak/clip-fraction
pass) over all 791 SA3 eval renders from the last 48h (`Mantu1/sa3_lora_runs`). Verdict:
**74% have clipped samples, 77% peak at exactly 0 dBFS** — the raw SA3 output (>1.0 peaks)
is being CLAMPED to [-1,1] on write, not peak-normalized. Worst 3.6% of samples clipped
(psy prompt, newcap5/evr3x arms). **Root cause is INCONSISTENCY, not a universal miss:**
`newcap8_promptstyle_longform` is clean (−0.5 dB headroom, 0% clip) while density_control /
promptstyle / bracket clip 67–100%. So the peak-normalize fix EXISTS and works — it's just
not applied in every render script. Each new render script re-introduces a raw/clamped save →
that's the "every second day" recurrence. **Durable fix: route EVERY SA3 render/save through
`sa3_control.audio_io.save_audio()` (peak-normalize), or add a written-file assert (no sample
> target ceiling ~ −1 dB).** Not a one-off re-render — a centralization/guard problem.
Audit script: scratchpad/clip_audit.py. See [[avp-corpus-overnight]] for the parallel MIR work.

### finding · first Kim-validated usable transition

Kim on `chroma_morph_barsnap`
`kaikki2angelic__w1025_nl42_chroma`: *"a completely useable transition."* Recorded in the
run's `run_meta.json` findings (alongside the earlier negative: slerp-midpoint @ nl .55
= identity-losing drone). Operating point that worked: bar-snapped window ~1025, nl 0.42,
chroma-morph ON. The chroma/plain A/B and the nl bracket did their job — the method
(bungee beatmatch + latent slerp + graded a2a refine + stem-chroma LatCH morph) is now
listener-validated, not just metric-validated. C's method, G's pages, my deploys.

## 2026-07-08

### finding · the latent encodability screen exists now

Kim asked whether we ever had
the latent-dim × feature-timeseries correlation over the dataset — we didn't (only pooled
scalar probes + the un-run DiT-layer map). Built + ran it (999 crops, CPU): frame-level
ridge R² ranks features flux .84 → vocals .02, and the thin tier (beat/downbeat activations)
is exactly the set of guidance-dead heads from the 06-28 sweep — a minutes-cheap screen that
predicts head viability before training. Encoding is distributed (no single steerable
channel; family clusters). Expectation-order for the LUMI all-features array. Matrix:
`mir/stats/latent_dim_feature_xcorr.csv`.

### finding · Kim's ear vs the mid-noise band — ear wins, regime explains

He heard a2a
melodies going stereotypical at nl .4–.55. Measured on the a2a_kaikkialla ladder: chroma
flux floors exactly there (−20% vs source) then overshoots source at .7 — U-shape ⇒
posterior-averaging regime artifact (melodic contour destroyed at that SNR, model fills
with corpus-mean filler; CFG sharpens), NOT a static prior. Matches SDEdit projection +
Kynkäänniemi interval-CFG + EDM churn literature. The principled fix is the one we already
built: chroma-morph guidance re-supplies the destroyed evidence in-band. Tool:
`mir/src/tools/melodic_movement_ladder.py`.

## 2026-07-09

### finding · tempo_iqr meter — LR-window hypothesis confirmed by the predictive test

tempo_iqr meter (mir/src/tools/tempo_iqr.py) run on the fresh arm-G + r16-fine ladders. Arm G (r128@lr1e-4) is flat tempo-stable across the whole 3000-step run (never collapses), vs r16@lr2e-4's narrow window. Meter independently reproduces C's ep31 notch (ep31-34 = narrow stable island, resolving the spike-vs-plateau Q). Tool fix: rank ckpts by MEAN iqr, not median (median floors at 0 on mostly-stable ladders). Feeds C's ship-checkpoint picker. WORKLOG 2026-07-09.

### finding · pending-D reanalyze complete; subprocess-isolation was the right call

All 1346 avp
augmentation variants now carry the full CPU MIR feature set (rms bands / spectral / chroma+key / bpm /
onsets / syncopation / timbral / per-stem), measured not derived — augs change signal non-analytically
(transient softening, HF dulling). Two in-process architectures failed first: a ProcessPool poisons on one
madmom **segfault** (BrokenProcessPool), and `as_completed` **hangs forever** on one worker stuck in an
untimed madmom step (a silent 3-hour stall). The fix that held: `subprocess.run` per variant with a hard
600s timeout — a stuck child gets SIGKILLed, a crash surfaces as a return code, the ThreadPool driver is
never poisoned. 0 quarantined, ~10h. The 255 bpm-canary flags are **madmom metrical ambiguity, not
transform errors** (69% cluster at clean 2×/1.5× ratios; the canary doesn't octave-fold the compare so it
over-reports). Tool: `mir/src/tools/reanalyze_variants.py`. Phase-2 GPU features (audiobox + essentia)
deferred to a card-free window.

### finding · LUMI is EFP-WebUI-submitted, NOT raw sbatch (the finding that saves three failed attempts)

Our LUMI-G allocation is accessed through the EuroHPC Federation Platform. Jobs submit ONLY
through the web platform (`workflows.my-eurohpc.eu`) — the SSH login's default account is `default_no_jobs`
(MaxSubmit=0) precisely because direct Slurm submission is deliberately disabled. I burned three `sbatch`
attempts (AssocMaxSubmitJobLimit → Invalid account/partition combination) before Kim's hunch ("do jobs have
to be configured in the WebUI?") + the quickstart doc confirmed it. The `sbatch/*.sbatch` script BODIES
still carry over — they get registered as EFP *Job Scripts* and launched via *Workflows*, with
partition/account/resources set in the WebUI (dropdowns), not by `sbatch`. Partition is `standard-g` ONLY
(whole-node-exclusive billing caveat). SSH stays useful for data staging / container build / fetching
results. Bundle + access-model block documented in `SAO/lumi/README.md`. Blocked on Kim reporting the
Create-Jobscript form layout so I can shape the hello-world job for the WebUI abstraction.

## 2026-07-10

### finding · the layer map exists — acoustic attributes live LATE, in self_attn+ff, NOT cross_attn

Ran the Axis-1 causal localizer on SA3 medium-base (`control/sa3_control/layer_patch_map.py`):
TADA-style activation patching extended past cross-attention to all three module types,
scored by target-aware MIR meters, 1728 cells (4 acoustic concepts × 3 prompt-pairs ×
2 seeds × 24 blocks × 3 modules), ~40 min GPU. **All four attributes (onset density,
bass weight, brightness, noisiness) localize to blocks ~16–23 via self_attn and ff;
cross_attn medians are 0.00 at every layer** — the opposite shape from TADA's
cross-attn-12/13 bottleneck (categorical semantics ≠ acoustic realization). Rhythm
engages self_attn earlier (12–19) than timbre — temporal attribute, temporal-mixing
module. Routing implication: acoustic-control DoRA rank → late self_attn+ff as a SOFT
AdaLoRA prior (TADA's −21% hard-mask warning). Methods lesson: plain librosa
onset_detect over-fires ~3× on textured drones — the validated meter is p95-normalized
strength-gated peak-pick (dense 9.2/s vs sparse 4.2/s). Full FINDINGS.md in
`sa3_control_runs/layer_map_2026-07-10`. Follow-ups: layer-group patching
(distributed-mechanism test), timestep-resolved patching (feeds Axis-2 directly).

### finding · why scalar-head guidance buzzes — constant targets demand temporally-flat audio

The quality-gated re-bracket (#49) turned the gain-512 negative into a mechanism: **all 16
cells fail CE/PQ at every gain 32–256 while steering the right direction in every one** —
the damage is gain-independent, so the knob was never the problem. A scalar head guided to
a constant per-frame target demands temporally-FLAT attribute values, and flat hardness
over time IS the buzz Kim heard ("dentist's drill" = constant HF). Timeseries heads steer
acceptably because their targets vary in time. Fix: a pooled-mean guidance loss
(match `mean(pred)` to the scalar, model distributes the attribute naturally) — one
loss-type in `latch_guided`, folded into C's T2 branch on the same seam. Until it exists:
scalar heads are probe-quality, not guidance-ready (depth/booming retrains deferred).
Board: `renders/hardness_bracket_2026-07-10` (hear the buzz). The quality gates paid for
themselves on their first run.

**CORRECTION, same evening — the flatness hypothesis is FALSIFIED.** Implemented the
pooled-mean loss (`scalar_pooled`, committed) and re-bracketed: near-identical CE/PQ
damage at every gain including 512 (19/20 cells fail; the lone pass is noise). Pooling
explicitly permits temporal variation, so the constant-target-flatness story is dead.
Revised suspects: (1) **degenerate Jacobian** — a head trained on constant per-frame
targets learns near-identical frame mappings, so any loss through it pushes spatially
uniformly regardless of the loss's shape; (2) **shortcut feature** — corpus hardness may
correlate with distortion, making the head's steepest-ascent direction *be* distortion.
Both testable: retrain on windowed timbral `_ts` (time-varying targets), and
spectral-diff steered-vs-base. Two wrong hypotheses killed in one evening at ~10 min
each — the quality-gate directive is cheap science.

### negative · hardness steer at gain 512 — the meter moved, the audio broke (quality-gate lesson)

Kim's ear on my steer-verification clips: **both steered outputs are perceptually ruined**
("down = a slab of concrete dragged on rock, up = a dentist's drill") despite the target
meter reading monotone and near-target. The guidance moved timbral_hardness by destroying
the audio, not by steering timbre — gain 512 was borrowed from the energy-head regime with
NO quality gate. **The lesson (Kim's directive): every steer eval runs the established
quality metrics (Audiobox CE/PQ, zero-crossings) alongside the target meter** — a
target-only readout can pass while the output is garbage. Direction is right, so the head
is plausibly fine at a lower gain / different ρ-μ: re-bracket with CE/PQ/ZCR gates before
any further claims. Annotated in the run sidecar + the live page. The 06-28 sweep protocol
had this gate ("CE holds"); I skipped it in the smoke — don't.

### finding · first scalar-target LatCH head — hardness steers in the strong class

Kim asked for a LatCH head against the AudioCommons timbral-hardness model (scalar —
the meter is scalar-per-call). Added a `scalar_json` target-source to the latch trainer
(constant `(1,T)` target from the per-crop `.TIMBRAL.json` sidecars G extracted; the
head learns a pooled readout), trained on 5398 crops with the validated EMA recipe
(loss .49→.127 ≈ 87% of variance). **Steer smoke at gain 512: baseline hardness 69.4 →
steered-down 60.2 (target 59) / steered-up 77.3 (target 73)** — monotone, near-target,
17-point spread (±2.2σ of the corpus), measured with the actual `timbral_hardness`
meter. First scalar-target head, and it lands in the strong-steer class alongside
rms_bass/mid — the energy-family gain regime (≈512) holds for timbral scalars. Depth
and booming heads are now a one-command retrain each. Ops lesson: co-residency with a
jobs=12 extraction OOM'd the first launch at the 93 GB ceiling — 2 dataloader workers
+ no `--compile` coexists fine (compile is marginal for a 5-7 M head).

### finding · avp own-music dataset-release spec drafted

Kim wants to publish his own CC music as a
distributable SA3 dataset (latents + all timeseries + creator captions) by model-release time. Brainstormed
to a spec with a governing **invertibility rule**: release representations in inverse proportion to
reconstructability — full-mix audio (his licensed work) OK; hand-crafted MIR timeseries (non-invertible) OK
for all stems; neural embeddings (partially invertible) → clean subset only; SA3 latents (decoder-invertible
= audio-equivalent) reproduce-only, never over sample-library-contaminated stems. Canonical build =
clean-room regen on LUMI from the original waves (fits Kim's "document everything from scratch" ethos, now
affordable on the 5000 GCD-h). Spec:
`mir/docs/superpowers/specs/2026-07-09-avp-dataset-release-design.md`. Awaiting Kim's review.

## 2026-07-11

### finding · two Gemini Deep Research reports triaged + filed (long-form coherence, activation steering)
Triaged Kim's two commissioned Deep Research runs, grounding both against our code rather than taking them
at face value. **Long-form coherence:** verified SA3's DiT uses RoPE (`transformer.py:258`) and both failure
paths have code; citations 6/6 real. **Activation steering:** independently reaches OUR layer-map conclusion
(semantic bottleneck at 2–4 mid blocks) via the same TADA causal-tracing lineage — external corroboration of
our localizer — and hands us the operational CFG rule (steer the CONDITIONAL branch only). Both formatted
verbatim to `papers/deep-research/2026-07-11-*.md` (tables + refs reconstructed, stripped-LaTeX flagged) and
14 load-bearing PDFs downloaded to the local library (untracked per convention; the whole collection is
local-only, 0 in HEAD).

### finding · caught a mechanism/provenance bug before publishing the layer_map convergence page
Folded the three-way convergence (mir causal layer map + TADA + C's held-out mood AUC, all → mid-stack L8–18,
plus SHIFT's timestep-invariant directions replicating on SA3 at cross-σ .93–.99) + C's Phase-3 steering
payoff into the layer_map page as playable α-ladder A/B. **Before shipping, caught that C's run_meta sidecar
said "both CFG branches" while her posts said conditional-only** — held the page, flagged it; ground truth was
conditional-only (stale sidecar wording, now fixed at source + provenance-noted in all 4 metas). The 19×
mt_dark result is fully consistent with the report recipe. The honest failure cells (mt_relaxing DEAD despite
.889 AUC; mt_uplifting anti-direction-only) are the most interesting: probe-separable ≠ causally-steerable.

## 2026-07-12

### finding · RoPE jitter is null-by-construction on longform.py — the loop is conditioning-driven, not positional
Kim asked me to run the LoL Multi-Head RoPE Jitter experiment (my own #1 rec from the long-form triage).
Built + CPU-verified the jitter as a clean reversible toggle (`stable_audio_3/inference/rope_jitter.py`:
scale=0 bit-exact no-op, scale>0 makes heads phase-distinct, restores byte-identical). **But tracing the code
overturned the premise:** LoL's sink-collapse needs RoPE positions to EXTEND beyond the native window so
distant frames alias onto the clamped prefix. Neither SA3 path does that — `longform.py`
(InpaintContinuation) regenerates each window at RESET positions 0..W, and `fifo_infinite.py` uses a fixed
256-frame buffer at positions 0..256 (its custom per-frame code is timestep, not position). So the aliasing
the jitter fixes never arises → jitter is null there. The `longform.py` loop is the OTHER mechanism the
report names — self-similarity under a static prompt conditioned on the clamped prefix — which is exactly why
the prompt-arc works. **Right lever = the conditioning-side fixes: Incantation mask (bar the prompt's
cross-attn from clamped history) + SCA.** Jitter code kept ready for a future growing-single-window FIFO
where it WOULD apply. Good case of check-the-mechanism-before-the-fix: the build was cheap, the finding
saved a GPU experiment aimed at the wrong lever. Awaiting Kim's call: jitter confirmation vs Incantation-mask.

### finding · overnight experiment queue — two long-form fixes null, hardness shortcut confirmed, rank-vs-weight
Kim's overnight batch (he slept, ~7h window). **(1) Onset re-score** on the honest p95-gated meter:
FusionCC (A_cc_v2) 0.77 > plain Fusion (E_fusion_v2) 0.717 on the matched grid — the FusionCC metric
edge is real, not the old over-firing artifact (lr2e5-best 0.921 but on a wider grid, range-inflated,
not comparable). Folded into onset narrative §6. **(2) Both training-free long-form fixes NULL on
longform.py:** RoPE jitter (built `rope_jitter.py`, bit-exact no-op at scale 0) 0.704→0.709; Incantation
mask (`incantation_mask.py`, bar prompt cross-attn from clamped history, 24 blocks) 0.671→0.674. The
mechanism the nulls reveal: longform's loop is **self-attention continuing the clamped prefix**, not
positional aliasing (jitter target — positions RESET each window) nor cross-attn echo (mask target). The
lever is conditioning richness (the prompt arc C sees working). Caveat: longform.py at 240s static barely
loops (early 0.696→late 0.715) — the real loop lives in the a2a nl-0.55 regime, so the definitive test
belongs there. **(3) Hardness scalar-guidance buzz = SHORTCUT FEATURE confirmed** (`hardness_spectral_diff.py`):
the UP/harder direction adds >5kHz energy (hi-frac 0.16→0.88 with gain) + zcr blowup +0.14→+0.49 = a
distortion signature, exactly Kim's "dentist's drill" ear-verdict. Fix = Gram-Schmidt orthogonalize vs
brightness (per the activation-steering deep-research). Degenerate-Jacobian suspect untested (no windowed
timbral _ts exists). **(4) Rank vs DoRA-weight** (Kim's hypothesis, from matrix clips): rank-16 glitches
harder at w1.5 than rank-128 (hi-frac 0.219 vs 0.165, zcr +0.032 vs +0.005 = 6×) — CONFIRMED; low rank =
crude approx, scaling amplifies error into HF distortion. **(5) Comprehensive metrics DB** (`clip_metrics.py`
+ `clip_metrics_audiobox.py`): 10 CPU metrics over all 31646 eval clips + Audiobox CE/PQ (GPU, model-matrix
first). GPU-batching answer for Kim: Audiobox is ~1.5s/clip regardless of batch (WavLM saturates per clip),
so no batching win; everything else is CPU-parallel.

### project · model_matrix board — completion, discoverability, and two UX fixes
Ran the overnight model-matrix as the persistent deploy/watcher: the 6912-cell render completed clean, then
G's +1116 AVP prompt-extension. Landed three page fixes along the way: (1) `jsnum()` — the file:// embedded
snapshot keyed cfg/strength as "1.0" while the JS lookup builds "1", so every local cell missed (Kim's
"lit models, empty cells"); (2) skip prompt rows a model has zero coverage for, so the AVP-only prompts don't
render as blank grids on goa models (would re-read as the blank-cell bug); (3) `reattach()` — keep playback
continuing at the same playhead across checkpoint switches (A/B the same moment across checkpoints), which
also fixes highlight-loss on the 90s auto-refresh. Plus a landing-discoverability fix: added a "Recently
added" strip + a "mechanism / interpretability" category so the layer_map/steering work stopped being buried
in "other (30)".

### research · longform validation plan — six full-paper reads settle the port questions (Kim delegation via C)
Read FK-Flow, AID, LoL, TRI-TSMC, LatCH, RMR cover-to-cover for the validation-experiment plan
(`docs/ai-research/validation-experiment-plan-2026-07-15.md`). The one that changes our roadmap: AID's
Gaussian relaxation lives entirely policy-side (variance 2λ/(βd), fixed learning device; backbone appears
only as a deterministic drift) → the amortized-guidance bridge needs NO stochastic backbone — rectified
flow ports directly. Second: the LatCH paper's best variant (LatCH-B, heads trained on generated sampler
trajectories) is the one piece we never ported, and AID independently trains on rollouts — two papers
pointing at the same fix for train/inference mismatch at z0_hat. Third: our latch_guided already carries
the full TFG knob set (ρ/µ/γ/n_iter) — I had assumed n_iter/γ were missing; verified in the signature.
Negative/cautionary: FK on a deterministic flow ODE silently collapses particle diversity (FK-Flow Fig. 1)
— any E2 run MUST use the SDE-ified sampler, and TRI-TSMC is the escalation if ESS dies, not the default.

### project · comment loop close-out — CORS + two latent widget bugs (G handoff)
Decision: allowlist the GitHub Pages origin in comment.php (endpoint already public/unauthenticated →
zero new exposure; verified preflight/ACAO live). The real finds were two bugs that CORS alone would
have masked: comments.js used a RELATIVE endpoint (404 on the Pages origin no matter what CORS says),
and boot() only auto-initialized `.cmts[data-target]` while all four of G's new pages use `data-page` —
the page-level boxes would never have rendered on ANY origin. Both fixed + deployed; G's staged HTML
untouched. Lesson: a widget contract change (data-target→data-page) needs a grep over the widget's own
selectors, not just the docs.

### research · E0-A meter extensions built + smoke-gated (corr-dim needed a PCA fix; l_max is the killer stat)
Extended `mir/src/tools/recurrence_meter.py` with `dynamics_stats()` — finite-time corr-dim (G-P) +
RQA determinism (det / multi-scale line_frac / l_max / soft window-product), same whitened-patch
distance matrix as the validated novelty meter (refactor regression-tested bit-identical). Two
findings from the synthetic-tile smoke (ground truth by construction): (1) NEGATIVE — G-P on raw
~11k-dim patch vectors is meaningless (healthy AND loop read ~25: distance concentration measures
the embedding, not the dynamics); fixed by PCA→16 state space, after which corr_dim separates with
non-overlapping bootstrap CIs (healthy 6.7 vs tiled-loop 4.1). (2) det@4s is DILUTED because goa is
naturally repetitive (0.70 vs 0.72) — the discriminators are l_max (29s vs 208s; catches a
half-sequence loop at 130s that whole-clip corr-dim misses entirely) and line_frac_16s (0.031 vs
0.303, 10x). Implication for E1's torch potential: the 4s window-product form is too short — window
length is a hyper to sweep toward ~16s. Labeled-set AUC (F's manifest, Thu) arbitrates formally.

### research · E0 scoring day-early + a real meter vulnerability found (stride-commensurability)
F's manifest landed early → ran the AUC study same-day (eval/score_loopy_manifest.py → loopy_scores.json).
Real labels (8 loopy / 15 good): line_frac_8s 0.758 > det_soft 0.700 > det 0.658; r_max ~chance (0.542) —
consistent with the meter's own "no global threshold" doctrine, raw absolute stats don't compare across
tracks. The synthetic arm then produced an impossible-looking inversion (tiled loops reading LESS recurrent
than originals, r_max AUC 0.004) → chased to root cause with a constructed test: **patch-stride
commensurability** — period = exact multiple of the 1 s patch stride → r_max 1.000; period 0.4 s off the
grid → 0.404 (at 145 BPM that's half a beat; whitened cosine collapses). First hypothesis (mel hop
misalignment) was WRONG — hop-aligned tiles still read 0.404; the stride grid is the real cause, proven
by the 161f-vs-165f pair. Implications: (1) l_max / det_soft / line_frac are the meter's robust core
(0.98–0.99 AUC even under the artifact — per-clip RR threshold adapts); (2) #35 controller should NOT key
on novelty_floor alone; (3) E1's torch potential moves to stride-1 frames (no grid, fully robust, GPU-cheap).
Label gap (8 vs 20 loopy) escalated to Kim: fresh listening pass vs loosened tier vs proceed-noisy.

### research · build-everything day: E1 potential + pre-test, chroma384 harness, bands (2026-07-16)
Built and validated in one pass: (1) RecurrenceHead + band_hinge in latch_guided (stride-1 frames per
the commensurability finding; logsumexp soft-max; corpus-band hinge) — the σ-resolved pre-test (C's
design, model-free) shows a SANE surface (line-search reduces the potential at every noise level),
gradients survive γ≤0.2 (SNR 1.6–8.9; default γ=0.3 marginal → run the guide at γ≤0.2), and the hinge
correctly DORMANT on healthy corpus (≤2% patches above edge — sparse repellency as designed; C's
E2-as-primary warning stays live). (2) Corpus bands: 5401/5401, r_max q90=0.738, corr_dim corpus range
4.6–6.9 with the tiled-loop smoke at 4.05 BELOW q25 — bands and meter cohere. (3) chroma384_eval
harness: targets (T1/T2/T4/T5; palette T3 needs a prototypes build) + Δ-vs-baseline scorer; selftest on
the 30-years morph clip: matched-key beats wrong-key (0.789 vs 0.751) — thin absolute margin = the
chroma trap live, Δ-design vindicated. (4) chroma data store FOUND (latents_sa3_chroma, 5401 npz) —
train.py's "once that data exists" is STALE; wrote the LUMI adapter recipe (control/chroma384_LUMI_README.md).

### research · E1 pilot: FIRST CONFIRMED ANTI-LOOP STEERING (and two bugs the pilot caught first)
Three-round pilot night (~35 min GPU of Kim's 6 h cap, 12 renders à 44 s). Round 1 null → diagnosed, not
declared: the corpus-band edge (0.738, audio/1s-stride scale) NEVER fires in latent mode — loopy render
curves max at 0.44, and corpus latents OUT-RECUR model loops (crisp literal repeats vs approximate model
loops = a real domain shift; per-render-scale calibration, the meter's own doctrine, applies in-loop too).
Head statistic itself separates cleanly in latent mode (loopy med 0.390 > clean max 0.366) — the deferred
E0 latent-mode gate passes at ranking level. Round 2 (edge 0.34 + grad logging): guide fires, grads real
but ~2e-6 vs ‖x‖~800 → λ≤1e4 is a dead zone (the gain-512 lesson, ×100). Round 3: λ=1e7 → line_frac_16s
HALVED (0.517→0.277), l_max 123s→34s (below corpus median!), CE −0.33/PQ −1.16; λ=1e8 over-steers. The
tilt hypothesis is ALIVE with measured authority; operating point hunt (λ 1e5–5e6 dose-response) running.
E2's weights-only arm stays owed (C's rule) — now as the *cheaper-authority* question, not existence.

### incident · resident render-server OOM'd C's Kim-direct stereo sweep (all 3 arms, no ckpts)
My chain honored C's pause-the-poll-driver ask but left the explorer server RESIDENT after the last
render — and it had grown 8.5→12.4GB across jobs (no cache release between renders). C's three sweep
arms each OOM'd against it; her driver masked the failures (rc=0, "ALL DONE"). Found only when Kim
nudged me to read DMs/chat. Remediation: server killed (card 0.67GB), all my GPU work held until C's
sweep-done ping, ownership DM'd with the driver rc-capture bug flagged. LESSONS: (1) a "small renders"
plan is not a small FOOTPRINT plan — resident services are the hazard, and between-job growth makes
them worse; kill or shrink the server when any training window is announced. (2) Check the comms
BEFORE chaining anything onto a shared card, not after. (3) Driver scripts must propagate child rc —
a masked failure cost 6h of undetected loss.
