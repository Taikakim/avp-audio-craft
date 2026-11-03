---
name: synth-inversion-fx-leak
description: Surge XT FX in synth inversion — mix 0 does NOT silence the delay (found 2026-10-07); only slot TYPE Off works; all training/eval renders 10-06..10-07 carried a loud fixed delay; v3 clean retrain queued
metadata:
  node_type: memory
  type: project
  originSessionId: b207d8c1-afa9-47b8-bbe0-60db9d0c4899
  modified: 2026-10-07T09:48:26.501Z
---

Two FX problems in the synth-inversion renderer (stable-audio-tools/scripts/synth_inversion/surge_spec.py):

1. (2026-10-06) Hidden FX state across renders: after a patch with chorus/delay > 0, later renders in that
   instance differed. "Fixed" by setting FX output-mix / feedback to 0 (FX_RENDER_ENABLED=False).
2. (2026-10-07, found by Kim's ear on the eval page) **That fix never turned the delay off.** With the init
   preset's FX A2 = Delay, Output-Mix 0 leaves a live delay: one 8th note repeats at -11 dB every ~250 ms.
   Only setting fx_a1/fx_a2 **TYPE to Off** (raw 0.005) silences it. pedalboard then drops the Off slot's
   mix params from plugin.parameters, so set them only when FX are on. Test:
   `test_fx_off_single_note_has_no_delay_trail`. `surge_139_spec.py` still has the mix-only code (unfixed).

**Why:** every render 10-06..10-07 (H1 + H6 training data, refinement, all eval-page clips) carried the delay;
real stems don't, so it was a built-in domain gap. Kim's call: H1/H6 checkpoints near-useless, retrain once with
all improvements (v3: H1 recipe + cond_noise + MAE flow loss, FX truly off; `run_v3_clean.sh`, queued behind C's
Phase E). Old page `synth_inversion.html` has a warning banner; v3 page `synth_inversion_v3.html`.
**How to apply:** to verify FX are off, render ONE short note and check the tail for repeats (Kim's test) —
a zero mix value proves nothing. Before trusting any synth-inversion result, ask whether its renders predate
2026-10-07. Related: [[fleet-wait-arming]].
