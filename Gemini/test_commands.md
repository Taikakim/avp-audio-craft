# Evaluation and Test Scripts

Here is a collection of the existing evaluation and testing scripts used across the project, including what they do and how to invoke them from the command line.

> [!TIP]
> **Virtual Environments:** Remember to use the correct Python virtual environment for each task (e.g., `mir/bin/python` for Audiobox/MERT, `stable-audio-3/.venv/bin/python` for SA3 generation). Ensure you have `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` exported for SA3 environments.

---

## 1. DoRA Finetune Evaluation

### `eval_dora_cpu.py`
**Purpose:** An ALL-CPU audition-render harness for the SA3 DoRA finetune. It loads the base SA3-medium DiT on CPU, attaches the DoRA adapter, and generates 3 prompts × 1 seed for quick sanity checking. 
**Usage:**
```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python $SA3/scripts/eval_dora_cpu.py \
    --ckpt /run/media/kim/Lehto/sa3_lora_runs/.../epoch=9-step=50.ckpt \
    --out-dir renders_dora/ep9
```

### `eval_dora_quality.py`
**Purpose:** A POST-RUN quality scorer for the DoRA finetune. Given the output directory of `eval_dora_cpu.py`, it scores the clips using Audiobox Aesthetics and calculates the MERT distance-to-Goa (using Fréchet distance).
**Usage:** (Must be run in the `mir` venv)
```bash
MIR=/home/kim/Projects/mir
$MIR/mir/bin/python stable-audio-3/scripts/eval_dora_quality.py \
    --render-dir renders_dora 
```

---

## 2. Control Adapter Evaluation

### `onset_eval.py`
**Purpose:** Evaluates the onset-density attribute head. It generates clips over a grid of requested densities and gains, extracts the measured onset density using `librosa`, and reports the correlation. This is the primary bracketing test for onset.
**Usage:**
```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python control/sa3_control/onset_eval.py <onset_head.pt> \
    --densities "2,4,6,8,10" \
    --gains "0,1,2,4" \
    --out /run/media/kim/Lehto/sa3_control_runs/onset_eval
```

### `multi_eval.py`
**Purpose:** Similar to `onset_eval.py` but for a multi-prompt, multi-seed evaluation grid. It loads the model once and saves all wavs + a manifest.
**Usage:**
```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python control/sa3_control/multi_eval.py <onset_head.pt> \
    --prompts "psytrance, 140 bpm||goa trance, 145 bpm" \
    --seeds 1234,777 \
    --gains 1,2,3 \
    --densities 6.5,7,7.5,8 \
    --out <dir>
```

### `merit_eval.py` / `comprehensive_merit.py`
**Purpose:** Disentangled similarity evaluation (MERIT). It uses MERT + 3 heads to separate Melody, Rhythm, and Timbre similarity between a reference and the generated output, yielding a "transfer minus leak" margin.
**Usage:** (Not explicitly documented in bash, but follows a similar pattern to other control evaluators, requiring the `mir` venv if MERT is used outside the SA3 venv).

---

## 3. Asynchronous CPU Eval Servers

### `control_eval_server.py`
**Purpose:** An all-CPU long-lived file-drop server for evaluating control adapters. It loads the ONNX exported DiT and T5-Gemma once, waiting for jobs to be submitted to `SAO/control_eval_queue`.
**Usage:**
```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python $SA3/scripts/control_eval_server.py --threads 12
```

### `latch_eval_server.py`
**Purpose:** An all-CPU server similar to the control eval server, but for evaluating LatCH guidance. It applies torch autograd through the LatCH head over the plain DiT running on ORT CPU.
**Usage:**
```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python onnx/latch_eval_server.py 
```
*(You submit jobs to these using `submit_control_job.py` and `submit_latch_job.py` respectively).*

---

## 4. LatCH Validation

### `latch_validate.py`
**Purpose:** Validates the CPU-based LatCH guidance by comparing the output `z0` (latent) cosine similarity against a GPU reference to ensure math parity.
**Usage:**
```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python onnx/latch_validate.py
```
