---
name: sa3-field-guide-book
description: "The SA3 'Hands Inside the Instrument' field-guide book — a Hopkin-style book of questions for musicians; lives on audio-tools-avp main"
metadata: 
  node_type: memory
  type: project
  originSessionId: b1ee18e7-1ef0-45fd-90ba-5aadcdcad6ec
---

A complete book — **"Hands Inside the Instrument: Understanding and Tuning Stable Audio 3"**
— in the spirit of Bart Hopkin's *Experimental Musical Instruments*: a book of QUESTIONS not
blueprints, for a musician/luthier (acoustics + basic DSP, not a coder/mathematician). No
code, no heavy math. Preface + 16 chapters + index, ~44k words.

**Lives in `Taikakim/audio-tools-avp` (the stable-audio-tools fork, remote `avp` in
`/home/kim/Projects/SAO/stable-audio-tools`), on `main`, at `docs/book/`** (alongside the
existing architecture docs). Commits `822d851` (first edition) + `ca1b196` (polish), also on
branch `book/sa3-field-guide`. **It is DONE — do not regenerate it.** Edit in place if revising.

Arc (apprenticeship): what kind of instrument SA3 is → the latent material → carving from
noise + the molten-ness dial σ → the carver's body (attention, adaLN voicing, stabiliser
norms, RoPE/memory) → the voice (prompt/conditioner) → the dials already on it (CFG, SDEdit,
inpaint/mask, σ schedule) → the builder's additions (Ch11 **what a LoRA/DoRA actually is**,
Ch12 **re-voicing the body vs bolting on a sense**, Ch13 control heads / training-free
guidance) → Ch14 the **seven-axis map** of control methods → Ch15 honest frontier (per-moment
σ, live-feedback heads) → Ch16 **dreaming new controls + articulating them so an AI can build
them** ("a model's capacity stays locked until the right words are uttered"). Throughline:
where control can be injected, at training and inference.

Built + polished entirely via multi-agent **Workflow** orchestration (outline → parallel
synopses → overlap review → chapter drafts with Haiku connection-weavers → revision → a
per-chapter polish pass enforcing single-owner-per-concept and analogy variety). Related:
[[longform-render-sa3]], [[infinite-audio-fifo-sa3]].
