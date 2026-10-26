# ANTIGRAVITY — task log

> Terse, information-rich record of every experiment/research run/task worth tracking.
> Distinct from the journal (curated findings, links out) and WORKLOG.md (cross-repo
> relevant only) — see `SPEC-agent-profiles-journals.md` §3a. Reverse-chronological.

- [2026-10-26] Storage Space Reclamation & Safeguards:
  - Addressed critical storage exhaustion across drives (`/home` was at 100%, 2.6 GB free).
  - Cleaned package/tool caches: `uv cache clean` (freed 53.2 GB), `yay` cache (freed 15.0 GB), ROCm shader and thumbnail caches (freed 7.6 GB).
  - Pruned 46 redundant intermediate step checkpoints across `/home/kim/sao_runs/` (saving 42.6 GB) while strictly preserving all logs (`metrics.csv`, `manifest.json`), validation caches, and best/final checkpoints (160 checkpoints, 48.6 GB preserved, including `drum_sep_g2_kick_armA_v2/epoch=2-step=5000.ckpt`).
  - Total headroom reclaimed on `/home`: **+84.4 GB** (available free space jumped from 2.6 GB to **87 GB**, 91% use).
  - Enforced storage sandboxing: all Gate G3 datasets and models routed exclusively to `/run/media/kim/Mantu/` (175 GB free).

- [2026-10-26] SA3 Drum Separator Gate G2 Polish & Gate G3 Multi-Stem Pipeline:
  - Gate G2 STFT Wiener Mask Reconciliation: Implemented soft ratio masking ($M = |X_{\text{est}}|^\alpha / (|X_{\text{est}}|^\alpha + |X_{\text{mix}} - X_{\text{est}}|^\alpha)$) in `eval_separation.py` and deployed to `audition_console.py`. Held-out validation SI-SDR surged from +21.93 dB to **+26.43 dB** (+4.5 dB gain). Benchmark track `Acid Alien` improved to **+3.93 dB**, `Black Moon` to **+1.07 dB**, and `Goddess Guerrilla` to **-6.28 dB**. Pushed commit `549e97f` to `feature/sa3-drum-sep`.
  - Gate G3 Multi-Stem Dataset Encoding: Upgraded `build_pairs.py` to extract and pair 4 sub-stems (**Kick, Snare, Hi-Hats, Percussion**) across all 40 multitrack projects in `/run/media/kim/Mantu/avp-stems-original-classified` with dynamic $\pm 2.5\text{ dB}$ remix augmentations. Encoded 10-track held-out validation split and 30-track training split directly to `/run/media/kim/Mantu/drum_sep_data_g3/`.
  - Gate G3 Multi-Stem LoRA Training: Acquired discrete RX 9070 XT via `Misc/gpu_guard.sh acquire ANTIGRAVITY`. Launched 6,000-step training of unified prompt-conditioned SA3 DiT adapter (rank 32 LoRA + active 256-ch modular inlet) with AdamW + linear warmup (500 steps) + WSD schedule at lr 1e-4 targeting `/run/media/kim/Mantu/drum_sep_g3_multistem/`.


- [2026-10-23] External Review Analysis (Kuang V6.1 review, Surge oscillator fix, SA3 drum separator plan & Gate G0):
  - Fetched and reviewed collaborator commits across `stable-audio-tools` (`feature/v6-ablation`) and `stable-audio-3` (`feature/sa3-drum-sep`).
  - Reviewed Kuang's `V6_REVIEW.md` (§11): Surge Classic oscillator geometry confirmed (0.000 = symmetric square, no triangle); DPO sample spread collapse analysis; validated `mel_ssim_dist` correlation with Kim's ear ranks (rho = +0.67); inspected bugfix in `refine_v6_stems_cpu.py` (flushed synth render, retrigger lock, mid-channel scoring).
  - Reviewed `DRUM_SEPARATION_SA3_PLAN.md` and Gate G0 implementation `scripts/drum_sep/codec_ceiling.py`: evaluates SAME-L 93 ms latent frame transient preservation (onset F1 @ 20ms >= 0.90, attack dB >= -3 dB) before training SA3 mixture-conditioned drum separator.
- [2026-10-22] Drum Separation Benchmarks & Interactive Audition Console:
  - Benchmark BS-RoFormer SW, BS-RoFormer MUSDB18HQ, Separate-and-Detect (MSG-LD), and IDM against studio multitrack ground truth (`Goddess Guerrilla`, `Acid Alien`, `Black Moon`).
  - Result: BS-RoFormer SW achieves +18.65 dB SDR on Goddess Guerrilla (+9.8 dB over MUSDB baseline) and +15.89 dB on Acid Alien. Zero Wiener comb filtering.
  - Set up and verified Separate-and-Detect (MSG-LD 5-stem latent diffusion): downloaded checkpoints to `/run/media/kim/Mantu/checkpoints/separate_and_detect/`, patched Lightning 2.x and `soundfile` fallbacks, executed 50-step DDIM on ROCm GPU (RX 9070 XT, ~15.5s per 10.24s chunk, sequential B=1).
  - Deployed responsive interactive A/B comparison console across all 6 benchmark tracks (22-24 stems per track) at `/home/kim/sao_runs/drum_sep_comparison/listen/index.html`.
  - Documented complete findings in `docs/drum-separation-benchmarks-2026-10-22.md`.
- [2026-10-21] IDM 44.1 kHz 9-Class Drum Separation & Transcription Benchmark:
  - Built and executed IDM batch separation pipeline across 24 real bass stems and 23 matched real drum kits (47 audio sets, 423 stems total) in ~70s on CPU (~0.21x real-time).
  - Identified severe phase comb-filtering in IDM sub-band Wiener recombined stems (-3.11 dB to -111 dB SDR) and false-positive transient triggers on 303 squelches.
  - Deployed multi-stem console at `/home/kim/sao_runs/idm_stems_eval/listen/index.html`.
- [2026-10-08] v7 Transition Tempo and Phase Alignment:
  - madmom 10 ms quantisation fix: regression slope `np.polyfit(arange, downbeats, 1)` eliminates hi-hat gallop.
  - Phase alignment sign fix: `b_lo -= shift` advances correctly.
  - Vintage Goa sequencer jitter analysis: hardware swing template and 10-20 ms jitter measured across 2,291 kicks over 9 tracks.
