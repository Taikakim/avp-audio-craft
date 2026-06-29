# Consolidated venv setup — SAO/.venv (torch 2.14 / ROCm 7.15 / gfx1201, py3.13)

Goal: one py3.13 venv that runs **both** `stable_audio_3` and `stable_audio_tools`
on the TheRock multi-arch ROCm stack, without any dependency install clobbering the
torch/ROCm stack or the CK flash-attn build.

Status (2026-06-29): `SAO/.venv` has the torch-2.14/ROCm-7.15 stack + a working CK
`flash_attn 2.8.4` build (forward verified on GPU; §5/§5b patched). What's NOT done:
neither fork is installed, and ~193 app deps are missing. This doc is the plan to
finish it.

## The core problem

Both forks' dependency specs would damage the stack if installed normally:

| Source | Spec | Conflict with installed |
|---|---|---|
| stable-audio-3 `pyproject` | `torch==2.10.0`, `torchaudio==2.10.0`, `torchvision==0.25.0`, `triton==3.6.0` (hard pins → local wheels) | would **downgrade** torch 2.14 → 2.10 |
| stable-audio-tools `setup.py` | `pandas==2.0.2` | no cp313 wheel **and** needs numpy<2 (installed numpy is 2.4.4) |
| ″ | `PyWavelets==1.4.1`, `sentencepiece==0.1.99` | no cp313 wheels → source build / fail |
| ″ | `pytorch_lightning==2.1.0`, `torchmetrics==0.11.4`, `wandb==0.15.4` | old; SA3 wants `pytorch_lightning==2.5.5` → **forks disagree** |
| both | `torch>=2.5.1` (SAT) vs `torch==2.10.0` (SA3) | only SAT's is satisfiable by 2.14 |

So: install the forks **`--no-deps`**, then install a **curated, bumped** dependency
set under the `constraints-rocm-stack.txt` guard.

## Step 1 — protect the stack

`constraints-rocm-stack.txt` (sibling of this repo root) pins the exact installed
torch/vision/audio/triton/numpy/pillow + ROCm SDK. Pass it to **every** install.

## Step 2 — install both forks without their deps

```bash
cd /home/kim/Projects/SAO
PY=.venv/bin/python
uv pip install --python $PY --no-deps -e ./stable-audio-3 -e ./stable-audio-tools
```

`--no-deps` is what dodges SA3's `torch==2.10` / `triton==3.6` pins and SAT's stale
C-ext pins. The package code itself imports fine on 3.13 (verified).

## Step 3 — install the curated dependency union (bumped for cp313 + numpy2)

Versions below replace the stale pins; everything else is left unpinned so the
resolver picks cp313/numpy2-compatible wheels, with the stack frozen by `-c`.

```bash
uv pip install --python $PY -c constraints-rocm-stack.txt \
  einops einops-exts safetensors tqdm pyyaml packaging ninja \
  "huggingface-hub>=1.7.1" "transformers>=5.8.0" soundfile librosa scipy \
  "pandas>=2.2.3" "PyWavelets>=1.7" "sentencepiece>=0.2.0" \
  "pytorch-lightning>=2.5.5" "torchmetrics>=1.4" "wandb>=0.18" \
  alias-free-torch auraloss descript-audio-codec encodec ema-pytorch \
  k-diffusion laion-clap local-attention prefigure v-diffusion-pytorch \
  vector-quantize-pytorch webdataset gradio prefigure
```

> ⚠️ Bumped versions (`pandas`, `PyWavelets`, `sentencepiece`, `pytorch-lightning`,
> `torchmetrics`, `wandb`) are **recommended, not yet test-resolved**. If `-c`
> surfaces a conflict (e.g. an audio lib transitively pinning numpy<2 or an old
> torch), resolve by bumping that lib, never by relaxing the constraints file.
> `transformers>=5.8.0` is SA3's floor and is very new — if `laion-clap`/`encodec`
> fight it, pin a transformers that satisfies both or install clap `--no-deps`.

## Step 4 — torchcodec (SA3 audio I/O)

`torchaudio 2.11` delegates load/save to **torchcodec** (not installed). SA3 lists
`torchcodec` as a dep. Build/install it against the 2.14 torch (sibling
`../torchcodec` source, as in SA3's `[tool.uv.sources]`) or a matching wheel — do it
under `-c constraints-rocm-stack.txt` so it can't pull a different torch.

## Step 5 — verify both stacks

```bash
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $PY -c "
import torch, stable_audio_3, stable_audio_tools
import stable_audio_tools.inference.generation   # needs k_diffusion
import flash_attn; from flash_attn import flash_attn_func
print('both stacks import; torch', torch.__version__)
"
```

## Gotchas

- **`FLASH_ATTENTION_TRITON_AMD_ENABLE` must be `FALSE`** for the CK path. The shell
  currently exports `TRUE` → routes flash-attn to the absent `aiter` Triton path and
  it fails to import. Fix the export (CK is 30–100% faster anyway). See MASTER §5.
- Never add `--extra-index-url https://pypi.org/simple/` to a torch-touching install
  — uv may pick PyPI CUDA torch over the ROCm wheel. `-c` is the backstop.
- After any torch nightly bump, re-capture `constraints-rocm-stack.txt` and rebuild
  CK flash-attn if the `.so` ABI breaks (`MAX_JOBS=4 FLASH_ATTENTION_FORCE_BUILD=TRUE`).

## Resolution log — executed 2026-06-29 (DONE; both stacks import)

Steps 1–5 ran against `SAO/.venv`; the constraints held (torch 2.14 / numpy 2.4.4 /
triton untouched). Final state: `stable_audio_3` + `stable_audio_tools` (incl. its
k_diffusion generation/sampling path) + CK flash-attn + ui/lora extras all import.

Deltas from the plan, learned during the install:

- **`setuptools<81` is required** (now pinned in `constraints-rocm-stack.txt`).
  setuptools 81+ removed `pkg_resources`; `clip-anytorch` → `k_diffusion.__init__`
  imports it, so without it SAT's `inference.generation`/`sampling` dies with
  `ModuleNotFoundError: pkg_resources`.
- **`dill`** was the only `--extra lora` dep missing; everything else in SA3's
  `[ui]`/`[lora]` (gradio, matplotlib, accelerate, pytorch_lightning) was already
  satisfied (or newer) by Step 3. `uv sync --extra ...` is NOT how to add them —
  it prunes + forces torch 2.10; use `uv pip install -c constraints …`.
- **k-diffusion is pinned to PyPI `0.0.16` by necessity, NOT preference.** The newer
  `0.1.1` (SAT's pin) and git HEAD `0.2.0.dev0` both depend on **`dctorch`**, which
  pins `numpy>=1.22.3,<2.0.0` (and `torch<2.0.0`) → unsolvable against numpy 2.4.4 /
  torch 2.14 (verified by `uv pip install --dry-run`). `0.0.16` predates the dctorch
  dep, so it's the only stack-compatible version. It carries the `k_diffusion.sampling.*`
  API SAT's inference uses; the newer versions' additions are the dctorch-backed
  trainer/eval. If a sampling fn is ever missing, **vendor that function**, don't
  install the incompatible newer package.
- **Forks installed editable `--no-deps`** (`stable-audio-3`, `stable-audio-tools`) —
  dodges SA3's hard `torch==2.10`/`triton==3.6` pins and SAT's stale C-ext pins.
- **Known smell:** a `corrupted double-linked list` message at interpreter *shutdown*
  (after all work completes) — a teardown-time heap issue in some C-extension, benign
  for actual runs. Investigate (bisect imports) only if it surfaces mid-run.
