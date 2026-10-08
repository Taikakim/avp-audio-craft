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
