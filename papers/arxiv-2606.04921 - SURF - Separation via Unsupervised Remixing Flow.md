# SURF: Separation via Unsupervised Remixing Flow (2606.04921v1) — read by THE-FINN 2026-10-26

Henry Li, Robin Scheibler (equal), Efthymios Tzinis, Matt Shannon, Arnaud Doucet, John R. Hershey (Google, Google DeepMind), v1 dated 3 Jun 2026, ICML 2026. PDF: `arxiv-2606.04921 - SURF - Separation via Unsupervised Remixing Flow.pdf`.
**Read:** main text (pp. 1-10), Appendix D (experimental details, hybrid teacher, hyperparameters) and the ablation table; Appendix C proofs skimmed only. A demo page is mentioned without a URL; no code repository named (Appendix D has a PyTorch code listing for one iteration).

## What it contains
- **Goal:** train a GENERATIVE separator (flow matching) from mixtures only, with no clean sources and no pretrained clean-source prior. Motivation: no clean in-domain data, and domain shift for supervised models.
- **Base method:** FLOSS (Scheibler et al. 2025, "Source separation by flow matching"): flow from a mixture-consistent noise start (`x0 = m/K + projected noise`, so the stems always sum to the mix) to the sources, with a PIT step that picks the source order at each sample.
- **SURF loop (Algorithm 1):**
  1. A teacher separates a batch of real mixtures.
  2. All teacher stems in the batch are shuffled across mixtures and summed into new synthetic mixtures with known pseudo-targets ("remixing").
  3. The student flow model trains on those, with one of two losses: **ReMixIT** (targets = the teacher stems, so teacher errors are inherited) or **Self-Remixing** (the student's estimates are un-shuffled and must sum back to the ORIGINAL mixture, so teacher errors do not enter the target directly).
  4. Teacher = EMA of the student.
- **Start:** a MixIT teacher (trained on mixtures of mixtures). A **hybrid teacher** keeps training stable: below flow time beta the sampler jumps straight to the frozen MixIT estimate, above it uses the EMA teacher; beta decays 1 -> 0 over the first 200k steps.
- **Theory:** in the large-batch limit both losses equal a pseudo-supervised flow loss plus a correction term: ReMixIT's depends on the teacher's error, Self-Remixing's only on correlated student errors. ReMixIT is shown to be an instance of Wake-Sleep.
- **Results (all 16 kHz; audio model MB-TFLocoformer, 36M on Libri2Mix; 5-step Euler sampling):**
  - Libri2Mix speech, SI-SDR: MixIT 12.39, regression ReMixIT 13.22 / Self-Remixing 13.60, **SURF 16.54 / 16.28**, supervised flow 17.89.
  - AudioSet (731 h, real mixtures, no ground truth), evaluated on FUSS and LibriSpeech+FUSS: SURF best unsupervised on 1-2 sources, slightly worse on 3-4; better at getting the number of sources right.
  - Images (MNIST, CIFAR-10): close to supervised flow.
- **Ablations (CIFAR-10):** EMA 0.999 best, 0.9999 collapses (PSNR 13.4), 0 poor (16.6); **batch size matters a lot** (B=1 8.8 for Self-Remixing, B=256 19.5), because remixing needs many mixtures per batch; the hybrid-teacher schedule beats any fixed beta.
- **No music experiments.** Sources are treated as unlabelled and interchangeable (permutation-invariant), as in speech or universal separation.

## FOR US — is it useful?
1. **The remixing idea fits our data better than the full method.** We have far more psytrance mixtures than clean stems (12.5k bigset crops, the larger goa_archive), and a supervised separator that suffers from domain shift (BS-RoFormer files psytrance bass under `other`). Remix-style self-training with a STRONG teacher (BS-RoFormer SW instead of MixIT) is the domain-adaptation use the authors motivate but do not test.
2. **But SURF assumes unlabelled sources.** Our stems have roles (kick, bass, drums, other); PIT over interchangeable sources does not apply as is. A labelled variant (remix teacher stems role by role across tracks: one track's drums + another's bass + a third's other) is the natural adaptation; untested and not in the paper.
3. **Self-Remixing is the variant to prefer** with a biased teacher: its target is the real mixture, so the teacher's systematic error (missing bass) is not copied into the target. A labelled remix still cannot create a bass stem the teacher never produced, so this complements Kim's studio stems (true bass) rather than replacing them.
4. **Remixed stems are ready-made training data under Kim's note** (2026-10-26: stems need not be faithful or sum to the source). Cross-track remixes of separated stems give unlimited new mixtures with known parts, for a separator fine-tune (MIMO paper's augmentation is the same move) or for B14-style control training.
5. **Costs to plan for:** large batches of mixtures (B=256 in the best ablation), a generative separator trained from scratch, 16 kHz only in the paper. The regression versions (ReMixIT / Self-Remixing without flow) are the cheaper first step.
- **Verdict:** a careful, well-ablated method for speech and universal sound, with no music test. For us the transferable piece is remix self-training from a strong teacher on our own corpus, with Self-Remixing's loss. Not filed in EXPERIMENTS yet (Kim: wait for the other separation papers).
- **Leads it cites, unchecked:** FLOSS / Scheibler et al. 2025 (also cited by the MIMO paper for zero-sum noise); ReMixIT (Tzinis et al. 2022); Self-Remixing (Saijo & Ogawa 2023; Saijo et al. 2025); MixIT (Wisdom et al. 2020); MB-TFLocoformer.
