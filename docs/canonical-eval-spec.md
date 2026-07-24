# Canonical eval spec — comparable checkpoint auditions

*2026-07-06, GHOST-NOTE, per Kim's ask ("did we have the eval spec written down") —
this is the reference so future checkpoint audits stay comparable to past ones,
rather than each instance re-deriving prompts/seeds/params ad hoc.*

> ## ⭐ STANDING DIRECTIVE (Kim, re-affirmed 2026-07-24) — LUMI runs self-eval
> **Every LUMI training run produces its OWN full eval suite per this spec, as PART OF THE
> RUN** — rendered and scored on LUMI, so each checkpoint lands **audit-ready and comparable**
> and nothing waits on the scarce local card. "Full eval suite" = the correct eval family
> below (§1 control-adapter grid *or* §2 plain-DoRA sweep, picked by what the checkpoint is)
> **+** for any control-adapter checkpoint the **mandatory** control-head disintegration gate
> (`eval/control_head_disintegration_eval.py`, Kim 2026-07-20 — required before any
> "works/usable-range" claim) **+** the now-standard semantic columns (`eval/mood_drift.py`
> retention + `eval/clap_score.py` genre-hold). A training run is not "done" until its evals
> exist. This is a standing rule, not a per-run reminder.

Two distinct eval families exist and are **not interchangeable** — pick by what the
checkpoint actually is:

## 1. Control-adapter grid (gain × density sweep)

For checkpoints with a **trained control adapter** (cross-attention, e.g. onset-density
steering). Reference implementation: `control/sa3_control/onset_eval.py`, rendered/scored
sets: `composed_sweep/{A_cc,A_cc_v2,E_fusion,E_fusion_v2}`.

- **Prompts** (3): `"aggressive upbeat goa trance"`, `"energetic acid techno, 130 BPM,
  driving analog bassline, crisp drum machine"`, `"psytrance, 140 bpm"`.
- **Seeds** (2): `1234`, `4242`.
- **Gains**: `[1.0, 2.0, 3.0]`. **Densities**: `[1.0, 3.0, 5.0, 6.0, 7.0, 7.5, 8.0, 9.0, 12.0]`.
- **Generation**: `steps=24`, `cfg=6.0`, duration ≈ 20s (T=256 SAME-L latent frames, 23.8s actual).
- **Scoring**: `pq_score.py` (Audiobox CE/CU/PC/PQ + `spectral_balance`), plus onset
  requested-vs-measured correlation. Rendered via `Misc/eval_grid.py` (gain-grouped rows,
  CE/PC health badge, 6-metric sort — see `docs/superpowers/specs/
  2026-07-05-eval-grid-rich-renderer.md`).
- 3 prompts × 2 seeds × 3 gains × 9 densities = 162 clips per checkpoint.

## 2. Plain DoRA / caption quality sweep (no control adapter)

For checkpoints that are **just a DoRA/LoRA weight delta + caption changes** (no control
adapter — the gain/density axis is meaningless without one). Established 2026-07-06 for
the `dora128_everything_8ep_lr1x` audit; **this is the "canonical run" Kim asked about.**

### 2a. Prompt selection — by caption frequency RANK, not raw count

Prompts are chosen from the ACTUAL training-caption distribution (the merged 5-corpus
`t1` tier captions used by `train_lora.py --caption-sidecar`), not hand-picked genre
strings, so the eval measures the checkpoint on the tags it actually saw.

**Why rank, not count-percentile:** the caption count distribution is extremely
long-tailed (6110 total, 1882 unique; median count = 2, mean = 3.25, 90th percentile =
only 4) — most unique captions occur once or twice, so percentile-of-count degenerates
(25th/50th percentile both land on count=2). Rank position in the frequency-sorted list
is the meaningful axis instead.

- **COMMON** — rank 1/1882 (n=60): `"2020s goa trance, 145 bpm"`
- **MEDIUM** — rank ~50% (n=2): `"early 90s techno, house, 128 bpm"`
- **RARE** — rank ~85% (n=2): `"ambient, experimental, dark soundscape mood, 107 bpm"`

To regenerate this selection for a different/expanded corpus, see the frequency-analysis
snippet in `WORKLOG.md` (2026-07-06 entry) — reads every `t1` caption from
`mir/data/feature_tables/<corpus>/captions.json`, ranks by `collections.Counter`, and
picks by rank position (1, len//2, int(len*0.85)).

### 2b. Seeds, DoRA strength, length — the actual grid

- **Seeds** (2): `1234`, `4242` (matches the control-adapter convention above, for
  cross-family comparability where relevant).
- **DoRA strength** (3, deliberately asymmetric around 1.0): `0.8`, `1.0` (as-trained),
  `1.4`. Set via `stable_audio_3.models.lora.model.set_lora_strength()` **before**
  `merge_lora()` — see `onnx/export_dit_onnx.py --lora-strength`.
- **Lengths** (4, the ONNX ladder rungs): `256` (23.775s, baseline) / `512` (47.550s) /
  `1024` (95.100s) / `4096` (380.436s, ~6.3 min, the practical max). Each length needs
  its **own DiT ONNX export** (fixed-shape graphs, no dynamic axes) — see §3.
- **Generation params**: `steps=24` (see §2c for why), `cfg=6.0`.
- **Total**: 3 prompts × 2 seeds × 3 strengths × 4 lengths = **72 clips per checkpoint**.

### 2c. Step-count diagnostic (run once per model family, not per checkpoint)

A quick side-check before trusting `steps=24` as the sweep default: 1 prompt (COMMON),
5 seeds (`1234, 4242, 1000, 2000, 3000`), `steps ∈ {24, 48}` = 10 clips, T=256 only.

**Verdict (Kim, 2026-07-06, ear check on the staged page):** "the 24-step versions are
nearly identical to 48-step ones. Some slight differences in detail, but not really
quality." Matches the objective deltas (spectral centroid / RMS — small, mixed-sign
across seeds, no systematic drift). **`steps=24` is confirmed as the sweep default** —
cheaper, and the saving compounds most at T=4096 where step count dominates wall-clock.
Re-run this diagnostic if the base model or sampler changes; not needed per-checkpoint.

### 2d. Later step (not this pass)

Once a "best" checkpoint/strength/length combo is picked from the above, extend to the
FiLM (release-year) and LatCH-guided variants using the SAME prompt/seed grid, so those
stay comparable to the plain-DoRA results too.

## 3. Practical pipeline (ONNX, CPU-only, GPU stays free for training)

1. **Merge + export the DiT**: `onnx/export_dit_onnx.py --model medium-base --frames <T>
   --lora-ckpt <ckpt> --lora-strength <s> --out <name>.onnx --validate`. Validates against
   the torch reference at export time (`cos≈1.0` expected). One export per (T, strength)
   combo — 12 for the full §2b grid (11 after the T=256/s=1.0 baseline, which most
   checkpoint audits will have already produced once for a quick look).
2. **Text conditioning**: `onnx/make_text_cond_sweep.py --out-dir <dir>` — precaches
   cond/uncond npz per (prompt, T) combo (T matters because `seconds_total` feeds the
   global/timing conditioning, not just the text itself). CPU-only, ~1.4B weight load,
   cheap forward passes, one load for the whole sweep.
3. **Decode**: reuse the existing `same_decoder_L128.onnx` (or `same_decoder_L128_fp16.onnx`)
   — decoder is independent of DiT length (chunked internally), no per-length re-export.
4. **Generate**: `onnx/dit_onnx_infer.py --dit-onnx ... --decoder-onnx ... --cond ...
   --uncond ... --frames <T> --steps 24 --cfg-scale 6.0 --seed <s> --provider cpu`.
5. **Stage + describe**: transcode to AAC, stage under `~/.cache/evals_aac/{control_runs,
   renders}/<name>/`, write a `run_meta.json`/`_meta.json` sidecar (purpose, checkpoint id,
   grid params) per the standing self-describing-outputs convention (MASTER §4), rebuild
   `Misc/build_evals.py`.

**Provider note**: `stable-audio-3/.venv`'s onnxruntime is CPU-only (no MIGraphX EP
installed there — that's `mir`'s onnxruntime_migraphx build). Always pass `--provider
cpu` explicitly when using this venv; the auto-detect path would only matter in a venv
that also has a GPU EP installed.
