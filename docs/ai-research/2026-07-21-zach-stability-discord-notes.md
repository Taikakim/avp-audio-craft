# Zach (Stability AI) on Discord, 2026-07-21 — base→PT adapter transfer, layer roles, CFG

*Captured by CONTINUITY from Kim's paste (SA community Discord, ~01:45–01:53 AM). Kim: "solid
gold." Primary-source practitioner notes from the SA3 team — treat as strong prior, not gospel;
the transfer claim is exactly what task #55 tests empirically.*

## The headline claim (now triangulated 4 ways)

**L/DoRAs trained on `medium-base` work on the post-trained `medium`.** Confirmed independently
by: two Discord users, Dadabots, and now Zach from Stability directly:

> "we're really happy/lucky that the models trained on the base model translate to the
> post-trained model. There's basically no advantage to using the base model over the
> post-trained one except for having a stable flow model training objective, and for anything
> that requires flow model inversion"

One user further claims PT+finetune output is "not really different from base [medium+finetune],
and it's even better." Kim is suspicious (every shortcut he's seen — quantisation, post-training,
distillation — hurts information-dense boundaries and collapses toward an average, e.g. Flux Dev's
"is this background sound a pad or a filtered saw?" failures). **Empirical check = task #55**:
`fp32cmp_goa_t4096_bs4_lr1e4` rendered on PT medium as `*_ptm` rows on the model matrix.

## Zach's mechanism (why transfer works)

- Consistent across "basically every transformer-based model": **first 6-8 layers encode, last
  6-8 layers decode, the middle is "the projected realm of all knowledge and reason."**
- LoRA changes concentrate **in the middle layers** ("general knowledge is in the middle layer" —
  he had Claude analyze where LoRAs make the biggest changes).
- ARC post-training (flow model → "multi-step GAN") mostly **rewrites the last few decoder
  layers**, not the middle.
- Therefore base-trained LoRAs (middle) and ARC's changes (decoder tail) **don't interfere**.
- The middle realm is "very orthogonal (**Muon in the pre-training helps this**)" — which is also
  why **multiple LoRAs compose** without fighting each other.

**Cross-links to our own results:** our per-layer adapter-injection ablation (task #44,
`eval/ablate_adapter_layers.py`) measured where onset control enters — re-read those results
against Zach's encode/middle/decode split. Also `docs/dora-alpha-audit-2026-07-12.md` and the
DiT layer×feature activation extraction (task #25).

## Training-objective notes

- "Diffusion is actually pretty inefficient and has a pretty bad ceiling" — but "damn is
  diffusion (or flow matching) a stable training objective."
- **Flow matching "comes with its own data augmentation, so you can go dozens of epochs over
  small datasets without completely memorizing it (though hundreds of epochs is riskier)."**
  Directly relevant to our small-corpus DoRA epoch counts (avp = tiny corpus; our overtraining
  curves on the matrix stats page agree: quality peaks ep0-4 un-augmented).

## CFG on the post-trained model

- Zach: "**CFG is a horrible hack** (even though it works really well) and anything you can do
  to get rid of it is a good thing."
- "CFG artifacts really don't play nicely with pingpong sampling, though sometimes the model can
  still recover if you do **higher CFG at higher [noise] steps and turn it off later on with
  `cfg_interval_min`**."
- German (user): on PT, CFG "mostly just cooks the output"; habit = **seed-fishing at cfg 0,
  sounded better than cfg 1**; interval-CFG (high early, off late) is "the only way i found to
  have acceptable quality at over 8 steps."

**Cross-links:** our interval-CFG lane (task #26 + F's relayed A/B: sweep the high-noise upper
bound first, e.g. (0.0, 0.7) in flow-t units) — German's field experience independently lands on
the same shape (guidance early in the schedule, off late). The `*_ptm` cfg7 probe cells on the
matrix (ep4) capture the "cooking" for the record.

## Standing implications if #55 confirms transfer

1. **Audition renders get ~6-10x cheaper** (8-step ping-pong, cfg 1) — the matrix PT pass runs
   ~3s/clip vs ~8s at steps24, with no CFG doubling. Big-page coverage and future bracket sweeps
   could default to PT for *listening* while training stays on base.
2. Training stays on `medium-base` regardless (stable flow objective + anything needing
   inversion — our SDEdit/a2a/separation machinery REQUIRES base, see MASTER: "post-trained =
   stochastic ping-pong, cfg inert").
3. LoRA composability (orthogonal middle) supports the dual/layered-LoRA experiments
   (`eval/dual_lora_a2a.py`, `eval/layered_lora_a2a.py`).
