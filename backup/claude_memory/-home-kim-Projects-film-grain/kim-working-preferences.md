---
name: kim-working-preferences
description: "How Kim works on film_grain — licensing care, taste-curve authority, sharing habits, run etiquette, build cadence"
metadata: 
  node_type: memory
  type: user
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-12T07:31:37.477Z
---

Kim (kim.ake@gmail.com, machine kim-deepspace, Finland/Helsinki tz):
- **Licensing-careful**: replaced a Helsingin Sanomat demo photo with CC `demo.jpg` for anything shareable (journalist permission pending); swap HS-derived images off shared artifacts when replacements exist.
- **Has the eye**: their GIMP-tuned print curve (150→197, 209→240) is the default display transform (`make_positive.py`, dated attribution in code); tone decisions defer to them — implement exactly, keep provenance. Judged sky over-exposure correctly (camera-side, not print-side) from one look at a PGM.
- **Shares publicly**: LinkedIn/Facebook posts about the experiment; wants paste-ready technical lists, accurate claims ("emergent, not programmed" is the differentiator they market). Business thesis: free distilled models + paid consulting (studios; restoration training data).
- **Outputs location**: all film_grain outputs (renders, logs, fit traces, shareable page sources) go under `/home/kim/Projects/film_grain/renders/` — never scratchpad/tmp, so they survive context resets (explicit instruction 2026-08-10).
- **Run etiquette**: check GPU/CPU idle ≥10 min before committing runs; `/tmp/gpu.lock` convention is machine-wide (their other agent swarms follow it). Comfortable with multi-day GPU runs when the output caches ("pack once, render forever" landed well). Has LUMI access ([[lumi-supercomputer-access]]).
- **Cadence**: says "go ahead with X" to greenlight builds; uses "ultracode" deliberately for big physics steps; appreciates honest ETA/quality flags and post-hoc accounting of what broke; darkroom background (school) — paper grades, dev-time push/pull vocabulary lands. Diagnoses from images alone (GIMP histograms found the RD-grid bug signature).
- **v3-era decisions (2026-08-12)**: showcase exposure eref 0.65 (their strip pick); TOKEN-BREAK mode on the film_grain stream — only roadmap planning/docs + heavy LUMI runs until further notice. LUMI allocation: ~2500 GCD-h, expires ~2026-08-25 (use-it-or-lose-it; burn menu in SESSION_STATE.md).
