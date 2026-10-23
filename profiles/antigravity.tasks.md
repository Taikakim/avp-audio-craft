# ANTIGRAVITY — task log

> Terse, information-rich record of every experiment/research run/task worth tracking.
> Distinct from the journal (curated findings, links out) and WORKLOG.md (cross-repo
> relevant only) — see `SPEC-agent-profiles-journals.md` §3a. Reverse-chronological.

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
