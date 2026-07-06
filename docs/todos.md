# TODOs — open work across the pipeline

Keep this honest and current. Move done items to `WORKLOG.md`. Newest concerns near top.

## Now / next

- [ ] **Rank-16 Fusion comparison rerun with the improved dataset stack** (Kim 2026-07-07,
      from the dora_results audition): same recipe as `sa3-goa-dora-47s-b4-cont/x20b3ygb`
      (the Hall-of-Fame run) but with everything we've built since: tiered captions
      (T1 era-fronted / T2 Granite / T3 raw via `--caption-sidecar`), curated tag vocab,
      `--track_type_prob 0.5`, multi-source weighting. Direct A/B against the HoF ckpt.
- [ ] **Big-rank damping experiment** (Kim's rank-128 "pawn my head" hypothesis: r64 ≤ r16,
      r128 degrades in-dataset goa into diffuse/impact-less while out-of-dataset prompts
      survive): try (a) LR scaled by rank — rsLoRA-style `alpha ∝ sqrt(rank)` or lr×~0.35
      for r128-vs-r16, (b) grad accumulation, (c) EMA over adapter weights (our proven
      drift fix from the LatCH ES work). Context: `docs/checkpoint-hall-of-fame.md`.
- [ ] **Novelty-gated update weighting** (Kim's idea, same audition): down-weight updates
      for material the model already renders well, let "remote areas grow" — cheapest
      testable form is per-crop focal-style loss reweighting by an EMA of that crop's own
      RF loss (low loss = familiar = down-weight). Folded into
      `docs/research-brief-relevance-routed-dora.md` (UPDATE 2026-07-07) as the data-axis
      sibling of the two existing axes.
- [x] **Export the *control-adapted* DiT to ONNX** — DONE (2026-06-27). Adapters
      (`to_k`/`to_v`/`to_out` + conditioner) fold into the DiT graph as forward inputs:
      `onnx/export_dit_control_onnx.py` + `onnx/dit_control_onnx_infer.py`,
      fp16 fixed (PE moved host-side, 3.1 GB), GPU MIGraphX cos=1.0/100%-on-EP. The all-CPU
      eval path is now canonical: `sa3_control_onnx.py` (shared gen-core) +
      `control_eval_server.py` + `submit_control_job.py` (file-drop queue
      `SAO/control_eval_queue`) — 8-step grid ≈5.4 min CPU vs ~42 min GPU-with-compile, so
      CPU is the default eval path, not a fallback. (MASTER §5; move to WORKLOG.)
- [ ] **SA3 LoRA retrain** on the new `latents_sa3` (5400 T=4096 beat-aligned crops). Caches
      warm. rank 16 dora-rows bf16 `--compile`, `MIOPEN_FIND_MODE=2`. Decide step budget +
      `--demo_every ≥1500`. Watch that step time drops to ~2-3 s now T is fixed.
- [ ] **Validate the CK flash-attn build** (`sa3-rocm7.13-test`, scripts 02-05): numerical
      correctness + benchmark vs Triton-AMD backend. BUILT but unproven; on the experimental
      7.14 stack. If it's correct AND faster, plan a path to the production stack.
- [ ] **`relative_position_ts` LatCH head** — train a head on the new structural-position
      ramp; test as an inference knob (0=intro, 0.5=mid, 1=outro). Novel control.

## LatCH

- [ ] Promote the whole-track **per-stem heads** (onset_envelope_drums etc.) to full-data
      production runs — smoke-validated, not shipped. `rms_other`/`onset_envelope_other`
      looked strongest; vocals weakest (sparse in Goa).
- [ ] Re-test LatCH LR knee at **lr 3e-3** (1e-3 won at every batch in the 10ep/50% sweep —
      the knee may not have been reached).
- [ ] SA3 LatCH **Phase 2**: ping-pong guidance for post-trained small/medium, SAME-L/medium
      heads, σ-relative-window transfer. (SA3 memory `latch-sa3-phase1.md`.)

## SA3 training (beyond LoRA)

- [ ] Decide if short-form (<T=1024) inference quality from the T=4096-only LoRA is adequate;
      if not, a **multi-length** Phase-2 LoRA with quantised T buckets (`training-findings.md`).
- [ ] Per-epoch **prompt re-randomisation** — current SA3 crop prompts bake one §3.5 sample
      into the `.json` at encode time; for training variety, regenerate at dataloader time.
- [ ] Recover the **579 dropped sources** (<380 s or no downbeats) if short-form matters —
      currently excluded from `latents_sa3`.

## Infra / docs

- [ ] Confirm CLAUDE.md **`@import`** of an absolute cross-tree path actually inlines in a
      fresh session (fallback instruction is in place regardless).
- [ ] mir + SAT + SA3 have **uncommitted working-tree changes** from this session's scripts
      (timeseries, encoders, train_latch/train_lora flags). Decide what to commit where.
- [ ] Push branches that are local-only (`mir/whole-track-timeseries`, etc.) if you want
      off-machine backup.
