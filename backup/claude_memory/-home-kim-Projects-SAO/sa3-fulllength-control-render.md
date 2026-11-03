---
name: sa3-fulllength-control-render
description: "SUPERSEDED for the stereo claim (see sa3-fulllength-4096-render, 2026-08-26). State of the full-length (4096-frame) onset-density control render task — diagnosis done, windowed render fix pending GPU. Resume here."
metadata: 
  node_type: memory
  type: project
  originSessionId: 085d95f2-1875-4707-ac4d-9d05b552b676
---

Task (Kim, 2026-06-28): full-length **4096-frame / 380.4 s** onset-density-steered render from **ep15 = `riffer_step81000.pt`** of the most recent Fusion run `/run/media/kim/Mantu/sa3_control_runs/onset_FUSION_lr2e5_40epoch/`, **gain 2, density 7**, medium-base. (ep15 because 5400 steps/epoch × 15 = 81000. Confirmed scalar onset_density head: scalar_norm `[7.107, 1.419]`, n_tokens=min(args,16)=**16**, control_dim 768, **crop_frames 512**.)

> ⚠ **SUPERSEDED IN PART, 2026-08-26:** the "single-shot 4096 breaks stereo" claim below
> NO LONGER REPRODUCES on the current stack (torch 2.14 / ROCm 7.14, CK flash-attn):
> single-shot 378 s measured L/R corr +0.884..+0.944 with no dead channel. See
> [[sa3-fulllength-4096-render]]. The rest of this note (crop_frames, the clamp-save
> bug, the windowed tooling) still stands.

**Diagnosis (settled, with data):**
- medium-base **native length IS 380 s / 4096 frames** (config `sample_size=16777216`). My earlier "120 s" was wrong — that's only the `generate()` *default* `sample_size=5292032`.
- **Single-shot 4096 generation breaks stereo** (L/R corr ~0, one channel silent for minutes) — and it does so for the **pure base model too** (`pure_L4096.wav`: corr nan/+0.08), so it is **NOT the control adapter**. medium-base simply must be rendered **windowed** for long form. Evidence table: short ≤512-frame control clips corr **0.91–0.99**; pure *windowed* `SAO/Misc/longform_pure_6min.wav` corr **+0.82**; single-shot 4096 (control & pure) corr **~0**. (crop_frames=512 matters for control *quality* past ~48 s but is NOT the stereo cause.)

**Fix path = windowed render, tool already exists:** `stable-audio-tools/avp_sa3/sa3_control/steered_longform.py` — `DevelopmentRenderer` (30 s windows / 5 s overlap = ~322 frames, inside the 512 crop), `SteeredGenerator` applies the onset adapter per-window, continuation modes clamp/sdedit/crossfade, per-window density schedule. Constant density 7 via **`--shape linear_descending --lo 7 --hi 7`** (no "flat" shape; lo=hi → constant).

**BUG I found + patched (UNCOMMITTED working-tree edit):** `steered_longform.py:290` saved via `sf.write(args.out, wav.clamp(-1,1)...)` — raw clamp, not peak-norm → first windowed render came out **63% railed/clipped** (RMS 0.9, ~1 onset/s — garbage; all metrics on it are meaningless). Patched to `save_audio(args.out, wav, sr)` (peak-norm, per MASTER §5 / repo CLAUDE rule). **Decide whether to commit this fix.**

**PENDING — the corrected windowed render is NOT yet verified** (re-render OOM'd: GPU was grabbed by another job; Kim then scheduled a long run, so we paused). Resume command (run when GPU free):
```
PYTHONPATH=/home/kim/Projects/SAO/stable-audio-tools/avp_sa3 \
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_ALLOC_CONF=expandable_segments:True \
/home/kim/Projects/SAO/stable-audio-3/.venv/bin/python -m sa3_control.steered_longform \
  /run/media/kim/Mantu/sa3_control_runs/onset_FUSION_lr2e5_40epoch/riffer_step81000.pt \
  --shape linear_descending --lo 7 --hi 7 --gain 2 --duration 380.4 \
  --window-sec 30 --overlap-sec 5 --prompt "psychedelic goa trance, 145 bpm" \
  --steps 50 --cfg 7 --seed 1234 --continuation clamp \
  --out /home/kim/Projects/SAO/control_eval_queue/outbox/render_FUSION_ep15_g2_d7_windowed_v2.wav
```
Then measure **per-channel** onset (mono-sum cancels when corr is low) + L/R corr. Expected if good: corr ~0.8 (like pure windowed), density ~7. If stereo still mediocre un-clipped → try `--continuation crossfade` or `sdedit`, or `--ridge` (gain-per-density; ~1.9 at d=7). Always check GPU with `rocm-smi --showpids` first (contention has bitten us repeatedly — exactly why the CPU eval path exists).

**Artifacts** in `/home/kim/Projects/SAO/control_eval_queue/outbox/`: `render_FUSION_ep15_g2_d7_L4096.wav` (single-shot, good density ~6 but BROKEN stereo — already sent to Kim), `..._windowed.wav` (CLIPPED v1, disregard), `pure_L4096.wav` (proof base breaks single-shot). `render_ep15_full.py` / `pure_render.py` live in the session scratchpad.

Related: this session's CPU eval server + shared core are committed (sa3 `2fa9e07`, tools `5c0f844`, SAO `61fc1fc`) — see [[sa3-onnx-amd-inference]]. SA3 venv = `/home/kim/Projects/SAO/stable-audio-3/.venv/bin/python` (3.13). Save audio ONLY via `sa3_control.audio_io.save_audio` (never raw torchaudio/sf clamp).

**Why:** multi-turn debugging that's easy to lose across a context break; the diagnosis (single-shot-long breaks stereo; windowed is the path; the clamp bug) and the exact resume command must survive.
**How to apply:** in the morning, run the command above once the GPU is free, verify stereo+density, then report to Kim and ask about committing the `steered_longform.py` save-clamp fix.
