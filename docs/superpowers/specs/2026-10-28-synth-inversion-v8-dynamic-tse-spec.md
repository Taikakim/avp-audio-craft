# Synth Inversion V8 Specification: Asymmetric Target Sound Extraction & Dynamic Parameter Inversion

**Author / Proposer:** ANTIGRAVITY <antigravity@aavepyora.online> & Kim  
**Supervision & Ownership:** WINTERMUTE (per `OWNERSHIP.md`)  
**Reviewers:** KUANG, Claude Opus 5.5, CONTINUITY, WINTERMUTE  
**Date:** 2026-10-28  
**Status:** REVISED SPECIFICATION (Post-Review Consensus)  
**Target Repos:** `stable-audio-tools` (`scripts/synth_inversion/`), `stable-audio-3`  

---

## 0. Executive Summary & Review Consensus

In V7, we explored direct **Mixture-to-Patch** synth inversion using the *Point-and-Play* (Tian et al., arXiv:2610.19445) paradigm—extracting synthesizer timbre directly from a dense polyphonic mix without prior stem separation. 

The initial V7 audition board reported 0.0% patch retrieval against a 58.3% raw mixture baseline. As clarified during code review:
1. **The 0.0% vs. 58.3% metric was a broken-instrument artifact:** `laion_clap.CLAP_Module()` was instantiated without loading its pretrained weights (`630k-audioset-best.pt`), collapsing the HTSAT backbone to random projections (cosine similarity ~0.023 for all inputs and cues). The 58.3% baseline reflects the raw mixture through an unconditioned CLAP encoder.
2. **Prior Demucs benchmarks:** The "+23% Demucs damage" diagnostic was evaluated on a single 0.8s slice of a snare stem mixed with isolated Surge notes; it did not evaluate kick-and-bass sixteenth-note collisions.
3. **The True Separation Bottleneck:** In modern psytrance, the bass is ducked/sidechained under the kick; in classic Goa trance, the bass sub carries minimal patch identity beyond pitch and level. **The timbre identity lives primarily in the 120–2500 Hz body band**, where interference arises from leads, acid lines, and pads rather than kick sub-bass.

### The Core Thesis of V8:
1. **Asymmetric Extraction:** We are not building a stem remixer constrained to conserve total mix energy across all stems. We train a single-sound extractor optimized exclusively on the target synth stem ($\min \|\hat{S}_{\text{synth}} - S_{\text{synth}}\|$). Backing drums and accompaniment are discarded.
2. **Reliability Masking over Greedy Inpainting:** Rather than arbitrarily assigning 100% of contested sub energy to the synth or hallucinating inpainting through transients, the extractor outputs an estimated stem alongside a **per-bin target-to-interference reliability mask** $W(t, f)$. Downstream inversion weights its parameter evidence by $W(t, f)$.
3. **Dual-Representation Parameter Space:** We decouple the **59-parameter static patch core** (`surge_spec_v6.py`: oscillators, ladder/warp filters, categoricals, envelopes, keytracking) from **3–4 dynamic 10 Hz automation lanes** (Filter Cutoff, Resonance, Waveshaping Drive, FM depth) with smoothness constraints.
4. **Phrase-Level Multi-Note Training:** We move beyond isolated 0.8s single notes to multi-note phrases on the 10 Hz grid (aligned with Stable Audio 3's 92.9 ms latent rate), natively modeling legato, overlapping envelopes, release accumulation, and sixteenth-note Goa basslines.

---

## 1. System Architecture

```
+----------------------------------------------------------------------------------------------------+
| 1. MUSICAL DATA AUGMENTATION ENGINE                                                                |
|                                                                                                    |
|  [Real Multitrack Archive] ---> [Isolated Kicks + Drum Loops] ---> [Self-Similar Kick Swap]        |
|  [Surge Patch Bank / Transcribed Stems] -------------------------> [Random Pedalboard FX Rack]     |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
                                      [Dynamic Training Mixture]
                                                  |
+-------------------------------------------------v--------------------------------------------------+
| 2. ASYMMETRIC TARGET SOUND EXTRACTOR (TSE)                                                         |
|                                                                                                    |
|  Audio Prompt / Cue --------------------------> [FiLM / Cross-Attention Conditioner]               |
|  Mixture Spectrogram X(t, f) -----------------> [2D Complex U-Net / ConvNeXt Backbone]            |
|                                                  - Single-Target Loss: min ||S_hat - S_target||    |
|                                                  - Outputs Target Audio S_hat(t)                   |
|                                                  - Outputs Reliability Mask W(t, f)                |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
                               [Estimated Target + Reliability Mask W(t, f)]
                                                  |
+-------------------------------------------------v--------------------------------------------------+
| 3. DYNAMIC PARAMETER INVERTER (Static Core + 10 Hz Automation Lanes)                               |
|                                                                                                    |
|  High-rate Mel Spectrogram (~100 fps) --------> [Sequence Encoder + OT-CFM Flow Head]              |
|  Transcribed Note Roll (Pitch / Onsets) ------>  - Static Patch: 59 params (categoricals, EGs)     |
|  Reliability Mask W(t, f) -------------------->  - Dynamic Lanes: Cutoff, Res, Drive (10 Hz)       |
|                                                  - Occam Flatness / Smoothness Penalty             |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
                       Native Surge Patch (.fxp) + MIDI CC Automation (.mid)
```

---

## 2. Pillar 1: Musically-Grounded Augmentation Engine

Generic synthetic datasets (`bank_v6` arpeggios, Slakh) fail to reflect the phrasing, microtiming, and acoustic density of real electronic productions. V8 builds an automated, dynamic remixing pipeline from genuine multitrack projects:

### 2.1. Corpus Inventory
The training archive contains **40 full multitrack projects** comprising **1,326 authentic studio stems**:
* **Drums & Percussion:** 200 drum stems, 113 isolated kick stems.
* **Bass & Low End:** 120 rolling/sub basslines.
* **Melodic Synths:** 145 leads, 148 arp & key lines, 73 acid 303 riffs, 111 pads.
* **SFX & Chops:** 119 psytrance sound effects, 64 vocal chops.

### 2.2. Real Stems as Extraction Targets (Mitigating the Synthetic Gap)
If the extractor's targets are exclusively Surge XT re-renders, the model overfits to "finding the sound that looks like Surge". Real productions feature analog hardware, Access Virus, and Roland TB-303 units.
* **Dual Target Distribution:** Training targets are sampled from both clean Surge renders (with known ground-truth parameters for downstream inversion) and real multitrack synth stems (unlabeled for parameters, but authentic in acoustic timbre).
* **Target Definition:**
  - **Clean Target ($S_{\text{target}}$):** Dry synth render (effects bypassed) or clean studio synth stem.
  - **Mixture ($X_{\text{mix}}$):** Clean target passed through a randomized live `pedalboard` chain (delay, chorus, flanger, saturation), summed with drum stems and accompaniment.
  - Surge's internal chorus/delay parameters are held bypassed during target extraction training.

### 2.3. Drum Augmentation & Hit Replacement
* **Kick-Only Hit Substitution:** In full drum stems, transient tails overlap heavily (reverb claps and hi-hats bleed across kick decays). We perform hit replacement **only on isolated kick stems**, substituting hits with self-similar kicks sampled from the 113 AVP kick library based on audio feature embeddings.
* **Loop-Level Stem Swapping:** Full percussion loops are swapped as entire coherent phrases to avoid transient slicing artifacts.
* **Ducking Consistency:** Archive bass stems frequently carry production sidechain ducking. When pairing Surge re-renders with substituted kicks, we re-key the volume ducking envelope from the new kick transient.

---

## 3. Pillar 2: Asymmetric Target Sound Extractor (TSE)

### 3.1. Elimination of the "Greedy" Sub-Bass Rule
The draft spec proposed assigning 100% of contested low-frequency energy to the synth. Code review and acoustic analysis showed this is counterproductive:
* In modern rolling psytrance, bass notes duck on the kick's downbeat. Forcing 100% energy into the bass stem invents non-existent bass notes on every kick downbeat, tricking the downstream inverter into predicting artificial transient thumps and oversized filter envelopes.
* In classic Goa trance, the bass is present under the kick, but the sub-bass (<120 Hz) carries minimal timbre information beyond fundamental pitch and level. The sonic identity lives in the 120–2500 Hz body band against other melodic synths.

**Rule:** We train with the unconstrained single-target loss:
$$\mathcal{L}_{\text{TSE}} = \|\hat{S}_{\text{synth}} - S_{\text{synth}}\|_1 + \mathcal{L}_{\text{multi-STFT}}(\hat{S}_{\text{synth}}, S_{\text{synth}})$$
The network learns the true physical arrangement distribution from multitrack data rather than relying on a handcrafted allocation heuristic.

### 3.2. Per-Bin Reliability Masking $W(t, f)$
Instead of hallucinating inpainting through kick transients, the extractor outputs:
1. The estimated target audio $\hat{S}(t)$.
2. A per-bin confidence / reliability map:
   $$W(t, f) = \sigma\left(\text{Conv}(\text{Features})\right) \in [0, 1]$$
   $W(t, f)$ reflects the estimated Target-to-Interference Ratio (TIR). Where a loud kick drum or crashing snare obliterates the synth signal, $W(t, f) \to 0$. The downstream inverter and loss functions weight parameter evidence proportionally to $W(t, f)$, avoiding parameter overfitting in masked regions.

### 3.3. Architecture & ModularOptimizer Integration
* **Backbone:** 2D Complex U-Net / ConvNeXt operating on multi-resolution STFT spectrograms.
* **Conditioning:** Clean audio cue (1.0s clean target slice) encoded via a LoRA-adapted pretrained HTSAT backbone, integrated via FiLM / cross-attention layers.
* **ModularOptimizer (Fusion v2) Routing:**
  - Conv2d 4D kernels (`out, in, kh, kw`) are flattened to 2D matrices `(out, in * kh * kw)` before assignment to the spectral / NorMuon optimizer group.
  - Depthwise separable convolutions remain in the sign group.
  - Per-group learning rates are explicitly defined, satisfying `strict_group_lrs`.

---

## 4. Pillar 3: Dynamic Parameter Inverter (Static Patch + Automation Lanes)

### 4.1. The 59-Parameter Layout (`surge_spec_v6.py`)
Following V6 standardization, the core synthesizer state consists of **59 parameters** (114 dimensions one-hot encoded):
* 3 Oscillators (Classic / Modern, relative octaves $-2 \dots +2$, fine detune $\pm 0.2$ st, shapes, sub mix).
* Dual Filters (10 lowpass models, resonance, ladder drive, feedback, routing).
* Waveshaper (8 analog curves, drive).
* Envelopes (FEG attack/decay/sustain/release, AEG attack/decay/sustain/release).
* Modifiers (noise color, analog drift).
* *Conditioning:* `midi_note` is supplied as an external conditioning input, not a predicted knob.

### 4.2. Decoupling Static Patch Core from Dynamic Automation
Predicting a free 59-parameter trajectory per 100ms creates severe unidentifiability: the model can explain a physical filter envelope as knob automation, or explain knob automation as an envelope.

We enforce an explicit architectural separation:
1. **Static Patch Prediction (Once per clip):**
   - All categorical parameters (oscillator types, filter types, waveshaper modes).
   - Envelope parameters (FEG amount, decay, sustain, release; AEG decay, sustain, release).
   - Relative oscillator octaves and tuning.
2. **Dynamic Automation Lanes (10 Hz rate):**
   - **Filter 1 Cutoff**
   - **Filter 1 Resonance**
   - **Waveshaper Drive**
   - **FM Depth / Mix**
3. **Temporal Regularization (Occam Flatness Penalty):**
   Automation lanes are regularized with a curvature penalty:
   $$\mathcal{L}_{\text{smooth}} = \lambda_{\text{smooth}} \sum_{t=1}^{T-1} \|\theta_{\text{auto}}(t+1) - 2\theta_{\text{auto}}(t) + \theta_{\text{auto}}(t-1)\|^2$$
   Automation features faster than 250 ms are heavily penalized, ensuring that fast per-note dynamics are absorbed by physical envelope parameters rather than high-frequency lane wiggle.

### 4.3. Phrase-Level Modeling & Sequence Alignment
* **Input Resolution:** Encoders receive high-rate mel frames (~100 fps, 128 mel bands) to preserve crisp attack transients and percussive plucks.
* **Output Grid:** Sequence heads output automation at **10.76 Hz (92.9 ms per frame)**, matching Stable Audio 3 latent frames and LatCH conditioning grids.
* **Phrase Context:** Training clips are 4.0 seconds (43 latent frames). The non-causal sequence model accumulates evidence across the entire phrase, resolving retrigger state, overlapping legato notes, and envelope release accumulation.
* **DAW Packaging:** 
  - Static parameters export to native Surge `.fxp` presets (`audio_utils.save_patch`).
  - Dynamic automation lanes export as standard MIDI Continuous Controller (CC) tracks mapped to Surge Macro knobs in a accompanying `.mid` file, ensuring universal compatibility across Bitwig, Ableton, and Reaper.

---

## 5. Pre-Flight Diagnostics (Cheap Tests Before GPU Phase 1)

To protect compute resources and validate acoustic assumptions before scheduling large-scale training, the following three CPU-only checks are pre-registered:

### R1. Archive Contested-Bin Census
* **Objective:** Determine empirically whether the primary extraction challenge is under the kick drum or in the midrange synth body band.
* **Method:** Across the 40 multitracks in `$ARCHIVE_ROOT`:
  1. Extract kick transient onsets from clean kick stems.
  2. Measure energy in bass, acid, and lead stems within $\pm 30$ ms of kick onsets in:
     - Sub-bass band ($< 120$ Hz)
     - Body band ($120 - 2500$ Hz)
  3. Measure the percentage of bass energy masked by other synths (cells where lead/acid/pad energy is within 6 dB of bass).
  4. Aggregate and report by subgenre (Old-School Goa, Modern Psytrance, Acid Trance).

### R2. Oracle Repair Benchmark
* **Objective:** Verify whether contested sub-bass time-frequency cells are the true bottleneck for Demucs/BS-RoFormer degradation.
* **Method:**
  1. Create mixtures: authentic kick stems + Surge renders of known patches following real bass grooves.
  2. Separate using Demucs and BS-RoFormer.
  3. Form an **Oracle Repaired** stem by splicing ground-truth audio into the separated output *only* in contested cells (kick-on frames, 40–150 Hz).
  4. Evaluate parameter inversion error using the V6 inverter across:
     - Clean Ground Truth
     - Raw Separated Stem
     - Oracle-Repaired Stem
  5. *Kill Condition:* If Oracle Repair does not recover at least 50% of the degradation between raw separation and clean ground truth, sub-bass masking is not the bottleneck (damage is driven by wideband bleed or phase distortion), and sub-bass inpainting is invalid.

### R3. V7 Registered Benchmark Baseline
* Re-run V7 Step 0 with the bug-fixed, pretrained CLAP backbone on 100 candidate patches across +6 dB, 0 dB, and -6 dB SNR regimes with confidence intervals.

---

## 6. Phased Implementation Roadmap & Gates

```
+------------------------------------------------------------------------------------+
| CHEAP PRE-FLIGHT (CPU)                                                             |
|  [R1: Archive Census] -----> [R2: Oracle Repair Test] -----> [R3: V7 Bugfix Check]  |
+-----------------------------------------+------------------------------------------+
                                          | All Gates Pass
                                          v
+------------------------------------------------------------------------------------+
| PHASE 0: Musical Dataloader Harness (~1 GPU Hour)                                  |
|  - 40 multitracks loaded (6 held-out songs reserved)                               |
|  - Self-similar kick swap & Pedalboard FX chain implemented                        |
|  - 200-step dataloader benchmark (verifying >= 50 samples/s throughput on 12 CPUs) |
+-----------------------------------------+------------------------------------------+
                                          | Throughput Verified
                                          v
+------------------------------------------------------------------------------------+
| PHASE 1: Asymmetric Target Sound Extractor (~3 GPU Hours)                          |
|  - 2D Complex U-Net with ModularOptimizer 4D kernel reshape                        |
|  - Evaluated on held-out songs vs matched two-stem baseline and BS-RoFormer         |
|  - Gate: Separation Tax on V6 Inversion (Mel-SSIM error <= 1.25x of clean stem)    |
+-----------------------------------------+------------------------------------------+
                                          | Separation Gate Pass
                                          v
+------------------------------------------------------------------------------------+
| PHASE 2: Dynamic 10 Hz Parameter Inverter (~4 GPU Hours)                           |
|  - Decoupled Static Patch (59 params) + 3-4 Dynamic Automation Lanes (10 Hz)       |
|  - Evaluated on dynamic filter sweep benchmarks                                    |
|  - Gate: Centroid Trajectory Correlation (Spearman rho >= 0.80 on sweep lanes)     |
+-----------------------------------------+------------------------------------------+
                                          | Inversion Gate Pass
                                          v
+------------------------------------------------------------------------------------+
| PHASE 3: Prompt Conditioning & DAW Packaging                                       |
|  - Pretrained CLAP text encoder + 1.0s audio cue conditioning                      |
|  - Full export: .fxp Surge patch + .mid MIDI CC automation bundle                  |
+------------------------------------------------------------------------------------+
```

---

## 7. Ownership & Routing

* **Line Ownership:** WINTERMUTE (`OWNERSHIP.md`)
* **Optimization & Architectures:** WINTERMUTE
* **Evaluation, Benchmarks & Metrics:** CONTINUITY
* **Author / Spec Revision:** ANTIGRAVITY <antigravity@aavepyora.online>
