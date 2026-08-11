# StoryScope: Investigating idiosyncrasies in AI fiction (preprint, under review 2026)

*Our template for content-invariant idiosyncrasy scoring: measure the choices behind the artifact, not its surface — the analog of dodging our production/mastering confound. (Russell, Rajendhran, Pham, Iyyer, Wieting — UMD & Google DeepMind; no arXiv id, code/data github.com/jenna-russell/storyscope. Subagent deep-read, THE-FINN 2026-08-12.)*

## What it contains

StoryScope asks whether AI-generated fiction can be distinguished from human fiction **without relying on stylistic signals** (word choice, syntax, em-dashes), using only discourse-level *narrative* features (plot structure, character agency, chronological discontinuity, thematic explicitness).

Method (a three-stage LLM pipeline over a parallel corpus):
- **Data**: 10,272 human writing prompts, each written by a human author (extracted from Books3) and mirrored by five LLMs (Claude Sonnet 4.6, DeepSeek V3.2, Gemini 3 Flash, GPT 5.4, Kimi K2.5), yielding 61,608 stories averaging ~4,753 words. AI mirrors are reverse-engineered by inferring each human story's premise, so plots/characters are matched.
- **Pipeline**: (1) each story is converted to a structured JSON template along 10 of NarraBench's 12 narrative dimensions (Agent, Social Network, Event, Plot, Structure, Setting, Time, Revelation, Perspective, Style) — this abstracts away surface wording and forces later stages to reason over narrative content; (2) comparative analysis across the six sources on a held-out 600-story discovery pool induces discriminative features; (3) feature discovery yields 408 candidates deduplicated to **304 features**. Features are then assigned to all 61,608 stories (Gemini 3 Flash), and XGBoost + SHAP identifies **30 "core" features** (stable human-vs-AI markers) and per-model **"fingerprint" features** (6-way attribution).

Key findings (cite-accurate):
- **Narrative features alone reach 93.2% macro-F1** for human-vs-AI detection — within 2.8 points of the narrative+style model (96.0%), i.e. retaining ~97% of the combined signal. The **30 core features alone** hold 84.8% macro-F1 (~91% of the narrative model).
- **6-way authorship attribution**: 68.4% macro-F1 from narrative features (77.3% with style); attribution is much harder than detection because the AI models overlap.
- **Rarity/originality**: human stories are, on average, **rarer** in narrative-feature space — **mean rarity percentile 0.71 (human) vs 0.49 (AI)**. AI models cluster in a tight, shared region of narrative space, well-separated from the more diverse human region (LD projection, Figure 2).
- **Content signatures** (not style): AI over-explains themes (states the moral 77% vs 52%), favors tidy single-track plots (79% "no subplots" vs 57%), tighter causal chains and protagonist-driven resolutions (69% vs 46%); humans use more time jumps/flashbacks/nonlinear structure, more ambiguous endings, more fourth-wall breaks, and reference specific real texts/authors ~2x more (47% vs 24%). Per-model fingerprints: Claude = flat event escalation, GPT = over-indexes on dream sequences, Gemini = defaults to external character description.
- **Robust to style edits**: after LAMP span-level artifact rewriting (decliché, remove purple prose) on Gemini stories, narrative detection barely moves (93.9% vs 95.5%, −1.6 pts) — the narrative choices are largely orthogonal to surface prose.

## FOR US

This is a **cross-domain method-borrow, not a domain transfer** — StoryScope is text/fiction, we are music; none of its features (plot, narrator, chronology) or its LLM-template pipeline literally apply to audio. What ports is the **measurement philosophy** for our rarity-lite / content-invariant idiosyncrasy scorer:

- **Score the choices, not the surface.** StoryScope's whole thesis is that *stylistic* signals (their em-dash/word-choice analog of our production/mastering artifacts) are a confound you deliberately strip, and that a **content/structure** feature space still carries the distinguishing signal. This is exactly our stance: raw-spectral features are dominated by the generation-vs-real production gap, so a content-focused representation is the right substrate. Their 93.2%-narrative-vs-96.0%-with-style result is the concrete evidence that a style-free space keeps ~97% of the signal — a useful existence proof for arguing our content-only scorer isn't leaving much on the table.
- **Rarity as a proxy for distinctiveness/originality.** Their **0.71 (human) vs 0.49 (AI) mean rarity percentile** is precisely the kind of contrast our rarity-lite scorer targets — "how far from the crowd's defaults" a generation sits, computed in a content space rather than a surface space. It validates rarity-percentile-in-feature-space as a defensible distinctiveness metric.
- **Edit-robustness as a design goal.** Their LAMP result (detection survives surface rewrites) is the property we want from our scorer: distinctiveness judgments should not flip when only production/mastering changes. Worth borrowing as an explicit invariance test — perturb production, confirm the rarity score is stable.
- **Fingerprints per generator.** Their per-model fingerprint idea (source-specific feature concentrations) is a plausible analog if we ever want per-checkpoint/per-decoder idiosyncrasy signatures on SA3 outputs.

## What stays ours

- **The representation.** We do **gen-vs-gen kNN rarity on MERT embeddings**, not an LLM-induced structured-feature vector. StoryScope's 304 narrative features are a text-only, LLM-annotation construct with no musical counterpart; MERT is our content-space substitute and the mechanism is entirely ours.
- **The production-confound finding.** Our specific empirical result — that raw-spectral features are dominated by the generation-vs-real production gap rather than musical content — is ours and is *why* we do gen-vs-gen rather than gen-vs-real comparison. StoryScope reaches an analogous conclusion in a different modality (strip style, keep structure) but never touches audio production/mastering; the confound and its avoidance strategy in music are our contribution.
- **gen-vs-gen framing.** We compare generations to other generations to cancel the cross-domain (gen-vs-real) gap. StoryScope compares AI to human in a matched-plot parallel corpus — the opposite move — which we deliberately avoid precisely because in audio that cross-domain axis is the confound.
