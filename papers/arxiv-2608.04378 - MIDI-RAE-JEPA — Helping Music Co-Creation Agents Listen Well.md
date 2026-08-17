# Helping Music Co-Creation Agents 'Listen' Well — MIDI-RAE-JEPA / STORMBIRD (2608.04378)

*Project-POV note, THE-FINN 2026-08-18. Scott H. Hawley, Belmont University. **BLOG-PAGE-LEVEL
ONLY — the arXiv abstract and PDF have NOT been fetched.** Surfaced by Kim via the project blog
(drscotthawley.github.io/midi-rae-jepa-son/), not our own search. Downgrade this note's confidence
accordingly; do not cite it as verified until someone pulls the PDF.*

**What it claims (per the blog summary).** A Swin-Transformer masked autoencoder trained on
piano-roll IMAGES of MIDI (POP909, 909 songs; cross-domain eval on Lakh512), learning a six-level
hierarchy (L0 = one vector per 128×128 crop, coarsest; L5 = 4×4-pixel patches, finest) with
**"internal-consistency objectives (LeJEPA attraction + SIGReg, factorization, cross-level
masked-embedding prediction) — no reconstruction loss."** A lightweight auxiliary chord loss
(λ=0.5) makes chord root linearly decodable at 90% (chance ~8.3%). Phrase-boundary signal rises
monotonically toward COARSER levels, peaking at L0 (F1@32 = 0.303, ~3× a pixel baseline of 0.098).
Pitch-transposition and time-translation equivariance are near-perfect exactly at the levels where
the geometric (factorization) objective acts, degrading at finer levels. Self-reported failure
modes: two architecture variants ("plus2", "coarse") show catastrophic chroma collapse (R² −77 to
−713); EMOPIA emotion probes barely beat chance (0.4–0.49 vs 0.25).

**Domain gap — the thing to hold onto.** This is SYMBOLIC (MIDI-as-piano-roll-image), not audio
latents. Nothing here ports as code even once released. What's potentially relevant is the
DESIGN, not the artifact: a hierarchy of musical structure (phrase boundaries) EMERGING from
self-supervised JEPA-style training with no hand-crafted tree, peaking at the coarsest learned
level — a data point for "is hierarchical musical structure learnable without being architected
in," which sits adjacent to but is NOT the same claim as our own metrical-tree PE hypothesis
([[relational-weights-theory-survey]] thread, docs/superpowers/specs/2026-07-31-metrical-tree-pe-
design.md) — ours argues position should be GIVEN as a tree (flat RoPE → phrase-blindness);
this paper gets phrase-structure to emerge WITHOUT one, in a different modality. Corroborating
or competing, not yet clear which — that read needs the PDF, not the blog page.

**Status vs our work.** NOT a graduated arm. Code marked "soon," not released; no weights.
Nothing actionable today. Flagged for C to read (metrical-tree / structure-recall thread owner)
and decide whether it's worth a PDF deep-read given the two-week deliverable window — this is
squarely research-adjacent, not on the AVP/density-adapter/pitch-melody-head critical path.

**Links (from the blog page, unverified beyond that):** arXiv 2608.04378 · PDF
hedges.belmont.edu/midi-rae-jepa-cait.pdf · probe suite github.com/drscotthawley/stormbird
(code, not weights) · demo drscotthawley-hf.space.
