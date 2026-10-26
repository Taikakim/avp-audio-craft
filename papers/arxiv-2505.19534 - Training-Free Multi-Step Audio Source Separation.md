# Training-Free Multi-Step Audio Source Separation (2505.19534v1) — read by THE-FINN 2026-10-26

Yongyi Zang (independent), Jingyi Li (UIUC), Qiuqiang Kong (CUHK), v1 dated 26 May 2025, preprint. PDF: `arxiv-2505.19534 - Training-Free Multi-Step Audio Source Separation.pdf`.
**Read:** all 19 pages (main text, appendices A-C; the appendix per-step figures exist only as captions in the text extraction). Code (Apache 2.0): github.com/yongyizang/TrainingFreeMultiStepASR (not cloned).

## What it contains
- **Method (Algorithm 1).** Start with `y0 = f(x0)` from any pretrained one-step separator. Each step: build K candidate inputs `x_t = r*x0 + (1-r)*y_{t-1}` for K evenly spaced r in [0, 1], run the separator on each, score each output with a metric R, keep the best. They use K = 10, T = 20.
- **Why it works (their argument).** Separators are trained on random remixes `y = s*p + (1-s)*q`, which are points on a straight line between interference and clean source, so the trained network can denoise at any point on that line. They show the separation loss equals a denoising-diffusion-bridge loss for one weighting (w = s^2).
- **"Always improves" (Theorem 1) is weak:** r = 1 reproduces the one-step input, so the selected output can never score lower ON THE SELECTION METRIC. It says nothing about other metrics or about listening.
- **Speech enhancement** (BSRNN medium). Intrusive, selection by a fast PESQ estimator: PESQ 3.20 -> 3.28 after one step, 3.29 after 20; STOI flat; SI-SNR DROPS 19.27 -> 18.69. Blind, selection by UTMOS: UTMOS 2.31 -> 2.34, DNSMOS up slightly; the 6x-larger model still wins UTMOS. Most of the gain is in the first step; stable after about two.
- **Music** (DTTNet released checkpoints, MUSDB18-HQ test). uSDR step 0 -> 1 -> 20: vocals 10.25 -> 10.41 -> 10.45, bass 7.09 -> 7.38 -> 7.54, drums 6.13 -> 6.44 -> 6.45, other 8.75 -> 9.13 -> 9.11. Drums and other peak around step 5. **The music selection metric is an SDR against the ground-truth stems** (6 s chunks, per channel), so these numbers are oracle-selected; the authors list this as a limitation.
- Hardware: one RTX 4090. Cost: about K separator passes per step.

## FOR US — is it useful?
1. **Cheapest separation upgrade we have seen: no training, works on our existing BS-RoFormer SW.** One step captures most of the gain, so K = 5-10 and T = 1-2 is the realistic setting; that is 5-20x the current separation cost per stem. For a 6-stem model run per target stem, the cost multiplies by the stems we care about (drums, bass).
2. **The catch is the metric.** Without ground truth we need a non-intrusive score. Kim's 40 studio multitracks give ground truth, so we can test which proxy picks the same r as true SDR before running the corpus. Candidate proxies (untested): leakage in kick-free sections, low-band energy capture (the `eval/stem_bass_capture.py` measure from the F6 bake-off), PQ on the stem.
3. **It fits "stems need not be faithful" (Kim 2026-10-26).** The blend re-injects part of the mix at every step, so the chosen r is a direct knob between "clean but dull" and "full high end with some bleed". With a high-end-preservation term in the metric, the search would pick that trade-off per track.
4. **It will not fix a wrong assignment.** If the separator files psytrance bass under `other`, re-feeding the bass estimate starts from almost nothing; the F6 fine-tune is still needed for that.
5. **The bridge view also explains** why our separation-style data mixing gives models that tolerate partially separated inputs, which matters for the MIMO paper's iteration too.
- **Verdict:** a free, low-risk probe once a metric is chosen; the music gains in the paper are an upper bound because of the oracle metric. Not filed in EXPERIMENTS yet (Kim: wait for the other separation papers).
- **Leads it cites, unchecked:** DTTNet (Chen et al., ICASSP 2024); Jeon et al. "Why does music source separation benefit from cacophony?" (ICASSPW 2024); Zhou et al. denoising diffusion bridge models (2309.16948).
