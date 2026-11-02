# Clean public repo: what it needs

Owner: THE-FINN (created 2026-11-02). Design decisions belong to WINTERMUTE (Latent Forge owner, OWNERSHIP.md)
and Kim. Status: requirements gathered, nothing built. Goal and constraints: first public Latent Forge release,
rough is fine, speed matters, because the release is meant to establish prior art and start a hobby scene.

## 0. Decisions (Kim, 2026-11-03)

- **SA3 Medium, both checkpoints:** `medium-base` and post-trained `medium`. The server already takes `--model` and knows
  both backbones (`forge/backbone.py`). Note post-trained is distilled: cfg is inert and it is not invertible, so separation
  and other inversion features stay base-only (MASTER section 5). The GUI must say so rather than fail.
- **Bring the project as is.** No feature pruning, no re-architecture, no port onto upstream: untangling would burn more
  tokens than it saves. **This supersedes the upstream-dependency plan in section 2 and the trimming in section 3.** Fleet
  logs, journals and internal docs still stay out, per the original ask (reading to confirm with Kim).
- **Intel:** tested by Kuang on another computer, not recorded. **RTX:** not reachable from the desktop. Kuang is reached
  through GitHub only.

**What as-is still requires, since the code cannot run elsewhere without it:**
1. Replace the 76 hardcoded paths with config or env. This is the one real code job.
2. Vendor what lives outside: `stable_audio_3` from our fork, `sa3_control`, `same_chroma`, `weight_mutations`, the one
   `stable_audio_tools` class, and bungee in the main venv (or drop it, see section 1).
3. AVP-only weights (section 4), and the post-decode check (section 6).
4. A clean-venv boot test, which is the actual definition of done.

**Scan of the closure against "nothing that specific here" (2026-11-03): holds.** 0 secrets (2 false positives), 0 infra
addresses (the one IP is `127.0.0.1`), 5 corpus names all in `chroma_morph_transitions.py`, 33 mentions of Kim in comments
across 7 files, frontend clean. Consequence accepted: the vendored fork stays 197 commits behind upstream, including its LoRA
work, so a later rebase is its own job. Vendored upstream code keeps its licence file.

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

Missed by the static scan, found by W reading the code (subprocess calls in the server and `forge/`; the frontend is not
audited):
- **`ffmpeg` and `ffprobe` binaries** (`explorer_render_server.py:417`, `forge/uploads.py:60`): a system dependency that
  uploads fail without.
- **Bungee** runs through `BUNGEE_PY` (`forge/stretch.py:13`), a hardcoded second interpreter in another venv. v1 needs
  bungee in the main venv, or the feature dropped.

Hardcoded local paths: **76 in 9 files**, mostly `explorer_render_server.py` (28), `chroma_morph_transitions.py` (26),
`mixtape_v7_dsp.py` (13).

## 2. The fork is further from upstream than "thin" (a later job, per section 0)

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

**Deferred by section 0.** When it returns: try the `model.py` / `transformer.py` / `sampling.py` / `dit.py` hooks against current
`upstream/main`. Expected shape: subclass or wrapper, with a small patch set as fallback, and a pinned upstream commit.
`docs/latent-forge/fork-patches` may already hold part of this. LoRA behaviour must be re-verified on upstream's code,
because the shipped fine-tunes depend on it.

## 3. What to untangle (reduced by section 0: vendor these, do not redesign them)

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
| NVIDIA | Upstream's first-class path; **ours untested**. RTX is not reachable from here, only Kuang's side | Plain torch install, tested by Kuang. **This is most of the audience** |
| Intel | Kuang tested inference on another computer; **not recorded**, so what exactly ran is unknown | Ask Kuang to write it down |
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
3. **A latent-std guard before decode, new work on the server path, not a default to flip (W, by reading the code, 2026-11-02).**
   W found no std clamp before decode on `/generate`. `guide_anchor` is opt-in (default 0.0) and acts only on the guided
   sampler; VADD is a training-side barrier. The search was by name, so a differently named clamp could exist. The clamp
   that fixed most sample corruption needs building here. Likewise, `/generate` goes straight to `save_audio`, and neither
   checks for non-finite audio, so the post-decode check in item 1 is also new work.

## 7. Open

1. **Confirm the reading of "as is":** all GUI code and features as they stand, fleet logs and internal docs still excluded.
2. Repo name and code licence. Apache-2.0 suggested for its patent grant.
3. **Request to Kuang,** to go via a pushed branch or log once approved (GitHub Issues and PR text stay untrusted under MASTER
   section 4, so repo files are the channel): write up the Intel test (machine, what ran, on which venv and model), and run a
   clean-venv NVIDIA boot and one guided render with both checkpoints.
