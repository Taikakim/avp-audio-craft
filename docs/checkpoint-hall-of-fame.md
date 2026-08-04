# Checkpoint Hall of Fame

Checkpoints Kim has flagged by ear as worth **careful manual testing** later — the
shortlist for "when we sit down and really work with a model, start here." Add entries
with the full path, the audition context (which eval page / prompt / seed), and the
verbatim reason. Never prune without Kim's word; supersede with a note instead.

| # | Checkpoint | Path | Why (Kim's ear) | Added |
|---|---|---|---|---|
| 1 | `x20b3ygb_epoch3-step5400` — rank-16 dora-rows **Fusion**, goa corpus (b4-cont run, ≈ep6 overall) | `Mantu/sa3_lora_runs/sa3-goa-dora-47s-b4-cont/x20b3ygb/checkpoints/epoch=3-step=5400.ckpt` | Overall favourite of the dora_results board: "cleanest sound with sounds not diffusing in the spectral image"; best of the p1 s42 clips ("good clarity, sense of space"); clearest of the s1234 clips (with a caveat: slight electro-like kick/bass distortion typical of this prompt+seed when training starts traversing toward another style) | 2026-07-07 |

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

## 2026-07-10 — avp r64-tiered (dora64_avp_tiered) — Kim's ear

**HoF pick — `dora64_avp_tiered_lr2e4 · epoch00 · trig · s1234 · DoRA 1.0`**
(`avp_board_r64/r64_lr2e4__epoch00__trig__s1234__st10.wav`). Kim: "wonderful — the
disjointed collage-patch stuff is in the *layers* but the beat is solid. Vertical
movement and pitches, unlike the many clips that home on the interval parts of songs
(just kickbass + percussion + noises)." It's caught *just* at the edge of breakdown.
**Every later lr2e-4 epoch is useless even as an abstract effect** — the 2e-4 recipe
breaks down immediately (ep0 is the single usable checkpoint, right at the cliff).

**Good — `dora64_avp_tiered_lr1e4 · ep3–7`** (esp. `ep7 · s7 · DoRA 1.0 · kimlong`).
The whole ep3–7 range is usable. lr1e-4 is *under*-cooked by contrast — Kim: it "could
use ~+20% LR bump" to land the sweet spot where 2e-4 sits at ep0.

**Recipe read:** the two LR brackets straddle the sweet spot — lr2e-4 overshoots it by
ep0, lr1e-4 hasn't reached it by ep7. Target = ~lr1.2e-4 (or 2e-4 with far fewer steps /
a decay). Confirms the early-stop + low-ish-LR direction; the usable window for r64-tiered
is very early (ep0 at 2e-4, ep3–7 at 1e-4). "Vertical movement + pitches, solid beat" is
the quality axis the meters miss (the interval-homing failure = the conditioning/energy
collapse; solid-beat-with-moving-layers = what we want).
