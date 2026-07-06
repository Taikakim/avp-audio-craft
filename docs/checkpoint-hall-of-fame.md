# Checkpoint Hall of Fame

Checkpoints Kim has flagged by ear as worth **careful manual testing** later — the
shortlist for "when we sit down and really work with a model, start here." Add entries
with the full path, the audition context (which eval page / prompt / seed), and the
verbatim reason. Never prune without Kim's word; supersede with a note instead.

| # | Checkpoint | Path | Why (Kim's ear) | Added |
|---|---|---|---|---|
| 1 | `x20b3ygb_epoch3-step5400` — rank-16 dora-rows **Fusion**, goa corpus (b4-cont run, ≈ep6 overall) | `Mantu1/sa3_lora_runs/sa3-goa-dora-47s-b4-cont/x20b3ygb/checkpoints/epoch=3-step=5400.ckpt` | Overall favourite of the dora_results board: "cleanest sound with sounds not diffusing in the spectral image"; best of the p1 s42 clips ("good clarity, sense of space"); clearest of the s1234 clips (with a caveat: slight electro-like kick/bass distortion typical of this prompt+seed when training starts traversing toward another style) | 2026-07-07 |

## Audition context for entry 1 (dora_results.html, 2026-07-07)

The observations that surrounded the pick — kept because they generalize:

- **Rank 16 Fusion (x20b3ygb)**: after ~step 2700 the style goes "back and forth,
  drifting around the best solution" (consistent with the trajectory finding: direction
  found, then drift — the EMA/early-stop regime). For prompt+seed pairs *further from*
  the base model (p1 s42), learning continued through the last checkpoint — nowhere
  near stopped. For close pairs, later steps mostly wander.
- **Rank 64 (i8nygj4y)**: surprisingly NOT better than rank 16. Genres drift around;
  checkpoints in the same series sound quite different from each other.
- **Rank 128 Fusion (mqe3ne49)**: WORSE — in-dataset goa prompts degrade into "diffuse
  and impact-less" after ~step 5400 (s1234) / ~2700 (s42), while out-of-dataset prompts
  (techno, psytrance) learn fast and stay fine. Kim "ready to pawn my head" that bigger
  ranks need regularisation/damping (grad-accum, lower LR, EMA).
- **Rank 128 AdamW**: won't learn the new style at our settings — p0 tries to find goa,
  falls back to "happy synth music" by step 10800. Same AdamW style-inertia we saw with
  the FiLM adapter. Fusion learns where AdamW refuses.
- **Soups**: basic soups all lose to normal checkpoints (psytrance snappy/clear though);
  cross-optimizer soups nearly identical to Fusion-only — AdamW contributes ~nothing.
- **s42 vs s1234**: different but "same, nothing conceptually new" — possibly the model
  shuffling existing material for styles the training set lacks (modern psytrance).
