# Help pane and glossary component for blog and site pages: requirements so far

Status: REQUIREMENTS CAPTURE (CONTINUITY, 2026-10-26, asked by Kim). NOT an approved design: nothing is built, and the
design document proper (with a reviewer pass) has not been written. This file exists so a context compaction cannot lose
what Kim asked for. First target page: `blog/2026-10-21-muon-survival-guide-DRAFT.md` (published as
`/files/blog/2026-10-21-muon-survival-guide.html`).

## Why (Kim)
A reader meets an unfamiliar concept, glosses over it, and the gap accumulates: later text is harder to follow and reading
gets tiring. The component should catch the gap at the moment it opens, and let the reader check they understood it.

## Requirements from Kim (his words condensed)
- A **library of hypertargets** (glossary terms); the page **automatically highlights and activates them anywhere** in the text.
- A **collapsible sidebar** where the help texts stay open, with **interactive visualisations** where needed (how activation
  patterns fire, how batches turn into gradient updates). A **back button** is needed (history stack inside the pane).
- **Modular, universal component** for the whole site, activated per page where it makes sense.
- **Quiz after each help section:** 3-5 questions of increasing difficulty, **five options each**; a wrong answer gives
  feedback explaining why the correct option is correct; feedback arrives after the question and swaps the pane content.
- The page **summary** must give the reader trust that the text is approachable for different levels of understanding.

## Terms Kim has named so far
2-D weight matrices; weight; gradient history (the draft's section 3 phrase "that weight's own gradient history"); momentum; orthogonal matrix (Kim, 2026-10-26).
Candidate list from reading the page (not yet agreed): optimizer, AdamW, Muon, momentum, gradient, Newton-Schulz iteration,
orthogonal matrix, singular value, learning rate, weight decay, batch size, gradient accumulation, gradient clipping,
fine-tuning, pre-training, LoRA, DoRA, rank, embedding, diffusion model, latent, held-out loss, NaN, EMA, warmup and cosine decay.

## Interactive pieces asked for (each a lazy-loaded module; real simulation, not a drawing)
1. **Step size, Muon vs AdamW** (links from "Muon sets the step size from the learning rate, not from the gradient"): nodes
   and wires, wire thickness = per-weight step, real AdamW and Muon steps on a tiny matrix; scenarios steady / noisy /
   gradient drops 100x / rises. The draft sentence is imprecise (AdamW is also scale-invariant); the real contrast is
   independence from gradient consistency and history (AdamW's step shrinks for ~1000 steps after a drop and under noise,
   pure-noise floor sqrt((1-b)/(1+b)) = 0.23 at b = 0.9; Muon's does not). Reword the draft sentence and section 5 first.
2. **Batch-size slider** (links from the summary bullet on small-batch noise): 2D loss valley, true gradient vs a cloud of
   minibatch gradients, noise ~ 1/sqrt(B), calibrated to W's measurement on the onset head (half-batch cosine 0.37 early,
   0.08 late; B_simple 81 -> 333). Batch 1-16 is an EXTRAPOLATION (the measurement is at 64+): label it. Readout of what an
   SNR-based add-on sees (~0.18-0.23 at pure noise). No 3D layer view: our noise numbers are run-level, not per layer.
3. **Rank for LoRA and DoRA** (Kim 10-26): slider for rank r; bottleneck diagram d -> r -> d (parameters 2*d*r vs d*d);
   DoRA toggle adds a per-row magnitude dial; panel showing how much of a full-rank change a rank-r adapter keeps, using our
   measured spectrum of full fine-tune deltas (whole-model energy: r128 26%, r512 65%, r1024 89.5%; r90 medians 747-1110 of 1536;
   attention at r128 40-68%). Interpolate between measured points only with a label. Links to the extraction paragraph.

## Design calls so far (CONTINUITY's, not yet approved)
- Mark terms at BUILD time in `Misc/publish_blog.py` (first occurrence per section; skip headings, code, links), so the page
  works without JavaScript; the pane and quiz are runtime. Vanilla JS, no dependencies; glossary as JSON (shared base file +
  per-page file); aliases per term; deep links by URL hash; bottom sheet on phones; keyboard and screen-reader accessible.
- Reuse the site masthead and `site/edg3.css`; keep the publisher's redaction pass.
- Build locally; do NOT publish to the public site without Kim's go.
- Content cost: ~25 terms x 3-5 questions x 5 options. Wrong options need real thought; Kim reviews the questions.

## Blog-draft fixes found while scoping (made or pending in the draft)
- DONE 10-26: section 7 paragraph "Extracting an adapter from a full fine-tune did not work" (evidence: journal 2026-07-24,
  DISCOVERIES 'xft distillation: rank limit, not a bug').
- PENDING (draft is W's lane; Kim asked, awaiting go): "units" -> "scale" for the learning-rate claim (Summary bullet,
  section 4 heading); Summary bullet and section 5 sentence on step size; section 1 table batch column (control heads say
  16-32 but section 6 trains 64/128/256 effective); "how to read this" paragraph after the Summary.
- Open question: KIM-TASKLIST 251 says the 60 extracted adapters have zero rendered cells while EXPERIMENTS.md:44 calls them
  "broken"; the blog paragraph rests on Kim's glitch report plus the reconstruction and spectrum checks, not on a canonical-clip board.
