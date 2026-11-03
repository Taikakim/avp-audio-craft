---
name: sa3-dora-goa-finetune
description: "SA3 DoRA Goa finetune (2026-06-30) — light touch, early-is-best, DATA (not capacity) is the lever"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

SA3 medium-base DoRA finetune on the Goa corpus (NVMe latents_sa3, beat-aware T≈512 crops, full-state ckpts).
**4 variants:** rank-16-AdamW, rank-64-AdamW, rank-128-AdamW, rank-128-Fusion(+2×LR, components
mona/ns5/normuon/sf, **shampoo OFF** — KL-Shampoo two-sided preconditioners OOM rank-128 on 16GB; turning it off
fixed it). Eval = render (GPU, 2 seeds 1234/42, via `eval_dora_cpu.py --device cuda --seeds`) + Audiobox
(CE/PQ/PC/CU) + MERT distance-to-Goa (`cos_dist_mid`/`_up` + Frechet vs a cached 150-clip Goa ref;
`eval_dora_quality.py`). Soups via `soup_dora.py` (within-variant) + `soup_cross_dora.py` (cross). UI =
riffer-evals `dora_results.html` (playable same-playhead cells + metrics, all variants + soups + cross).

**The finetune is a LIGHT touch** (all cosD_mid 0.024–0.036, tight) and **early-is-best — more training drifts
AWAY from Goa** (by ear: later ckpts lean modern-psytrance, not 90s goa). Best single overall =
**rank-128-AdamW ep0 (0.0242)** — extra rank bought ~2% (a small win, not a leap; ep0 still beat all later
epochs). Fusion didn't improve the mid but **won the upper/harmony layer** (cosD_up 0.0159 vs ~0.021).

**Soups:** within-run, **expdesc/goodearly (early-weighted) beat expasc (late-weighted)** → confirms early-is-best;
the literal "exp ascending" recipe (last-epoch ~44%) was wrong here. Best soup r16_goodearly 0.0252 ≈ best single
→ **souping buys robustness, not a jump**. Cross-optimiser (0.25·AdamW-r128-ep0 + 0.75·Fusion-r128-ep3, ratio
sweep 10/90…30/70): **doesn't beat the best single on cosD_mid** (Fusion-dominated ~0.0266, didn't fully fuse
timbre+harmony) BUT **best Frechet (0.071) + good CE (cross_10A90F 6.77)** = a distribution-match/quality play.

**ROOT CAUSE of the modern-psytrance drift = the DATA, not capacity.** Captions mix genre — "goa" 12407 vs
"psytrance" 6329 for the *same* 90s music (Spotify/MB metadata inconsistency) — and ~1800 tracks are 2007–2019
(modern tail). So the model learns a smeared goa+modern blend. **The real lever for a 90s-Goa identity = a cleaner
subset (year ≤ ~2001, drop the modern tail, prefer goa-labeled) + re-encode + re-train + early-stop** — more
rank/Fusion/cross is marginal. This echoes [[sa3-latch-head-sweep]] (averaging/early-stop > more).

Train edits (UNCOMMITTED, stable-audio-3 fork): `train_lora.py` (--ema/--grad-accum/--beat-aware-crop/--optimizer
fusion), `data/dataset.py` (beat_aware_crop downbeat-aligned), `training/diffusion.py` (full-state ckpt).
Run dirs: Lehto/sa3_lora_runs/{sa3-goa-dora-47s-b4(+-cont)=r16, -r64, -r128-fusion, -r128-adamw, soups_dora/}.
