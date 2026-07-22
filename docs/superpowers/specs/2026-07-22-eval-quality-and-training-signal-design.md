# Eval Quality Suite & Training-Signal Design

**Status:** DRAFT for Kim's review (WINTERMUTE, 2026-07-22)
**Origin:** Kim's "is `Stability-AI/stable-audio-metrics` / `csteinmetz1/auraloss` useful to us?" call,
plus his directive: *"we should have an eval spec for assessing quality and using during training too… training LATCH and FiLM heads is cheap, decode per iter is not impossible if that creates a better model, since eventually the training only needs to be run once."*

## 1. The gap

`eval/clip_metrics.db` (columns: `path,dur,rms,crest,zcr,onset_p95,centroid,flatness,flux,hf_ratio,bpm,ce,pq,cu,pc`) already covers three of the five axes a generated clip can be judged on:

| Axis | Question | What we have |
|---|---|---|
| **Quality** | Does it sound good? | Audiobox `ce/pq/cu/pc` (per-clip) |
| **Authority** | Did the requested control move? | feature deltas / direct-feature measurement (per-clip) |
| **Integrity** | Is it intact (not buzz/dead)? | disintegration gate — flatness/hf_ratio/zcr/beat/CE-drift ([spec](2026-07-20-control-head-disintegration-gate.md)) |
| **Adherence** | Does it match its *prompt*? | **— nothing —** |
| **Fidelity** | Does it match a *ground-truth target*? | **— ad hoc only** (`stem_score.py`) |
| **Realism** | Is the output *distribution* like real music? | **— nothing systematic** |

The two external repos map cleanly onto the three missing axes, and — crucially — the two *differentiable* ones (Adherence, Fidelity) can also be used **inside the training gradient**, not only after the fact. That dual role is the reason this is one spec, not a metrics changelog.

## 2. Metric taxonomy (source-mapped)

### 2a. Adherence / **degeneration detection** — CLAP score  *(from stable-audio-metrics; laion_clap, pure torch → ROCm-ok)*
`cos(text_embedding(prompt), audio_embedding(clip))`. Per-clip, needs no reference set. Every model_matrix / eval cell already carries `prompt_text`, so it is a drop-in column.

**The primary use is a degeneration detector, not a fine-grained quality ranker (Kim, 2026-07-22).** "If we prompt for psytrance, it should not sound like drones or noise." CLAP's measured discrimination profile (§5) is *exactly* shaped for this: it barely separates near-synonym prompts (psytrance-A vs psytrance-B, matched 0.263 vs in-set-mismatch 0.232 — margin ~0.03) but *massively* separates genre-vs-noise/other (matched 0.263 vs far-control 0.005 — margin 0.257). So it is a poor intra-genre judge and an excellent **"has this run collapsed out of its requested genre into drone/noise/mush"** alarm. A healthy psytrance clip sits ~0.26 vs its prompt; a degenerated one falls toward the ~0.00–0.05 floor — a large, monotone, monitorable drop. This is the **semantic complement to the DSP disintegration gate**: the DSP gate ([spec](2026-07-20-control-head-disintegration-gate.md)) catches *buzz* (flatness/hf/zcr) and *dead* (authority≈0); CLAP catches the third failure mode — output that stays DSP-plausible but has **semantically drifted** off the prompt.

**Corollary caveat:** because intra-set ranking is weak, CLAP must NOT be read as "cell A is more psytrance than cell B." Use the *absolute score and its drop*, not fine ranking among near-synonyms.

### 2b. Fidelity — auraloss MR-STFT / SI-SDR / Sum-Difference-STFT  *(Apache-2.0, ALREADY vendored)*
`stable-audio-tools/training/losses/auraloss.py` is already in-tree (used at weight 0.1 as the VAE reconstruction loss). Reference-based waveform-domain similarity where a ground truth exists: **a2a re-render vs source, generative-separation fidelity, FlowEdit anchoring, ONNX-decoder distillation validation.** `SumAndDifferenceSTFTLoss` is the stereo variant — relevant since SA3 is stereo and we track stereo width/corr. Deterministic and cheap; a complement to CLAP/FAD, not a replacement. (The pip `auraloss` package is NOT installed in any venv; only the VAE-training path needs it. The vendored copy covers in-tree use.)

### 2c. Realism — FAD / KL  *(corpus-level; ROCm path settled by research 2026-07-22)*
Distributional distance between a checkpoint's output set and a real-music reference set. One number per checkpoint → "which LoRA / training-length is distributionally closest to real Goa/avp," and — the strategic value — **numbers comparable to the published Stable Audio papers** (for the Sourcebook/writeup). Reference-set-based (compute reference stats once), aggregate (not per-cell).

**ROCm feasibility (was flagged as the OpenL3/TF/CUDA blocker — research says it's a non-issue):**
- **FDopenl3-proper is the ONLY awkward metric — substitute it, don't port it.** Upstream OpenL3 is TF+kapre (CUDA-11.8 friction); a pure-torch `torchopenl3` exists (MAE <1e-3 vs TF) but is unmaintained (2021, pre-torch-2.10). Not worth babysitting for one metric.
- **The whole modern FAD ecosystem is pure-PyTorch** and runs on our ROCm torch (or CPU on the 9900X) unchanged — no NVIDIA/CUDA deps. **`gudgud96/frechet-audio-distance`** (`pip install frechet-audio-distance`) does **CLAP-FAD** directly, at CLAP's native 48 kHz, **reusing the same laion_clap we just stood up.** For *music* the perceptual-correlation literature (Microsoft "Adapting FAD" 2311.01616; ETH ICASSP-2025) rates **CLAP-Music-FAD and MERT-FAD** as first-class and rates the original **VGGish-FAD as poorly correlated (<0.1)** — so CLAP-Music-FAD is arguably a *better* realism number than FDopenl3 for our domain, and it's ROCm-native today.
- **KLpasst** = `hear21passt` (pure torch), matches Stability/MusicGen `KL_PaSST` (32 kHz) exactly; pair with `audioldm_eval`'s KL harness rather than hand-rolling the divergence.
- Optional robustness: a second FAD backend (PANNs or MERT via `microsoft/fadtk`) — FAD is embedding-sensitive, so always report *which* embedding and never compare FAD across embeddings.

NB: we dropped OpenL3 as a *conditioning feature* (C's retrieval gate); using CLAP/PANNs/MERT for FAD sidesteps that debate entirely.

## 3. Eval-time integration

- **Per-clip metrics (CLAP, auraloss-fidelity where a target exists)** → new `clip_metrics.db` columns (`clap`, `mrstft_fid`…), same UPDATE-by-path pattern as the Audiobox pass. Surfaced on the eval boards beside ce/pq/cu/pc.
- **Corpus metrics (FD/KL)** → a per-checkpoint table (`realism(model,ckpt) → {fd, kl, n}`), surfaced in the model_matrix header block (already shows good-fraction), NOT per cell.
- All follow the disintegration-gate discipline: a metric that moves is not proof of quality — CLAP can be high on a well-produced clip that ignores the *specific* prompt, so adherence is reported **alongside** integrity + quality, never as a sole verdict.

## 4. Train-time integration (Kim's decode-per-iter reframe)

The RF loss is blind to many perceptual attributes (it is an MSE in latent velocity space). The **meter-in-the-gradient** pattern (decode `z0_hat` → frozen probe → match request, t-gated) puts a perceptual signal INTO the gradient. Its scope condition is settled ([perceptual-signal spec](2026-07-02-perceptual-signal-optimizer-directions.md), MASTER §4): **it helps only for fine-grained properties the RF loss cannot already see** (onset timing: yes; global genre: no — the meter just drags output toward the probe manifold and hurts).

**Kim's reframe changes the cost side, not the scope side.** A LatCH head (~5–7 M params) or a FiLM conditioner is cheap; a VAE decode per step is affordable *because the run happens once and buys a permanently better head.* So decode-per-iter is a first-class option for the cheap heads, where it was previously dismissed on cost. Candidate train-time meters, gated by the scope condition:

| Meter | Differentiable? | Good train-time target | Avoid for |
|---|---|---|---|
| **auraloss MR-STFT / mel-STFT** | yes | fine spectral *texture* control | broad timbre (RF sees it) |
| **auraloss SumDiff-STFT** | yes | stereo-field control head | mono targets |
| **CLAP text-consistency** | yes (CLAP is torch) | prompt/style *adherence* nudge | global genre (the genre negative) |

**Guards (mandatory, from the perceptual-signal spec):** supervise a dim-subset, monitor held-out dims for pathological drift (the probe-hack guard); t-gate the meter (only late, low-t steps where `z0_hat` is meaningful); keep the RF loss dominant (meter is a small-weight auxiliary). Any train-time meter run must emit the standard tiered telemetry so the per-layer fingerprint is comparable across features.

### 4b. CLAP as a train-time degeneration MONITOR (not a gradient term)
Distinct from §4's gradient meters and much cheaper: every N steps, decode a couple of fixed-prompt sample latents → CLAP-vs-that-prompt, and log it. RF loss is blind to control *and* nearly flat, so it cannot tell you a run has started emitting drone/noise — but a **falling CLAP-vs-prompt curve says exactly that**. This operationalizes the standing "the head finds the control direction then **drifts**" finding (MASTER §4, the EMA/early-stop result): CLAP-vs-prompt is the missing early-warning signal for that drift, and its **turn-down is a principled early-stop / checkpoint-select trigger** (stop, or pick the pre-drift checkpoint, when CLAP-vs-prompt rolls over). It also gives the checkpoint-ladder view: across epochs the curve should hold; the epoch it falls off is the collapse point. Because it needs only a few decodes at a coarse cadence, it is affordable on *any* run, not just the cheap heads — a good default to wire into the telemetry alongside the trajectory panels.

## 5. Prototype result (CLAP, this session)

`eval/clap_score.py` (sat-venv, laion_clap 630k+audioset non-fusion, CPU). Builds the sampled-clip × unique-prompt cosine matrix + a fixed far-control set. Two torch-2.6/transformers compat shims baked in (weights_only=False + strict=False load, both for the trusted official checkpoint). **300 stratified model_matrix clips:**

| Quantity | Value | Reading |
|---|---|---|
| matched cos (own genre prompt) | **0.263 ± 0.115** | healthy adherence band |
| in-set mismatch (other genre prompts) | 0.232 | near-synonyms cluster → intra-set ranking weak |
| **far-control cos** (violin / podcast / ocean / metal) | **0.005** | genre-vs-other floor ≈ 0 |
| **margin vs far (headline)** | **0.257** | CLAP strongly tracks genre-vs-non-genre |
| true prompt beats ALL far controls | **71.3 %** | adherence hit-rate |
| in-set retrieval top-1 / top-3 | 19.0 % / 38.7 % | above 8.3 % chance but weak (expected) |

**Verdict: the degeneration-detector use is validated; the fine-ranking use is not (and should not be attempted).**

**Sampling-bias correction (2026-07-22):** the first `stratified_sample` keyed on (model, prompt) only → drew 96% cfg1/w0.6 (first in manifest order), which depressed matched-cos and faked a "weak-steering degenerates" signal off 12 strong cells. Fixed to key on (model, prompt, cfg, strength). On the corrected **balanced 500-clip** sample the numbers are cleaner and the general checkpoint is clearly the better detector.

**Checkpoint A/B — general 630k vs music_audioset (HTSAT-base), balanced 500:**

| (balanced 500) | general 630k | music_audioset |
|---|---|---|
| matched cos | **0.352** | 0.293 |
| far-control floor | **−0.017** | +0.043 |
| margin vs far | **0.369** | 0.251 |
| **steering separation d** (strong-vs-weak, = well-formedness sensitivity) | **1.00** | 0.59 |
| dynamic range p05–p95 | **0.155–0.499** | 0.115–0.442 |
| beats-all-far hit-rate | 93.6% | 94.8% |

**Decision (data-driven, not ear): the general 630k is the default degeneration checkpoint** — bigger genre-vs-noise margin, cleaner near-zero floor, and *higher* sensitivity to output well-formedness (d=1.00 vs 0.59: it drops harder on degenerate output, which is exactly the detector's job). The music_audioset checkpoint compresses the cosine scale and is NOT an upgrade here; kept available via `clap_score.py --music-ckpt` for future music-specific tasks. What still needs **Kim's ear** is only the *threshold* (which absolute CLAP value = "degenerate") — tee up the lowest-CLAP clips (~3.6% sit below 0.10) for him to confirm they are the drone/noise ones. CSVs this session: `clap_gen500.csv` / `clap_mus500.csv` (scratch).

## 5b. Full-corpus scan result (31,639 cells, general 630k, 2026-07-22)
Ran the whole model_matrix (`eval/clap_degen_model_matrix.csv`; summary `eval/clap_degen_summary.md`, ear-calibration ladder `eval/clap_degen_audition.csv`). **The scan independently reproduces the fleet's established quality ordering — semantically, via genre-collapse rate:**
- **rank-16 adapters collapse out-of-genre ~40%** (worst dora16_avp_originals 64ep ep7: 44.8% of cells CLAP<0.10) vs **rank-128 ~3%** (sa3-goa-dora-47s-r128) → confirms "rank-128 good / rank-16 harsh" on a new axis.
- **cfg1 is the degeneration zone** (0.20–0.25) vs cfg7–16 healthy (0.31–0.39); **DoRA w2.0 degrades at every cfg** (over-applied adapter → off-genre). Sweet spot cfg7–16 × w0.6–1.0.
- Overtraining shows: dora16_avp_originals at 64ep is the single worst.

So CLAP-degeneration is validated as **both a quality proxy that agrees with CE/PQ+ear AND a per-cell genre-collapse flag.** Corpus percentiles p01/p05/p50/p95 = −0.061/0.023/0.324/0.489; 11.7% of cells sit below 0.10 (candidate-degenerate; threshold TBD by Kim's ear via the audition ladder).

## 6. Rollout (order set by Kim 2026-07-22 — train-side monitor promoted to first)

1. **CLAP degeneration monitor — train side (§4b)** — wire the periodic decode→CLAP-vs-prompt curve into the training telemetry as an early-warning / early-stop / checkpoint-select signal. *(the highest-leverage use per Kim — catches the "finds direction then drifts" collapse the RF loss is blind to; Kim promoted this ahead of the eval-side flag)*
2. **CLAP degeneration flag — eval side** — land a `clap` column over model_matrix + control evals; on the boards, flag cells whose CLAP-vs-prompt falls toward the far-control floor (a genre-collapse / drone-noise marker), paired with the DSP disintegration gate. *(prototype done; scale is a CPU pass, no GPU-lock)*
3. **auraloss fidelity score** — wire MR-STFT/SI-SDR reference scoring into `stem_score.py`'s path + a2a/separation/distillation checks. *(vendored code already present)*
4. **CLAP-in-the-gradient, one cheap head (§4)** — pick a fine-grained spectral/stereo target, decode-per-iter, matched-length trajectory vs a no-meter baseline, disintegration-gated. *(the decode-per-iter experiment Kim greenlit)*
5. **Realism, corpus-level — ROCm path settled (research 2026-07-22): not a jury-rig, it's `pip install`.**
   - (a) **CLAP-Music-FAD via `gudgud96/frechet-audio-distance`** — pure torch, ROCm-native, reuses our laion_clap, 48 kHz, literature-endorsed for music. The primary realism number. *Lowest effort, do first.*
   - (b) **PaSST-KL via `hear21passt`** — pure torch, matches Stability/MusicGen `KL_PaSST` exactly (32 kHz). *Low effort.*
   - (c) optional: a second FAD backend (PANNs/MERT via `microsoft/fadtk`/`audioldm_eval`) for embedding-robustness.
   - (d) **FDopenl3-proper: substitute, do NOT port** — only worth it to reproduce a *published* FDopenl3 number; CLAP-Music-FAD is a better music metric and ROCm-native today.

## 7. Decisions (Kim 2026-07-22)
- **CLAP checkpoint: A/B'd → KEEP GENERAL 630k** (2026-07-22). Downloaded + tested the music_audioset (HTSAT-base) checkpoint per Kim; on the corrected balanced sample the general 630k is the *better* degeneration detector (§5: margin 0.369 vs 0.251, steering-separation d=1.00 vs 0.59, cleaner floor). Music kept available via `--music-ckpt` but is not the default. *(Note re Kim's `clap-htsat-fused` link: that's the general-domain HF transformers fused model — not music-specialized; the music_audioset .pt above is the music one, and it still lost the A/B.)*
- **Rollout order: train-side degeneration monitor FIRST** (was #2 → now #1); eval-side flag second.
- **FD/KL: research the ROCm jury-rig cost + prior art first**, then decide (§6 step 5). PaSST-KL / CLAP-FAD are the likely ROCm-native first cuts; FDopenl3-proper deferred if OpenL3-on-ROCm is as painful as feared.
