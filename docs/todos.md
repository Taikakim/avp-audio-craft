# TODOs — open work across the pipeline

Keep this honest and current. Move done items to `WORKLOG.md`. Newest concerns near top.

## Now / next

- [ ] **Export the *control-adapted* DiT to ONNX** (not just the base DiT, which is done —
      GPU-verified ~7.8× RTF, `stable-audio-3/scripts/export_dit_onnx.py`). Our control
      eval/inference needs the adapters (`to_k`/`to_v`/`to_out` + conditioner) fused into the
      graph; the current export is base-only, so it can't run control heads. Doing it brings the
      ~7.8× DiT speedup to *control* inference — big for deployment + large eval sweeps. Builds
      directly on the base export. (2026-06-24)
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
