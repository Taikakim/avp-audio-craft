# Kim's section-by-section review of the Muon survival guide (2026-10-26) -- captured so a compaction cannot lose it

Source: Kim's message of 2026-10-26 to CONTINUITY, read against `blog/2026-10-21-muon-survival-guide-DRAFT.md` (draft owner: W).
Status: CAPTURED, mostly NOT yet actioned. Sorted by what each item needs. Kim's rule of thumb: if half a sentence is numbers
and shorthand the reader glosses over it; give the plain meaning first, move numbers to the section that owns them, say
where we used a textbook implementation, our own variant, what we KNOW and what we guess.

## A. Terms for the help pane (glossary entries; explanation must be plain, in OUR models' terms)
Newton-Schulz iterations; directions; "strong or weak gradient along a direction" (what that means for us); direction rank
(the Muon figure axis); hidden layer; embedding; input projection; layer; bias; normalisation gain; magnitude vector; scalar
(our sense, beyond "one number"); attention projection; fused matrix; QKV (needs an assembly-line animation); 3D tensors in
relation to these; fused modulation layer; AdaLN (readers confuse it with AdamW), emitter, hidden matrix, time-embedding
layers; m x n matrix; row normalisation step; LoRA A; sign step/sign descent; held-out loss; weight decay (how it affects
everything; link the dynamic-weight-decay paper; relation to gradient-noise level); weight norm; "scales the decay with the lr so
the norm settles" (decay of what?); Schedule-Free (link the original and SF+ papers); parameter groups ("a group that doubles"
-- which groups?); logging bin (set by whom, how, why); "path of the weights"; convergence in latent-diffusion fine-tuning
(loss barely moves while the model improves); momentum and what it costs (generalisation? role of dataset diversity/size);
gradient accumulation vs a true bigger batch (what can break); Adam vs AdamW (interchangeable?); EMA (own section: the
too-long-EMA mistake); rotation of LoRA A; NorMuon "cancels the shape-based radius exactly"; radial brake; Cautious masking.

## B. Visuals/animations asked for
QKV and fusing as a factory assembly line; our routing vs the proposed routing with gradients/updates moving (replaces the
AdaLN/emitter/time-embedding paragraph); the step-size figure with bf16, fp32, fp16 and fp8 noise floors on it (or a
pointer to section 10); LoRA A rotation graphic; whole-track fine-resolution spectra for the epoch-3 and epoch-12 clips plus a
difference spectrogram (2048 bins, 50% overlap, 2x oversampling); a link to our raw run database/findings for run labels.

## C. Text edits for the draft (W's file)
- Section 4: say what biases/gains mean in our heads; B2/B3 (keep a sentence: "enabled training at an lr where a shared one
  failed", drop numbers); explain "same sweep, prompt, seed, latent level stayed in range": the second drone clip sounds like
  smooth whooshes, not a healthy contrast -- state whether it is the first clip with std normalised.
- Section 5: why the loss does not show weight growth; "weight norm"; what a spike count of 5 means and why 5 is a lot;
  logging bin; median-vs-mean example needs a plain gloss; "one run that converged" -- how do we know (latent-diffusion loss
  hides progress); "we audited one optimizer" -- ours or found?
- Section 6: "in one comparison" -- which; what the ranking was on 5,401 vs 12,524 crops; "result pending" -- are runs lined
  up; losses keep falling on adapters that already ring (note it); batch-size/momentum costs; accumulation caveats.
- Section 7: Adam vs AdamW wording; Moonlight variant vs textbook vs ours (no such comparison found, see D); Zach's
  comment on late Muon adoption (SA3 pre-training probably AdamW) is in CLAUDE.md, not in the guide; LoRA A result: was the
  EMA too long? give a graphic; "rotation"; sign descent and the multiplicative magnitude update -- details, published?
- Section 8: add short estimates of why we did not see the papers' gains; Shampoo/Mousse vs textbook Muon comparison; Full
  Fusion stack vs our current runs; was KL-Shampoo broken/capped (10x lr)?; NorMuon sentence; why our variant steps 2-3.6x
  larger on wide matrices (did we find out?); rewrite B2/B3 and "two heads" rows in plain words (which two heads, which old
  run); radial brake: why no help, listening tests?, what "size" and why would it change; link every method to its paper; label
  textbook vs own implementation, known vs guessed.
- Section 9/10: only Kim listened (not "listeners"); epoch-12 clip has a glitch near 0:02 too; steered head glitches can depend
  on the sound (bright cymbal over-steered at the hf head), so listen carefully; fp32 "more muted" vs bf16 and cases where fp32
  was worse; Lion allows a full fine-tune of Stable Audio Medium Base on 16 GB (Kim's statement; verify before writing).
- Section 11: link our optimizer GitHub and give start-up options.
- New sections: DoRA vs full-FT results (did the post cover `/run/media/kim/Mantu/sa3_lora_runs/`, which also holds Lion
  comparisons?); EMA.

## D. Factual look-ups (what I found 2026-10-26)
- "Print the parameter groups at start-up": NOT in docs/TRAINING.md (grep empty). F30 (TRAINING.md:127) and test-plan:344 hold the
  routing-regex gaps (`attn.qkv` not split, `adaLN_mod`, time embedding). Add the advice to TRAINING.md or the sa3-training skill.
- Did we try splitting QKV against the recommendation? UNRESOLVED: `--fusion-split-qkv/--fusion-split-adaln` exist and
  EXPERIMENTS.md:121 asks whether they were on in the regsweep/surgical arms; no result found.
- Moonlight-variant vs textbook Muon vs ours: no registered arm found in TRAINING.md / the test plan / EXPERIMENTS.md. Gap.
- SA3 pre-training optimizer: CLAUDE.md records Zach: Muon on 2-D matrices, adopted late/brief, base overwhelmingly AdamW-shaped.
  The guide says "not stated in its report" (true of the report); add the unpublished developer remark, labelled as such.
- Hyperball results: EXPERIMENTS.md 1033-1038, 1193, 1263 (a hyperball retraction that pins zero-init adapters at zero); F2
  bounded-norm full-FT arms are "READY, waits on captions". Nothing found that is rendered and auditionable; Kim to confirm.
- AdaGC by ear: docs/training-findings.md 2026-09-28 (b0x arms sound close to Base). SNR gate at other noise floors: TRAINING F27
  only measures the floor (0.183); no calibrated-floor run found.

## E. Experiments and ideas to register
Cautious masking only late in training (less noisy gradients); LoRA-TSD on both LoRA and DoRA; MONA, KL-Shampoo and SOAP with
gradient accumulation / larger batches, with a theoretical benefit estimate from the noise numbers; SNR gate at calibrated floors;
bf16 vs fp32 Newton-Schulz: log what bf16 loses (fp32 first, then convert to cause exactly that loss, accounting for batch noise,
update noise, magnitudes); fp32-vs-bf16 listening comparison on DoRA/full-FT incl. runs where fp32 was worse; larger batch by
accumulation results (guide section 10); multi-resolution stacked-window loss to catch local glitches; log how well the data fits
inside the chosen latent resolution during runs; Moonlight/textbook/ours three-way arm; QKV-split arm.

## F. Engineering asks (ModularOptimizer, not the blog)
Warn when learning rates look out of proportion between groups; expect two learning rates and refuse a single uniform lr for
Muon without an explicit flag; print parameter groups at start-up.
