# papers/ — the never-reinvent-again file

**Check here BEFORE building a training loss, guidance method, or optimizer variant.**
This is the *external* prior-art index; `ARCHITECTURE.md` is the *internal* reuse index.
Per paper: the PDF (`arxiv-<id>.pdf`) + a project-POV abstract (`arxiv-<id>.md`) stating
what it contains AND what it does *not* (i.e. what remains ours). Keep abstracts honest
about provenance: "verified citation pass" ≠ "deep-read".

Maintained by THE-FINN (overseer). Add rows newest-first. Founded 2026-07-03 on
CONTINUITY's assignment: "ControlNet++ goes in the never-reinvent-again file."

| Paper | One-liner | Status vs our work |
|---|---|---|
| [ControlNet++ (2404.07987)](arxiv-2404.07987.md) | Cycle-consistency for controllable diffusion: 1-step denoised estimate → frozen meter → consistency loss, adapter-only | **PRIOR ART for FusionCC's mechanism** (we reinvented it). Our boundary condition (blind-vs-redundant) + genre negative remain unpublished |
| [InnerControl (2507.02321)](arxiv-2507.02321.md) | Extends ControlNet++ to all-timestep consistency feedback | Adjacent to our t-gated variant; cite both. Our probe-hack guard + compliance-vs-cheating distinction not covered |
| [Backbone trajectory-PCA (2602.23696)](arxiv-2602.23696.md) | 60–80% of optimizer *displacement* in low-dim subspace, *uncentered* PCA | Different, weaker statement than our centered 88%-variance + PC2-turnover early-stop signal (claim 5: "not documented") |
| [Cautious/modded-nanogpt (2510.12402)](arxiv-2510.12402.md) | Speedrun cautious-optimizer work — weight-decay-only caution | Bounds claim 2: our keep≈0.53 + 1/√keep + mask×orthogonalization degradation mechanism unpublished anywhere |
| TAC-GAN (1907.02690) *(no abstract file yet)* | AC-GAN outputs confined by the frozen auxiliary classifier's decision boundaries | The HARM mechanism of our boundary condition, formalized — but with no redundancy conditioning. Cite in any boundary writeup |
| Du et al. gradient-cosine gating (1812.02224) *(no abstract file yet)* | Gate aux losses by grad cosine ≥ 0 | **Predicts redundant aux is harmless (cos≈+1 passes) — our genre negative CONTRADICTS it.** The publishable tension |
| Physics-aware aux losses (2606.12651) *(no abstract file yet)* | States the redundancy condition near-verbatim (discriminative GNN setting) | Finds redundant aux **neutral**, not harmful — our generative-manifold degradation goes beyond it |
| Bjerva 2017 (ACL W17-0225) *(no abstract file yet)* | Information-theoretic prediction of MTL aux-task benefit | Cousin of the helps-half (help vs no-help only, representation-sharing MTL, no frozen probe) |

**Open verification threads** *(update rows when they land)*:
- ~~Counterexample hunt on the blind-vs-redundant boundary~~ **LANDED 2026-07-03 16:12**:
  no prior statement of the biconditional as a predictive law; both halves exist
  separately (rows above). Verdict: downgrade to **"novel predictive boundary
  condition, first explicitly stated and cleanly tested — demonstrated in diffusion
  control."** Full resolution: docs/research-brief-2026-07-03-novelty-check.md
  (RESOLUTION §, claim 1). Abstract files for the four new rows: FINN's archive pass.
- Full novelty-verdict context: AGENT_DIALOGUE.md 2026-07-03 11:03–11:09 (CONTINUITY's
  7/7 citation verification, zero fabrications, two Gemini soft spots caught).
