# Synth Inversion V8 Specification: Asymmetric Target Sound Extraction & Dynamic 10 Hz Parameter Inversion

**Author / Proposer:** ANTIGRAVITY <antigravity@aavepyora.online> & Kim  
**Supervision & Ownership:** WINTERMUTE (per `OWNERSHIP.md`)  
**Target Reviewers:** CONTINUITY, WINTERMUTE, THE-FINN, GHOST-NOTE  
**Date:** 2026-10-28  
**Status:** DRAFT — FOR TEAM REVIEW & FEEDBACK  
**Target Repos:** `stable-audio-tools` (`scripts/synth_inversion/`), `stable-audio-3`  

---

## 0. Executive Summary & Why V8 Exists

In V7, we attempted direct **Mixture-to-Patch** synth inversion using the *Point-and-Play* (Tian et al., arXiv:2610.19445) paradigm—extracting synthesizer timbre directly from a dense polyphonic mix without stem separation. 

The empirical evaluation produced a decisive negative result (0.0% patch retrieval vs. 58.3% for raw mixture baseline). Two root causes were identified:
1. **Implementation Defect:** `laion_clap.CLAP_Module()` was initialized without `load_ckpt()`, rendering the HTSAT backbone an unaligned random projection.
2. **Fundamental Acoustic Obstacle:** Point-and-Play relies on a **1D temporal scalar gate** ($a_i \in [0, 1]$ across all frequencies for a 20ms frame). In electronic music (Goa, Acid, Techno), the kick drum and synth bass strike on the identical 16th-note grid and share the identical sub-bass band ($40 - 150\text{ Hz}$). A 1D time gate cannot untangle overlapping frequencies; it either passes both or silences both.

Standard 4-stem Demucs works better (+23% error vs clean, 58.3% retrieval), but it suffers from the **"Sum-to-Mix" compromise**: because it is constrained to conserve total energy across all stems ($\sum \hat{S}_k = X_{\text{mix}}$), it must compromise in contested sub-bass bins so the kick drum doesn't sound hollow.

**The Core Thesis of V8:**
We are **not** building a DJ stem remixer where all stems must sum back up to the master. **We only care about recovering the true synthesizer sound; the backing drums are discarded.** 
V8 replaces the flawed 1D scalar gate with an **Asymmetric Target Sound Extractor (TSE)** that claims 100% preference over contested frequencies, trained on an authentic **musically-grounded augmentation engine** (Kim's 1,326 multitrack stems, self-similar drum hit replacement, live Pedalboard FX), feeding a **dynamic 10 Hz block-based Surge XT parameter predictor** with continuous spline automation.

---

## 1. Architectural Architecture: The Three Pillars

```
+----------------------------------------------------------------------------------------------------+
| 1. MUSICAL DATA AUGMENTATION ENGINE                                                                |
|                                                                                                    |
|  [Real AVP Stems] -------> [Note Onsets & Grooves] -------> [Surge XT Bank / Patch Randomization]   |
|  [AVP Drum Library] -----> [Self-Similar Hit Swap] -------> [Pedalboard Live FX (Reverb/Delay/Sat)]|
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
                                      [Dynamic Training Mixture]
                                                  |
+-------------------------------------------------v--------------------------------------------------+
| 2. ASYMMETRIC TARGET SOUND EXTRACTOR (TSE)                                                         |
|                                                                                                    |
|  Prompt / Cue (Text or 1s Audio) ---> [Cross-Attention Conditioner]                                |
|  Mixture Spectrogram X(t, f) ------> [2D Time-Frequency Complex U-Net]                            |
|                                       - Greedy Contested Frequency Preference (50-150 Hz)          |
|                                       - Harmonic Continuity Inpainting Through Transients          |
|                                       - Zero Drum Reconstruction Loss                              |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
                                      [Clean Isolated Synth Mel]
                                                  |
+-------------------------------------------------v--------------------------------------------------+
| 3. DYNAMIC 10 Hz (100ms) BLOCK-BASED PARAMETER INVERTER                                            |
|                                                                                                    |
|  Clean Mel Frames (10.76 Hz) -------> [Flow-Matching Trajectory Inverter (25 Euler Steps)]         |
|                                       - Outputs 40 x 53 parameter blocks per 4-second clip         |
|                                       - Cubic Spline Parameter Interpolator                        |
|                                       - Audio-Rate Surge XT Automation Engine                      |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
                            Surge XT Patch (.vstpreset) + DAW Automation Curves
```

---

## 2. Pillar 1: The Musically-Grounded Augmentation Engine

Generic synthetic datasets (`bank_v6` arpeggios, Slakh) fail to reflect the phrasing, microtiming, and acoustic density of real electronic productions. V8 builds an automated, dynamic remixing pipeline from Kim's own multitrack archive:

### 2.1. Corpus Inventory
In `/run/media/kim/Mantu/avp-stems-original-classified`, we have **40 full multitrack song folders** holding **1,326 authentic studio stems**:
* **Drums & Percussion:** 200 drum stems, 113 isolated kicks.
* **Bass & Low End:** 120 rolling/sub basslines.
* **Melodic Synths:** 145 leads, 148 arp & key lines, 73 acid 303 riffs, 111 pads.
* **SFX & Chops:** 119 psytrance sound effects, 64 vocal chops.

### 2.2. Groove-Preserved Synth Augmentation
* We take the rhythmic structure, swing, onsets, and velocity envelopes from genuine AVP bass and acid stems.
* Instead of audio time-stretching, we parse the note events and re-render them through Surge XT across diverse preset topologies.
* **Benefit:** The training signals exhibit authentic human groove and syncopation, not toy scalar exercises.

### 2.3. Self-Similar Drum Hit Replacement
* Real drum loops in Goa/Psytrance/Techno possess complex microtiming. 
* We preserve the exact track grid, but at each detected transient peak (kick, snare, hat), we dynamically substitute the hit with a self-similar hit randomly sampled from the 113 AVP kicks and 200 drum stems.
* **Benefit:** The mixture collision changes completely on every batch step while preserving genuine musical swing and rhythmic context.

### 2.4. Live Pedalboard FX Rack
In real productions, synths are rarely dry. We pass rendered stems through Spotify's `pedalboard` library on the fly:
* **Time-domain:** Tape delay, ping-pong delay, spring/room reverb.
* **Modulation:** Analog phaser (slow sweep), multi-voice chorus, negative-feedback flanger.
* **Coloration:** Tube drive, soft saturation, bitcrushing, resonant peaking filters.
* **Benefit:** The extractor learns to ignore wet reverb washes and delay repeats, focusing on the core periodic oscillator dynamics.

---

## 3. Pillar 2: Asymmetric Target Sound Extractor (TSE)

### 3.1. The Contested Frequency Problem
In electronic music, the kick drum fundamental ($40 - 80\text{ Hz}$) and the synth bass fundamental land in the identical frequency bins at the identical downbeats.

| System | Optimization Objective | Behavior in Contested 50–100 Hz Bins | Result on Synth Recovery |
| :--- | :--- | :--- | :--- |
| **Demucs v4** | $\min \sum_{k} \|\hat{S}_k - S_k\|$ with $\sum \hat{S}_k \approx X$ | Splits the energy so kick doesn't sound hollow | Lossy (+23% parameter error, softened body) |
| **Point-and-Play (V7)** | 1D temporal scalar gating $a_i \in [0, 1]$ | Mutes or passes the entire 20ms frame | Catastrophic failure (0% retrieval) |
| **V8 Asymmetric TSE** | $\min \|\hat{S}_{\text{synth}} - S_{\text{synth}}\|$ (Drums ignored) | **Greedy claim:** Gives 100% of contested energy to synth | **Exact harmonic preservation** |

### 3.2. Harmonic Inpainting
Synthesizers consist of continuous, periodic oscillator waveforms governed by differential equations. A kick drum is a localized transient burst (decaying in 30–50 ms).
* The 2D U-Net is trained with a multi-resolution STFT loss + spectral continuity penalty.
* When a kick transient obscures the synth fundamental, the network uses the unmasked upper harmonics ($2f_0, 3f_0, \dots$) and the preceding/following cycles to **inpaint the continuous synthesizer waveform** right through the transient.

---

## 4. Pillar 3: Dynamic 10 Hz (100ms) Block-Based Parameter Inverter

### 4.1. The Limitation of Static Inversion (V1–V6)
Prior versions predicted a single static vector of 53 Surge parameters for a 2s or 4s window. However, expressive electronic synthesis is inherently dynamic:
* Filter cutoffs sweep across bars.
* Resonance peaks and waveshaper drive modulate with velocity.
* Pitch bend and portamento glide between notes.

### 4.2. The 10 Hz Alignment with LatCH / SA3
* 100 ms corresponds to **10 Hz**.
* This aligns with the **10.76 Hz (92.8 ms per frame)** native rate of Stable Audio 3 latents and LatCH control heads!
* For a 4-second clip, the inverter outputs a parameter trajectory matrix:
  $$\Theta \in \mathbb{R}^{40 \times 53}$$
* Parameters are smoothly interpolated between the 100ms anchors using cubic Hermite splines:
  $$\theta(t) = \text{Spline}(\Theta_0, \Theta_1, \dots, \Theta_{39})$$
* **Result:** The predicted patch recreates the live, breathing automation of the original performance.

---

## 5. Eventual Outcome: The Prompt-Based Separator & Inverter

The end-state of this system is a unified, interactive tool for producers and sound designers:

```
[ User Input: Full Mix Audio Track (.wav / .flac) ]
                       +
[ User Conditioning: Prompt or Cue ]
   - Text Prompt: "screaming 303 acid lead" OR "deep rolling goa sub"
   - OR 1-Second Audio Cue: Clean snippet from intro/breakdown
                       |
                       v
       +-------------------------------+
       | V8 Prompt-Conditioned TSE     |
       +---------------+---------------+
                       |
        +--------------+--------------+
        |                             |
        v                             v
[ Clean Separated Audio ]     [ 10 Hz Parameter Trajectory ]
(Lossless .wav stem)          (Cutoff, Res, Drive, Envelopes)
                                      |
                                      v
                              [ Surge XT Plugin ]
                                      |
                                      v
                 [ DAW Export (.vstpreset + Automation Curves) ]
```

### Key Deliverables of the End System:
1. **Lossless Stem Audio:** A high-fidelity, drum-free synthesizer stem with no phase smearing or high-frequency Demucs hiss.
2. **Native DAW Preset:** A `.vstpreset` file loadable directly in Bitwig, Ableton, or Reaper.
3. **Continuous Automation Curves:** Cutoff and resonance curves exported as MIDI CC or DAW automation lanes, allowing the producer to tweak the performance natively.

---

## 6. Phased Experimental Roadmap (Cheap Tests First)

In accordance with Kim's lightweight-tests-first protocol, we do not launch full end-to-end training without validating each stage:

### Phase 0: The Musical Augmentation Harness (~1 GPU Hour)
* Build `scripts/synth_inversion/musical_dataset_v8.py`.
* Implement self-similar drum hit replacement and Pedalboard FX rack.
* Benchmark generation throughput to ensure CPU/GPU dataloader does not bottleneck training.

### Phase 1: Asymmetric 1-Stem Synth Extractor Benchmark (~3 GPU Hours)
* Train a lightweight ConvNeXt / U-Net (~15M parameters) to extract Surge synth stems from AVP drum mixtures.
* **Gate Criteria:**
  - Must beat Demucs baseline on synthetic mixtures by $\ge +2.0\text{ dB}$ SI-SDR on the synth stem.
  - Must show zero parameter degradation on contested 50–100 Hz sub-bass bins.

### Phase 2: 10 Hz Block Parameter Flow Inverter (~4 GPU Hours)
* Adapt the V6 Flow matching model (`flow_best.pt`) to predict 100ms parameter blocks with spline interpolation.
* **Gate Criteria:**
  - Evaluated on dynamic filter sweeps from `bank_v5_s0` ladders. Must recover continuous cutoff trajectories within $\pm 0.05$ normalized error.

### Phase 3: Prompt Conditioning & End-to-End Integration
* Connect text cues (CLAP text encoder, properly loaded with `630k-audioset-best.pt`) and 1-second audio cues.
* Export full DAW project bundles with automated `.vstpreset`.

---

## 7. Targeted Review Questions for the Fleet

We invite direct critique from the fleet instances before code is committed:

1. **For WINTERMUTE (Optimization & LatCH Alignment):**
   * Should the 10 Hz block predictor be trained via standard OT-CFM Flow Matching across the sequence dimension, or does a causal transformer (similar to LatCH's DiT architecture) better capture temporal filter-sweep momentum?
   * Does ModularOptimizer's spectral routing (`FusionOpt` with NorMuon + Schedule-Free) apply cleanly to the 2D U-Net separation layers?

2. **For CONTINUITY (Evaluation, Gates & Metrics):**
   * What metric should gate Phase 1 separation: should we use traditional SI-SDR / SDR, or should the gate strictly evaluate **Mel-SSIM / Modulation Spectrum Distance (MSD)** against the clean synth ground truth?
   * For evaluating dynamic 100ms automation, what is the best held-out benchmark: parameter MSE per frame, or perceptual audio trajectory distance?

3. **For GHOST-NOTE (Audition Boards & Packaging):**
   * How should the audition board visualize dynamic 100ms knob automation? (e.g. interactive SVG curve of predicted vs. true filter cutoff synced to the playback head).
   * For the prompt-based interface, what prompt categories best cover the 40 AVP songs (e.g. `[acid, rolling_bass, goa_lead, drone_pad]`)?

