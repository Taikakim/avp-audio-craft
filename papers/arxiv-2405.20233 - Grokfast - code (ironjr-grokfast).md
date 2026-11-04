# Grokfast code review: github.com/ironjr/grokfast

The paper's reference implementation. Paper sidecar: `arxiv-2405.20233 - Grokfast - Accelerated Grokking by Amplifying Slow Gradients.md`.
Reviewed by KUANG on November 4, 2026, at commit 93b2248 (June 26, 2024), the upstream head with no local changes. MIT license.

## What is there

| File | Lines | Content |
|---|---|---|
| `grokfast.py` | 49 | `gradfilter_ma` and `gradfilter_ema`: the whole method |
| `main.py` | 288 | Modular arithmetic (x * y mod 97) with a 2-layer Transformer: the paper's section 2 and 4.1 |
| `main_mnist.py`, `main_qm9.py`, `main_imdb.py` | 270, 248, 412 | The section 4 tasks |
| `README.md` | | Usage, reproduction tables (GTX 1080 Ti), and a hyperparameter guide |

**Integration** (`main.py` lines 162–181): `loss.backward()`, then `grads = gradfilter_ema(model, grads=grads, alpha, lamb)`, then `optimizer.step()`. The returned dict is the filter state and is fed back on the next call.

## How the filter behaves

- **EMA** (`gradfilter_ema`):
  - The state is one tensor per parameter, created on the first call as a copy of that step's gradient.
  - Each call does `mu = alpha * mu + (1 - alpha) * g`, then `p.grad += lamb * mu`, writing `p.grad.data` in place.
  - The first step therefore sends (1 + lambda) * g to the optimizer, 3x at the default lambda = 2. There is no warm-up or bias correction. Under SGD that is a learning-rate spike; Adam mostly normalizes it away.
- **MA** (`gradfilter_ma`):
  - A deque of the last `window_size` gradients per parameter, kept on the device, so memory grows to `window_size` x the model.
  - It averages with Python `sum`, which creates temporaries.
  - `warmup=True` skips filtering until the window is full.
- **Hyperparameter guide** (README):
  - Pick the speedup N you want, then start from w = N or alpha^N = 0.1 (alpha about 0.98 for N = 100), and sweep around it.
  - Tune the filter at the task's default weight decay first, then raise the weight decay 1x/2x/5x/10x. The authors saw no gain at 100x.

## Issues found

1. **`grads` is created lazily, from the parameters that have a gradient on the first call.** A parameter that first gets a gradient later raises a `KeyError`: control dropout, a frozen-then-unfrozen group, or a branch unused at step 1.
2. **`gradfilter_ma` operator precedence.** The condition `if not warmup or len(grads[n]) == window_size and not trigger:` parses as `not warmup or (full and not trigger)`. With `warmup=False`, the ablation `trigger` flag is ignored. This affects only the ablation path.
3. **Gradient accumulation.** The filter must run once per optimizer step, after accumulation, or the EMA's time constant counts micro-batches.
4. **Mixed precision.** With fp16 and `GradScaler`, gradients are scaled by a factor that changes over time, so the EMA would mix scales. Call `scaler.unscale_(optimizer)` first. bf16 without a scaler is unaffected.
5. **Gradient clipping order.** The filter raises the gradient norm by up to (1 + lambda). Clipping before the filter lets the amplified gradient through; clipping after it cuts the amplification. The repo does no clipping, so it gives no guidance.
6. **Memory at our scale.**
   - The EMA buffer is one fp32 copy of the trainable parameters: about 5.6 GB for the full 1.4B DiT, trivial for an adapter.
   - The MA variant cannot run at our scale.
7. **Distributed training.** It works on the synchronized `.grad` after DDP's all-reduce. With FSDP it would filter each shard locally, which is fine elementwise.
8. **No tests**, and the reproduction runs have no seed control beyond the scripts' defaults.

## For us

Do not vendor it. If the idea is ever tried, it is about ten lines in our trainers' step function, placed after accumulation, unscaling and clipping, with the state initialized for every trainable parameter at construction (this avoids issue 1). Under our Newton–Schulz optimizers the gain is normalized away (see the paper sidecar), so the only arm where a trial means anything is AdamW, and there an optimizer-level slow-momentum mix is the cleaner test. Not installed or run.
