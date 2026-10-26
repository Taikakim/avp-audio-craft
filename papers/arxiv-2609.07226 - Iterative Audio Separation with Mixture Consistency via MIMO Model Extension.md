# Iterative Audio Separation with Mixture Consistency via MIMO Model Extension (2609.07226v1) — read by THE-FINN 2026-10-26

Yukara Ikemiya, WeiHsiang Liao, Yuki Mitsufuji (Sony AI), v1 dated 7 Sep 2026. PDF: `arxiv-2609.07226 - Iterative Audio Separation with Mixture Consistency via MIMO Model Extension.pdf`.
**Read:** all 8 pages (method, ablation, both experiments, conclusion). Code and weights: github.com/SonyResearch/mimo-audio-separation (README and docs read via the GitHub API 2026-10-26, not cloned).

## The repo (checked 2026-10-26)
- **MIT licence**, PyTorch, Hydra configs, Accelerate DDP; Singularity container built for CUDA 12.1 / PyTorch 2.5 (we would run it outside the container on ROCm, untested). Training needs a Weights & Biases key.
- **Released weights, all trained on MUSDB18-HQ train only** (museval SDR, median of medians):
  - BS-RoFormer 2-stem (vocals/accompaniment): small 12.1M SISO 9.64 / 16.80, MIMO 16.3M 10.17 / 17.64; large 72.2M SISO 11.40 / 18.48, MIMO 71.4M 11.62 / 19.04.
  - **SCNet 4-stem, 10.6M** (vocals/bass/drums/other): SISO 9.71 / 9.65 / 10.61 / 7.26, **MIMO 9.82 / 10.46 / 10.93 / 7.69**, MIMO-gen 9.88 / 10.17 / 10.81 / 7.61.
  - No MIMO version of a 4-stem BS-RoFormer, and nothing trained on electronic music.
- **Custom stems are a config change:** the dataset reads one folder per track with one file per stem; `inst_list` names the stem files and `gather_list` groups them into targets (e.g. `[[0], [1, 2, 3]]` = vocals vs the rest). A kick / bass / rest target over Kim's classified studio stems maps onto this directly. `trainer.finetuning=true` starts from existing weights with a fresh optimizer and schedule. `MIMOBase` (`src/model/mimo_base.py`) wraps any backbone for the iteration and the projection.
- Augmentation flags: `aug_mix` (cross-track mixing), `aug_volume`, `aug_flip`.

## What it contains
- **MIMO extension.** The separator takes all K current stem estimates as input (first iteration: mix/K for every stem) plus a learnable iteration-index embedding, and outputs K refined estimates. For mask models (BS-RoFormer) it predicts one mask per (output, input) pair and sums: `S_k = sum_j m_kj * S_j`. Only the input/output modules change.
- **Mixture-consistency projection** after every iteration: `s_k += (x - sum_j s_j) / K`, so stems always sum to the mix. Also stabilises training by narrowing what the model must predict.
- **Loss** per iteration: STFT L1 + 2 x waveform L1, plus 0.01 x adversarial loss; summed over iterations with weight i (later iterations count more). Peak-normalised input.
- **Discriminators:** a per-stem multi-band discriminator (DAC design) helps; a multi-stem (set-level) discriminator HURTS in both the 1- and 3-iteration cases. Feature-matching loss made training unstable, so only the adversarial term is used.
- **"Generative" variant:** zero-sum noise on the inputs (the noise cancels in the sum, so consistency holds) plus the clean mix as an extra input. Small extra gains on some stems.
- **Augmentation:** each stem drawn from a random position of a random track (cross-track remixing), channel swap, phase inversion, random gain, and with small probability a stem replaced by silence.
- **Evaluation:** MUSDB18-HQ test stems cleaned first (1 s segments under 0.01 peak set to silence), metrics on 1 s segments, median per track. New **LPR** (leakage power ratio): energy in the estimate where the reference is silent, relative to the reference's median non-silent level, in dB.
- **Results.**
  - Ablation (small BS-RoFormer, 4 s, vocal/accompaniment): one-step SISO, SIMO and MIMO are equal (vocal SDR 10.36-10.41); three iterations + stem discriminator give 11.05.
  - 72M BS-RoFormer, 8 s: vocal SDR 11.40 -> 11.62 (museval); vocal LPR -48.2 -> -58.4 dB; out-of-domain MoisesDB vocal SDR 12.15 -> 12.44.
  - 4-stem SCNet (10.6M): vocals 10.39 -> 10.57 (gen 10.72), bass 9.10 -> 9.80, drums 11.32 -> 11.73, other 7.21 -> 7.63.
  - Gains saturate around 4 iterations (they use 3 for BS-RoFormer, 2 for SCNet). Training: 1M steps, batch 96 (BS-RoFormer, bf16) / 48 (SCNet, fp32).
- Figure 4 claims iteration + stem discriminator also restores high frequencies lost in the accompaniment (visual only, no metric for it).

## FOR US — is it useful?
Context: our stems feed controls and training data, not remix delivery, so **they need not be faithful to the source or sum to the mix** (Kim 2026-10-26). That changes which parts matter.
1. **Mixture consistency is not a goal for us.** The projection is free to apply to existing BS-RoFormer outputs, but its value to us is limited. It also spreads the residual evenly, so it cannot fix the psytrance-bass mis-assignment (F6 bake-off: BS-RoFormer 4-stem bass capture 0.00). A variant that suits our case (my idea, untested): give the residual's high band to EVERY stem that should carry it, i.e. duplicate rather than split, so stems keep the mix's air and transients.
2. **The iteration is the real gain**, and it needs a training run (1M steps at their scale). The cheapest real route is fine-tuning the released 10.6M MIMO SCNet 4-stem (its bass is the stem that gained most, 9.65 -> 10.46) on our stems; small enough for the local GPU. For the training-free route see Zang et al. 2505.19534 (sidecar next to this one).
3. **Data recipe for F6 (kick / bass / rest).** Kim's 40 studio multitracks (`Mantu/avp-stems-original-classified`, stems pre-classified into kick, bass, leads, ...) plus their cross-track remixing and silent-stem dropout. MUSDB has only 100 training tracks, so 40 clean psytrance tracks is a meaningful set.
4. **Stem-wise discriminator, not the multi-stem one.** Directly reusable if we fine-tune.
5. **Evaluation protocol** (1 s segments, median, LPR on silent regions) fits our separation benchmarks; LPR on kick-free breakdowns would measure kick bleed directly.
- **Verdict:** solid, modest gains (0.2-0.7 dB SDR, about 10 dB less silent-region leakage on vocals). Worth borrowing the eval protocol now; the MIMO fine-tune only when F6 gets compute. Not filed in EXPERIMENTS yet (Kim: wait for the other separation papers).
- **Leads it cites, unchecked:** Scheibler et al. "Source separation by flow matching" (WASPAA 2025, zero-sum noise); Tunturi 2025 master's thesis (test-data cleaning, LPR); Koizumi et al. WaveFit (fixed-point iteration).
