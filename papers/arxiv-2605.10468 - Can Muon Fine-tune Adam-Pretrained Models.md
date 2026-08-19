# Can Muon Fine-tune Adam-Pretrained Models? (2605.10468v1) — deep-read

Qu, Huang, Horvath (MBZUAI / Nanjing), ICML 2026 (PMLR 306), May 2026.
PDF: `arxiv-2605.10468 - Can Muon Fine-tune Adam-Pretrained Models.pdf`. **Read in full by C
2026-08-19 (pp. 1–9 main, 13–32 appendices A–G); every number below is from the PDF, not from
the external summary that pointed us at it.** Kim flagged it as "might be highly relevant" the night
the step-resolution trajectory data landed; it is.

## What the paper actually shows (with its own numbers)
- **The optimizer-mismatch phenomenon, reproduced at accessible scale.** Two 561M NanoChat models
  pretrained from scratch (Muon vs Adam, ~11B tokens, matched CORE 0.21/0.19), then fine-tuned on
  WikiText-2. Table 1 (relative PPL, lower better): Adam-pretrained → Full-Adam **0.710** vs
  Full-Muon 0.719 (+0.009); LoRA-Adam 0.721 vs LoRA-Muon 0.723 (+0.002). Muon-pretrained → the
  mirror image. **Symmetric: matched optimizer wins both ways.** The effect is real and small in
  absolute terms — the paper's own framing is "degraded", not "fails".
- **Mechanism = distinct implicit biases.** Toy underdetermined regression `Wx=y` from `W0=0`:
  SignGD (Adam proxy) → `W* = y·sign(x)ᵀ/‖x‖₁` = **min max-norm** solution (Thm 3.1/D.2); exact-
  orthogonalization Muon → `W* = y xᵀ/‖x‖²` = **min spectral-norm** solution (Thm 3.2/D.3). In real
  nets: Muon-trained QKV keeps **higher stable rank and SVD entropy** throughout pretraining (Fig 2,
  10, 11 — Muon ~90–180 vs Adam ~40–110 stable rank on NanoChat), i.e. structurally different weights.
- **Mismatch = sensitivity to update strength.** LR sweeps (Fig 4): under mismatch the whole
  perplexity-vs-LR curve shifts **up and left** — smaller optimal LR AND worse best PPL. Weight-space:
  under full FT, Muon on Adam-pretrained Llama-2-7B moves **5.6–7.4× further in cosine distance**
  than Adam (Table 17, math/code); forgetting is worse (Table 5: Full-Muon 55.4 vs Full-Adam 56.8
  commonsense after math FT) **despite** worse fine-tune performance — "actively disrupts pretrained
  knowledge", not merely "learns less".
- **LoRA mitigates.** Gap shrinks 78 % (Adam-pretrained) / 39 % (Muon-pretrained) on NanoChat;
  T5-Base GLUE (Table 2): Full-Muon 88.77 < Full-Adam 89.14 but LoRA-Muon 88.97 ≥ LoRA-Adam 88.93 and
  **LoRA-Muon-PE 89.20 is the best of all**; Llama-2-7B (Table 3): Full-Muon math 57.4 vs Full-Adam
  61.7, but LoRA-Muon 59.6 ≈ LoRA-Adam 59.6, and LoRA-Muon wins code/commonsense; CLIP ViT-B/32
  (Table 4): LoRA-Muon(-PE) 84.5–84.7 > LoRA-Adam 84.2. Meta-analysis: pooled gap reduction 0.72 %
  (Muon) / 0.83 % (Muon-PE), p<0.001. Under LoRA, Muon's cosine distance is **0.2–0.8× Adam's**.
- **Rank matters (Fig 5–7).** Where mismatch is pronounced (MetaMath), LoRA-Muon matches/beats
  LoRA-Adam at r ≤ 64 and **degrades at r ≥ 128** ("updates increasingly resemble full FT");
  forgetting: LoRA-Muon forgets LESS than LoRA-Adam at low rank, MORE at r ≥ 256. Where mismatch is
  mild (code, vision), LoRA-Muon is fine at every rank, advantage widening with rank on StanfordCars.
- **Theory of the LoRA effect (App D.3–D.4).** Fine-tuning from `W0` = fitting the residual with a
  correction Δ; each optimizer reaches exact fit with the smallest budget in ITS native norm; under
  a fixed-subspace LoRA surrogate the worst-case mismatch inflation is **≤ r (Adam-native) / ≤ √r
  (Muon-native)**, collapsing to 1 at r=1 and recovering full-FT formulas at A=I. Clean.
- **Variants:** Adam-tuned LoRA variants (rsLoRA, LoRA-One, PiSSA) improve LoRA-Adam but **do not
  transfer** to LoRA-Muon (rsLoRA's α/√r AMPLIFIES update magnitude → worse under mismatch); DoRA,
  AdaLoRA, LoRA-Pro, LoRA-RITE only run with Adam ("algorithm-modifying, not directly compatible").
  Polar Express (better orthogonalization) helps full-FT Muon, slightly hurts LoRA-Muon on NLG.
- **F.2 — spectral analysis of the LoRA A and B matrices themselves:** LoRA-Muon keeps stable rank
  ~6–7 of 8 and SVD entropy 0.98–1.0 in BOTH A and B; LoRA-Adam ~3–5 / 0.80–0.95. Muon's flattening
  bias reaches the adapters. **Measured on A and B separately, never on the product B·A.**
- **Setup facts that matter for us:** their Muon = Moonlight variant (`0.2·√max(m,n)` scaling,
  classical momentum 0.95 + Nesterov, NS5 in bf16), **no weight decay on Muon params (NLU/NLG; 0.1
  in vision for both)**, **cosine LR decay + 3 % warmup everywhere**, LR swept per method (Muon's
  optimum ≠ Adam's: Full-Muon 5e-5 vs Full-Adam 1e-5 on Llama; LoRA both ~5e-4). Muon LoRA is only
  1.1–1.3× slower than Adam LoRA; full-FT 2.3–2.9× but confounded by ZeRO-2 vs DDP.
- **Limits stated by the authors:** LLM/CLIP only, ≤13B, mismatch severity task-dependent for
  unknown reasons, "specialized initialization or warmup" might close the gap — left open.

## FOR US — what changes, what it confirms, what stays ours
- **SA3-medium's base is "overwhelmingly AdamW-shaped"** (Zach: Muon adopted late and briefly;
  `CLAUDE.md`). Our **full-FT + Fusion (Muon/NS5) runs are the paper's mismatch case**: predicted
  degraded quality, larger weight displacement, MORE forgetting, and hypersensitivity to update
  strength. That is a paper-grounded frame for W's family collapsing late (ep59+), the drone, and
  "grad-clip / AdaGC did nothing" (they act on the gradient; Muon's magnitude is set by LR).
  **Prescription:** full-FT with the matched optimizer (AdamW, properly decayed) or Muon at a much
  smaller LR + decay + short; or don't full-FT — adapt.
- **Our healthy family (LoRA/DoRA r128 + Fusion) is the paper's mitigated case** — consistent with
  the archive (Fusion DoRA sounds fine; full-FT Fusion drones). Two cautions from the rank study:
  (a) at **r ≥ 128** LoRA-Muon starts to behave like full FT when mismatch is pronounced — our r128
  is at the edge and our **r256 arm** (`smoke_r256_a256`, path-eff 0.899, HIGH-EFF = straight-line
  march) is the kind of thing that predicts; (b) **DoRA-rows + Fusion is an untested combination**
  in the paper — they found Adam-tuned variants don't transfer to Muon and did not run DoRA-Muon.
  We should not assume DoRA's benefit carries over; a DoRA-vs-plain-LoRA arm under Fusion is cheap.
- **It never runs Muon at constant LR.** Cosine + warmup everywhere. That is independent support
  for the damping work of 2026-08-19 (`--fusion-decay cosine`, `FusionOpt.decay_schedule`) and
  for the finding that our constant-LR Fusion never slows.
- **F.2 matches C's mechanism and our step data complements it.** NS5 makes each factor (A, B)
  spectrally flat — they measure exactly that. Our trajectory sketch adds the view they don't take:
  the **product B·A** at r16 is rank-1-dominant under BOTH optimizers (top-1 0.55 Fusion / 0.58
  AdamW), because every step's `dB = δ_t (A x_t)ᵀ` shares the input factor `A·x̄`. Flat factors,
  spiky product. Their entropy plots would not have seen it.
- **The clean theory result to keep:** LoRA mismatch inflation ≤ r / √r — the formal reason "constrain
  the update" works, and why rank is the knob (moderate ranks; not r256 for a mismatched full-width
  fine-tune).
- **What stays ours:** everything about the small-batch regime — the paper's batches are 32–256 and
  its gradients carry signal; nothing in it addresses gradient window-SNR = 1/w, walk-vs-drift, or
  Muon as low-rank signal amplifier at bs1. And nothing addresses diffusion/DiT, DoRA, SF averaging,
  or NorMuon (they use plain Moonlight Muon).
- **On the external summary that pointed here:** its "answer is essentially no, not naively" overstates
  a paper whose own effect sizes are ~1 % absolute; the accurate statement is "measurably worse and
  it forgets more, LoRA closes most of the gap, rank and LR need Muon-specific tuning."

## Concrete follow-ups this licenses (cheap first)
1. **DoRA-vs-LoRA under Fusion** at r128 on goa (their variant-transfer warning), 1 GCD each.
2. **Rank ladder r∈{16,32,64,128,256} × {AdamW, Fusion} with per-optimizer LR sweep** — the paper's
   protocol; with the trajectory sketch on, we also get walk-vs-drift per cell.
3. **Full-FT AdamW-with-cosine as the matched control** for the drone family (never run: our
   full-FTs were Fusion or constant-LR AdamW).
4. Adopt their defaults for any Fusion arm: warmup ≥ 3 % (also fixes the zero-init-B first step,
   6× too large in our data), cosine decay, Muon LR swept separately from Adam's.
