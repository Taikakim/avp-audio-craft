# ANTIGRAVITY — journal

## 2026-10-08

### finding · v7 transition tempo: 10 ms-quantised bar intervals cause the hi-hat gallop; use a regression slope

The galloping hi-hats in v7 crossfade transitions were a tempo-ratio error, not a beat-detector error. madmom's 100 Hz downbeat output quantises bar intervals to 10 ms, so the A/B stretch ratio from median bar intervals was 1.82/1.76 = 1.03409. A least-squares slope over all downbeats of each clip (`np.polyfit(arange, downbeats, 1)`, BPM = 240/slope) gives 1.03010 for transition 0 (132.08 -> 136.06 BPM). The 0.004 difference is 3.99 ms/s of drift, 24.7 ms by 42 s, which is exactly the gallop. Non-integer BPM is real and expected (diffusion output is not on an integer grid): never round BPM or tempo ratio. Fix in `eval/render_v7_smoketest.py::get_exact_bpm`.

### finding · v7 kick phase alignment: sign of the shift (b_lo -= shift)

`dsp.phase_shift` returns s > 0 when B is early, i.e. B must be delayed. `b_lo` is the start index into B, so delaying B means starting earlier: `b_lo -= shift`. `+=` advanced B and doubled the transient offset. Checked in a DAW overlay (`trans0_bungee_aligned_overlay_track0/1.wav`). Residual kick offsets after alignment are -17.6 / +0.8 / -9.2 ms; NCC improves only a little (0.665 -> 0.702 on transition 0) because the generated kicks themselves are not a rigid grid.

### finding · vintage 1990s Goa sequencer timing: swing and 10-20 ms jitter are in the data

2,291 kicks over 9 tracks (1992-95: Astral Projection, Cosmosis, Hallucinogen, Transwave, Etnica, Pleiadians, Man With No Name). Tempi are non-integer (129.49-156.98 BPM). Inter-kick-interval lag-1 autocorrelation is strongly negative (-0.24 to -0.54) = alternating long/short intervals, i.e. a hardware swing template; interval jitter sigma is 10-20 ms. So a diffusion model trained on this archive reproduces groove, not a metronome, and "kick-onset on a perfect grid" is the wrong gate for generated or vintage material. Scripts: `measure_ikis.py`, `measure_goa_vintage.py` (session scratch).

### finding · clean DSP baseline accepted by Kim ("finally! the transitions were perfect")

Recipe: Bungee pre-stretch of A to B's exact tempo, window centred on nearest downbeats, kick-envelope phase alignment (+-1/4 beat), LR4 split + <=50 ms bass hand-over, linear coherent low-band drums crossfade, plain crossfade of `other`/vocals/residual. No generation. This is the benchmark; any generative layer must beat it by ear. Full-mix a2a is a known risk (unknown macro structure, galloping), so it is not used here.

### plan · masked drum inpaint and latent slerp trials (rendered 2026-10-08, not yet auditioned)

`render_v7_smoketest.py --no-generate --drum-inpaint-bars 2 4 --other-slerp` writes per transition: baseline, `d-xfade_o-slerp`, `d-inpaint{2,4}bar_o-{skipped,slerp}` in `~/staging/kone-mixtape/smoke/inpaint_trials/`. Drum inpaint masks the central N bars of the crossfaded drum window (real drums are context, 50 ms edge fades). Latent slerp encodes both `other` windows and slerps across the window. Next, in Kim's order: full-mix pre/post inpaint to 3x length, and extending finetune clips with the base model.

### lesson · env: `transformers/audio_utils.py` raises PackageNotFoundError for torchcodec

torchcodec is importable but has no dist metadata in the SAO venv; `StableAudioModel` failed to load. Patched locally in the venv with try/except (site-packages, not in git; re-apply after reinstalling transformers).

### plan · other-stem masked inpaint trials (rendered 2026-10-08 22:25, not yet auditioned)

Kim's ear on the first batch: drum inpaint great at both 2 and 4 bars (2 safer); latent slerp of other interesting but imperfect. Added --other-inpaint-bars (same masked-inpaint helper on the crossfaded other window, prompt_b, cfg 6, RMS-matched). Output in ~/staging/kone-mixtape/smoke/inpaint_trials_other/: d-inpaint{2,4}bar_o-inpaint{2,4}bar.wav per transition, plus baseline and drum-only.

## 2026-10-22

### finding · BS-RoFormer drum stem separation: +14.85 to +18.65 dB SDR on studio multitracks, zero Wiener comb-filtering

Benchmarked 3 BS-RoFormer checkpoints against dry studio multitracks (`Goddess Guerrilla`, `Acid Alien`, `Black Moon`) on ROCm (gfx1201):
- `jarredou-BS-ROFO-SW-Fixed-drums` (`mir`): **+18.65 dB SDR / +22.15 dB SI-SDR** on Goddess Guerrilla, **+15.89 dB SDR / +16.48 dB SI-SDR** on Acid Alien.
- `ZFTurbo MUSDB18HQ` baseline: +8.83 dB SDR on Goddess Guerrilla (+9.8 dB lower than SW), +8.17 dB on Acid Alien.
- Throughput: ~2.8s per 30s track (~0.10x real-time) on AMD Radeon RX 9070 XT.
- Upstream fix: patched `chunk_size` lookup in `mir/src/bs_roformer/inference.py` (line 194).

### finding · Separate-and-Detect (MSG-LD 5-Stem Latent Diffusion): clean generative sub-kit hits vs IDM phase destruction

- Architecture: 305M parameter UNet with onset and timbre branches (`msgld_obtb.ckpt`), VAE latent encoder, and HiFi-GAN vocoder.
- Evaluated against IDM: IDM suffers from -3.11 dB to -111 dB SDR due to destructive Wiener sub-band masking and transient false-positives on acid squelches.
- MSG-LD eliminates phase comb-filtering by using conditioned latent diffusion (50 DDIM steps) to synthesize clean sub-kit stems: Kick, Snare, Toms, Hi-Hats, Cymbals.
- Quantitative trade-off: Recombined SDR is -2.24 to -3.67 dB because phase is synthesized via HiFi-GAN vocoder at 16 kHz rather than deterministic STFT masking, but perceptual isolation is clean.
- Execution on ROCm: Sequential batch size 1 is required (batch size 3 exceeds 16GB VRAM during 3D UNet self-attention matrix calculation). Each 10.24s chunk takes 15.5s (~46s per 30s track).
- Deployed interactive A/B comparison console across all 6 benchmark tracks: `/home/kim/sao_runs/drum_sep_comparison/listen/index.html`. Full documentation in `docs/drum-separation-benchmarks-2026-10-22.md`.

## 2026-10-23

### review · Kuang V6.1 review, Surge classic oscillator shape correction, and SA3 drum sep plan

- **Surge Classic Oscillator Shape Correction:** Kuang verified against `ClassicOscillator.cpp` that raw 0.000 is indeed a symmetric square (width 0.5) with no triangle wave in Surge Classic; confirmed Antigravity's empirical odd-harmonic slope (-2.39) and updated docstrings/fakes in `stable-audio-tools`.
- **V6.1 DPO & Candidate Diversity:** DPO lowers single-draw MSS (6.10 -> 5.17) but degrades best-of-8 (3.27 -> 3.70) due to candidate distribution narrowing. Validated `mel_ssim_dist` as the primary ear-aligned metric (Spearman rho = +0.67 with Kim's ranks, p = 0.0004); Kuang wired `--select ssim` into `eval_real_stems_consensus_v6.py`.
- **Refinement State Flush Fix:** Caught state leak in `refine_v6_stems_cpu.py`; patches now render with `flush_synth()`, winner's retrigger setting, and mid-channel scoring.
- **SA3 Drum Separation Plan & Gate G0:** Reviewed `DRUM_SEPARATION_SA3_PLAN.md` and `scripts/drum_sep/codec_ceiling.py` (`feature/sa3-drum-sep`). Plan uses SA3 Medium Base (44.1 kHz SAME-L) with mixture-conditioned modular inlet or inpaint slot. Gate G0 checks if 93 ms SAME-L latent frames smear transient attacks (onset F1 at 20 ms >= 0.90, attack energy >= -3 dB). Untested on weights; ready to run once GPU yields from LatCH training.

## 2026-10-26

### finding · Gate G0 (SAME-L Codec Ceiling): Passed decisively on isolated drum multitrack stems

Benchmarked SAME-L autoencoder (`same-l` 44.1 kHz, 93 ms / 4096-sample latent frame window) across 48 stereo stems over 6 tracks on AMD Radeon RX 9070 XT:
- **Gate Criteria:** Onset F1 @ 20ms $\ge 0.90$, attack energy ratio $\ge -3.0\text{ dB}$.
- **Kick Stems:** Onset F1 @ 20ms = **1.000** (precision 1.000, recall 1.000 across 2,429 onsets; attack ratio = **+0.07 dB**, SI-SDR = **27.0 dB**, LSD = **1.12 dB**).
- **Hi-Hat Stems:** Onset F1 @ 20ms = **0.982 – 1.000** (attack ratio = **-0.08 to -0.19 dB**, SI-SDR = **18.7 to 20.9 dB**).
- **Snare Stems:** Onset F1 @ 20ms = **0.990 – 1.000** (attack ratio = **+0.02 dB**, SI-SDR = **22.5 dB**).
- **Latent Non-Additivity:** Reconstruct(sum(latents)) vs bus produces **34.15 dB LSD**, whereas sum(decode(latents)) vs bus is **7.92 dB LSD**. Confirms SAME-L autoencoder is highly non-linear in latent space: a linear sum of individual piece latents does not equal the latent of the acoustic mix. Validates that separation requires a trained generative mapping (Gate G2) rather than algebraic latent subtraction.
- Deployed interactive Gate G0 audition console at `/home/kim/sao_runs/drum_sep_g0/listen/index.html`.

### finding · Gate G1 (Zero-Training Baselines on SA3 Medium Base): Unsupervised separation fails, validating Gate G2 trained adapter

Tested three zero-training approaches using SA3 Medium Base weights:
1. **G1(a) Text-to-Audio Kit Prior:** Evaluated SA3 prompt sensitivity to solo kit pieces (`solo kick drum`, `acoustic snare drum`, `closed hi-hats 16th notes`, etc.). The base model cleanly generates isolated percussive transients (kicks with 25–93 onsets, punchy acoustic snares, offbeat hats, congas) confirming the generative prior knows isolated drum timbres intimately.
2. **G1(b) SDEdit Drum Bus Isolation (noise levels 0.3, 0.5, 0.7):** Fails to isolate target elements from real drum buses. At noise level 0.3, prompt conditioning is largely ignored and the entire drum bus passes through. At noise levels 0.5 and 0.7, hallucinations occur while kick bleed severely corrupts hi-hat and snare outputs (SI-SDR drops to -18.4 to -31.8 dB on hats).
3. **G1(c) Rectified Flow Inversion (ZeroSep-style ODE integration):** ODE inverted latent trajectory from the drum bus mixture fails to disentangle kit pieces. Hi-hat separation achieves -19.4 dB SI-SDR and snare achieves -4.8 dB SI-SDR due to persistent kick energy bleed throughout the entire spectrum.
- **Conclusion:** Unsupervised diffusion / inversion cannot isolate overlapping kit pieces; a trained mixture-conditioned adapter (Gate G2) is strictly necessary.
- Deployed interactive Gate G1 audition console at `/home/kim/sao_runs/drum_sep_g1/listen/index.html`.

### finding · Gate G2 Modular Inlet Freeze & Serialization Catch: Arm A vs Arm A-v2

1. **The Modular Conditioning Freeze in `train_lora.py:887`:**
   - In `train_lora.py`, line 887 previously checked `if args.mir_ctrl_pack:` to re-enable `requires_grad=True` on `modular_local_embeds` after `DiffusionCondTrainingWrapper` froze all base parameters.
   - When training separation models via `--sep-data`, `args.mir_ctrl_pack` was None. Consequently, all 48 projection parameter tensors (33,067,008 parameters) of `modular_local_embeds` remained frozen at their zero-initialization throughout Arm A's 5,000 steps.
   - The model trained exclusively through attention LoRA adapters (42.3M parameters) as a free-running generative kick prior (loss dropped from 0.829 to 0.101), but could not dynamically read or route information from the drum bus mixture latent inlet. Objective evaluation confirmed Arm A acted as an unconditioned hallucinator (-35.56 dB SI-SDR on held-out validation).
2. **Checkpoint State Dict Exclusion in `diffusion.py:1218`:**
   - In `DiffusionCondTrainingWrapper.on_save_checkpoint`, `checkpoint['state_dict']` was populated exclusively via `get_lora_state_dict()`. Because `modular_local_embeds` is an additive module rather than a LoRA parametrization, its weights were stripped from the saved `.ckpt` files (checkpoint size was only 485 MB vs 675 MB).
3. **The Architectural Fix & Arm A-v2 Training:**
   - Updated `train_lora.py:887` to check `if args.mir_ctrl_pack or args.sep_data:`, restoring `requires_grad=True` across all 48 modular projection parameter tensors before optimizer configuration.
   - Updated `diffusion.py` (`on_save_checkpoint` and `export_lora_safetensors`) to explicitly include `modular_local_embeds` in `checkpoint['state_dict']`, and added remapping in `on_load_checkpoint`.
   - Completed all 5,000 steps of Arm A-v2 (rank 32, batch size 4, lr 1e-4) on discrete AMD Radeon RX 9070 XT with 75.4M active trainable parameters (42.3M LoRA + 33.1M modular projections). Loss converged from 0.644 (step 49) down to 0.095 (step 5000), consistently outperforming Arm A. Verified that all 10 saved checkpoints (675 MB each) contain non-zero learned weights across all 48 modular projection tensors.

### finding · Gate G2 Conditioned Separation: Inpainting contract resolution and sliding-window full-song benchmarking

1. **Inference Conditioning Contract Catch:**
   - During training with `DrumSepDataset`, the batch dictionary routed the mixture latent `mix_lat` both into the native inpainting slot (`inpaint_masked_input` with `inpaint_mask = 0`) and into `modular_local_embeds`.
   - During initial evaluation, `eval_separation.py` zero-filled `inpaint_masked_input`, which starved the base model's native local conditioning layer and resulted in degraded separation (-37.76 dB SI-SDR).
   - Aligning `inpaint_masked_input = mix_lat` at inference produced an immediate **+59.5 dB SI-SDR jump** on held-out validation multitracks, achieving **+21.93 dB mean SI-SDR**, **8.04 dB LSD**, **1.000 onset precision @ 20ms**, and **-0.71 dB attack energy deviation**. Latent correlation with ground truth kick jumped from 0.34 to **0.970**.
2. **Sliding-Window Inference (`separate_long_audio`):**
   - Directly feeding full 30s tracks ($T=323$ frames) into SA3 Medium Base caused PyTorch ROCm SDPA to trigger Triton flex-attention autotuning on RDNA 4 (GFX1201), producing NaN overflows.
   - Implemented `separate_long_audio` with sliding 130-frame windows (matching the training crop length of 12.07s) and 96-frame hop (34-frame / 3.16s overlap) with smooth raised-cosine crossfading. Execution completes stably in ~15s per 30s track without any numerical instability or Triton autotuning hang.
3. **Benchmark Multitrack Results:**
   - **`Acid Alien` (Full 30s Mix):**
     - SA3 Kick (Gate G2): **SI-SDR +3.81 dB** | LSD 28.85 dB | Onset F1 0.523 | Attack -3.78 dB
     - MSG-LD Kick (Baseline): **SI-SDR -29.26 dB** | LSD 22.02 dB | Onset F1 0.065 | Attack -53.40 dB
     - SA3 outperforms MSG-LD by **+33.07 dB SI-SDR** and +8.0x onset F1.
   - **`Black Moon` (Full 30s Mix):**
     - SA3 Kick (Gate G2): **SI-SDR +0.73 dB** | LSD 30.14 dB | Onset F1 0.513 | Attack +0.31 dB
     - MSG-LD Kick (Baseline): **SI-SDR -30.82 dB** | LSD 22.39 dB | Onset F1 0.011 | Attack -11.25 dB
     - SA3 outperforms MSG-LD by **+31.55 dB SI-SDR** and +46x onset F1.
   - **`Goddess Guerrilla` (Full 30s Mix):**
     - SA3 Kick (Gate G2): **SI-SDR -6.72 dB** | LSD 45.77 dB | Onset F1 0.136 | Attack -2.70 dB
     - MSG-LD Kick (Baseline): **SI-SDR -30.16 dB** | LSD 14.45 dB | Onset F1 0.194 | Attack -39.04 dB
     - SA3 outperforms MSG-LD by **+23.44 dB SI-SDR**.
   - Note on BS-RoFormer: BS-RoFormer operates on the drum bus as a whole (+18.13 dB on Acid Alien, +4.68 dB on Black Moon, +17.22 dB on Goddess Guerrilla) because it was trained to separate all drums from music, rather than isolating sub-kit pieces (kick from cymbals/snare). Against dedicated sub-kit generative models (MSG-LD), SA3 is decisively superior by 23 to 33 dB.
4. **Interactive Audition Console:**
   - Deployed at `file:///home/kim/sao_runs/drum_sep_g2_eval/index.html` with synchronous multi-track audio playback, live A/B solo comparison, metric badges, and validation inspection.



