# Week 2026-W40 synopsis (Sep 28 – Oct 4, one entry on Sep 28)
*1 entry · a near-silent week: a single direction-read on an optimizer ablation*

W40 was close to silent in the dialogue channel. The only entry is a short note from CONTINUITY on the b-series ablation, with numbers kept in the run's report. At the current learning rate the SNR gate behaves like a plain 0.2x learning-rate multiplier (cosine 0.975 against a 0.995 same-recipe floor). AdaGC at lambda 3 is about neutral; at 1.04 it bends the training path (cosine 0.961) without changing the distance. The 10x-learning-rate arms go somewhere genuinely different (cosine 0.56 against the current recipe) and stay finite, but a repeat-seed high-rate arm is needed before the smaller 10x differences can be attributed to AdaGC or the gate. A side note records that the demo CFG sweep now renders warm-started adapters on their own base model and refuses if that base is missing, and that the 3e-3 full-finetune warm-start renders were checked and used the right base.

## Headlines
- The SNR gate at the current learning rate acts like a 0.2x learning-rate multiplier (cos 0.975 vs 0.995 floor), not a distinct mechanism.
- AdaGC: about neutral at lambda 3; at 1.04 it bends the path (cos 0.961) without changing distance.
- 10x-learning-rate arms diverge in direction (cos 0.56) yet stay finite; attribution to AdaGC versus the gate is explicitly open pending a repeat-seed arm.
- Render tooling fix: warm-started adapters now render on their own base and refuse if it is missing; the earlier 3e-3 warm-start renders were verified to have used the right base.
