---
name: riffer-listening-verdict
description: "Producer's subjective listening verdict — Fusion preferred, cross_25A75F a standout, longer Fusion has vibe"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

Producer's verdict after thorough listening (2026-06-26). Treat as **authoritative where it conflicts with metrics** — subjective quality is the real eval (see [[riffer-product-vision]] on the predictable↔oblique span; numbers map it, the ear judges it).

- **Fusion runs are the most useful overall** and **tolerate heavier steering** better than AdamW.
- **cross_25A75F (25% AdamW + 75% Fusion model-soup) is the surprise standout** — "the musicality of Fusion and the acoustic and structural rigour of AdamW," a top favourite. The numbers agreed (best |m-r| 1.4, kept range). **Cross-optimizer souping is a real recipe** — and it's free (CPU averaging, no training). Worth sweeping more ratios.
- **Favourites right now:** Fusion-40ep **ep20**, Fusion-40ep **soup_expasc**, and **cross_25A75F**.
- **Longer training is subjectively BENEFICIAL for Fusion** — the 40ep Fusion has "a strong vibe" *despite* its control metrics (range) being narrower. This **refines the earlier "longer hurts" conclusion**: that was metric- and AdamW-specific. Longer training narrows control *reach* but matures the *vibe*, and for the production tool the vibe wins → **a longer Fusion run is worth pursuing** (e.g. extend past 40ep, or a fresh long Fusion). The map (range↓) and the territory (vibe↑) diverge here.

Pairs with [[sa3-riffer-findings]] and [[lumi-cluster-bracketing]].
