# DoRA/LoRA alpha-vs-rank audit — 2026-07-12

Question: is the rank sweep confounded by a fixed alpha (e.g. alpha=45 held constant while
rank varied), silently damping effective adapter scale s = alpha/rank at higher ranks?

## Where the numbers come from

- **Scale law in code:** `stable-audio-3/stable_audio_3/models/lora/model.py:38` —
  `self.scaling = lora_alpha / rank` (**linear** alpha/r, NOT alpha/sqrt(r)). Applied in
  `dora_forward` as `V = W_2d + scaling * lora_strength * delta` (lines 187–207), i.e. it
  weights the BA contribution inside the DoRA direction before row-norm + learned magnitude.
- **Default:** `stable-audio-3/scripts/train_lora.py:407` — `--lora_alpha` default `None`
  → line 188 sets `alpha = rank` (s=1). `--lr` default 1e-4 (line 482).
  The LUMI launcher `lumi/sbatch/dora_run.sbatch` never passes `--lora_alpha` → alpha=rank there too.
- **Per-run source:** last checkpoint of each run dir under `/run/media/kim/Mantu/sa3_lora_runs/`
  (torch.load, cpu) — every training ckpt carries a `lora_config` dict {rank, alpha, adapter_type, …};
  lr read from `optimizer_states[0].param_groups`. All runs are `dora-rows`.
  Cross-checked against wandb `config.yaml`/`wandb-metadata.json` under `stable-audio-3/wandb/` where present.

## Table

| run | rank | alpha | s = alpha/r | lr | notes |
|---|---|---|---|---|---|
| **goa 47s sweep (dataset: goa 47s latents)** | | | | | |
| sa3-goa-dora-47s | 16 | 16 | 1.00 | 1e-4 (default; no --lr in wandb args) | bs1; single ckpt, no opt state |
| sa3-goa-dora-47s-b4 | 16 | 16 | 1.00 | 1e-4 | bs4 |
| sa3-goa-dora-47s-b4-cont | 16 | 16 | 1.00 | 1e-4 | continuation |
| sa3-goa-dora-47s-r64 | 64 | 64 | 1.00 | 1e-4 | |
| sa3-goa-dora-47s-r128-adamw | 128 | 128 | 1.00 | 1e-4 | |
| sa3-goa-dora-47s-r128-fusion | 128 | 128 | 1.00 | 2e-4 | |
| sa3-goa-dora-47s-r128-fusion-caut | 128 | 128 | 1.00 | 1e-4 | train.log confirms rank=128, alpha=128.0 |
| **goa newstack / newcaptions / everything** | | | | | |
| dora16_goa_newstack_8ep | 16 | 16 | 1.00 | 2e-4 | |
| dora128_47s_newcaptions_5ep | 128 | 128 | 1.00 | 2e-4 | |
| dora128_newcap_continued_3more | 128 | 128 | 1.00 | 2e-4 | |
| dora128_newcap_continued_8ep | — | — | — | — | no ckpts on Mantu; skipped |
| dora128_everything_8ep_lr1x | 128 | 128 | 1.00 | 2e-4 | |
| dora128_everything_8ep_lr3x | 128 | 128 | 1.00 | 6e-4 | |
| dora128_everything_8ep_lr0.5x | — | — | — | — | no ckpts on Mantu; skipped |
| **avp family** | | | | | |
| dora16_avp_8ep | 16 | 16 | 1.00 | 2e-4 | |
| dora16_avp_familiarity_8ep | 16 | 16 | 1.00 | 2e-4 | |
| dora16_avp_freeform_8ep | 16 | 16 | 1.00 | 2e-4 | |
| dora16_avp_originals_64ep | 16 | 16 | 1.00 | 2e-4 | |
| dora16_avp_originals_densewin | 16 | 16 | 1.00 | 2e-4 | |
| dora16_avp_originals_earlyeps | 16 | 16 | 1.00 | 2e-4 | |
| dora16_avp_originals_win7 | 16 | 16 | 1.00 | 2e-4 | |
| dora16_glitchheal_5ep_2xlr | 16 | 16 | 1.00 | 2e-4 | exclude seconds_total |
| dora64_avp_tiered_lr1e4 | 64 | 32 | **0.50** | 1e-4 | ⚑ alpha≠r, ≠2r; = sqrt(16·64) |
| dora64_avp_tiered_lr2e4 | 64 | 32 | **0.50** | 2e-4 | ⚑ same |
| dora128adj_avp_8ep | 128 | 45 | **0.352** | 2e-4 | ⚑ alpha≠r, ≠2r; 45 ≈ sqrt(16·128)=45.25 |
| dora128adj_avp_8ep_final | 128 | 45 | **0.352** | 2e-4 | ⚑ same |
| dora128adj_avp_aug10_lr1e4 | 128 | 45 | **0.352** | 1e-4 | ⚑ same |
| dora256_avp_aug10_lr7e5 | 256 | 64 | **0.25** | 7e-5 | ⚑ alpha≠r, ≠2r; = sqrt(16·256); lowest lr too |
| **probes / misc** | | | | | |
| dora128_300trk (sub-run 59h2y4zo) | 16 | 16 | 1.00 | 1e-4 | ⚑ MISNAMED: folder says 128, ckpt says r16; 300trk dataset, 2026-06-01 probe |
| dora128_300trk (sub-run pzqv5mcw) | 16 | 128 | **8.00** | 1e-4 | ⚑ explicit `--lora_alpha 128` at r16 → s=8; aborted 380s-duration probe |
| soups_dora (14 merged ckpts) | 64 | 64 | 1.00 | — | soup; inherits parents' config |
| soups_dora_caut (3 merged ckpts) | 128 | 128 | 1.00 | — | soup; inherits parents' config |

(Other dirs under sa3_lora_runs — avp_board*, renders_*, chroma_*, a2a_*, newcap8_*, etc. —
are render/eval outputs with no training checkpoints; not applicable.)

## Conclusion

1. **The specific hypothesis is REFUTED:** alpha was *not* held constant across ranks. alpha=45
   appears only at r128; the avp rank arms used alpha = 16/32/45/64 at r = 16/64/128/256, i.e.
   alpha ≈ 4·sqrt(r) — a deliberate rank-stabilized (rsLoRA-style) schedule with alpha/sqrt(r) ≈ 4
   held constant ("adj"/"tiered" naming reflects this).
2. Since the code applies **linear** s = alpha/r, the avp arms have effective s = 1 / 0.50 / 0.352 / 0.25
   (r16→r256): rank-consistent under the rsLoRA lens, but monotonically damped (4/sqrt(r)) under the
   classic lens — the avp rank sweep is only "clean" if you accept rsLoRA scaling as the equalizer.
3. The **goa 47s sweep** (r16/r64/r128) is the opposite convention: alpha=rank everywhere → s=1 flat;
   internally consistent classically, but effective adapter magnitude grows ~sqrt(r) under the rsLoRA lens.
4. **Real confounds found:** (a) cross-family r128 comparisons — `dora128adj_avp_*` (alpha=45) vs any
   alpha=128 r128 run (goa/newcap/everything) differ by 2.84× adapter scale on top of dataset differences;
   (b) lr co-varies with rank in the avp sweep (r16@2e-4 … r256@7e-5), so the r256 arm is doubly damped
   (s=0.25 AND 0.35–0.7× the lr of other arms) — rank-vs-lr not separable there;
   (c) `dora128_300trk` is misnamed: it holds two r16 probes, one with s=8 (alpha=128 at r16).
5. Skipped for lack of checkpoints: `dora128_everything_8ep_lr0.5x`, `dora128_newcap_continued_8ep`.
   No run required guessing — every audited run's (rank, alpha) came from its checkpoint `lora_config`
   (lr from optimizer state; the two no-opt-state cases from wandb args/logs).
