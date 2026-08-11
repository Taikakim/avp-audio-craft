# Multi-Adapter Evaluation Script

The new script has been successfully created at `control/sa3_control/multi_adapter_onset_eval.py`. It is designed to handle the complex evaluation scenario you requested, allowing you to bracket over onset density parameters while applying a fixed style and a frozen DoRA finetune simultaneously.

## Features Implemented

1. **DoRA Merging for VRAM Savings:**
   - The script loads your specified DoRA checkpoint and immediately executes a custom `merge_and_unload_dora()` function.
   - This function evaluates the active `LoRAParametrization` directly into the base network's weights, bypassing the need for separate $A$ and $B$ parameter tensors during the forward pass.
   - The DoRA modules are then deleted and `torch.cuda.empty_cache()` is called, freeing up valuable VRAM before the generation loops begin.

2. **Multi-Adapter Injection:**
   - I built a `MultiControlledCrossAttention` wrapper that replaces the `ControlledCrossAttention`. 
   - It manages an arbitrary number of adapters (in this case, two: the FILM onset conditioner and the style conditioner).
   - During inference, it dynamically computes the weighted sum of outputs from all active adapters and injects them into the base attention layer.

3. **Pre-Computed Latent Bypassing:**
   - The script accepts a `--reference-latent` parameter for the style conditioner. It directly loads the `.npy` latent and passes it to the style attribute encoder, entirely skipping the VAE.

4. **Onset Bracketing Loop:**
   - It iterates over the specified grid of `--densities` and `--onset-gains`, whilst keeping the style gain fixed (via `--style-gain`).
   - The results are analyzed via `librosa` and saved to `manifest.json`.

## How to Run the Script

Here is an example command to launch the bracketing test:

```bash
SA3=/home/kim/Projects/SAO/stable-audio-3
$SA3/.venv/bin/python control/sa3_control/multi_adapter_onset_eval.py \
    --dora-ckpt /run/media/kim/Lehto/sa3_lora_runs/.../epoch=9-step=50.ckpt \
    --onset-ckpt /path/to/onset_head.pt \
    --style-ckpt /path/to/style_head_from_yesterday.pt \
    --reference-latent /run/media/kim/Lehto/latents_sa3/my_track_latent.npy \
    --densities "6,7,8,9,10" \
    --onset-gains "1.0,2.0,3.0" \
    --style-gains "1.0,1.5,2.0" \
    --out-dir /run/media/kim/Lehto/sa3_multi_eval_output
```

> [!TIP]
> **Performance:** Because DoRA is fully merged into the base weights and the audio VAE is bypassed via the `.npy` latent, this script is highly optimized for VRAM usage and should comfortably fit within your available memory during the bracketing runs.
