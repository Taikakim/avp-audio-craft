# Extraction checks: why did the SVD-extracted adapters glitch? (November 4, 2026)

**Question.** In July 2026, the full fine-tunes were extracted into LoRA and DoRA adapters at ranks 16, 64 and 128 (`eval/extract_svd_adapters.py`). All of them glitched by ear. The cause was put down to rank: the fine-tune's change is close to full rank, and rank 128 keeps 26 % of its energy. That rank finding stands. What was never isolated is whether the *glitch* comes from rank or from something the extraction got wrong.

**What the July extraction left out.**
- **Non-matrix tensors.** It carries only the weights of the 229 target modules. Every other tensor the fine-tune changed stays at base: the per-block AdaLN `to_scale_shift_gate`, the 64 memory tokens, RMSNorm and query/key-norm gains, feed-forward biases and the embeddings.
- **The real loader at full rank.** The full-rank change was never loaded through `load_lora` and rendered. The July check compared whole weight matrices (cosine 0.99), and the base weights dominate that number.
- **fp16 files.** `save_lora_safetensors` stores every tensor in fp16, so the July adapter files were fp16. For DoRA this includes the magnitude, whose rounding can be large next to a small change.
- **Differential attention.** SA3 medium uses it (`attn_kwargs.differential: true`). Each head outputs softmax(q·k)·v − softmax(q₂·k₂)·v with λ fixed at 1. Where the two maps nearly cancel, an uneven error between them is amplified. Rank 128 kept only 40–68 % of the attention change, against 92–96 % for the other layers.

## The script

`eval/xft_extraction_checks.py` works on one fine-tune checkpoint and does no training.

**Measure stage (CPU).**
- The change of every tensor against medium-base, summed per family, with targets and omitted tensors kept apart.
- The dtypes, and a **bf16 floor** per tensor: what rounding base to bf16 alone would show as a change. If the fine-tune was saved in bf16 against an fp32 base, rounding noise is full rank. That would inflate the July spectrum.
- Whether the checkpoint carries an EMA, and how far the EMA is from the online weights.
- One SVD per target module (the extractor's math and sign convention), giving the energy kept at each rank. For the fused attention projections it also gives the error of each output block (q, k, v, q₂, k₂).

**Render stage (GPU).** The variants are rendered with fixed prompts and seeds (24 steps, guidance 6, 30 s, bf16, as the forge defaults). Each render saves a wav and its latents.

The **probe** is the main number. Every DiT call of the fine-tune's own render is recorded, then replayed through each variant on exactly the same inputs. `rel_change` is the variant's output error divided by the base model's error, both against the fine-tune: 0 means the fine-tune itself and 1 means as far off as base. It is reported for the early, middle and late thirds of the trajectory. Renders diverge chaotically, so their latent distances only point the way. The probe compares like with like.

| Variant | Target weights | Everything else | Checks |
|---|---|---|---|
| `fullft` | fine-tune | fine-tune | The reference. Its replay error is the noise floor. |
| `base` | base | base | |
| `matrices_only` | fine-tune | base | **Check 2:** a perfect extract of the 229 modules. |
| `nonmatrix_only` | base | fine-tune | The omitted part on its own. |
| `all_r{R}` | rank R | base | The July LoRA, merged in weight space. |
| `all_r{R}_plus_nonmatrix` | rank R | fine-tune | Does copying the omitted tensors rescue rank R? |
| `attn_r{R}` | attention rank R, the rest fine-tune | fine-tune | **Check 4:** the attention cut alone. |
| `nonattn_r{R}` | attention fine-tune, the rest rank R | fine-tune | Its complement. |
| `loader_{lora,dora}_full_fp16`, `loader_dora_full_fp32` | full-rank extract through `load_lora` | base | **Check 3:** should match `matrices_only` (the twin column). |
| `loader_lora_r{R}`, `loader_dora_r{R}` | the July files rebuilt (fp16) through `load_lora` | base | The LoRA should match `all_r{R}`. |

## Run (desktop)

Use one fine-tune: the spectrum run, the goa T=256 fine-tune at the July pick. Its path comes from the extractor's manifest:

```
cd <avp-audio-craft checkout on feature/xft-extraction-checks>
CKPT=$($PY -c "import sys; sys.path.insert(0, 'eval'); import extract_svd_adapters as x; \
  print(x._ckpt_path('fullft_goa_t256', x._fullft_labels()['fullft_goa_t256']))")
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE $PY eval/xft_extraction_checks.py \
  --ckpt "$CKPT" --out $RUNS/xft_checks/fullft_goa_t256 --ranks 16,128
```

Run `--stage measure` first if a short CPU-only pass is wanted. It writes `measure/` and prints the family table. The default `--stage all` then renders.

**Resources (estimates, not measured).**
- **RAM.** The base in fp32, the fine-tune, and the full-rank factors (about 8 GB) are all in memory at once. Plan for about 40 GB of RAM at the adapter-writing peak.
- **GPU.** The full-rank loader variants wrap every Linear in the model at rank 1 536, which adds several GB of GPU memory.
- **Out of memory.** If a full-rank variant runs out of memory, skip it with `--variants '^(?!loader_.*full)'` and report that it was skipped.
- **Time.** The SVD pass is one CPU SVD per module, the same work as one July extraction. There are 18 variants with 6 renders each.

**Outputs.**
- `measure/`: `families.json`, `tensors.csv`, `svd_modules.csv` and `attn_blocks.csv`.
- `render/<variant>/`: the wavs and latents, plus `render/report.md` and `report.json`.
- `measure/adapters/`: the rebuilt adapter files.

## Reading the results

| If | Then |
|---|---|
| A `loader_*_full` row's twin is well above `fullft`'s replay floor in fp32 | **The loader or the file layout has a bug.** This is check 3. |
| fp32 matches its twin but the fp16 row does not, mainly `loader_dora_full_fp16` | **The fp16 file format is a cause**, for example the DoRA magnitude rounding. |
| `matrices_only` has a large `rel_change` or glitches by ear | **The omitted tensors are a cause.** `families.json` names which family carries their change. |
| `attn_r128` is far worse than `nonattn_r128` | **The attention cut is the fragile part**, consistent with differential attention. `attn_blocks.csv` shows whether q₂/k₂ lose more than q/k. |
| `all_r128_plus_nonmatrix` sounds clean where `all_r128` glitches | Rank 128 plus the copied tensors is a usable partial extract. |
| Many tensors sit under 2× the bf16 floor, and the dtypes are bf16 against fp32 | Part of the July spectrum is rounding noise. Recompute the spectrum before quoting the rank numbers again. |
| None of the above | The July verdict holds: the glitch is the rank. |

The ear decides; the numbers point to where to listen. Listen to `matrices_only`, `all_r128`, `all_r128_plus_nonmatrix`, `attn_r128` and `nonattn_r128` against `fullft` on the same prompt and seed. Do it blind if possible.

The Muon write-up's sentence that "the extraction itself was correct" waits for these results.

## Tested and not tested

**Tested on CPU** (`eval/tests/test_xft_extraction_checks.py`, 14 tests):
- the family rules, and the SVD (matches the extractor; full rank is exact);
- the per-block errors, padding and variant composition, and the measure summary;
- the full-rank extract through the real `load_and_apply_loras` on a tiny model, for LoRA and DoRA in fp32 and fp16, including padding past a module's own rank;
- the whole render stage end to end on a fake model: the replay is deterministic, base reads 1.0, and the loader variants match their twins.

**Not tested:**
- the real model (medium-base download, GPU), memory and time;
- whether the probe hook sees the real DiTWrapper's calls (the script stops if it records none);
- the real checkpoint's key layout beyond the coverage gate it shares with the extractor.
