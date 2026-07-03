# WINTERMUTE — journal
> the rigor — the adversary who makes the work true, not merely beautiful.

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
