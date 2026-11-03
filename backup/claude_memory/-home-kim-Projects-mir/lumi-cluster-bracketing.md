---
name: lumi-cluster-bracketing
description: "SA3 riffer systematic sweeps (soup-design, crop/LR ablations) move to the LUMI cluster as it comes online"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

The user is bringing up access to **LUMI** (EuroHPC supercomputer, AMD GPUs) to run **systematic bracketing** of the SA3 riffer control-adapter experiments that the local single-GPU box can only do serially. The local box stays for one-off "vibe" runs; **Lumi is for the parallel sweeps.**

Flagged targets for Lumi:
- **Soup-design space** — peak *position* × *width* (σ) × *epoch range*, **per run** (optimum differs: AdamW favors *early* checkpoints, the 40ep Fusion favors *mid-late*). Motivating detail: the exp-peak@ep20 soup is a Gaussian — ep25≈61%, ep30≈13%, ep40≈0.03% of ep20's weight, so effective mass is ep14–30, *not* a true ep1–40 average. The span is the knob to bracket.
- **Crop-size** (256/512/1024) and **LR/optimizer** ablations.

Cheap because soups are CPU-only to build; only eval needs GPU and it's embarrassingly parallel. Relates to [[latch_recipe]] and the riffer findings.
