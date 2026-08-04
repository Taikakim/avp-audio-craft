# SA3 Model Index

> [!WARNING]
> **Stale roster — doc-oversight 2026-08-05.** This hand-compiled index (2026-07-04, ~24 checkpoints)
> is far behind the live eval board, which now carries **227 model labels**, each with its real recipe
> pulled from the checkpoint. Until this page is regenerated from the manifest
> (`~/.cache/evals_aac/model_matrix/manifest_live.jsonl`), treat the **live board** as the source of
> truth for the current roster; the entries below are a July-4 snapshot kept for their by-ear verdicts.
> *(The real fix is a generator that emits this file from the manifest — flagged in the doc-oversight review.)*

> [!NOTE]
> Compiled 2026-07-04 from `/run/media/kim/Mantu/` (all models migrated here; Lehto is training-data-only).
> Cross-referenced against [WORKLOG.md](file:///home/kim/Projects/SAO/WORKLOG.md).
> **Scope caveat:** this index only covers trained artifacts under `Mantu/`. Adapters/heads that live
> in a repo are NOT captured by that scan — the **SA3 LatCH guidance heads** (§3b) are the known exception,
> added by hand. The **base models** themselves (`small-music-base`, `medium-base` — there is no `small-base`;
> §7 mutants derive from `medium-base`, and generative separation/editing needs a `-base` ckpt) are the
> upstream Stability weights, not indexed here.

---

## ⭐ Top-Tier Models (Ship / Use)

| Role | Model | Path | Why |
|------|-------|------|-----|
| **DoRA** | r128f exponential-ascending soup | `Mantu/sa3_lora_runs/soups_dora/r128f_expasc.ckpt` | Best DoRA soup; base run fréchet **0.0750** |
| **Onset** | FusionCC (CC-loss) | `Mantu/sa3_control_runs/onset_FusionCC_lr1e-4_randomcrop/riffer_final.pt` | Best onset steering: corr g2 **.880** (vs .584 baseline) |
| **Onset (ONNX)** | FUSION lr2e-5 40ep exppeak soup | `Mantu/sa3_control_runs/onset_FUSION_lr2e5_40epoch/soup_exppeak.pt` | Baked into ONNX DiT; monotonic 3→11 onsets/sec |
| **Style** | fpC AdamW | `Mantu/sa3_control_runs/style_fpC_adamw/riffer_final.pt` | Ship this — genre-CC variant **hurt** steering |
| **ES cond** | v3 field-best | `Mantu/sa3_control_runs/es_conditioner_v3/cond_fieldbest.npz` | Best grid point (a=1.17, b=−0.38) |

> [!WARNING]
> **Earlier in this session I recommended `style_fpC_genrecc`** — that was wrong! WORKLOG says genre-CC **HURT** steering (Goa 0.92→0.65, Psy 0.46→0.03). Use `style_fpC_adamw` instead.

---

## 1. DoRA Finetunes

All under `Mantu/sa3_lora_runs/`.

### sa3-goa-dora-47s-r128-adamw ⭐ Best clean run
- **Type:** DoRA rank-128, AdamW, 8 epochs, 47s crops
- **Checkpoints:** `epoch={0-7}-step={1350-10800}.ckpt` (2.0 GB each)
- **Quality:** Fréchet distance **0.0750** — the baseline winner in cautious A/B
- **Params:** Use as-is or via soups

### sa3-goa-dora-47s-r128-fusion
- **Type:** DoRA rank-128, FusionOpt (SF-NorMuon), 8 epochs
- **Checkpoints:** `epoch={0-7}-step={1350-10800}.ckpt` (4.0 GB each)
- **Quality:** Clean run, feeds into `r128f_*` soups

### sa3-goa-dora-47s-r128-fusion-caut ⚠️ DIVERGED
- **Type:** DoRA rank-128, FusionOpt + Cautious masking
- **Checkpoints:** 8 epochs (4.0 GB each) — **NaN after ep2**
- **Quality:** Healthy ep0–2 fréchet 0.0785 (competitive), then **full collapse**
- **Root cause:** Cautious rescale inflates effective LR by +37% (keep_frac ≈ 0.53)
- **Verdict:** ep0–2 usable as palette option; ep3+ garbage

### sa3-goa-dora-47s-r64
- **Type:** DoRA rank-64, 8 epochs
- **Checkpoints:** 8 × 1.0 GB

### sa3-goa-dora-47s-b4 / b4-cont
- **Type:** DoRA default rank, batch-4 variants
- **Checkpoints:** 3–5 epochs (260 MB each)

### dora128_300trk
- **Type:** DoRA rank-128, 300-track/607-crop subset, T=4096
- **Notes:** First full run. "Lightning tqdm SILENT in non-TTY"

### DoRA Soups (`soups_dora/`)

| Soup | File | Size | Notes |
|------|------|------|-------|
| **r128f expasc** ⭐ | `r128f_expasc.ckpt` | 667 MB | Exponential ascending blend of r128-fusion epochs |
| r128f expdesc | `r128f_expdesc.ckpt` | 667 MB | Exponential descending (more early-epoch weight) |
| r128f goodearly | `r128f_goodearly.ckpt` | 667 MB | Hand-picked early-epoch blend |
| r64 expasc/desc/goodearly | `r64_*.ckpt` | 335 MB | Rank-64 equivalents |
| r16 expasc/desc/goodearly | `r16_*.ckpt` | 87 MB | Rank-16 equivalents |
| cross 10A90F–30A70F | `cross_*A*F.ckpt` | 667 MB | AdamW × Fusion cross-optimizer blends |

### DoRA Cautious Soups (`soups_dora_caut/`)

| Soup | File | Notes |
|------|------|-------|
| r128caut expasc | `r128caut_expasc.ckpt` | Only ep0–2 are healthy |
| r128caut expdesc | `r128caut_expdesc.ckpt` | Use with caution |
| r128caut goodearly | `r128caut_goodearly.ckpt` | |

---

## 2. Onset FiLM Heads

All under `Mantu/sa3_control_runs/`.

### onset_FusionCC_lr1e-4_randomcrop ⭐ Best onset head
- **Type:** FusionOpt + Control-Consistency loss, lr1e-4, random crop
- **Checkpoints:** `riffer_final.pt` (1.9 GB) + 10 intermediates + ONNX exports
- **Quality:** **First significant win of the campaign.**
  - Corr/gain: g1 .558→**.752**, g2 .584→**.880** (P=.99 significant), g3 .702→**.889**
  - Tracks mid-range beautifully: req 5/6/7 → meas 6.0/6.8/7.6 (vs baseline's 8.5–8.7 overshoot)
- **Params:** onset_gain 1.0–3.0; density 3–12

### onset_FUSION_lr2e5_40epoch ⭐ ONNX reference
- **Type:** FusionOpt, lr2e-5, 40 epochs
- **Checkpoints:** `riffer_final.pt`, **`soup_exppeak.pt`** (239 MB), `soup_expasc.pt` + 40 intermediates
- **Quality:** Monotonic, calibrated steering: density 3→4.88, 11→11.15 onsets/sec
- **Notes:** `soup_exppeak.pt` is baked into the ONNX DiT control graph (Kevin Griffing VST handoff)
- **Params:** onset_gain 1.0–3.0; full density range

### onset_FusionCaut_lr1e-4_randomcrop — Palette option
- **Type:** FusionOpt + Cautious masking
- **Checkpoints:** `riffer_final.pt` (1.9 GB) + ONNX exports + `landscape/`
- **Quality:** "Quality TRADE not win — drier/cleaner separation, muted highs, smears when pushed. Over-trains: **ep5 sweet spot**, ep10 over-injects at low density."
- **Verdict:** Keep as palette option with early-stop; **not default**
- **Params:** onset_gain ≤ 2.0; ep5 checkpoint preferred

### onset_Fusion_lr1e-4_randomcrop — FusionCC baseline
- **Type:** FusionOpt, lr1e-4, random crop, 10 epochs
- **Checkpoints:** `riffer_final.pt` (239 MB) + `soup_exppeak.pt` + ONNX exports
- **Quality:** Corr/gain: g1 .582, g2 .657, g3 .793 — the "E_fusion" baseline

### onset_density_400trk_crop1024 — Original scalar head
- **Type:** Onset density scalar, 400 tracks, crop 1024
- **Checkpoints:** `riffer_final.pt` (232 MB) + 12 intermediates
- **Quality:** "Steers SA3 output onset density at corr **+0.90** (gain 1): sparse→dense = 4.3→8.3 onsets/sec"

### onset_FUSION_lr8e5_* (10ep, 1ep, 1.2ep)
- **Type:** Higher-LR FusionOpt variants (quick experiments)
- **Checkpoints:** `riffer_final.pt` + intermediates

### onset_FUSION_lr1e4_5000_* (FIXED, ckpt, crop1024, crop512)
- **Type:** lr1e-4 / 5000-step variants with different crop sizes
- **Checkpoints:** Various `riffer_step*.pt`

### onset_AdamW_lr7.5e-5_randomcrop_20ep
- **Type:** AdamW baseline, lr7.5e-5, 20 epochs, random crop
- **Checkpoints:** `riffer_final.pt` + 19 eval subdirs
- **Notes:** Part of optimizer bracket (AdamW vs FusionOpt)

### onset_Fusion_opb_* (10ep, 30ep, lr1.5e-4_30ep)
- **Type:** Onset-per-beat mode (onsets aligned to beat grid)
- **Notes:** `opb_30ep` aborted (only train.log). `opb_lr1.5e-4_30ep` has 29 steps + evals.

---

## 3. Style Fingerprint Heads

All under `Mantu/sa3_control_runs/`.

### style_fpC_adamw ⭐ Ship this
- **Type:** Fingerprint variant C (genre k+1 + year = 13 dims), AdamW
- **Checkpoints:** `riffer_final.pt` (957 MB) + 7 intermediates
- **Quality:** Best genre steering. Goa confidence **0.92**, Psy **0.46**
- **Params:** style_gain 0.25–1.0; `fp_in_dim=13`, `fp_variant="C"`

### style_fpC_genrecc ⚠️ Don't use
- **Type:** Fingerprint C + Genre-Consistency loss
- **Checkpoints:** `riffer_final.pt` (957 MB) + 7 intermediates
- **Quality:** Genre-CC **HURT** steering: Goa 0.92→**0.65**, Psy 0.46→**0.03**
- **Verdict:** "Meter-in-the-gradient does NOT transfer onset to genre — adds interference not signal"

### style_fpA_adamw
- **Type:** Fingerprint variant A (genre + year + bpm + sync = 15 dims), AdamW
- **Checkpoints:** `riffer_final.pt` (957 MB), `riffer_step5400.pt`

### style_fpB_adamw ❌ Empty
- **Type:** Never trained (0 files)

---

## 3b. SA3 LatCH Guidance Heads (gradient guidance — NOT a FiLM adapter)

> [!IMPORTANT]
> **This whole family is missing from the tables above because it does not live under `Mantu/` —**
> it lives in the SA3 repo: `stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt`.
> These are a **different control mechanism** from §2/§3. §2/§3 are **forward FiLM adapters** baked
> into the DiT (a pure forward mod; gains **1.0–3.0** / **0.25–1.0**). LatCH heads are a **gradient
> guidance** method — the DiT runs forward-only, autograd flows through the ~5–7 M-param head only
> (fp32 head, fp16 CK-FA DiT). **Do not cross the gains:** LatCH energy heads operate at **gain ≈512**,
> ~170× the adapter gains — feeding 3.0 to a LatCH head does nothing; feeding 512 to a FiLM adapter blows up.

**14 medium heads** (`adaln_zero`, `standardized`, **depth 4**): `beat_activation`, `downbeat_activation`,
`hpcp`, `onset_envelope`, `onset_envelope_drums`, `rms_drums`, `rms_energy_air`, `rms_energy_bass`,
`rms_energy_body`, `rms_energy_mid`, `spectral_flatness`, `spectral_flux`, `spectral_kurtosis`,
`spectral_skewness`.

- **Load via the canonical loader, never hardcode arch:** `stable_audio_3.models.latch.load_latch_from_checkpoint(path, device)`
  auto-detects in/out ch, dim, depth, num_heads, t_injection and attaches `std_mean`/`std_std` as `head.metadata`.
  Constructing `LatCH(dim=256, depth=6, …)` **silently fails** to load these (state-dict mismatch).
- **Sibling `latch_weights_sa3/` (no `_medium`) = epoch-numbered snapshots** (`_ep<N>.pt`, simpler `concat`
  keys, **no `_best.pt`**). Not the production heads — don't load them as medium heads.
- **Operating gain ≈ 512 for energy heads** (NOT 48–96, NOT 128 — **gain 128 is a dead zone**). Ladder
  128→1024 monotonic (~40–47× MERT-Δ growth). At gain 8, `corr=1.0` is a **mirage** (rank-corr ≠ magnitude) — judge by spread.
- **Steering verdict (14-head sweep, 2026-06-28):**
  - **Strong:** `rms_energy_bass` (+5.1 dB @512), `rms_energy_mid` (+6.0 dB @512)
  - **Moderate:** `rms_energy_body`, `spectral_skewness`, `rms_energy_air`
  - **Dead at any weight:** `beat/downbeat/onset` activation heads, `hpcp`, `spectral_kurtosis` (perturb CE without steering)
- **`spectral_skewness` was re-trained with EMA (2026-06-29) and reversed its "architecture-limited" verdict** —
  the ceiling was **damping-limited**, fixed by EMA 0.999 + grad-accum + early-stop, not a lower LR.
- **Eval energy/timbre heads with the MERT _mid_ layer** — the upper layer is melody/harmony and blind to a
  bass-RMS change (it mislabeled the two best heads "dead" on the first pass).
- **CPU eval path exists:** `onnx/latch_eval_server.py` + `submit_latch_job.py` (plain DiT on ORT CPU, torch
  autograd through the head only). Provenance/results: riffer-evals `latch_sweep.html`, mir memory `sa3-latch-head-sweep`.

---

## 4. ES Conditioners

All under `Mantu/sa3_control_runs/`.

### es_conditioner_v3 ⭐ Best ES
- **Files:** `cond_es_best.npz`, **`cond_fieldbest.npz`**, `cond_final.npz`, `es_state.npz`, `es_history.json`
- **Quality:** "Real but modest transfer. Paired improvement +0.28 onsets/s mean error."
  - Field-guided jump found best grid point OFF the walk line (a=1.17, b=−0.38)
  - Terrain is SMOOTH and walkable; descent continues past gen-20 endpoint
- **Notes:** These are raw FiLM layer weights (`.npz`), not standard adapter `.pt` files

### es_conditioner_v2 ⚠️ Failed
- **Quality:** Per-coordinate norm issue — no real learning

### es_conditioner_pilot ⚠️ Failed
- **Quality:** No real learning — seed-window luck only

---

## 5. Riffer / Audio-Reference Adapters

All under `Mantu/sa3_control_runs/`.

### riffer_400trk_lr1e-4_crop1024
- **Checkpoints:** `riffer_final.pt` (239 MB) + 10 intermediates
- **Quality:** "Retrained full-effect at 400trk/lr1e-4 to test if more-data/lower-LR smooths"

### riffer_200trk_* (6 optimizer variants)
- **Type:** 200-track riff adapter optimizer bracket (AdamW/Fusion/SF-AdamW, various LRs)
- **Quality:** "Riffer works, but only reference-specific at lr1e-4 (peaks step ~6000, then elbow-declines); heavier LR mode-collapses"

---

## 6. Onset Adapter Soups

Under `Mantu/sa3_control_runs/soups/` (12 profiles for onset_FUSION_lr2e5_40epoch):

| Soup | Profile | Size |
|------|---------|------|
| soup_expasc_ep10-40 | Exponential ascending | 239 MB |
| soup_exppeak20_ep10-40 | Exponential peak at ep20 | 239 MB |
| soup_exppeak25_ep10-40 | Exponential peak at ep25 | 239 MB |
| soup_asc_ep10-40 | Linear ascending | 239 MB |
| soup_desc_ep10-40 | Linear descending | 239 MB |
| soup_cosasc_ep10-40 | Cosine ascending | 239 MB |
| soup_cosdesc_ep10-40 | Cosine descending | 239 MB |
| soup_sine_ep10-40 | Sine | 239 MB |
| soup_tri_ep10-40 | Triangle | 239 MB |
| soup_valley_ep10-40 | Valley | 239 MB |
| soup_A_ep10_ep40 | Simple average ep10+ep40 | 239 MB |
| soup_ep20_ep40 | Simple average ep20+ep40 | 239 MB |

Under `Mantu/sa3_control_runs/soups_vibe/` (cross-optimizer soups):

| Soup | Notes |
|------|-------|
| `cross_25A75F.pt` | 25% AdamW + 75% Fusion |
| `cross_25A75F_caut.pt` | + Cautious variant |
| `cross_25A75F_caut_ep2.pt` / `_ep5.pt` | Cautious early-stop variants |
| `best_of_runs.pt` | Cherry-picked best |
| `AdamW_peak_mix.pt` / `Fusion_peak_mix.pt` | Per-optimizer peak blends |
| + 4 ONNX export subdirs | |

---

## 7. Mutated Base Models

Under `Mantu/sa3_mutated_checkpoints/` (each ~4.6 GB + .wav preview).
Created by [mutate_weights.py](file:///home/kim/Projects/SAO/stable-audio-3/scripts/mutate_weights.py).

| Variant | Drift | Shuffle | Blur | Contraction |
|---------|-------|---------|------|-------------|
| Pure drift (gentle) | **0.01** | 0 | 0 | 0 |
| Pure drift (moderate) | **0.05** | 0 | 0 | 0 |
| Pure shuffle (gentle) | 0 | **0.01** | 0 | 0 |
| Pure shuffle (moderate) | 0 | **0.05** | 0 | 0 |
| Pure blur | 0 | 0 | **0.1** | 0 |
| Pure contraction | 0 | 0 | 0 | **0.1** |
| Drift + shuffle + blur | **0.02** | **0.01** | **0.05** | 0 |
| Drift + blur + contraction | **0.02** | 0 | **0.05** | **0.1** |

---

## 8. Composition Evaluations

### composed_sweep
- **Location:** `Mantu/sa3_control_runs/composed_sweep/`
- **Contents:** `E_fusion/` (162 cells), `A_cc/` (162 cells), `E_fusion_v2/`
- **Verdict:** Stage1 complete (324 cells, 2 seeds). FusionCC advantage **replicates**.

### sa3_multihead_bracket ⭐ 4-knob validated
- **Location:** `Mantu/sa3_lora_runs/sa3_multihead_bracket/`
- **Contents:** 12 WAV renders + `manifest.json` + `run_meta.json`
- **Verdict:** "4-knob composition VERIFIED: energy guidance steers hard ON TOP of the full stack — hi-lo spread +15.2 dB @512, +23.4 dB @1024, monotone, direction correct"

> [!CAUTION]
> All server-rendered evals since 2026-06-27 had a clipping bug. Re-render before final ear verdicts.

---

## Quick Reference: Recommended Run Command

```bash
python control/sa3_control/multi_adapter_onset_eval.py \
    --dora-ckpt  /run/media/kim/Mantu/sa3_lora_runs/soups_dora/r128f_expasc.ckpt \
    --onset-ckpt /run/media/kim/Mantu/sa3_control_runs/onset_FusionCC_lr1e-4_randomcrop/riffer_final.pt \
    --style-ckpt /run/media/kim/Mantu/sa3_control_runs/style_fpC_adamw/riffer_final.pt \
    --reference-latent /home/kim/Projects/latents_sa3/003231.npy \
    --densities "5,6,7,8,9,10" \
    --onset-gains "1.0,2.0,3.0" \
    --style-gains "0.25,0.5,1.0" \
    --out-dir /run/media/kim/Mantu/sa3_lora_runs/sa3_multihead_bracket
```
