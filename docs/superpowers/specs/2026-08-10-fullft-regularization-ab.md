# Full-FT regularization A/B — bounding the latent-scale runaway without dulling detail

**Author:** CONTINUITY · **Date:** 2026-08-10 · **Status:** spec (impl pending)
**Context:** follow-up to the full-FT spectral-drone incident (lumi-ops SKILL "FULL-FT LATENT-SCALE
RUNAWAY"; `docs/lumi-throughput-workflow-guide.md` §7). First A/B (`fullft_wd_ab.sbatch`, job
20940322) tests whether **weight decay** bounds the runaway. This one tests **gentler / more targeted**
regularizers, because plain `wd 0.1` may sand off the fine features we're trying to strengthen.

## Question
The full-FT latent output scale runs away (global std 0.7→5.6, ep3→ep7; `#chan>2.0` 0→166/256) because
FusionOpt's NS5/Muon update injects grad-magnitude-independent energy and the default `spectral_wd=0.01`
is too weak. Plain weight decay bounds it but is **blunt** — it shrinks *all* weight directions,
including the subtle feature-bearing ones. **Can a scale-relative gradient limiter (AGC) and/or a
targeted output-scale penalty bound the runaway with less collateral on fine detail than broad weight
decay?**

## Two new levers (must be implemented — see §Impl)
1. **AGC (Adaptive Gradient Clipping, NFNets / Brock et al.)** — instead of hard-clipping the global
   grad norm, clip each unit's gradient *relative to its own weight norm*: `g ← g·min(1, λ·max(‖w‖_u,ε)/(‖g‖_u+δ))`,
   per output-unit (row for 2D matrices). Near-noise / small-weight params keep moving; only
   large-grad-relative-to-scale units are reined in. The scale-relative version of "don't limit
   everything uniformly."
2. **Output-std penalty** — the pathology is measured in the *output* (z0 per-channel std drifting off
   the data distribution). Penalize it directly: `L_out = λ_out · mean_c (std_c(ẑ0) − std_c(z0_data))²`,
   where `ẑ0` is the model's predicted clean latent and `z0_data` the batch's real latents. Targets the
   exact measured failure, is naturally per-channel/data-driven (tracks whichever channels drift), and
   touches the *loss*, not the weights — so it can't broadly shrink features. **t-gate: apply only at
   low noise (t<0.5)** where `ẑ0` is reliable.

## Arms — {limiter} × {output-reg} at wd=0.01, + references (8 GCDs, 1 arm/GCD)
| # | label | weight_decay | grad limiter | output-reg | purpose |
|---|-------|--------------|--------------|-----------|---------|
| 0 | `anchor`      | 0.01 | none        | off | positive control — reproduce the runaway on this stack |
| 1 | `reg_only`    | 0.01 | none        | on  | does the output penalty **alone** bound it? |
| 2 | `clip`        | 0.01 | hard 1.0    | off | plain global-norm clip |
| 3 | `clip_reg`    | 0.01 | hard 1.0    | on  | clip + penalty |
| 4 | `agc`         | 0.01 | AGC 0.01    | off | scale-relative clip alone |
| 5 | `agc_reg`     | 0.01 | AGC 0.01    | on  | the gentle targeted stack |
| 6 | `wd`          | 0.1  | none        | off | the plain-decay fix (first-A/B winner) — the **detail baseline to beat** |
| 7 | `adamw_fair`  | 0.1  | grad-clip   | off | **fairly-tuned AdamW** (lr `${ADAMW_LR:-2e-4}`, NOT fusion's 8e-5) — the Part-I control: does a well-tuned AdamW full-FT just train stably at ~1.1× the cost, making the Muon-repair machinery moot? (replaced the low-info `wd_agc_reg`) |

> **Part-I fair-baseline correction (2026-08-10, Kim direct + arXiv 2509.02046).** "Fantastic Pretraining
> Optimizers and Where to Find Them" shows prior Muon>AdamW speedups (~2×) came from an UNDER-tuned AdamW;
> the real gap at 1.4B is ~1.1×. AdamW's optimum LR is *higher* than Muon's, so the AdamW arm must use its
> own LR (`ADAMW_LR`, default 2e-4), never fusion's 8e-5. **One arm at one LR is a start, not a fair tune** —
> the rigorous version resubmits an `ADAMW_LR` bracket (1e-4 / 3e-4 / 6e-4). If a fairly-tuned AdamW full-FT
> is stable, the whole latent-runaway problem is Muon-specific and the Hyperball/CMuon/SFWN machinery is
> optional polish, not a necessity.

Reproduces the failing setup faithfully: **full-FT, big goa set (live-encode `--data_dir` + sidecar),
bf16-mixed, T512, bs4, 10 ep, FusionOpt(all-on)+EMA**, single-GPU per arm (ROCR-pinned,
LightningEnvironment — the `precision_ladder`/`fullft_wd_ab` pattern). bf16 per Kim (speed); note it's a
precision confound vs the fp32 #68, but the reg comparison is internal so it holds.

## Metrics & gates
- **Primary (bounded?):** the z0-std table — global std + `#chan>2.0` per arm × {ep2,4,6,8,10} × cfg{1,7,16}
  (reuse the `fullft_wd_ab` probe tail). Winner: std tracks the data latents' ~1.0, **0 non-finite**,
  cfg16 stable. `anchor` should climb (positive control); if it doesn't blow up by ep10 the stack is too
  short → extend or raise lr.
- **Detail (the real question):** render cfg7/w1 cells per arm → **Kim's ears** + DSP proxy
  (disintegration gate: whitening/hf/beat-loss drift vs base; + HF-energy retention vs the `wd` arm).
  A winner must bound the runaway **and** retain fine detail **≥ the `wd` baseline**, ideally better.
- **Objective sanity:** RF train-loss curve per arm — does the output penalty distort the main loss?

## What each comparison decides
- `reg_only` vs `anchor` → can the targeted penalty bound it with **zero** extra weight decay? (the
  cleanest "no collateral" outcome)
- `clip` vs `agc` → is scale-relative clipping better than global hard clip?
- `*_reg` vs `*` → does the output penalty add bounding/detail on top of a limiter?
- `agc_reg` vs `wd` → does the gentle targeted stack match/beat plain decay on **detail** at equal
  bounding? (the headline)
- `wd_agc_reg` → belt-and-suspenders; watch for over-regularization (duller than `wd`).

## Implementation (train_lora.py + SA3 training wrapper)
- **Flags:** `--grad-clip-mode {norm,agc}` (default norm; `--gradient_clip_val` already exists),
  `--agc-lambda 0.01`, `--output-std-penalty <λ_out, 0=off>`, `--output-std-t-gate 0.5`.
- **AGC:** override `configure_gradient_clipping` in `DiffusionCondTrainingWrapper` (FusionOpt is custom,
  so Lightning's built-in AGC path isn't wired) — per-param per-row clip as above; skip 1D/scalar params.
- **Output penalty:** in `training_step`, reconstruct `ẑ0` from the model's velocity prediction per the
  wrapper's **rectified-flow** parameterization — **VERIFY the exact form/sign** in
  `stable_audio_3/training/diffusion.py` (RF: `z_t=(1−t)z0+t·ε`, target `v=ε−z0` ⇒ `ẑ0 = z_t − t·v̂`);
  compute per-channel std of `ẑ0` and of the real `z0` over (batch,time), add `λ_out·MSE(std)` gated to
  `t<t_gate`. Log both stds to the CSV so the table can read them without a render.
- **Reuse:** clone `lumi/sbatch/fullft_wd_ab.sbatch` → `fullft_reg_ab.sbatch` (8 arms, the probe tail
  unchanged). Corpus knob defaults to the big goa live-encode set; a `--subset N` / `--steps` cap is
  available if 10 ep × 23k on one GCD is too slow (est. ~6–12 h/arm live-encode; pre-encoded `latents_sa3`
  is the faster equivalent if wall-time bites).

## Index
- Reuse index / Doc map: `ARCHITECTURE.md` (add under specs).
- On result: fold the winner + the detail-vs-bounding tradeoff into the lumi-ops SKILL bullet +
  `training-findings.md`; if a targeted lever wins, make it the full-FT default in `train_lora.py`.
