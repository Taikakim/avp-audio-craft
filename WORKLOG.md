# WORKLOG — cross-project audio pipeline

Reverse-chronological. Append an entry (newest at top) when you finish or learn
something an agent in another repo would want to know. Keep entries short; move
durable facts into `MASTER.md`. Conventions:

```
## YYYY-MM-DD — <who/model> — <one-line title>
- bullet of what ran / landed / broke
- paths, commands, results worth reusing
```

## 2026-06-23 — Opus 4.8 — Onset LatCH head STEERS generation (corr 0.986) — working rhythm control, no MERT

- **Capstone of the rhythm thread.** Trained an **onset LatCH head** (`scripts/latch/train_latch.py --feature
  onset_envelope`, production arch: adaln_zero/depth4/4.9M, standardized, smooth_l1; 12 ep, loss 0.29→0.17,
  ~20 min) on `latents_sa3`, then steered `medium-base` via the production `model.generate(latch_configs=...)`.
  **The existing LatCH head arch is ALREADY temporal** (RoPE self-attn over the sequence) → no new arch needed,
  just train on a rhythm feature. (This is why §6's CNN matched MERT — the head family was always temporal; the
  per-frame *linear* probe was the artifact.)
- **Steering verified, closed loop:** requested onset 0.4→2.3 → measured output onset-strength rises
  **monotonically, corr 0.986** (gain 48). A/B render (same seed/prompt): baseline 0.771; gain 48 low 0.731/high
  0.834 (spread 0.10); **gain 96 low 0.702/high 0.907 (spread 0.21 ≈ 2× — authority scales with gain)**, pushing
  both sides of baseline. Audible A/B + the trained head + verifier persisted at `cu_reward_renders/analysis/`.
- **Net:** a temporal LatCH head on the SAME-L latent is a **working, gain-scalable rhythm control — no MERT, no
  MERT-conditioner, no base finetune** — the §6 prediction realised. Doc §7, `avp/main` a8984cf.
- **Next / reusable:** beat + downbeat heads same recipe; compose with chroma/RMS (multi-head endgame). The §3
  per-frame steerability map is a **linear lower bound** → re-probe *temporally* before calling any feature
  "hard." Ops: `verify_latch.py` is rms-only; the onset verifier in `analysis/` is the template for new features.

## 2026-06-23 — Kim + Opus 4.8 — SA3 DiT → ONNX on AMD: full text→audio reproduces torch (GPU-verified)

Extended the SAME ONNX/AMD work (decoder/encoder, prior entries) to the **DiT** — the full
text→audio path now runs on ORT+MIGraphX. Tooling in `stable-audio-3/scripts/`: `export_dit_onnx.py`,
`dit_onnx_infer.py` (host rectified-flow sampler), `precache_dit_cond.py`. Doc:
`stable-audio-3/docs/onnx-amd-inference.md`. Commits `e310a4b..7f6c220` (branch `latch-sa3-phase1`).
- **Export = `DiffusionTransformer._forward` (CFG-free core), DiT-only load** from the cached
  safetensors (no T5-Gemma needed; text is precached). Same recipe as the AE (flash-off + opset 18);
  the DiT was *structurally friendlier* (no chunk-folding, global self-attn → plain SDPA). CFG + Euler
  sampler on the host; CFG collapses to velocity space `v=v_unc+cfg·(v_cond−v_unc)`.
- **CRITICAL FIX (now MASTER §5):** medium-base DiT needs a **257-ch `local_add_cond`** (inpaint_mask +
  masked_input). For text-to-audio it's zeros, but the DiT **projects it with a bias** → `None ≠ zeros`
  (cos 0.98). First export wrongly omitted it (false cos=1.0 None-vs-None). Fixed → input fed zeros.
- **Validated:** corrected DiT export vs torch cos=1.0; **MIGraphX vs CPU cos=1.000000, 100% on-EP,
  191ms/call** (~13min compile); **full 8-step real-prompt gen ONNX z0 vs torch z0 cos=0.999944**; real
  structured audio. **DiT-only RTF ≈7.8×.** Ladder exported L∈{256,512,1024,2048,4096}.
- **Gotchas (MASTER §5):** t5gemma `b-b-ul2` (gated) — HF **Xet stalls**, fetch via `HF_HUB_DISABLE_XET=1`
  / `curl -C-`. **Don't co-resident fp32 DiT (~5.8GB)+decoder on 16GB** → VRAM saturates, decoder compile
  thrashes (31min vs 9min).
- **Follow-up (same session): batch=2 + fp16 export, bench + gen-server, + a VRAM correction.**
  `export_dit_onnx.py --batch 2` (one DiT call/step CFG, cos 1.0) + `--fp16`. `bench_dit_onnx.py`
  (ONNX-vs-torch gen benchmark, fairness-reviewed) + `latent_server_dit_onnx.py` (low-VRAM gen server).
  **CORRECTION to the VRAM fix:** `migraphx_fp16_enable` (runtime fp16 EP) does NOT help co-residency —
  it loads the fp32 weights then quantizes at init, so DiT+decoder **OOMs harder** (HIP OOM, measured).
  The real fix is **fp16-EXPORTED onnx files** (DiT 2.9GB + decoder 0.9GB load directly) or separate
  processes. fp16 DiT export needs `convert_float_to_float16_model_path` + external-data save (>2GB).
- **BENCHMARK (2026-06-24, GPU free) — the ONNX/MIGraphX port is a VRAM/deployment win, NOT speed.**
  L256/8-step DiT loop (decode excluded — unfair across venvs): **torch eager cuda-fp16 0.707s (44ms/call,
  RTF 33.6×)** vs **ONNX-fp16 MIGraphX 2.314s (144ms/call, RTF 10.3×)** → **eager torch ~3.3× faster**
  (MIGraphX's compiled graph doesn't beat torch's tuned rocBLAS/MIOpen here; torch+CK-FA would widen it).
  Quality identical (z0 cos 0.9993). ONNX's value = **3.8GB resident, zero torch/ROCm-torch dependency**
  (coexists with training, portable single graph) — the original low-VRAM motivation. fp16 ~25% faster
  than fp32 MIGraphX. **Use ONNX for low-VRAM coexistence; torch for raw speed.** Server CPU-smoke passed
  (boot→/generate→valid 23.8s WAV). Tools: `bench_dit_onnx.py` (added `dit_loop_s`), `latent_server_dit_onnx.py`.

## 2026-06-23 — Opus 4.8 — Curated-reference reward viable; SAME-L steerability map measured (rhythm is the weak axis)

- **Curated reference set = a genre-neutral reward** (the way past Audiobox's genre bias). 48 aavepyora tracks
  (`/run/media/kim/Lehto/aavepyora_flac/`) MERT-embedded vs contrasts: **AUC 0.999 vs default SA3 output**
  (1-NN purity 0.97 — strong steering gradient), **~0.87 within-genre vs goa at MERT layers 5–6** (timbre/
  production; layer 23/semantic only 0.77 — can't tell two goa apart). Use **layers 5–6, mean-centred**
  (MERT space is anisotropic, raw cosines ~0.95); **48 tracks suffice — the limit is the metric, not data**.
  Caveats: goa contrast is SAME-L-reconstructed → 0.87 is an upper bound; embed references **through a SAME-L
  round-trip** to make the reward codec-fair (generations are decoded too).
- **SAME-L steerability map** (200-crop per-frame ridge `latent→feature`, split by track; CPU): negative
  control `relative_position`=**0.044** (probe is honest). **Easy:** spectral flux 0.88, flatness 0.80.
  **Medium:** bass-energy 0.50, **chroma 0.42** (matches chroma-steer needing ~15× gain), air-energy 0.35.
  **Hard:** onset 0.31, beat 0.30, **downbeat 0.16**, mid/body energy ~0.11. **Rhythm is the weakest family
  → this EXPLAINS the riffer's rhythm-transfer failure (MERIT≈0): the bare latent doesn't linearly carry
  downbeat.** (Per-stem features dropped — absent in some crops; stemmed-only re-run pending.)
- **Multi-band MERT-conditioner design** (the next-control idea): ~3–5 MERT-layer *bands*, each a GLIGEN-gated
  decoupled cross-attn adapter (gate→0 = off; strength slider = on/off UX), pooled-global, self-supervised on
  `latents_sa3` — a multi-band extension of the riffer. Gated by SAME-L (only surfaces tangled-but-present
  features, not discarded), and "explicit beats opaque" (complement the scalar heads).
- **MERT-vs-SAME-L probe RUN (same day, GPU): MERT exposes rhythm the bare latent hides.** 80 goa windows
  decoded→MERT, per-frame probe vs the SAME-L latent: **beat 0.36→0.83, onset 0.33→0.71, downbeat 0.17→0.39**
  (all at **MERT layers ~1–6**); spectral-flux tie (~0.85), chroma SAME-L wins (0.42 vs 0.37); neg-control <0.1.
  → the precondition holds **for rhythm only** → the multi-band conditioner collapses to a **single rhythm band
  (MERT L1–6)**, and this is the concrete fix for the riffer's rhythm failure. Rhythm is *present-but-nonlinear*
  in the latent, so the cheaper **alternative is a nonlinear MLP rhythm head on the SAME-L latent** (target-driven)
  vs the MERT band (reference-driven) — likely both. Doc §5 updated, `avp/main` 6f0aa36.
- **CORRECTION (same day): a temporal latent head matches MERT — you DON'T need MERT for rhythm.** Built §5's
  head as a **1D-CNN** (~4s context): **beat 0.86, onset 0.81, downbeat 0.58** vs MERT's linear-probe
  0.83/0.71/0.39. Per-frame MLP barely helped (downbeat 0.03 — failed); only temporal context recovers rhythm.
  → the §3/§5 ceiling was **missing temporal context, not absence**: the latent never hid rhythm, the per-frame
  LINEAR probe couldn't see it; MERT "won" only because it's temporal and the probe wasn't. **Verdict: rhythm
  control = a temporal (1D-CNN) LatCH head (no MERT, no finetune); MERT's niche narrows to the reference-STYLE
  reward.** General lesson: **LatCH heads for temporally-structured features must be temporal, not per-frame**;
  the per-frame steerability map (§3) is a linear lower bound. Doc §6, `avp/main` 09e18a6.
- **Docs:** finding written to AVP `docs/book/findings/2026-06-23-curated-reference-rewards-and-the-same-l-steerability-map.md`
  (+ findings README + advances Sourcebook §Ch13/§Ch8), pushed `avp/main` c1e4f46. Recipe `fk-steering-cu`
  already updated 2026-06-22. Ops: MERT-v1-330M loads on the ROCm sa3 .venv (`trust_remote_code`, ~163 s).

## 2026-06-22 — Opus 4.8 — Audiobox-aesthetics as an SA3 reward: confirmed on medium-base (240 samples)

- **Question:** is Audiobox CU (Content Usefulness) a good steering reward for SA3 (toward the FK-steering
  recipe `avp_sa3/recipes/inference_recipes.yaml` `fk-steering-cu`)? Ran best-of-N (rung 1 of the ladder)
  on **medium-base, 240 samples / 10 genres**, scored all 4 axes (mir `audiobox_aesthetics.py`).
- **CU ≈ PQ (robust):** within-prompt CU↔PQ **+0.87** across every genre (+0.66..+0.95). "Usefulness" is
  essentially a **production-quality** signal, not a distinct reusability axis.
- **No quality/complexity tradeoff:** PQ↔PC **+0.25** (genre-dependent −0.36..+0.71). The **−0.26 seen on
  n=8 small-base did NOT replicate** — it was small-sample noise. Higher complexity doesn't cost quality.
- **The orthogonal lever is complexity/enjoyment:** CE↔PC **+0.62** (busier = more enjoyable, within genre);
  **PC reads arrangement density** (ambient/piano ~2.5 vs lo-fi/house ~5.6). All 4 axes +corr within-prompt
  → a weighted **hybrid won't fight itself**. CE has the widest meaningful headroom — best single "good music" reward.
- **Reward choice is NOT moot despite correlation:** BoN argmax differs (CU-winner ≠ PQ 8/10 prompts, ≠ PC
  10/10) — the top sample under each reward differs even when axes correlate.
- **Ops facts (reusable):** medium-base loads 12.7 s (flash_attn 2.8.4), **~9.7 GB VRAM loaded** → can't
  coexist with Audiobox (~8 GB) → score sequentially. **TunableOp cache does NOT persist across processes**
  (`apply_profile`-after-import warning is real): first gen of a (batch,dur) shape tunes ~7 min, then
  **2.24 s/sample** steady-state — so do a whole run in ONE process. 240 samples in 16.2 m.
- **Next:** FK particle loop still unbuilt; if pursued, target CE or a PC-with-PQ-floor hybrid, not CU. Recipe
  updated to BoN-tested (`avp/main` 0d7cfdd).

## 2026-06-22 — Opus 4.8 — Branch consolidation + AudEdit findings doc; Gradio_Lab parked (pre-SA3)

- **Repo roles clarified** (now durable in `MASTER.md` §1 "Separation of concerns"): mir = features +
  the latent-explorer-becoming-a-tool; AVP = model-agnostic *what* of control; SA3 = thin fork = the
  *how* to interface with the SA3 model, changed only for components upstream lacks.
- **Consolidated to main + pruned branches** (relief for branch sprawl): mir `main` ← merged
  `sa3-latent-explorer` (incl. whole-track-timeseries) + `same-chroma` (SAME chroma extractor +
  `gen_same_chroma_ts.py`), pushed `Taikakim/mir-feature-extraction`. Deleted **8 local + 6 remote**
  stale branches (all proven merged). `.gitignore` now excludes wheels/`data/`/`renders/`/`*.pt` sweeps
  across mir + AVP. SA3 left as-is (its `latch-sa3-phase1` is 54-ahead/28-behind fork-main → needs a
  careful reconcile, not a sweep).
- **AudEdit (2606.15149) finding landed** in AVP `docs/book/findings/2026-06-22-audedit-into-our-control-stack.md`
  (+ Sourcebook cross-link), pushed `avp/main`. Verdict: complement-not-substitute; `sa3_flowsep.py` is
  already a near-faithful Algorithm 1; highest-leverage next is a cheap **entanglement probe**, not the
  data-engine. Codec caveat: paper SAME=32-ch vs our SAME-L=256-ch.
- **`avp/Gradio_Lab` NOT merged — parked.** It's **pre-SA3** work (Kim's Stability-AI gradio UI tweaks:
  model loading, dual-model **bracketing**, presets). 4 months stale; AVP's `interfaces/diffusion_cond.py`
  has since diverged (LatCH/sigma), so it's a genuine **manual reconciliation** (overlapping CFG-slider
  edits; unify `generate_cond`'s `*sampler_selections` varargs vs `latch_*` kwargs + the flat Gradio
  inputs list) that **needs a GUI launch-test** → blocked by the busy GPU. `gradio.py` itself merges
  clean (main never touched it). Do it as a focused launch-testable session later; drop `claude.log`,
  keep main's `CLAUDE.md`/`README.md`/`train.py`.

## 2026-06-21 — Opus 4.8 — Long-form SA3 generation MERGED — GPU-validated, drift-free

- **MERGED to `Taikakim/stable-audio-3` main** (PR #1, merge commit `378b0a6`; 17 commits preserved:
  spec → plan → TDD tasks → review fixes → doc). Sliding-window **inpaint-continuation + crossfade** —
  render longer than SA3's native window, drift-free by construction (every window a fresh in-distribution
  generation latent-clamped to the previous tail).
- **GPU-validated** (`small-music-base`): 18/18 CPU tests + 2 GPU generation tests pass; 2-min render
  `drift_log` RMS **flat [1.03, 0.95, 0.75, 0.83, 1.04]** — no collapse. The earlier **FIFO/diagonal-denoising
  prototype** (`fifo_infinite.py`) cratered to **~0.03 at ~18 s** → sliding-window beats per-frame FIFO on the
  untrained model.
- **Finding:** SA3 inpaint **SOFT-conditions** the prefix (clamp-region mean-abs err **~0.064**), NOT a hard
  clamp → the `continuation_join` slerp seam blend is load-bearing.
- Self-contained (no `fifo_infinite` dependency). Files: `stable_audio_3/inference/longform.py`,
  `scripts/longform_render.py`, `tests/test_longform.py`, `docs/workflows/longform.md`. FIFO kept as the
  future **Approach-C** engine behind the swappable `ChunkGenerator` seam. Built via superpowers
  subagent-driven-development (TDD + per-task + whole-feature review). CLI: `uv run python
  scripts/longform_render.py --prompt "..." --duration 120 --window-sec 30 --overlap-sec 5 -o out.wav`.

## 2026-06-20 — Opus 4.8 — Attribute branch VALIDATED: onset-density head steers output (corr +0.90); riffer = variation-not-transfer

- **THE pivot result:** an explicit **onset-density** scalar head steers SA3 output onset density at
  **corr +0.90** (gain 1): requested sparse→dense → measured 4.3→8.3 onsets/sec; gain 0 flat 7.2
  (control off); gain 2/4 overdrive into incoherence. **Explicit conditioning works where the opaque
  riffer reference failed (MERIT ≈ 0)** → riffer's failure was the opaque signal, not the plumbing.
  Code: `avp_sa3/sa3_control/` — `ScalarAttributeEncoder` (FiLM tokens), `--control-mode scalar`,
  dataset per-crop `.json` scalar, `onset_eval.py` (re-extract density via librosa). Heads at
  `Lehto/sa3_control_runs/onset_density_400trk_crop1024/`. Smoke gotcha: `--smoke` forces fp32 →
  OOMs 16 GB; real runs are bf16. Next: time-varying onset_envelope_ts curve, then **compose heads**
  (riffer + onset, independent gains) — the endgame.
- **Riffer reframed (not dead):** comprehensive MERIT (480 clips, all models, gains 0.1→8) = the
  opaque riffer does NOT transfer mel/rhy/tim; high gain → distortion. BUT it's a real
  **reference-conditioned variation** instrument (kick-in threshold ~gain 0.6; narrow real *timbre*
  transfer only at the most-trained ckpt). Retrained full-effect at 400trk/lr1e-4 (12 ckpts) to test
  if more-data/lower-LR smooths the effect.

## 2026-06-20 — Opus 4.8 — Riffer LR/optimizer bracket + MERIT eval wired; 3 ref repos mined

- **Optimizer bracket** (200 tracks, `avp_sa3`): AdamW (2e-4/4e-4/6e-4+warmup, crop2048) vs
  **FusionOpt** (`Taikakim/fusion-optimiser`) SF-NorMuon / SF-AdamW / 5e-5, crop1024 (FusionOpt
  **OOMs at crop2048 no-ckpt** → crop1024 fix). **Fusion tax confirmed, matched-crop:** SF-AdamW
  1.46 it/s > SF-NorMuon 1.31 (NS5/NorMuon overhead) — both faster than AdamW@2048 only via crop.
  `train.py` gained `--optimizer adamw|fusion|sfadamw|fusion_full`, `--warmup-steps`,
  `--timestep-sampler` (log_snr, underfit borrow), `--resume` (warm-start). Collapse map → pick best
  by **cross-ref-diff**, then a **full-data crop-512 run** sized to finish by morning.
- **MERIT eval wired** (`sa3_control/merit_eval.py` + bracket `MERIT_EVAL=1`): MERT-330M + 3 heads →
  **S_mel/S_rhy/S_tim** disentangled similarity → per-checkpoint `merit_margin` (transfer−leak per
  factor; >0 = riffer transfers *that* factor). **Fixes the metric crisis** (chroma blind to collapse,
  cross-ref-diff blunt, loss noise-dominated). Runs CPU; validated. Heads in `Projects/MERIT/models`.
- **3 reference repos cloned to `Projects/` + mined** (all SA3-relevant): **underfit** (dada-bots LoRA
  dashboard → DoRA, short-crop/47s, log_snr sampler, the "elbow=creatively-underfit" recipe);
  **audioscope** (mech-interp activation steering → free mood vectors from our essentia labels + the
  per-layer probe = attribute-branch *injection-layer* diagnostic; `@torch.compile` monkey-patch gotcha);
  **MERIT** (the eval above). Folded into `avp_sa3/sa3_control/ATTRIBUTE_BRANCHES.md` (next-milestone design).



Exported the SAME-L autoencoder to ONNX for low-VRAM AMD inference via ORT + MIGraphX (a
decode path that runs without the torch stack / alongside a training job). Tooling in
`stable-audio-3/scripts/`: `export_same_onnx.py` (export+validate) + `decode_onnx.py` (host
chunk-loop runner). Doc: `stable-audio-3/docs/onnx-amd-inference.md`. Commit `3e5a9eb` (branch
`latch-sa3-phase1`). CPU validation (ORT vs torch): **decoder L128 cos=0.99998, encoder L128
cos=0.999996** (mean|Δ| ~5e-4 / ~9e-3; the encoder's larger abs Δ is just latents' wider range
— judge by cos/relative, not an audio-calibrated threshold).
- **Key: don't export varlen.** SAME folds the sequence length-dependently; export the
  *fixed chunk* (`decode` on `[1,256,L]`) and loop+overlap-add on the host (port of
  `AudioAutoencoder.decode_audio(chunked=True)` — `decode_onnx.py` does this).
- **Two gotchas (now in MASTER §5):** flash-off alone routes to **FlexAttention** (unexportable
  HOP, dies on `bitwise_and`) → also set `transformer.flex_attention_available=False;
  flex_attention_compiled=None` for math-equivalent masked-SDPA; and **opset ≥ 18** (17 emits an
  invalid `Split(num_outputs)`). `onnxscript`/`onnxruntime` install is additive (no torch/numpy bump).
- **GPU-VERIFIED (2026-06-20, RX 9070 XT, mir venv `onnxruntime_migraphx` 1.23.2):** the SAME
  decoder runs **100% on the MIGraphX EP, zero CPU fallback** (`--report-placement`), numerically
  identical to torch (**cos=0.999998**, max|Δ|=2.8e-4), at **RTF ~39×** post-compile. → **ONNX
  inference on AMD is verified.** The SA3 venv's own `onnxruntime` (1.27) is CPU-only — run the
  GPU EP from the mir venv or `uv pip install onnxruntime-rocm`.
- **THE catch: ~9-min MIGraphX AOT compile per session** (CPU-bound — NOT exhaustive-tune [tried
  off] nor chunk size [same at L32 vs L128]; the masked-SDPA fallback expands into many attention
  ops MIGraphX chews on). **ORT compiled-model caching is NOT exposed in this `onnxruntime_migraphx`
  1.23.2 build** (`migraphx_save/load_compiled_model` + `_model_name`/`_model_path` all rejected →
  silent CPU fallback; `decode_onnx.py` now detects that & retries on the bare GPU EP). Real
  mitigation: **a long-lived server compiles once at boot** (the latent_server pattern) → per-request
  cost is nil; or a newer ORT-ROCm build with cache options.
- **Seam test PASSES** (overlap=16, 512-latent/4-chunk): torch chunked≈unchunked (cos=1.000004) →
  overlap≥receptive field; ONNX-chunked vs torch-UNCHUNKED **cos=0.999997**, per-boundary local
  max|Δ| (1.5–3.5e-4) = same order as elsewhere → **no seam**. Stitch is EP-independent (run on CPU,
  no GPU contention with the riffer bracket) so it also covers MIGraphX (per-chunk cos=0.999998).
  → **full ONNX-on-AMD decode path verified end-to-end.**
- **Wired into the explorer:** `mir/scripts/latent_server_onnx.py` (mir branch `sa3-latent-explorer`,
  commit c854edc) — low-VRAM ONNX decode player (~2 GB GPU, MIGraphX, runs alongside training),
  endpoint-compatible with the torch `latent_server_sa3.py` (/status /crops /meta /decode /mix
  /source; /steer→501, stays on the torch player). Compiles the ONNX once at boot. Viewer targets
  it via `SA3_PLAYER_PORT=7893` (`player_client` now env-configurable). CPU-smoke-tested
  (decode/mix/status serve); GPU path is the same session with `--provider migraphx`.
- Context: cgisky `stable-audio-3-rs` (cloned to `Projects/stable-audio-3-rs`) proves SAME ONNX/MNN
  export works (CUDA/Windows); our path is ONNX + ORT-MIGraphX on AMD instead.

## 2026-06-19 — Opus 4.8 — SA3 riffer validated; pivoting to attribute-branch control
- **`avp_sa3/sa3_control/` riffer** (decoupled cross-attn adapter on SA3 medium-base) works,
  but only **reference-specific at lr1e-4** (peaks step~6000, then "elbow"-declines); **heavier
  LR mode-collapses** (lr1e-3 collapsed by step6000). Metric lesson: **chroma corr can't see
  collapse — use cross-reference AUDIO diff**; RF loss is a non-metric (flat for both). Gain knob
  ~1–2 clean, >4 artifacts (SA3-medium needs gain>1, the LatCH lesson).
- **Save audio via `soundfile` PCM_16**, never `torchaudio.save` — torchcodec is absent on the
  7.14 venv (ImportError) and clips fp16 where present. (`sa3_control.audio_io.save_audio`; MASTER §5.)
- Running overnight: 200-track LR×optimizer bracket (AdamW / FusionOpt SF-NorMuon / SF-AdamW;
  FusionOpt OOMs at crop2048 no-checkpoint → run at crop1024). Borrowed `--timestep-sampler`
  (log_snr) + the short-crop lever from **dada-bots/underfit** (cloned to `Projects/underfit`).
- **NEXT MILESTONE (decided): attribute branches** = explicit time-varying MIR-feature control of
  SA3 — the actual differentiator (leverages the mir pipeline; nobody else can). Design:
  `avp_sa3/sa3_control/ATTRIBUTE_BRANCHES.md`. Eval is *measurable* (decode→re-extract→correlate).
  Align with `mir/plots/explorer_sa3/` (same data; its LatCH `/steer` = the training-free twin).

---

## 2026-06-19 — Kim + Opus 4.8 — SA3 latent explorer (viewer + decode/mix/steer player), GPU-validated

Built an SA3-only latent viewer + player on **mir branch `sa3-latent-explorer`** (the old 64-d
Small explorer/player stay on other branches as a reference, untouched). Purpose: review SAME-L
encoder quality on `latents_sa3` + latent-space DJ mixing + LatCH-head auditioning.
- **Two processes:** Dash viewer `mir/plots/explorer_sa3/` (mir venv, port 8051, reads
  `.json`/`.TIMESERIES.npz` sidecars directly — sidecars are the only feature source) ⇄ HTTP ⇄
  player `mir/scripts/latent_server_sa3.py` (SA3 venv, port 7892, owns SAME-L VAE + LatCH heads).
  Config `mir/latent_player_sa3.ini`. Spec/plan in `mir/docs/superpowers/{specs,plans}/2026-06-19-*`.
- **GPU-validated** on the RX 9070 XT: `/decode` (380.4 s chunked reconstruction), `/mix`
  (slerp latent interp of two crops → decode), `/meta`, `/status`. `/source` (original-audio A/B
  slice) works only with **Mantu mounted** (source_path lives there) — correct 500 otherwise.
- **`/steer` fix worth reusing:** the hardcoded `LatCH(dim=256,depth=6,num_heads=8)` couldn't load
  the production same-l heads (`latch_weights_sa3_medium`, depth 4 / adaln_zero / standardized).
  Now loads via `stable_audio_3.models.latch.load_latch_from_checkpoint` (auto-detects arch);
  default `latch_weights_dir` → `latch_weights_sa3_medium` (the dir with `_best.pt`). 14 heads
  list; steering changes the audio (gain ≈48–96, MASTER §5). See MASTER §5 head-family gotcha.
- Built via subagent-driven TDD: 9 tasks, per-task + whole-branch review, 24/24 non-GPU tests.

## 2026-06-19 — Kim + Opus 4.8 — SA3 long-form render (sliding-window + crossfade) implemented & reviewed; GPU validation pending

Built the **offline long-form generation** feature on SA3 (branch `latch-sa3-phase1`,
commits `5f6f808..796a76d`, 14 commits, pushed to `fork`). This is the productionised
successor to the FIFO prototype: instead of one OOD FIFO stream (which drifts/collapses
after ~18 s), it renders **overlapping windows, each latent-clamped to the previous tail
via SA3 inpainting, stitched with slerp crossfades** — drift-free by construction.
- Files: `stable_audio_3/inference/longform.py` (PromptSchedule, slerp+CrossfadeStitcher,
  DriftMonitor, ChunkGenerator seam + InpaintContinuationGenerator + SDEditReanchor,
  LongFormRenderer), `scripts/longform_render.py` (CLI: prompt or `t:prompt|...` schedule),
  `tests/test_longform.py`. Docs: `docs/workflows/longform.md`,
  spec/plan under `docs/superpowers/`.
- **Swappable `ChunkGenerator` seam:** Approach A (inpaint-continuation) ships now;
  Approach C (`BoundedFifoGenerator`, the FIFO surgery) drops in behind the same interface
  after a finetune. `SDEditReanchor` built (latent audio2audio re-noise→denoise) but reserved
  for opt-in transition morph / C's drift refresh.
- Built via subagent-driven-development (fresh implementer+reviewer per task, 2-stage gates).
  Reviews caught & fixed real bugs: slerp endpoint imprecision, an `n==0` transition crash,
  a `parse_schedule` colon-prompt crash, and (final whole-feature review) **missing [-1,1]
  output clamp** (MASTER.md §5 clip gotcha), **single-shot decode OOM** (now `chunked=True`),
  NaN-retry/fail-fast + a drift canary, and **transition windows were clamping to the OLD
  prompt's tail** (fixed → fresh chunk on transitions).
- **Status: CPU 18/18 green, ruff clean. GPU render NOT yet runtime-validated** — dev box
  VRAM held by a control-head training run. GPU-gated tests now skip cleanly on low VRAM.
  Merge deferred until outputs verified. Validate when free: `uv run pytest
  tests/test_longform.py -v` + a 2-min CLI render (acceptance = flat `drift_log` rms).
  Recovery map: `stable-audio-3/.git/sdd/progress.md`. Details: [[infinite-audio-fifo-sa3]].

## 2026-06-18 — Kim + Opus 4.8 — InfiniteAudio FIFO prototype for SA3 (written+reviewed, UNTESTED); forage-dj vs mir beatmatch

Ported InfiniteAudio (arXiv:2506.03020) long-form / FIFO "diagonal denoising" to SA3 on
branch `latch-sa3-phase1`. Files: `docs/INFINITE_AUDIO_FIFO.md`,
`stable_audio_3/inference/fifo_infinite.py`, `scripts/fifo_infinite_smoke.py`.
- **Finding:** SA3's DiT only accepts a *scalar-per-batch* timestep (`dit.py:239`, folded
  into adaLN global cond). True FIFO needs *per-frame* σ `(B,T)` → requires model surgery
  and is **out-of-distribution** (untrained). Not a sampler swap. Live config (small-music-base):
  patch_size=1, timestep_cond_type=global, global_cond_type=adaLN, num_memory_tokens=64,
  downsampling_ratio=4096.
- Surgery = guarded monkeypatch making adaLN per-token (3 injection points, delegates the
  long methods; scalar path byte-identical). CFG done manually (2 cfg=1.0 passes) since the
  DiT's internal CFG assumes scalar sigma.
- **Status: NOT run (GPU was busy).** Adversarial-review workflow (5 lenses, 38 agents)
  found 18 issues — all fixed. Core surgery (delegation, shapes, signs) verified correct.
  First validation: `fifo_infinite_smoke.py --parity` (gate on REL err <5e-3; ROCm GEMM
  floor ~1e-3..1e-2 abs). Biggest expected failure = **rotary positional drift**. Fallback
  if too OOD: sliding-window inpaint-continuation (no surgery). Details: [[infinite-audio-fifo-sa3]].
- **forage-dj** (cloned to `/home/kim/Projects/forage-dj`): its "long-form" is just
  generate-fixed-tracks (≤47–60s) + DJ equal-power crossfade (`src/foragedj/mixer.py`) —
  **nothing reusable** for continuous diffusion. And mir's `scripts/latent_server.py`
  `beatmatch_crossfade_to_wav` (downbeat-grid tempo match via `.DOWNBEATS`, phase-lock,
  latent-space crossfade) is **strictly more advanced** than forage-dj's fader — no port up.

## 2026-06-18 — Kim + Opus 4.8 — SA3 generative source separation: FlowEdit works, true inversion is cfg-fragile

Built two text-prompted separators on SA3 `medium-base` (rectified flow), both in
`stable-audio-3/scripts/`. Context: the old `mir-same-chroma/scripts/sa3_zerosep_lite.py`
was plain **SDEdit** (init_audio+init_noise_level → one linear noise blend), which is why
its outputs followed the prompt but had **no tie to the input**.
- **`sa3_flowsep.py`** — inversion-FREE FlowEdit/AUDEDIT (arXiv:2412.08629 / 2606.15149).
  Keeps z_edit=x0, integrates the difference field `v(z_tar,target) − v(z_src,source)` along
  SA3's schedule, skipping the high-noise head (`--n-max`). Monkeypatches
  `sampling.sample_discrete_euler` for one `generate()` call (reuses cond/varlen/decode);
  builds source+target cond via `conditioner`+`get_conditioning_inputs`. cfg_src 3.5 /
  cfg_tar 13.5, n_max 33. **Robust to high cfg** (shared noise cancels) → stays anchored.
- **`sa3_zerosep_rf.py`** — true RF-Solver inversion (arXiv:2411.04746): reverse-Euler +
  2nd-order Taylor invert x0→noise at cfg=1, round-trip gate, then prompt-swapped re-denoise
  (cfg swept off the shared inversion). Inversion is **near-transparent** (eps std 1.006,
  latent round-trip rel err **0.229**, reconstruction env-corr **0.967**). But separation is
  **cfg-fragile**: cfg 8 collapsed (env-corr 0.05–0.11, prompt-prior dominates); sweet spot
  ~cfg 2 (0.10–0.28).
- **A/B (Acid Alien 400–410 s, env-corr ↗ mix):** FlowEdit lead/bass/drums 0.90/0.32/0.18
  vs RF best ~0.28/0.13/0.21. FlowEdit anchors better; RF gives cleaner instrument timbre
  (RF bass centroid 931 Hz vs FlowEdit 3030 Hz) but re-imagines more.
- **Takeaways:** (1) real ZeroSep = edit-friendly **DDPM** inversion, does NOT port to flow
  matching — the flow analogue is RF/ODE inversion, or (better here) inversion-free FlowEdit.
  (2) Must use a **-base** checkpoint (post-trained = stochastic ping-pong, cfg inert).
  (3) **cfg≈1 for inversion** — high cfg ruins recoverability (MusRec); asymmetric cfg
  (low invert / bounded regen) is mandatory. (4) Both are generative re-synthesis, **not
  masking** → not clean stems; for clean drums/bass use mir Demucs/BS-RoFormer. Generative
  value = **open-vocab** extraction ("isolate the acid lead"). (5) **env-corr ↗ mix is only a
  faithfulness proxy for the DOMINANT source** — on a full-arrangement window all isolated
  sources score low (each is only a part of the mix); honest non-dominant eval needs
  reference stems.
- Full discography (real-music test corpus) downloaded to `/home/kim/Projects/discography_flac`
  (`aavepyora-2017-discography` FLAC subtree, 284 tracks).
- **Update — η faithfulness controller added to `sa3_zerosep_rf.py`** (fixes RF-Solver's
  "clean but far from input"). On the re-denoise, pull predicted-clean `z0 = x − t·v`
  toward the encoded mixture: `z0 ← (1−η)·z0 + η·x0_src` for `t ≥ τ` (τ=0.3), rebuild
  `v = (x − z0)/t`. **First tried the RF-Inversion `(anchor−x)/(1−t)` field — wrong sign +
  blows up at t→1 under SA3's descending-t Euler** (centroids exploded, near-silent); the
  z0-anchor (the SA3 mean-guidance form from `latch_guided`/`steer_chroma`) is stable.
  η-sweep env-corr↗input (Acid Alien lead 400 s) — **a clean monotone dial:** bass
  0.10→0.72→0.92→0.97, lead 0.09→0.90→0.97→0.97 across η = 0/0.3/0.5/0.7. **η≈0.3–0.5 =
  separation sweet spot** (anchored but still prompt-shaped); η≈0.7 over-anchors → its
  centroid hits the full-mix centroid = just rebuilding the mix. Committed to SA3 fork
  `latch-sa3-phase1`.

## 2026-06-01 — Kim + Opus 4.8 — SA3 DoRA finetune staged + a GPU-wedge lesson (cost the run)

DoRA dim-128 (`dora-rows`) finetune of SA3 `medium-base` on a 300-track / 607-crop subset
(`/run/media/kim/Lehto/latents_sa3_lora300`, symlinks). `scripts/train_lora.py` extended
(backward-compat) with `--epochs`, `--accumulate_grad_batches`, `--gradient_clip_val`,
`--checkpoint_every_epochs` — `DiffusionCondTrainingWrapper` uses **automatic** optimization,
so Lightning grad-accum is live. Launch staged: `/tmp/launch_dora.sh` (rank128, 30 ep, eff
batch 128 = micro 1 × accum 128, ckpt/5ep, `--no_demos`). Fits 12–13 GB at T=4096.
- **First run trained fine** (~2 s/microbatch at T=4096, loss decreasing, CSV-logged).
- **LESSONS (these cost the run):**
  1. Lightning's tqdm is **SILENT in a non-TTY** — the progress signal is the CSV at
     `lightning_logs/version_N/metrics.csv` (read the **newest** version dir — a relaunch makes
     a new one). Don't kill a working run to "fix monitoring."
  2. **Repeatedly hard-killing a multi-GB GPU process WEDGES the HIP runtime** — every
     subsequent run loads the model (12 GB, GPU 99%) but hangs on a stuck kernel
     (`futex_do_wait`, no optimizer step) even with the *identical config that just worked*.
     GPU returns to clean-idle between runs but won't train. Recovery = `sudo rocm-smi
     --gpureset -d 0` (needs sudo; unavailable unattended) or reboot.
  3. Setting `MIOPEN_FIND_MODE` in env also froze a run (mir CLAUDE.md warns this).
- TODO after GPU reset/reboot: `bash /tmp/launch_dora.sh`. Full T=4096 ≈ 9 h for 30 ep; add
  `--duration 100` (T≈1076) to fit a session. Then the FusionOpt-vs-AdamW comparison.

## 2026-06-01 — Kim + Opus 4.8 — probed the 2 un-probed timeseries fields: beat is NOT dead

Ran the ridge decodability probe over ALL 21 latents_sa3 timeseries fields (was 19; the only
gap was `beat_activation` + `downbeat_activation`, skipped on the SAO-Small §9 "beat = dead
control" assumption). `/tmp/ridge_probe.py` (N=400, SEED=0, track-disjoint) →
`/tmp/sa3_autotests/ridge_probe_all.log`. The 19 prior features reproduced exactly.
- **`beat_activation` = R² 0.62 → STRONG** (3rd overall, above skewness/onset_drums/rms_drums).
  The SAO-Small "beat dead" verdict was LATENT-SPECIFIC (acoustic conv-VAE); it does NOT carry
  to SAME — SAME's contrastive/semantic training encodes metrical structure linearly. Fixed
  `docs/latch.md` (it listed beat as a documented don't-retry dead end).
- **`downbeat_activation` = R² 0.31 → viable.**
- New live control candidates for SA3-medium, still UNTRAINED: beat_activation (0.62),
  onset_envelope_drums (0.57), rms_drums (0.54), hpcp (0.48), downbeat_activation (0.31).
  Caveat: beat/downbeat are sparse spike-trains — decodability is real, but a closed-loop
  verify is needed to confirm they steer (a spike target may behave unlike a smooth feature).

## 2026-06-01 — Kim + Opus 4.8 — SA3 medium heads ARE controllable (gain was ~10× too low)

Closed-loop verify + latent-steering + gain sweep of the trained SA3-medium heads on
`medium-base`. Scripts: `scripts/latch/verify_medium_heads.py` (committed),
`/tmp/gain_sweep_flux.py`, `/tmp/latent_edit_steer.py`. Logs in `/tmp/sa3_autotests/`.

- **CODE FIX (landed):** `stable_audio_3/inference/latch_guided.py` `head_loss()` only knew
  `mse`/`bce_logits` → raised `Unknown loss_type: 'smooth_l1'`. EVERY smooth_l1-trained head
  was silently un-guidable. Added `smooth_l1`/`huber`/`l1`. Any `--standardize` smooth_l1 head
  now guides.
- **GAIN FINDING (the headline):** default `rho=mu=8` gives near-zero authority (4σ request →
  ~2% measured Δflux; `corr=1.0` is a MIRAGE — rank-corr rewards direction not magnitude).
  Flux spread scales ~LINEARLY with gain: g8→0.78, g24→2.62, g48→5.43, g96→10.52, mono +
  in-distribution throughout (no degradation at g96; real crops span flux 12–96).
  **→ SA3-medium operating gain ≈ 48–96 (~6–12× the SAO-Small default of 8). It was low gain,
  NOT weak heads.** Window (0,1) marginally beats (0.4,1.0); gain is the dominant lever.
- **Confirmed per-head @ gain 64, ±1.5σ, same-noise (`verify_medium_heads.py --gain 64`):**
  flux 27.3→33.5 (Δ6.2, ±10%), flatness 0.26→0.33 (Δ0.07, ±12%), skewness 1.93→2.18 (Δ0.25,
  ±6%), onset_envelope 0.85→0.89 (Δ0.04, ±2.5%) — all monotonic. **Controllability tracks the
  decodability probe R² exactly** (flux .90 > flatness .78 > skewness .61 > onset .56): the
  ridge probe is a validated end-to-end predictor of head authority. onset is decodability-
  limited (near the controllable floor — more gain won't buy much).
- **Steering (direct latent edit, no diffusion):** shift clean SAME-L latent along the ridge
  flux-direction β by `k·σ_proj`, decode. **+β raises flux cleanly/monotonically 5/5 crops
  (12→34, ~3×); −β is content-limited** (works where flux headroom exists, reverses into
  artifact-noise on already-low-flux crops). A training-free "flux/brightness up" knob for the
  decodable features, complementary to the heads.
- **Ops lessons (unattended runs):** (1) `pkill -f "pat"` self-matches the shell running it
  when "pat" is in its own argv → kills itself; never pkill from a script that contains the
  pattern string. (2) a `pgrep`-string wait loop hung overnight on orphaned persistent
  DataLoader workers that kept matching after the main proc exited — don't gate auto-runs on
  pgrep; use the trainer's own exit / a checkpoint sentinel.

## 2026-05-31 — Kim + Opus 4.8 — SA3 is a SEMANTIC latent (SAME): decodability map

Ridge decodability probe over all 19 latents_sa3 features (`/tmp/ridge_probe.py`,
clean latent, track-disjoint, §1 method) — run BEFORE auditioning to skip dead heads.
Full ranking + the SAME explanation now in `docs/latch.md`. Headlines:
- **SA3 VAE = SAME** (Semantically-Aligned Music autoEncoder): deterministic transformer
  AE, 256-d @ 10.76 Hz, trained for semantic structure (chroma+ILD regression, T5Gemma
  contrastive) + diffusion-alignment, not faithful low-level acoustics.
- **`rms_energy_bass` DEAD (0.10)** despite being the SAO flagship (corr 0.965) — the VAE
  change (acoustic conv → semantic SAME) silently rewrote the controllable-feature menu.
- **STRONG:** spectral_flux/flatness/skewness (0.6-0.9), onset_envelope(+drums) 0.56,
  rms_drums 0.54, hpcp 0.48. **DEAD:** band-RMS, relative_position, vocals.
- **relative_position dead** (local 0.03, global-pooled 0.08, flux sanity 0.98) — drop the
  GUI position slider. Whole-track property the local latent can't carry; target ill-posed.
- Better-fit control for semantic latents: SAME's built-in chroma+ILD readouts, text-aligned
  latent steering (needs a learned text→latent bridge — critic, not CLIP-shared space),
  LatCH only for the decodable temporal features. Next: latent-direction edit test.

## 2026-05-31 — Kim + Opus 4.8 — SA3 MEDIUM LatCH heads: train all features

Training 19 LatCH heads for the SA3 medium grid (SAME-L 256x4096) on the beat-aligned
`latents_sa3` (5400 crops + `.TIMESERIES.npz` companions). Trainer adapted (commit
7247df6): `target_source=npz`, bf16 autocast, `--standardize`. Recipe: adamw 3e-4,
adaln_zero, bf16, standardize, smooth_l1, bs32, 20 ep, save-best-only → `latch_weights_sa3_medium/`.

- **bf16 autocast is a 6.4x throughput lever** on RDNA4 at T=4096 (fp32 12 → bf16 77
  items/s, bs32). fp32 is pathologically slow for this head. Sweet spot bs32/bf16 =
  77 items/s / 8.3 GB (bs64 → 16.3 GB, too close). ~70s/epoch → ~23min/head → ~7h total.
- **Standardize is essential** here: rms_energy_bass target mean −21.9 dB / std 14.5 —
  un-normalized loss would be swamped by the offset (LATCH_RESULTS §18).
- Features (19): rms_energy×4, spectral×4, onset_envelope (+drums/bass/other/vocals),
  rms_{drums,bass,other,vocals}, relative_position, hpcp. **Skipped beat_activation /
  downbeat_activation** (§9: beat = dead control). hpcp trains 12-ch smooth_l1 (no cosine
  in this trainer — refine later).
- TunableOp OFF (avoids first-shape tune stall; bf16 default heuristic is fine). No
  `--compile` (state_dict `_orig_mod.` prefix + per-head warmup not worth it here).
- Per-stem onset/rms heads are the novel medium-grid contribution; relative_position is
  the new structural-position control. Launched 18:08; ETA ~01:00.

## 2026-05-31 — Kim + Opus 4.8 — torch.compile benchmark (full optimization ladder)

Same 50-step LatCH-guided gen, eager vs `torch.compile` (default mode, DiT only — the
sampler calls it no_grad), TunableOp ON throughout, Inductor graphs persisted to the
per-stack `inductor_cache`. All 8 clean, outputs match eager.

| stack | backend | eager | compiled | compile speedup |
|---|---|---|---|---|
| 2.12/7.14 | CK flash     | 14.26 s | **12.99 s** | 1.10× |
| 2.12/7.14 | SDPA         | 19.72 s | 18.63 s | 1.06× |
| 2.10/7.2.3| Triton flash | 27.73 s | **16.15 s** | **1.72×** |
| 2.10/7.2.3| SDPA         | 32.84 s | 21.33 s | **1.54×** |

- **Same pattern as TunableOp: compile transforms the 2.10 stack (1.5–1.7×), barely
  moves 7.14 (1.06–1.10×).** All the optimization headroom is on the old stack.
- **Full ladder (prod Triton): 51.72 → 27.73 (+TunableOp) → 16.15 (+compile) = 3.20×.**
- **Fully-optimized CK vs Triton = 1.24×** (16.15/12.99), down from raw 3.57× → 1.96×
  (TunableOp) → 1.24× (TunableOp+compile). The big early gap was optimized-new-vs-
  unoptimized-old; with both fully optimized the 7.14/CK edge is modest.
- **Which lever wins depends on stack:** on 2.10, compile > backend (compiled-SDPA 21.33
  beats eager-Triton-flash 27.73); on 2.12, flash > compile (eager-CK 14.26 beats
  compiled-SDPA 18.63).
- **Best per stack:** 2.12 = CK+compile 12.99 s (3.85 st/s, fastest overall); 2.10 =
  Triton+compile 16.15 s (3.10 st/s). Compile cost ~28–44 s one-time (persisted); VRAM
  slightly lower compiled. Free lever noted: `set_float32_matmul_precision('high')` (fp32).

## 2026-05-31 — Kim + Opus 4.8 — Attention benchmark, TunableOp ON (corrects the gap)

Rerun of the backend matrix below with **TunableOp ON** + persistent per-venv tunings
(`~/pytorch-tunings-7.14` for the 2.12 stack — NEW, mirrors the 7.2.3 layout; canonical
`~/pytorch-tunings-7.2.3` for prod 2.10). Confirms the TunableOp-off caveat was material.

| backend | venv | wall OFF | wall ON | TunableOp speedup |
|---|---|---|---|---|
| CK flash    | test/2.12 | 14.48 s | 14.18 s | 1.02× (negligible) |
| SDPA        | test/2.12 | 20.07 s | 19.75 s | 1.02× |
| Triton flash| prod/2.10 | 51.72 s | **27.73 s** | **1.87×** |
| SDPA        | prod/2.10 | 56.80 s | **32.78 s** | **1.73×** |

- **TunableOp is ~1.8× on the prod 2.10 stack, ~1.0× on 7.14** — 7.14's default hipBLASLt
  heuristic is already near-tuned (only 46 GEMM shapes cached vs prod's 210 KB).
- **Corrected fair CK-vs-Triton = 1.96×** (was 3.57× off): stack 1.66× × kernel 1.18×.
  The off run had nearly DOUBLED the apparent advantage by handicapping prod's tuned cache.
- **CK flash = 1.39× over SDPA, identical on/off** (flash kernels are orthogonal to GEMM
  tuning). Clean, real win. Triton = 1.18× over its SDPA.
- Net: 7.14 stack ~1.66× faster even fully-tuned (worth migrating, not the 2.8× off-run
  implied); CK is the better flash kernel; the stack upgrade is the bigger lever.
- math/none reference crashed both venvs (forced SDPBackend.MATH faults the GPU at T=1292;
  no coredump cascade — handler failed cleanly). Non-essential. Next: torch.compile bench.
- Persistent 7.14 tunings now at `~/pytorch-tunings-7.14/tunableop_results0.csv`. See
  `docs/venvs.md` for the per-stack tunings-dir mapping.

## 2026-05-31 — Kim + Opus 4.8 — Attention backend benchmark: CK vs Triton vs SDPA vs math

Head-to-head: one 50-step LatCH-guided SA3 generation (small-music-base, the only trained
SA3 head = rms_energy_bass ep10), T=1292 (120 s), fp32, rho=mu=8, n_iter=6. TunableOp OFF,
warmup discarded, median of 2 timed. Harness `/tmp/bench_latch_attn.py`, runner
`/tmp/run_bench_matrix.sh`, raw `/tmp/bench_results.txt`. All 6 outputs match (out_mean
−0.0152) → every backend numerically correct.

| backend | venv/torch | 50-step wall | steps/s | vs same-venv SDPA |
|---|---|---|---|---|
| CK flash    | test / 2.12+rocm7.14 | 14.48 s | 3.45 | **1.39×** |
| SDPA        | test / 2.12 | 20.07 s | 2.49 | 1.00 (anchor) |
| math (none) | test / 2.12 | 19.00 s | 2.63 | 1.06× |
| Triton flash| prod / 2.10+rocm7.2.3 | 51.72 s | 0.97 | **1.10×** |
| SDPA        | prod / 2.10 | 56.80 s | 0.88 | 1.00 (anchor) |
| math (none) | prod / 2.10 | 63.66 s | 0.79 | 0.89× |

- **CK vs Triton end-to-end = 3.57×.** Decomposed via the SDPA anchors: **stack
  (2.12/7.14 vs 2.10/7.2.3) = 2.83×** (dominant); **flash kernel (CK uplift 1.39 vs
  Triton 1.10) = 1.26×**. CK is the more effective flash backend AND it's on the faster stack.
- **CAVEAT — TunableOp OFF inflates the cross-stack gap.** The within-venv flash ratios
  (1.39×, 1.10×) are clean; the 2.83× stack gap is partly artifact (prod 2.10 normally uses
  its tuned GEMM cache). A TunableOp-on rerun is needed for realistic cross-stack absolutes.
- **Lower bound:** small-music-base, not medium. CK's uplift should be larger on the medium
  DiT at T=4096. VRAM: flash/SDPA 3.31 GB, math +0.4 GB (O(T²) attention matrix).
- **Takeaways:** (1) CK flash is a real ~1.4× over SDPA on its native stack — worth adopting.
  (2) The bigger prize is the 7.14 stack itself (~2.8×) — prioritise migrating prod SA3
  (.venv, torch 2.10) to the 7.14/official-CK path once CK is fully trusted.

## 2026-05-31 — Kim + Opus 4.7 — TheRock 7.14 + CK flash-attn for RDNA4: VALIDATED

Follow-up to the 4.8 entry below ("CK-FA build status: BUILT, NOT YET VALIDATED"). Validation
done; recipe + numbers below. Full recipe in SA3 auto-memory `rocm-flash-attn-env.md`.

- **flash-attn 2.8.4 CK build** for gfx1201/WMMA SUCCEEDED after two surgical patches on
  `ROCm/flash-attention` branch `rdna_fmha_gfx1100_gfx1201` (its `csrc/flash_attn_ck/` glue is
  older than its CK pin `08792e0`). Pulled `mha_bwd.cpp` + `mha_varlen_bwd.cpp` + `flash_common.hpp`
  from sibling branch `rocking/update_ck` (commit `d81a98630` "Add sink_ptr/d_sink_ptr to
  fmha_bwd_args"). Originals saved as `*.orig` in the checkout.
- **Verified end-to-end on `~/Projects/SAO/sa3-rocm7.13-test/.venv`** (torch 2.12.0+rocm7.14.0a,
  triton 3.7.0+rocm, gfx1201/RX 9070 XT 16 GB):
  - **varlen smoke** — `flash_attn_varlen_func` finite, max abs diff vs SDPA = **2.89e-04**
  - **SA3 small-music-base generation** — warmup **88 s** (TunableOp+MIOpen tune from scratch),
    cached **0.23 s** (~380× speedup); output fp16 finite, shape (1,2,264600)
  - **LatCH 1-step train with `FusionOpt(normuon, sf)`** — warmup 4.4 s, cached **21 ms**
  - **torch.compile + inductor on LatCH head** — eager 3.18 ms → compiled **2.04 ms** (1.56×),
    max abs diff = 2.4e-07
- **Critical runtime knob**: set `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` BEFORE `import flash_attn`
  — the Python wrapper auto-routes to aiter on HIP and aiter isn't installed in this test venv.
- **Tunings**: isolated to `~/Projects/SAO/sa3-rocm7.13-test/tunings/` so the 2.10/7.2.3 cache at
  `~/pytorch-tunings-7.2.3` is untouched (2.12 validator rejects 2.10 entries and TUNING=1 would
  otherwise overwrite). After warmup, TunableOp validator passes cleanly on the isolated cache
  (PT_VERSION=2.12.0, gfx1201, ROCBLAS_VERSION=5.5.0.62d3a262 all match).
- **Implication for the prod SA3 venv**: when ready to migrate the main `.venv` (torch 2.10/ROCm
  7.2.3) to the ROCm 7.14 / official-CK path for RDNA4, this is the known-working recipe.

## 2026-05-31 — Kim + Opus 4.8 — SA3 LoRA data pipeline + master docs

- **SA3 training dataset COMPLETE + ready.** `/run/media/kim/Lehto/latents_sa3/`:
  **5400 beat-aligned crops, T=4096, 0 failures**, 13 GB. Each crop = `.npy`
  (256×4096 fp16) + `.json` (full source `.INFO` + §3.5 prompt + crop offsets +
  rel_pos) + `.TIMESERIES.npz` (21 fields: 20 MIR @ resampled-to-4096 + the new
  `relative_position_ts` ramp). Next: SA3 LoRA retrain against this (rank 16
  dora-rows bf16 `--compile`, `MIOPEN_FIND_MODE=2`).
- **GPU coordination note:** the encode held ~14 GB VRAM (SAME-L + 380 s fp16
  activations) → hard-blocked the parallel **CK-FA validation** instance (needs
  VRAM for SA3 medium + FA). Encode finished ~`<time>`; VRAM released to 1.5 GB.
  **CK-FA build status: BUILT, NOT YET VALIDATED** — `flash_attn-2.8.4-cp313`
  compiled from source in `SAO/sa3-rocm7.13-test/` on a SEPARATE experimental
  stack (`amd-torch 2.12.0+rocm7.14.0a`, gfx1201 device wheels), NOT the prod
  7.2.3 stack. Numerical validation (scripts 02–05) pending on the other instance.
- **Created the docs layer:** `MASTER.md`, this `WORKLOG.md`, `ARCHITECTURE.md`,
  and `docs/{venvs,commands,latch,training-findings,lessons-learned,todos}.md`.
  Wired `@import MASTER.md` into the 3 project CLAUDE.mds (created one for
  stable-audio-tools, which had none). `git init`'d `SAO/` to version just these
  coordination docs (`.gitignore` ignores all nested repos/artifacts).
- **SA3 pre-encode, take 2 (beat-aligned, fixed T=4096).** First take used
  `pre_encode_dataset.py` default `--sample_size` (285 s, single random window/track)
  → cache thrash + lost ~38 % of each track. Pivoted to beat-aligned chunking:
  - `/tmp/sa3_beat_manifest.py` → `/tmp/sa3_crop_manifest.csv` (5400 crops / 2676
    tracks; dropped 471 sources < 380 s). Crop spec: first crop from song start, each
    next snaps back to downbeat-before-prev-end (overlap), final crop end-anchored.
  - `/tmp/sa3_encode_from_manifest.py` → `/run/media/kim/Lehto/latents_sa3/`. Per crop:
    `.npy` (256×4096 fp16, SAME-L) + `.json` (full source `.INFO` merged + §3.5 prompt +
    crop offsets) + `.TIMESERIES.npz` (whole-track sliced→4096 + `relative_position_ts`).
  - Encode running at finish of this session (~5400 crops, ~3.6 h). Post-pass
    `/tmp/sa3_add_relpos.py` ready (the in-flight run predates the rel_pos patch).
- **GOTCHA found: `MIOPEN_FIND_MODE=6` crashes SA3 medium DiT** → MASTER.md §5. Use mode 2.
- **GOTCHA found: batch=1 variable-length → kernel-cache thrash** → MASTER.md §5.
- **SA3 LoRA tuning runs** (10 steps each, warming caches): MIOpen(2) → +TunableOp →
  +torch.compile all OK. Added `--compile` and `--no_demos` flags to
  `stable-audio-3/scripts/train_lora.py`. First full run (rank 16 dora-rows bf16,
  5000 steps) killed at ~700 steps once the cache-thrash root cause was understood;
  re-launch pending against the new beat-aligned `latents_sa3`.
- **Whole-track timeseries** (21 G, 4461 npz @ 100 Hz) documented in `mir/CLAUDE.md`
  (new section) + MASTER.md §4. Producer `mir/src/spectral/whole_track_timeseries.py`,
  consumer `stable-audio-tools/scripts/whole_track_target_source.py`.

## (earlier — see per-repo memory + LATCH_RESULTS.txt)

- LatCH sweep / Fusion bake-off history: `stable-audio-tools/LATCH_RESULTS.txt` (§1–23).
- SA3 LatCH Phase-1 verification (bass RMS, corr 0.965): SA3 memory `latch-sa3-phase1.md`.
- SAO-Small finetune dev guidance (LR/batch/NaN): SAT memory `sao-finetune-dev-guidance.md`.
