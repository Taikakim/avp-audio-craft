---
name: shared-framework-multi-version
description: Gradio UI and framework serve multiple Stable Audio versions with different hyperparameters
metadata: 
  node_type: memory
  type: project
  originSessionId: a76bbe73-5250-4a70-accd-5324dfe52aa8
---

The Stable Audio project uses a **shared framework** that serves multiple major versions (Stable Audio 1, 2, and 3) with different sampler and hyperparameter settings.

**Why this matters:**
- Tasks touching the Gradio UI (`stable_audio_3/interface/`) or general infrastructure could affect multiple model versions
- Changes to sampling, conditioning, or inference paths need careful consideration of version-specific differences
- Testing may need to account for version-specific behavior differences

**How to apply:**
- When modifying shared UI components or inference infrastructure, check whether changes should be version-specific or generic
- When adding features to the Gradio interface, verify behavior across model generations (not just SA3)
- Hyperparameter defaults and sampler logic may differ between versions — verify current version behavior before generalizing
