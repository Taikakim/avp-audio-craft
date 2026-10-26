# ANTIGRAVITY — task log

> Terse, information-rich record of every experiment/research run/task worth tracking.
> Distinct from the journal (curated findings, links out) and WORKLOG.md (cross-repo
> relevant only) — see `SPEC-agent-profiles-journals.md` §3a. Reverse-chronological.

- [2026-10-26] SA3 Drum Separator Gates G0, G1, and G2 Dataset Pipeline:
  - Gate G0 (SAME-L Codec Ceiling): Benchmark completed on 48 isolated stems. Kick Onset F1 @ 20ms = 1.000, attack ratio +0.07 dB, SI-SDR 27.0 dB. Hi-hat F1 = 0.982-1.000, Snare F1 = 0.990-1.000. Confirmed non-additivity in latent space (34.15 dB LSD). Deployed audition console at `/home/kim/sao_runs/drum_sep_g0/listen/index.html`.
  - Gate G1 (Zero-Training Baselines): Tested solo kit priors, SDEdit across noise levels [0.3, 0.5, 0.7], and rectified flow inversion. SDEdit and flow inversion fail to isolate overlapping pieces (hats SI-SDR drops to -18 to -78 dB due to kick bleed), validating necessity of Gate G2 trained adapter. Deployed audition console at `/home/kim/sao_runs/drum_sep_g1/listen/index.html`.
  - Gate G2 Pipeline Implementation: Authored `scripts/drum_sep/build_pairs.py` with SAME-L batch-encoding and remix augmentations (+-2.5 dB). Added `DrumSepDataset` in `stable_audio_3/data/dataset.py`. Wired `--sep-data` with `mix_lat` modular inlet on layers 12-23 via `install_mir_control` in `scripts/train_lora.py`. Implemented `scripts/drum_sep/eval_separation.py` for comprehensive evaluation.
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
