# Optimiser findings, 2026-10-17 .. 10-26: briefing for the JEPA and drum-separation work

*Author: WINTERMUTE, 2026-10-26. Written for Antigravity, who continues the drum JEPA and the separation work. Sources are
cited per line. Full tables: `docs/TRAINING.md` §2 (F1-F30), `docs/training-findings.md` 2026-10-22, `EXPERIMENTS.md` E14-E19.*

**Scope warning first.** Almost everything below was measured on ONE task: the LatCH onset head (a d256 transformer of ~6M
parameters, trained from scratch on goa_bigset latents, ~12k crops, 40 epochs). It has not been checked on a JEPA encoder
or a separation model. Read each point as a strong prior for small from-scratch models and a hypothesis for fine-tuning a
pretrained separator.

## 1. The ranking at batch 64 (LatCH onset head, best held-out val, lower is better)

| arm | val | note |
|---|---|---|
| Muon (ModularOptimizer, Schedule-Free, EMA), b64 (`EB64`) | **0.1802** | best in every comparison so far, and the widest steering range (2.9 -> 12.1 onsets/s at gain 512) |
| same, stratified t (`ST64`) | 0.1819 | no gain (E14) |
| Muon head, then AdamW lr 1e-4 + warmup + cosine (`C1`) | 0.1839 | switching late buys nothing |
| AdEMAMix, continued 20 ep from its best | 0.1894 | ties KL-SOAP |
| Muon b256, lr x4 (linear rule) | 0.1900 | |
| AdamW, cosine to 0 over 40 ep (`AWc`) | 0.2002 | |
| AdamW, constant 3e-4 | 0.2080 | val swings 0.21-0.29 with no averaging or decay |
| AdamW cosine + AdaGC 1.04 (`AWcG`) | 0.2511 | stopped at ep 12; AdaGC hurt |

Sources: WORKLOG 2026-10-22 08:08 / 14:00, 2026-10-23 08:20; EXPERIMENTS E14.

## 2. Findings that should transfer

1. **Run-to-run noise is about 0.01 on this head (~5%).** EB64 and its rerun EB64r, same seed and recipe, read 0.1802 and
   0.1896. The data-worker count alone moved a run by 0.004 (F4). Do not rank arms that differ by less than this without a
   repeat.
2. **The mean held-out loss hides where optimisers differ.** Split by diffusion t, 51-55% of the loss sits at high noise
   (t > 0.7), where optimisers differ by 4-8%; at t <= 0.45 AdamW is 25-39% worse than Muon. A 12% gap in the mean is a 30%+
   gap where it matters (training-findings T1; `train_latch.py --val-t-bins`). For JEPA and separation, the same idea applies:
   log held-out loss per condition (per stem, per masking ratio, per input SNR), not only the mean.
3. **Batch above 64: scale lr linearly, not by sqrt.** b256 at lr x4 0.1900 vs lr x2 0.1964. The half-batch gradient cosine
   (0.37 early, 0.08 late) says the momentum is signal-dominated on every matrix, so the step saturates and the sqrt rule
   under-steps. Bigger batches were still worse than b64 at equal epochs (fewer steps). (T2; E17 review)
4. **A fresh AdamW on a trained model needs warmup and a low lr.** At step 1 every weight moves by about lr: switching the
   trained Muon head to AdamW at 3e-4 without warmup jumped val 0.180 -> 0.338 and never recovered; 1e-3 diverged. This is
   the lesson most likely to matter for fine-tuning a pretrained BS-RoFormer (T3).
5. **Keep optimiser state in fp32 when weights are bf16.** bf16 storage loses most of a Muon-family step at lr <= 1e-3 (29%
   of the fp32 change kept at 3e-4, 64% at 1e-3); FiLM `to_k/to_v` were nearly frozen late while the loss looked identical.
   Flag `--mod-state-dtype fp32` (`--modular-state-dtype` in the DoRA trainer); cost +13-21 ms per update. (F21, test plan A4)
6. **The 1-D / sign group sets the lr ceiling.** Gains and biases step a full lr per element while matrices step lr/sqrt(d_in);
   lr 3e-2 diverged until the sign group was capped at 2e-3, and even then it only matched lr 1e-2 (0.1889 vs 0.1822). If you
   use ModularOptimizer, give 1-D parameters their own small lr. (F24, test plan B)
7. **Less data hurts more than any optimiser choice.** 20% of the training set: 0.2614; plus 710 other-genre crops: 0.2471
   (a small gain, one seed); both far above 0.1802. Steps and data are confounded there (1/5 of the steps). (E14 addendum)
8. **Judge checkpoints on real data, not only on held-out synthetic loss.** Synth-JEPA H1: EMA and online tied on held-out flow
   loss and the Schedule-Free average was weakest there, but best on the 24 real stems. Flow-DPO rounds kept improving the
   rewarded MSS while mel-SSIM (the metric that tracked listening) fell back to baseline by round 4. (EXPERIMENTS H1, SJ2)

## 3. Things not to spend time on (tested or argued out)

- **Noise-based Muon variants (NAMO, HTMuon, SNR gate, MONA):** at our batch sizes no matrix is noise-dominated, so
  an SNR gate acts as an uncalibrated ~x0.2 lr cut, and MONA's gradient differences are mostly noise. HTMuon's gain over Muon
  shrinks to 0.02 ppl at 350M. All parked (E15-E17, F26, F27).
- **Shampoo/Mousse whitening on top of Newton-Schulz:** no measured gain on heads (F25). KL-SOAP ran but did not beat Muon.
- **AdaGC:** hurt (above). **Stratified timesteps:** no gain (E14).
- **SAMuon-style larger steps along momentum directions:** every probed band raised held-out loss at ep 5, 10 and 20; the
  leading directions oscillate (test plan P).
- **Routing radius under NorMuon:** cancels exactly, does nothing (F22).

## 4. Practical notes

- `Projects/Emerging-Optimizers` was updated 8accc9a -> aa32262 on 2026-10-22 (KL-Shampoo, Polar Express coefficient fix,
  AdaptiveMuon fix). Runs before that date used the old checkout.
- ModularOptimizer's routing regexes are written for DiT names; they miss some LatCH names (`attn.qkv`, `adaLN_mod`,
  `t_embedder.mlp`) and will likely miss BS-RoFormer's or a JEPA's. Print the group assignment before a first run (F30).
- Any trainer building ModularOptimizer must turn its per-step telemetry off (`_telem_on`) except on logged steps, or it
  syncs the GPU every step (F29).
- Save the best-val checkpoint explicitly, or keep the per-epoch val log next to the checkpoints: a prune on 2026-10-23
  deleted the best epoch of 13 runs that never wrote a `_best.pt`. `train_latch.py --save-every N` exists now.
- Guidance artefacts: the ~0.9 kHz ringing heard on some heads is a pitch that the prompt and finetune bring forward when
  the drums thin, not something an optimiser adds (E19). Do not rank optimisers by it.

## 5. Suggested defaults for a new small model (hypothesis for JEPA / separation)

Muon-family on 2-D matrices with fp32 state, AdamW (or a capped small lr) on 1-D and embedding parameters, warmup,
batch 64, EMA or Schedule-Free averaging with all three weight sets (online / EMA / average) saved and compared on real
data, held-out loss logged per condition, and a repeat run before believing any difference under ~5%. For fine-tuning a
pretrained separator, start from AdamW with warmup and a low lr; whether Muon helps there is untested here.
