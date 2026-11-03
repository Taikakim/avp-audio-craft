---
name: riffer-product-vision
description: "The riffer density control's north-star use-case is in-context density modulation (busy A-part → stripped intro, same identity)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

The production north-star for the SA3 riffer (onset-density control) is **in-context density modulation**: take a busy "A-part" draft clip and dial density DOWN to get an intro/breakdown that keeps the tune's identity — "interesting ways to strip the sound" instead of the cliché (mute percussion + minor pad + atmospheric FX). The user is a producer who hits this exact wall drafting intros from busy sketches.

**Why this reframes the work (it justifies the disentanglement chase):**
- It REQUIRES disentanglement — stripping density must keep style/context, else you get a *different track*, not a variation of the draft. This is why the ep2-clean finding, the learned tempo-shortcut, and BPM-norm matter as more than metrics.
- It points to an **editing mode**, not pure generation: anchor on the user's busy clip (inversion / FlowEdit — `sa3_flowsep.py` already exists in stable-audio-3) and re-generate at lower density → variations of THEIR sketch. The value is a model that has learned "what sparse versions of *this* sound like" = the sparse↔dense manifold the genre expansion (psychill/house/soft-techno) will fill in.

**The control is a SPAN, not a point — do NOT over-optimize for precision.** The tool must work *predictably* (tight tracking, disentangled) for the workflow, AND be pushable into the OOD / "oblique" regime (high gain, the kick/16th meld, style-morph) for serendipitous discovery — *"too much control is a trap."* The interesting failures ARE a feature: pushed past predictable, the tool becomes an Oblique-Strategies-like creative instrument. So the optimization target is the **span (predictable → oblique)**, not a single maximally-controlled point; the **gain knob is the predictability↔serendipity dial** (low = tight/in-dist; high = OOD/exploratory). Metrics (|m-r|, tempo-drift, style-drift) *map* the span — they are not targets to clamp everywhere. The oblique end is judged by ear (subjective "interesting-ness"), which is why hands-on manual auditing matters.

Pairs with [[sa3-riffer-findings]] and [[lumi-cluster-bracketing]]. Roadmap: combine the density head with SA3 generative editing for clip-anchored density variations.
