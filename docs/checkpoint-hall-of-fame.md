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

## 2026-09-27 — goa-style listening pass over the DoRA rows (Kim's ear, relayed in chat)

Verbatim per-model verdicts are in each label's `kim_feedback` (`Misc/models_index_overrides.json`,
surfaced in the census). The picks and the pattern:

**HoF picks (goa style)**
- `lion_lr1e-5` ep399 × rb_rare_8 — "very very excellent ... Chakra ... change-of-the-millennium with detuned sharp sounds"
- `x0eq_goa` ep19 × kl_2 — "superb, like Power-Gen from Astral Projection, or 1994-1996 hoover hard trance, just fantastic"
- `subloss_v3sel_k5` ep19 × kl_2 — "This just... Superb"; `subloss_v3sel_k2` ep19 — "also just superb, more aggressive"
- `fp32frames_goa_t4096_bs4_lr1e4` ep3 × kl_bracket_0 — "very excellent style" (slightly harsh)
- `lion_lr5e-5-batch32` ep444 × rb_rare_8 — "1998-early 2000s Phantasm Records ... UK post-goa"
- `winning_goa_t512_a45_fp32` ep50 × kl_2 — "very dark, very good" (the bf16 twin: great melodies, hot/thin)
- `fullft_avp_t256` / `fullft_avp_t256_sweep` ep153 — "excellent" / "fabulous" (full clip sets requested)
- dorlor "_excellent_" goa set: goa lora/dora × fusion/adamw (ep55-63), avpaug lora/dora (ep127-159) × rb_bracket_0;
  special mention `dorlor_suomi_dora_fusion_..._ep319_on_avpft153` ("almost falling apart but keeping its own")
- `dora128_everything_8ep_lr1x` ep0 × rb_mid_5 — "WTF? It's ep0 and already has an excellent style"
- `goa5k_r128_shampoo_subloss_k5_2026-09-26` step 8088 — "the most distinct melody ... the subspace thingy actually seems to work, although at the cost of bass sometimes"

**Pattern (Kim):** the old Schedule-Free / fp32frames / Lion / Fusion trains beat the new modular/shampoo ones at the
oldschool goa style AND the 90s production aesthetic; many learned it in 3-4 epochs. `goa3_avp_r128_shampoo` step
10144 "sounds close to AdamW". Plain AdamW at short horizons is "hopeless" (though dorlor AdamW at ep63 is excellent:
"even AdamW learns with time"). Direction: "drive our learning harder _and_ somehow control the issues we have."

**Measured explanation (W, same day):** "epoch" is not comparable. By latent frames seen: ablation a00 @1011 ≈ 4.1 M,
overnight goa5k @8088 ≈ 33 M, fp32frames_goa_t4096_bs4 "ep3" ≈ 88 M (~21x a00) — T4096 samples a whole track per
item, T256 one 23.8 s window. Plus the SNR gate cut the modular recipe's effective lr ~5x (ablation 2026-09-26,
`ablation_goa5k_2026-09-26/REPORT.md`).

**Ablation arms by ear (step 1011, rb_mid_4 / rb_rare_8):** a00 full = normal production balance, off-beat ride comp,
still club-trancey; a01 no_snr "more mature" but loses the sub-bass; a02/a03 ≈ a01; a04 more aggressive/snappy; a05
no_shampoo "could almost be old Prana"; a06 no_sf most sparse; a07 no_normuon sparse with a distinctive goa kick; a08
thin, rolling; a09 AdamW "cheap sounds"; a10 ≈ a00. Out-of-scope house prompt (rb_rare_6) ≈ identical everywhere.

**Requests from this pass:** ptm renders for goa5k subloss and the subloss_v3sel k2/k5/k12 arms; full clip sets for
fullft_avp_t256(_sweep) last ep and the terminal_winning ckpts (+ w0.5); a similarity metric over the ablation clips;
base + base_ptm rows pinned at the top of the player.
