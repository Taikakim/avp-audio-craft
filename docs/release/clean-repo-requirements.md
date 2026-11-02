# Clean public repo: what it needs

Owner: THE-FINN (created 2026-11-02). Design decisions belong to WINTERMUTE (Latent Forge owner, OWNERSHIP.md)
and Kim. Status: requirements gathered, nothing built. Goal and constraints: first public Latent Forge release,
rough is fine, speed matters, because the release is meant to establish prior art and start a hobby scene.

## 1. The audit (2026-11-02)

Static import closure from `eval/explorer_render_server.py` + `eval/forge_api.py`, lazy imports included.
**Limit: static only.** It does not see subprocess calls, dynamic loads, data files or the frontend. Bungee, for
one, is reached through `eval/forge/stretch.py` by path. Treat the numbers as a floor. A clean-venv boot test is
the real check.

| Source | Files | Lines | Fate |
|---|---:|---:|---|
| `stable_audio_3` (our fork) | 31 | 8,595 | 15 files identical to upstream, 16 differ (see section 2) |
| `eval/` top level | 14 | 6,277 | Render server stays; trim the rest (section 3) |
| `mir-same-chroma` checkout | 5 | 2,777 | Extract `compute_same_chroma`, drop the rest |
| `eval/forge/` | 29 | 2,344 | Moves nearly as is |
| `control/sa3_control` | 10 | 2,110 | Adapter core moves; `mert_selector` likely not |
| `stable-audio-3/scripts/weight_mutations.py` | 1 | 258 | Move or drop |
| **Total** | **90** | **22,361** | Plus `latent-forge/` (Svelte, 2.2 MB of src) |

Third-party: torch, torchaudio, numpy, scipy, einops, safetensors, transformers, huggingface_hub, fastapi, starlette,
uvicorn, soundfile, librosa, pydub, tqdm, packaging, dotenv, filelock, yaml; plus `flash_attn`, `stable_audio_tools`
and `audiobox_aesthetics`, see section 3.

Hardcoded local paths: **76 in 9 files**, mostly `explorer_render_server.py` (28), `chroma_morph_transitions.py` (26),
`mixtape_v7_dsp.py` (13).

## 2. The main finding: the fork is further from upstream than "thin"

Our branch is **277 commits ahead and 197 behind** `upstream/main`, merge-base 2026-05-29, and upstream is very active
(last commit 2026-10-30). **Correction to my first advice:** "upstream SA3 as a plain pip dependency" is the right
target but not free. The closure's fork changes split in two:

- **New files, which move cleanly into `latch_core`:** `inference/latch_guided.py` (590), `inference/longform.py` (338),
  `models/latch.py` (336), `inference/chroma_losses.py` (130), `inference/recurrence_potential.py` (98),
  `inference/latch_targets.py` (47). `rocm_env.py` (108) moves to the server or install layer.
- **Edits to upstream files, which are the real work:** `model.py` (+372/-45), `models/lora/model.py` (+102/-93),
  `models/transformer.py` (+77/-10), `models/lora/utils.py` (+8/-73), `models/lora/loader.py` (+8/-35),
  `inference/sampling.py` (+23/-3), `models/dit.py` (+16/-2), `__init__.py`, `models/lora/__init__.py`. The LoRA
  deletions probably mean we lack upstream's newer code, not that we removed anything. That needs checking, as
  upstream has since worked on rank padding, strength scaling and bake-dora.

**First concrete task:** try the `model.py` / `transformer.py` / `sampling.py` / `dit.py` hooks against current
`upstream/main`. Expected shape: subclass or wrapper, with a small patch set as fallback, and a pinned upstream commit.
`docs/latent-forge/fork-patches` may already hold part of this. LoRA behaviour must be re-verified on upstream's code,
because the shipped fine-tunes depend on it.

## 3. What to untangle

- **`eval/chroma_morph_transitions.py`:** the server imports it at boot and it brings 26 hardcoded paths and
  `mixtape_v7_dsp`. Move only the helpers the server uses.
- **`stable_audio_tools`:** `latch_guided.py:29` imports `time_cache` from it. Vendor that one class; do not make users
  install the whole package.
- **`mir-same-chroma`:** a stale checkout (last commit 2026-06-21) that MASTER's project map does not list. Extract
  `harmonic/same_chroma.py` (704 lines) into `latch_core`, and leave `core/*` behind if it allows.
- **`audiobox_aesthetics`, `mert_selector`:** reward selection for longform. Make optional or drop for v1.
- **`flash_attn`:** already optional in code. Upstream notes it is not in its `pyproject`. Measurements conflict on
  whether CK helps (see W42 synopsis). v1 default: off; SDPA for an install that just works.
- **Census tooling:** `model_db`, `model_roots`, `ckpt_probe`, `head_meta`, `adapter_slots` assume our drives. Replace
  with a models folder plus a manifest. C's `eval/ckpt_weights.py` is worth keeping for the weights selector.
- **Must NOT travel:** fleet logs, journals, internal docs, `CLAUDE.md`, sidecars, eval drivers, test scripts tied to our
  drives. Start from an allowlist, never a denylist. Fresh history. Run the leak gate over the first commit.

## 4. Weights

- Everything loaded by default must be trained on Kim's own music (MASTER section 4 rights tiers).
  **Needed: a manifest of every weight file the GUI can load by default.** Known so far:
  - **LatCH heads** chroma, onset, hardness, RMS: retrain on `Kosmos/latents/latents_avp`
  - **FiLM density adapter:** the shipped one is goa-trained, so it needs the same retrain, and the LatCH + FiLM hand-off depends on it
  - **Fine-tunes:** Kim's own music only
  - **Presets** that name goa checkpoints: rewrite
- Retrain cautions: split by source track (augmented copies leak across a crop split); 2,393 overlapping crops, so
  check one head's steering spread against its goa twin before committing all of them. Scratch note: the Lehto
  `latents_avp_aug10` "copy" is dangling symlinks, so this set has no backup.
- Hosting: Hugging Face, fetched at first run. SA3 base and the T5-Gemma encoder are gated: users accept those themselves.
- **Licences, unverified, read before release:** the repo's `LICENSE` file reads MIT, while upstream's README refers
  to the Stability AI Community License. Find out which covers what, and what it says about redistributing fine-tunes
  and adapters derived from the base weights.

## 5. Hardware

| Target | State today | Route |
|---|---|---|
| AMD ROCm | Our daily stack, version-fragile | `rocm_env` plus a documented wheel set |
| NVIDIA | Upstream's first-class path; **ours untested**, RTX available | Plain torch install. **Cheapest big win: this is most of the audience** |
| Intel | Kim reports inference proven; **no record in the repo** | Write it down first |
| Apple | Upstream has MLX, also LoRA training; our steering untested | Later |
| CPU | Upstream ships LiteRT/XNNPACK for **Small**; README lists Medium as GPU. Our ONNX DiT + decoder runs Medium on CPU, about 2x realtime at 8 steps (MASTER section 5) | ONNX for v2 |

**The driver-independent goal.** Upstream's LiteRT/XNNPACK route is already a C++ runtime with no GPU driver in the
loop, and ONNX Runtime on CPU has the same property. Both solve it for CPU. A GPU path always goes through some driver;
the realistic aim is a Vulkan-style backend that avoids ROCm/CUDA **version pinning** (not evaluated).

**The catch for steering, which decides the architecture.** FiLM adapters are forward-only and already bake into the
ONNX graph, validated at cosine 1.0. **LatCH is gradient guidance,** needing a gradient through the head on every step.
`onnx/sa3_latch_onnx.py` handles this by keeping torch for the head only. A torch-free runtime needs the head's gradient
exported as its own graph, or a hand-written one. That has not been tried, and is the first experiment for the C++ route.

**Suggested order:** v1 torch on NVIDIA, AMD and slow CPU. v2 ONNX CPU, with FiLM first. Then the head-gradient
experiment decides C++.

## 6. Release blockers known today

1. **Dead decode (W, 2026-11-02, MASTER section 5), a watch item more than a blocker so far.** A healthy latent can decode
   to all-NaN audio, written as a full-scale DC file, and a request can come out unsteered. The first guided render of a
   fresh process hit it in 3 of 3 tries, **but on direct `generate(latch_configs)` with the bare base model.** Through the
   render server, the GUI's path, C found 0 dead in 714 clips and two clean first requests on a fresh server, both with a
   DoRA installed first. The cause is not established, and a GUI on the bare base model with no DoRA is the untested
   case. Cheap guard regardless: check the audio after decode and refuse to show a dead clip. Unknown whether this is
   ROCm-only, so **test on NVIDIA**.
2. **Live-adapter render fault:** NaN or about 1e11 on identical inputs with a live DoRA; merged adapters are deterministic
   (W39 synopsis). v1 could ship merged only. Also unknown off ROCm.
3. **A latent-std guard before decode:** the clamp that fixed most sample corruption. Should be on by default.

## 7. Questions for Kim

1. Medium, Small, or both for v1? Small gets CPU from upstream for free, but all our heads and fine-tunes target Medium.
2. Repo name and code licence? Apache-2.0 suggested for its patent grant.
3. What does v1 include: arrangement and mixdown only, or also a2a, longform, separation? Each one adds to section 3.
4. Where is the Intel inference record?
5. Who gets NVIDIA test time on the RTX box, and is it reachable by an agent?
