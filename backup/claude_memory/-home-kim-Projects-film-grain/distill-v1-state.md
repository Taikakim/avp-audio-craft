---
name: distill-v1-state
description: State of the grain-distillation network (distill/) as of 2026-10-26 and data gotchas
metadata:
  type: project
---

distill/ holds v1 of DISTILL_PLAN (MeanNet + depth6/dim256 DiT, gates). Only local data exists: one 1920x1371 image, 8 stills + 24 motion frames + v2 flagship. No new LUMI grain fields were on any drive (Mantu/UUID checked; UUID `renders/` is the audio project's).

**Why:** Kim wants to replace slow/huge-field renders with a fast generator. 9-min smoke run matched mean D and pixel std but not the Wiener spectrum or seams — needs a long run.

**How to apply:** never train on `renders/demo1920v3_D.npy` (buggy streamed-RD render). v-loss ~1.0 is the Bayes floor for white-ish grain — judge with `distill/evaluate.py`, not loss. Raw hp-correlation between realisations is ~0.39 from image edges; compare against the sim-sim baseline. Long runs need Kim's go-ahead (local GPU = <10 min evals) — see [[kim-working-preferences]].

**Update 2026-10-26 evening:** 5k run (runs/v1_5k, 10 ckpts) — gates FLAT from step 500, so more steps won't help; fix objective/architecture (overfit test, patch/loss variants). 16 DDIM steps under-amplify grain (use >=64). Independent 64x64 tiles have a ~1.40 seam-ratio floor even with perfect sim tiles (neighbour pixel correlation) — seam gate needs overlap/cross-tile conditioning. /home was ~4 GB free (other writers); checkpoints are 62 MB each.

**Ladder 2026-10-26:** overfit (100 tiles) passes => architecture can represent grain; N=1000 vs 10000 give identical held-out spectrum error (mid -0.3, high +0.24 ln) => not data scale, it's objective/optimisation. Benchmark harness = distill/ladder.py --n 10000 (6 min/variant). Process exit prints a double-free abort (exit 134) after results are written.

**v2 2026-10-26:** conv output head (GrainDiT(head='conv')) fixed the spectrum — all gates pass at 64 DDIM steps except tile seams (1.39 = independent-tile floor 1.40). Best ckpt runs/v2_conv/ck_005000.pt. Loss weighting did not matter. Next: overlap/neighbour-conditioned tiles for seams; bigger model needs microbatching (512x8 OOMs at bs64). My earlier "v-loss~1.0 is the floor" was only true for white data.
