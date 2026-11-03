---
name: longform-render-sa3
description: "SA3 offline long-form render (sliding-window inpaint-continuation + crossfade) — implemented, CPU-tested, GPU validation pending"
metadata: 
  node_type: memory
  type: project
  originSessionId: b1ee18e7-1ef0-45fd-90ba-5aadcdcad6ec
---

Offline long-form SA3 generation (render audio longer than the native window to one `.wav`),
on branch `latch-sa3-phase1` (commits `5f6f808..796a76d`, pushed to remote **`fork`** =
Taikakim/stable-audio-3; **`origin` is the Stability-AI upstream — never push there**). The
productionised successor to the FIFO prototype ([[infinite-audio-fifo-sa3]]).

**Approach:** sliding-window — each window is generated fresh and **latent-clamped (SA3
inpaint) to the previous window's tail**, then slerp-crossfaded. Drift-free *by construction*
(every sample in-distribution), unlike pure FIFO which collapses ~18 s in. Prompt can be a
single string or a `t:prompt|t:prompt` schedule.

**Files:** `stable_audio_3/inference/longform.py` (PromptSchedule, slerp + CrossfadeStitcher,
DriftMonitor, `ChunkGenerator` seam + InpaintContinuationGenerator + SDEditReanchor,
LongFormRenderer), `scripts/longform_render.py` (CLI), `tests/test_longform.py`. Docs:
`docs/workflows/longform.md`; spec/plan under `docs/superpowers/`.

**Swap seam:** the renderer depends only on `ChunkGenerator` → Approach C (`BoundedFifoGenerator`,
the FIFO surgery) drops in later with no renderer change. `SDEditReanchor` (latent
audio2audio) is built but reserved for opt-in transition morph / C drift-refresh; default is
slerp-only.

**Status: GPU-VALIDATED (2026-06-20).** CPU 18/18 green, ruff clean; both GPU-gated generation
tests PASS (`InpaintContinuationGenerator`, `SDEditReanchor`); a 2-min CLI render held the
`drift_log` RMS **flat [1.03, 0.95, 0.75, 0.83, 1.04]** — no collapse (the FIFO prototype
cratered to ~0.03 at ~18 s). **Finding: SA3 inpaint SOFT-conditions the prefix, not hard-clamp**
(clamp-region mean-abs err ~0.064), so the `continuation_join` slerp blend is load-bearing.
Feature is done + validated → ready for a clean PR of the long-form work off `latch-sa3-phase1`.
SDD recovery ledger: `stable-audio-3/.git/sdd/progress.md`.

Built via superpowers subagent-driven-development; the per-task + final whole-feature reviews
caught real bugs (slerp endpoint imprecision, n==0 transition crash, parse_schedule colon
crash, missing [-1,1] clamp, single-shot-decode OOM, transition clamping to the OLD prompt).
