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

## 2026-07-06 — avp personal-corpus prep + the whole-track paradigm (reuse, don't re-cut)

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

Negative-result lessons: (1) orphan-pruning an analyzed corpus by matching **only `.flac`** source
files wrongly trashed folders for `.wav`-source keepers (3 of mine) — match **all audio extensions**.
(2) `pgrep -f 'script.py'` inside a shell whose own command line contains that string self-matches —
use `ps | grep '[s]cript'`. Reversible-delete (move to trash dir) caught the .flac bug harmlessly.

## 2026-07-07 — the recurring render-clipping bug, quantified (Kim: "we fix this every second day")

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

**2026-07-07 — first Kim-validated usable transition.** Kim on `chroma_morph_barsnap`
`kaikki2angelic__w1025_nl42_chroma`: *"a completely useable transition."* Recorded in the
run's `run_meta.json` findings (alongside the earlier negative: slerp-midpoint @ nl .55
= identity-losing drone). Operating point that worked: bar-snapped window ~1025, nl 0.42,
chroma-morph ON. The chroma/plain A/B and the nl bracket did their job — the method
(bungee beatmatch + latent slerp + graded a2a refine + stem-chroma LatCH morph) is now
listener-validated, not just metric-validated. C's method, G's pages, my deploys.

**2026-07-08 — the latent encodability screen exists now.** Kim asked whether we ever had
the latent-dim × feature-timeseries correlation over the dataset — we didn't (only pooled
scalar probes + the un-run DiT-layer map). Built + ran it (999 crops, CPU): frame-level
ridge R² ranks features flux .84 → vocals .02, and the thin tier (beat/downbeat activations)
is exactly the set of guidance-dead heads from the 06-28 sweep — a minutes-cheap screen that
predicts head viability before training. Encoding is distributed (no single steerable
channel; family clusters). Expectation-order for the LUMI all-features array. Matrix:
`mir/stats/latent_dim_feature_xcorr.csv`.

**2026-07-08 — Kim's ear vs the mid-noise band: ear wins, regime explains.** He heard a2a
melodies going stereotypical at nl .4–.55. Measured on the a2a_kaikkialla ladder: chroma
flux floors exactly there (−20% vs source) then overshoots source at .7 — U-shape ⇒
posterior-averaging regime artifact (melodic contour destroyed at that SNR, model fills
with corpus-mean filler; CFG sharpens), NOT a static prior. Matches SDEdit projection +
Kynkäänniemi interval-CFG + EDM churn literature. The principled fix is the one we already
built: chroma-morph guidance re-supplies the destroyed evidence in-band. Tool:
`mir/src/tools/melodic_movement_ladder.py`.
