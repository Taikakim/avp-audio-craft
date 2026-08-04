# Gemini deep-research brief — hierarchy-native positional encodings for music generators

*(CONTINUITY 2026-07-31, per Kim's fact-dense-brief convention: everything below is
measured/established on our stack; the questions ask for LITERATURE, not speculation.
Paste the whole brief as the query.)*

## Established facts (our system — treat as ground truth, do not re-derive)

We train and study a latent rectified-flow Diffusion Transformer for music (1.4B params,
24 transformer blocks, dim 1536), operating on a 256-channel continuous audio latent at
10.766 Hz frame rate (one frame ≈ 93 ms of 44.1 kHz stereo). Temporal position is encoded
with standard rotary position embeddings (RoPE, partial-rotary GPT-J style) over a flat
1-D frame index. Relevant measurements from our lab:

1. Generated music suffers a "loop attractor": in audio-to-audio regeneration at
   mid-to-high init-noise (nl ≥ .55), generated material loops a short phrase for minutes.
   We tested the RoPE-periodicity mechanism proposed for video models (single dominant
   temporal-RoPE frequency in attention; looping-vs-non-looping models split 0.796 vs
   0.316 there) and it does NOT discriminate on our model (0.419 loopy vs 0.395 non-loopy
   inputs): our looping is STATE-dependent (appears within one model as a function of
   noise level), not a fixed model property.
2. The surviving gap is long-range STRUCTURE recall: motif return, phrase-level
   self-similarity, key relationships across tens of seconds.
3. Music's positional structure is a literal tree: 16th-note → beat → bar → 8-bar phrase
   → section. Under flat RoPE, the transition bar-17→bar-18 is positionally identical to
   bar-1→bar-2; phrase position is architecturally invisible.
4. We are currently testing (training now) a RETROFIT: 4-level metrical position
   (subdivision-in-beat 0-3, beat-in-bar 0-3, bar-in-phrase 0-7, phrase-index 0-7) as
   hard-class FiLM conditioning through an adapter on the frozen base, against a
   permuted-sidecar matched baseline. The next escalation would be a from-scratch
   positional encoding replacing/augmenting RoPE in a small experimental model.
5. Adjacent measured fact: our latent's covariance eigen-spectrum is 786× anisotropic and
   near-degenerate eigenplanes carry approximate SO(2) symmetry (adjacent-eigenvector
   rotations perturb the flow field 1.8× less than random planes).

## Questions (literature synthesis wanted — cite real, verifiable work only)

Q1. What published positional-encoding schemes encode HIERARCHICAL or TREE position
    (not flat sequence index) in transformers? Cover: tree positional encodings from
    program-synthesis/AST work, hierarchical RoPE variants, multi-scale/multi-resolution
    PEs in long-context LLMs, and any music-domain positional schemes (REMI bar/beat
    tokens, Music Transformer relative attention, PopMAG/Museformer-style structures).
    For each: exact mechanism, what it was shown to improve, scale it was tested at.
Q2. Hyperbolic or mixed-curvature embeddings used specifically for POSITION (not general
    representation learning): does any work embed sequence position in hyperbolic space
    for attention? Results?
Q3. In music generation specifically: what conditioning or architectural mechanisms have
    measurably improved LONG-RANGE STRUCTURE (motif return, verse/chorus form, phrase
    repetition) — as opposed to local coherence? Include negative results.
Q4. For diffusion/flow models (non-autoregressive, bidirectional attention): is there
    evidence that positional-encoding choice affects generation structure differently
    than in AR models? Any DiT-specific PE ablations?
Q5. Failure modes: published cases where richer positional information HURT (overfitting
    to position, reduced invariance, train/test length mismatch), especially in
    generative models.

## Anti-play-acting constraints
- Cite only real, checkable papers (arXiv IDs / venues). We verify every citation before
  building; fabricated or unverifiable citations make the run worthless.
- If literature does not exist on a question, SAY SO — a confirmed gap is a valuable
  answer (we will then know we are first).
- Do not re-explain our own facts back to us; the value is what we have NOT measured.
