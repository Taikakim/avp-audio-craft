# Assessment — Gemini report #2, "Long-Form Audio Diffusion Research"

*(CONTINUITY, 2026-07-15. Source: `docs/ai-research/Long-Form Audio Diffusion Research.txt`
— Kim's second Gemini pass, different research brief. Verify-first applied: both load-bearing
external citations checked by hand. Companion: `gemini-report-assessment-2026-07-15.md` (W,
report #1) and `continuity-theory-review-2026-07-15.md`.)*

## Verdict up front

**Well-written, citations real — but largely a closed loop around our own shelf.** 8 of its
32 "works cited" are OUR source files (longform.py, rope_jitter.py, latch_guided.py,
fifo_infinite.py, incantation_mask.py, chroma_losses.py, distribution_shift.py, sampling.py),
and its two flagship "external" methods are the papers our code was already built from:

- **LoL / multi-head RoPE jitter (2601.16914)** — verified real (Jan 2026, 12-hour video).
  But `rope_jitter.py` cites it in its own docstring; F triaged it 07-11. Not a find.
- **LatCH (2603.04366, "Low-Resource Guidance for Controllable Latent Audio Diffusion")** —
  verified real, **ICASSP 2026, and the authors are the Stable Audio team** (Novack, Zukowski,
  Carr, Parker, Evans, Berg-Kirkpatrick, McAuley, Pons). Our latch infra implements it
  (`stable-audio-tools/scripts/LATCH_README.md` cites it). Not a find either.

**Do not cite this report as external validation of our stack.** Its authoritative-sounding
sections on DriftMonitor thresholds, post-hoc swap "superiority," Hann-smoothed chroma loss,
adaLN time caching etc. are our own code and docstrings narrated back in literature voice —
circular, not corroborating. (One section even cites a Reddit post.) It also over-states our
SaFa result: "seamless stitching, zero distortion" is the *seam-character* fix; W's co-score
showed loopiness untouched.

## The genuinely new deltas (three)

1. **SaFa's second operator — Reference-Guided Latent Swap — we never implemented it.**
   Unidirectional, applied in EARLY denoising steps to NON-overlap regions: a reference view
   feeds latent frames forward into subsequent windows to enforce *global* cross-view
   consistency (timbre, room acoustics, SNR). Our port took only the self-loop seam swap.
   This targets a third axis — cross-window timbre/acoustics drift — distinct from both the
   seam fix (done) and loopiness (unaffected). Cheap add in `longform.py`'s sequential frame:
   inject reference-window latents into each new window's early-σ steps (we already have the
   machinery: it is inpaint-style clamping with a schedule). → POOL, decent priority given
   the a2a lane.

2. **LoL's mechanism is a testable diagnostic for our RoPE-jitter NULL.** LoL reports that
   sink-collapse events coincide with local maxima of INTER-HEAD PHASE ALIGNMENT. We tested
   rope_jitter and got a null on loopiness — the unresolved question was why. The clean
   experiment: hook the rotary phases and measure inter-head phase concentration at loop
   onset in OUR windowed-SDEdit rollouts.
   - No concentration → LoL's pathology (autoregressive + attention sinks) simply is not our
     pathology; the null is *explained*, and rope_jitter demotes to a low-priority actuator
     in the breathing controller.
   - Concentration present → our null needs a re-look (scale sweep inside LoL's 0.05–0.10
     band, eval metric, context length).
   Either outcome is informative; cost is a forward hook + existing render infra. → POOL,
   this is the report's one real *experiment* contribution.

3. **Curved denoising (InfiniteAudio)** — attention-guided step selection concentrating NFE
   in the mid-schedule. Minor efficiency lever for streaming; we are not NFE-bound. → pool,
   low.

Unverified secondary lead: "When to Lock Attention: Training-Free KV Control in Video
Diffusion" (ResearchGate) — adjacent to incantation-mask territory; pull the abstract before
any weight is put on it.

## Methodological note for future Gemini probes (worth keeping)

Report #1 (brief = W's theory synopsis, no code) surfaced genuinely external material:
FK-Flow, AID, DEFAR, CQT-Diff, KoopmanFlow. Report #2 (brief evidently included our
inference code) spent most of its length re-deriving our own decisions and the papers we
already implement. **Code-in-brief makes Gemini orbit the code.** For novelty sweeps, feed
it the problem statement and the failure phenomenology — not the implementation.
