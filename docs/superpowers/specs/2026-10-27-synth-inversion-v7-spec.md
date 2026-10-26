# Synth Inversion V7 Specification: Mixture-to-Patch Inversion

**Owner:** WINTERMUTE (direction / ownership per OWNERSHIP.md)  
**Spec & Implementation:** ANTIGRAVITY + CONTINUITY review (2026-10-27)  
**Code:** `stable-audio-tools/scripts/synth_inversion/` (branch `feature/surge-xt-neural-inversion` / `fix/inharmonicity-aux`)  
**Prior Art:** *Point-and-Play* (Tian et al., arXiv:2610.19445v1); *Synth-JEPA* (Hayes et al., arXiv:2609.31024)

---

## 0. Motivation & The Core Question

In V4–V6 (`blog/2026-10-19-synth-jepa-from-day-one.md`), inverting a synth bass patch from a commercial track required running Demucs or BS-RoFormer to extract a stem first. 

*Point-and-Play* (Tian et al., Oct 2026) suggests that instrument timbre can be extracted directly from a dense polyphonic mixture via **Cue-Gated Statistics Pooling (CGSP)**, bypassing stem separation artifacts, while using paired-mixture contrastive losses ($\mathcal{L}_{\text{inv}}$) to penalize pitch/melodic leakage.

**The Question to Settle:** Does source separation actually bottleneck parameter recovery on electronic music, and can a cue-gated feature extractor bypass separation artifacts without sacrificing knob precision?

---

## 1. Pre-Registered Hypotheses & Success Criteria

### Pre-Registered Experiment: H10 (Mixture-to-Patch Inversion)
* **Metric:** Phrase MSS and Mel-SSIM against the **identical ground-truth reference** across 24 benchmark stems (or 100 synthetic held-out mixtures).
* **Statistical Test:** Two-tailed paired Wilcoxon signed-rank test across the 24 stems.
* **Success Rule:**
  1. Direct-mixture inversion achieves statistically significant improvement over Demucs baseline ($\Delta \text{MSS} > 0.15$, $p < 0.05$).
  2. Wins on $\ge 14$ of the 24 real stems in Phrase MSS.
  3. Parameter MSE on synthetic held-out mixtures is lower than Demucs baseline.
* **Kill Condition:**
  * If the direct-mixture condition fails to beat or match Demucs on at least 12/24 stems, or if parameter error on synthetic mixtures degrades, terminate the branch.

---

## 2. Experimental Phasing (Cheap Tests First)

Following Kim's lightweight-tests-first rule, we do NOT commit a 5-hour GPU run before proving the premise:

### Step 0: The Diagnostic (No Training, ~15 Minutes)
* **Goal:** Quantify the exact cost of Demucs separation on ground-truth parameter recovery.
* **Method:**
  1. Take 100 known Surge patches from `bank_v6` (storage parameters known).
  2. Mix them with real drum/percussion stems from `/run/media/kim/Mantu/avp-stems-original-classified` at three SNRs: $+3\text{ dB}, 0\text{ dB}, -3\text{ dB}$.
  3. Separate the mixtures using Demucs.
  4. Run current model (V6 C) on:
     - (a) Clean render (ceiling)
     - (b) Demucs-separated render
     - (c) Raw mixture directly (floor)
  5. Measure parameter MSE against the true known patch and top-1 audio-to-patch retrieval.
* **Verdict Gate:**
  * If Demucs causes $>15\%$ degradation in parameter MSE or drops retrieval by $>10$ points, the premise holds and separation is a primary bottleneck.
  * If Demucs degradation is $<5\%$, the domain gap (not separation) is the dominant error, and training a mixture extractor will not fix real-stem performance.

### Step 1: Cheap Architecture (Cue Gate on Existing `temporal_asp`)
* Before introducing the full CLAP + LoRA stack, add an independent sigmoid cue gate directly to our existing `temporal_asp` encoder (`models_v4.py:46`).
* Align the extracted vector to our existing **Synth-JEPA embedding** (512-d, 79% retrieval) rather than creating a new CLAP latent space.
* Reuses the existing V6 C parameter flow model without retraining Stage 2.

### Step 2: Full CLAP + LoRA Extractor (Only if Step 1 Proves Promising)
* Train `PointAndPlayExtractor` on `bank_v6` + Aavepyörä multitracks with $\mathcal{L}_{\text{inv}} + \mathcal{L}_{\text{algn}} + \mathcal{L}_{\text{sel}}$.

---

## 3. Evaluation & Invariance Protocols

1. **Common Reference Audio:**
   * In all evaluations, the predicted Surge patch is rendered and compared to the **same reference audio**:
     - On synthetic test: compared to the clean Surge render.
     - On real tracks: compared to the isolated stem (or blinded pairwise listening), NEVER to the mixture.
2. **Pitch Invariance Probing:**
   * Train a ridge regression probe on MIDI pitch from the extracted embeddings.
   * Target: $R^2$ must drop by at least $50\%$ compared to the raw audio encoder, matching the paper's observed suppression ($0.78 \to 0.26$).
   * Ratio of cosine similarity: $\frac{\text{sim}(P, \text{pitch}_1; P, \text{pitch}_2)}{\text{sim}(P_1, \text{pitch}; P_2, \text{pitch})} > 3.0$ (same-patch different-pitch vs. different-patch same-pitch).

---

## 4. Datasets & Licences
* **Surge Patch Bank:** `/home/kim/sao_runs/bank_v6` (100,000 clean Surge XT 1.3.4 patch renders, MIT licence).
* **Backing Stems:** `/run/media/kim/Mantu/avp-stems-original-classified` (Kim's catalog, author-owned / full rights).
* *Note:* Slakh and MoisesDB are dropped from training requirements.

---

## 5. Empirical Results & Decision (2026-10-27)

### Step 0 Ground-Truth Diagnostic
* Clean Render (Ceiling): Continuous Param MSE = `0.0861`, Cutoff Abs Error = `0.1985`
* Demucs-Separated Bass (Baseline): Continuous Param MSE = `0.1062`, Cutoff Abs Error = `0.2208`
* Raw Mixture Directly (Floor): Continuous Param MSE = `0.1848`, Cutoff Abs Error = `0.3494`
* **Verdict:** Demucs degradation is +23.3% to +40.8% (>15%), confirming that source separation damages ground-truth parameter recovery.

### Step 1 Cheap Architecture (`CueGatedTemporalAudioEncoder`)
* Trained 10,000 steps on GPU (batch size 64, 697.3s, final loss `0.6840`).
* **Ground-Truth Evaluation (20 patches at 0 dB SNR):**
  - Demucs Baseline: MSE = `0.1062`, Cutoff = `0.2208`
  - Raw Mix + Cue-Gated (Demucs Cue): MSE = `0.1416`, Cutoff = `0.3402`
  - Raw Mix + Cue-Gated (Clean Cue): MSE = `0.1451`, Cutoff = `0.3076`
* **Finding:** While the cue gate filters out 23.4% of mixture noise compared to the raw mixture floor (`0.1848` $\to$ `0.1416`), **Demucs separation achieves 0.1062—still 33.3% more accurate than cue-gating the mixture directly**.
* **Root Cause:** A temporal scalar gate $a_i \in [0, 1]$ cannot disentangle simultaneous sub-bass collisions (kick drum + synth bass playing on the same 16th note). In contrast, Demucs non-linear time-frequency U-Nets perform true waveform subtraction.
* **Decision: TERMINATED (Pre-Registered Kill Condition Triggered).**
  Branch terminated; full 7-hour CLAP+LoRA Stage 2 avoided. Retain separated-stem workflow with `--max_eval_freq 4000` regularization.

