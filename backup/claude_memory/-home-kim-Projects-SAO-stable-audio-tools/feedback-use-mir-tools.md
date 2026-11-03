---
name: feedback-use-mir-tools
description: "For LatCH range-bracketing and training-result verification, use the MIR project's existing tools instead of building bespoke SAO scripts"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

When setting LatCH target-slider ranges ("bracketing possible parameter ranges")
or verifying that a trained head actually controls its feature, **use the MIR
project's existing tooling** (`/home/kim/Projects/mir`, repo `Taikakim/mir-feature-extraction`)
rather than reinventing it in stable-audio-tools.

**Why:** MIR is the source of truth for the features — it computes them, stores
their distributions, and has verification scripts. Hand-rolling DB queries or
re-deriving feature math in SAO duplicates that and can drift from the real
definitions. (This session I sampled the DB by hand for ranges and wrote
`latch_verify_rms.py` re-importing MIR extractors — the user pointed out MIR
already has these.)

**How to apply:**
- **Range bracketing** (sensible slider min/max + linear/log per feature):
  `plots/build_dataset_stats.py` (per-feature distributions), `plots/correlate_features.py`.
- **Verify training results** (does generated audio exhibit the target feature):
  the real extractors in `src/spectral/` (`multiband_rms.py`, `timeseries_features.py`)
  — import these, don't re-implement; `scripts/verify_features.py` for coverage.
- The features + their canonical ranges live in the [[mir-project]] timeseries DB;
  prefer MIR's analysis over ad-hoc SAO scripts. See [[latch-verification]], [[latch-sigmas-schedule]].
