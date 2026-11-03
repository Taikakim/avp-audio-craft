---
name: scale-estimation-lessons
description: Wall-clock and RAM estimates broke twice at the 1.9B-crystal scale jump — never extrapolate linearly across scale without a measured constant; peaks include transients
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-09T01:16:54.260Z
---

Two burned estimates at film_grain's 1.9B-crystal flagship (2026-08-08/09):
(1) RAM: "field = 22 GB, fits" ignored per-sweep transients (int64 argsort permutation 15 GB + gathers + disp buffer) → kernel OOM at 73.5 GB RSS. (2) Time: linear scaling from 355M (104 s/sweep) predicted ~560 s/sweep; measured 2075 s — a 3.5× superlinear anomaly, still unprofiled (suspects: per-strip full-field membership scans ×22, per-strip GPU sorts). ETAs slipped "overnight" → "+1 day" → "+2 days".

**Why:** peak memory is resident + worst transient stack, and per-item constants drift with scale (cache behavior, scan counts scaling with strip count × field size).

**How to apply:** before any larger-scale run (full-frame 4.6B, LUMI), (a) measure the per-sweep constant AT a bracketing scale, (b) budget transients explicitly (the argsort→mask-selection fix cut ~30 GB and is the template), (c) quote ETAs only from measured constants at the target scale, (d) profile the 3.5× sweep anomaly first — it's a prerequisite for LUMI-scale packing.
