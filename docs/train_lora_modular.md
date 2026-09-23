# `train_lora_modular.py` — the operator's manual

*Every command-line option of `stable-audio-3/scripts/train_lora_modular.py`: what it does, its
default, the values we have actually tried, and what to expect if you move it. Written 2026-09-23 for
running training WITHOUT an agent in the loop. `Misc/check_train_manual.py` fails if a flag exists in
the script but not here — run it after changing the script's options.*

**How to read the "tried" column.** *Tested* = used in a run that was listened to and judged good.
*Tried* = run once, result noted. *Untested* = nobody has run it on audio; the description is what the
mechanism is designed to do, not a measured effect. Most ranges are untested — when you explore one,
change **one** thing against a run you already know, and write the verdict down (§8).

---

## 1. What this trainer is

It fine-tunes a small adapter (LoRA / DoRA) on top of SA3 `medium-base`, reading **pre-encoded
latents** (`.npy` files — see `docs/data.md` for which stores are trainable), and optimises it with our
**modular optimizer**: a pipeline of switchable mechanisms (momentum → orthogonalisation → row
normalisation → Schedule-Free averaging, plus optional extras). It renders demo clips at chosen steps
while training, and writes `run_meta.json` into the run folder so the run explains itself later.

Use `train_lora.py` instead for live-audio training (`--data_dir`), control heads, or the older
recipes; this one is the optimizer test bench.

## 2. Known-good starting points (copy, then change one thing)

Always from the SAO root, with `export` (a bare `VAR=x && python` does **not** reach Python):

```
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 && cd /home/kim/Projects/SAO
```

**A. The 300-track audition** (`audition_160ep_2026-09-22-b` — clean at every milestone, velocity in
band, your verdict: "very clean, small background sounds better defined"; ~2 h):

```
.venv/bin/python stable-audio-3/scripts/train_lora_modular.py --subset300 --frames 256 --model medium-base --rank 128 --lora_alpha 128 --adapter_type dora-rows --name MYRUN --output-dir /run/media/kim/Mantu/sa3_lora_runs --batch-size 32 --num-workers 10 --epochs 160 --lr 5e-4 --warmup-steps 75 --optimizer modular --modular-lmo-poly cubic5 --modular-schedule-free --modular-sf-c-warmup 75 --modular-sf-r 1.0 --modular-wd 0.02 --modular-wd-overtraining --eval_demos --eval_milestones 240 480 720 960 1200 1440 --checkpoint_every 100000 --purpose '...' --hypothesis '...' 2>&1 | tee /tmp/MYRUN.log
```

**B. Three corpora** (`goa3_avp_r256_2026-09-23`, rank 128 despite its name; "quite good, moving in
a good direction" at steps 1268–2536, but **it went NaN at ~step 6900**: best checkpoint step 5072. Cause:
small DoRA magnitudes crossed zero, §5b `--modular-magnitude-update`. Retry with that flag set to
`multiplicative`, and/or lr 5e-4, before trusting the full 10144 steps; ~5.7 s/step):

```
.venv/bin/python stable-audio-3/scripts/train_lora_modular.py --encoded_dir /home/kim/Projects/latents_sa3,/run/media/kim/Kosmos/latents_avp,/run/media/kim/Kosmos/latents_goa_bigset --caption_sidecar ,/home/kim/Projects/SAO/lumi/avp_captions_tiered.json,/run/media/kim/Kosmos/latents_goa_bigset/goa_archive_caption_sidecar.json --caption_probs "0,0.9,0.1;0,0.9,0.1;0.5,0.5,0" --frames 256 --model medium-base --rank 128 --lora_alpha 128 --adapter_type dora-rows --name MYRUN --output-dir /run/media/kim/Mantu/sa3_lora_runs --batch-size 32 --num-workers 10 --steps 10144 --lr 6e-4 --warmup-steps 75 --optimizer modular --modular-lmo-poly cubic5 --modular-schedule-free --modular-sf-c-warmup 1000 --modular-sf-r 1.0 --modular-wd 0.02 --modular-wd-overtraining --eval_demos --eval_milestones 1268 2536 3804 5072 6340 7608 8876 10144 --checkpoint_every 100000 --purpose '...' --hypothesis '...' 2>&1 | tee /tmp/MYRUN.log
```

**Always pass `--eval_demos`.** Without it an older demo path fires at step 1 and crashes on a
torchcodec import. **Always pass `--lr`** — its default (5e-6) is an AdamW-era value that leaves the
modular optimizer almost standing still.

### Before you launch
1. `rocm-smi --showpids` — is anything else on the GPU? Two jobs at once slow both and make the
   desktop stutter.
2. Disk: each rank-128 checkpoint is ~2.7 GB (`df -h /run/media/kim/Mantu`).
3. Milestones on epoch boundaries (§6) so checkpoints compare across runs.

## 3. Data and captions

| flag | default | what it does / range |
|---|---|---|
| `--encoded_dir` | — | One latent folder, or several comma-separated. Each folder is one *source*. Which folders are trainable: `docs/data.md`. |
| `--subset300` | off | Shortcut for the canonical 300-track goa subset (`latents_sa3_subset300`). Replaces `--encoded_dir`. Note: only ~42% of it is 1990s by release year. |
| `--caption_sidecar` | none | Caption file per source, comma-separated **in `--encoded_dir` order**; an empty entry keeps that source's stored prompts. Needed for `latents_avp` (its stored prompts are just the artist name) and `latents_goa_bigset` (stored prompt is the word `None`). |
| `--caption_probs` | `0,0.9,0.1` | Probability of each caption tier t1/t2/t3 (t1 short tags, t2 Granite-style description, t3 long Music Flamingo prose). One tuple for all sources, or `;`-separated per source. Goa bigset: T1 70% genre-correct, T2 48%, T3 1.2% ⇒ use `0.5,0.5,0`. |
| `--track_type_prob` | 0.0 | Chance of prefixing `TrackType: Music, VocalType: Instrumental, ` — the format the base model saw ~50% of the time. 0.4–0.5 stays in-distribution. *Untested here.* |
| `--source_weights` | equal per item | Relative sampling weight per source (comma-separated). Default: every *item* equally likely, so big sources dominate (bigset ≈ 62% of run B). `1,2,0.5` evens run B out to ~35/31/34%. |
| `--frames` | none | Training window length in latent frames (multiple of 256; 10.77 frames/s). **256 = 23.8 s** (what we use), 1024 = 95 s. Longer windows = more memory, more long-range structure per sample. Cropped at a random position from each 380 s item. |
| `--duration` | 380 | Same as `--frames` but in seconds; `--frames` wins if both are given. |

**Caption dropout:** 10% of prompts are blanked for classifier-free guidance, automatically (not a
flag). **What to check in the log:** one `[captions] source N ... audit of 200: X rejected, Y
distinct prompts` line per source. 0 rejected + many distinct = healthy. A `WARNING` = that source would
train on a placeholder or a constant label — stop and add a sidecar.

## 4. The adapter

| flag | default | what it does / range |
|---|---|---|
| `--rank` | 128 | Size of the adapter. Higher = more capacity to move away from the base model, more memory, bigger checkpoints (~2× per doubling). We use 128; 256 untested with this optimizer. |
| `--lora_alpha` | = rank | Output scale is alpha/rank. Keep alpha = rank (scale 1) unless you know why. |
| `--adapter_type` | `dora-rows` | `dora-rows` (= `dora`): LoRA plus a learned per-output-neuron magnitude — our standard. `dora-cols`: legacy per-input variant. `bora`: magnitude on both axes. `lora`: no magnitude. |
| `--dropout` | 0.0 | Dropout inside the adapter. Untested. |
| `--include` / `--exclude` | all | Name SUBSTRINGS selecting which layers get an adapter (not regex). Default = every eligible layer (229 on medium). E.g. `--exclude to_global_embed global_cond_embedder to_timestep_embed` leaves the global-conditioning path untouched. |
| `--lora_checkpoint` | none | Start from an existing adapter's weights (optimizer starts fresh). |

## 5. The optimizer

### 5a. Basics

| flag | default | what it does / range |
|---|---|---|
| `--optimizer` | `modular` | `modular` = this manual. `fusion` = older FusionOpt (mona+ns5+normuon+sf). `adamw`, `lion` = classic baselines (need their own LR: our AdamW LoRA runs used ~5e-5–1e-4). |
| `--lr` | **5e-6 (too low — always set it)** | Step size. Modular: **5e-4 tested** (run A). **6e-4 in run B was clean to step 5072, then NaN at ~6900** (magnitude zero-crossing, not LR alone). Higher = the adapter moves further from the base sooner; the failure mode is long (48 s) renders diverging to NaN while training loss still looks fine. ≥1e-3 not validated. |
| `--warmup-steps` | 0 | Linear LR ramp at the start. 75 tested. Protects the first steps, when B is still near zero. |
| `--weight_decay` = `--modular-wd` | 0.01 | Pulls the adapter back toward zero, i.e. toward the base model's sound. **0.02 tested.** Higher = more conservative, stays closer to medium-base; lower = drifts further. |
| `--modular-wd-overtraining` | off | Grows weight decay as √(epochs) (Everett & Qiu 2026) — 4× by epoch 16, 12.6× by epoch 160. Tested on (both runs). Suspected of pulling long runs back toward the base's modern-psy sound — *hypothesis, untested*; the test is one run without it. |
| `--gradient_clip_val` | 1.0 | Caps the global gradient size each step. Leave it. |
| `--modular-beta1` | 0.9 | Momentum: how much of past gradients carries into the step. Higher (0.95) = smoother, slower to turn; lower = more reactive, noisier. Only 0.9 tested. |

### 5b. The mechanisms (mix and match)

The mechanism audit (§7) tells you, during the run, whether each one you switched on is actually doing
anything — several have turned out to be inert in practice.

| flag | default | what it does | tried |
|---|---|---|---|
| `--modular-ns-poly` (= `--modular-lmo-poly`) | `quintic` | How the update is orthogonalised (Muon's core step: every direction of the update gets equal size). `cubic5` = the variant used in every good run. `cubic` = cheaper, less exact. | cubic5 tested |
| `--modular-normuon` / `--modular-no-normuon` | on | Normalises each output neuron's update to similar size, so no single neuron runs away. | tested, ACTIVE |
| `--modular-normuon-beta` | 0.95 | Memory of that per-neuron normalisation. Only 0.95 tested. | — |
| `--modular-schedule-free` / `--modular-no-schedule-free` | on | Instead of an LR schedule, the weights you render are a running **average** of the training trajectory — very smoothing. | tested, ACTIVE |
| `--modular-sf-c-warmup` | 2 × warmup | Steps of **undamped** training before averaging begins. Guidance: 5–20% of the run (75 of 1440; 1000 of 10144). Must be well below the total step count, or averaging never starts (the audit warns). Longer = more freedom early, the "switch the damping on later" idea. | 75, 1000 tested |
| `--modular-sf-r` | 1.0 | How strongly the average favours recent weights. Higher r = less smoothing, more like the latest weights. Only 1.0 tested. | — |
| `--modular-lora-a-lr-mult` | 1.0 | Extra step size for the adapter's *input* half (A). At 1.0, A barely moves all run (99% unchanged) — the adapter listens to a random slice of its input. 20× made A rotate but also doubled the total weight change and one 48 s render went NaN. Try 3–5 if exploring. | 20 tried |
| `--modular-magnitude-update` | `additive` | How DoRA magnitude scalars (one per output row) move. `additive` = fixed-size steps, the same absolute amount for every scalar — this walked the small global-conditioning magnitudes (≈0.13) through zero and caused the NaN in `goa3_avp_r256_2026-09-23`. `multiplicative` = each step changes a scalar by the same *fraction* of its own value (a step in log m), so small ones move as carefully as large ones and none can go negative. | multiplicative: unit-tested only, not yet run |
| `--modular-radial-brake` | 1.0 (off) | Each step, keep only this fraction of any growth in weight size (0.8 = keep 80%). Brakes runaway growth. | tried by Antigravity, not listened |
| `--modular-escape-velocity` (= `--modular-ev`) | off | Prodigy-style automatic step enlargement. **Inert in our runs** (the multiplier never left 1.0) and adds ~0.6 GB to every checkpoint. | inert |
| `--modular-ev-beta` / `--modular-ev-max` | 0.999 / 2.0 | Its memory and its maximum multiplier. | — |
| `--modular-snr-gate` | off | Shrinks the step when the gradient looks like pure noise. Never run. | untested |
| `--modular-split-qkv` / `--modular-no-split-qkv` | split | Treat the fused attention query/key/value matrix as separate blocks when orthogonalising. Leave on. | default |
| `--modular-split-adaln` / `--modular-no-split-adaln` | split | Same for the fused conditioning (AdaLN) emitters. Leave on. | default |

### 5c. Whitening (experimental — never run on audio)

Whitening reshapes each update by the measured curvature before orthogonalising (the Mousse idea). The
code runs; nobody has listened to a result. Test it as its own A/B against a known recipe.

| flag | default | what it does |
|---|---|---|
| `--modular-whitening` | `none` | `shampoo` = Kronecker-factor whitening, one-sided on the narrow side by default. `soap` = a rotated variant that is **not** real SOAP despite the name. |
| `--modular-precond-alpha` | 0.125 | Strength of the whitening (curvature exponent); 0.125 per the Mousse paper's ablation, 0.25 = classic Shampoo. |
| `--modular-beta-precond` | 0.95 | Memory of the curvature estimate. |
| `--modular-precond-freq` | 10 | Recompute the curvature every N steps. 1 = every step (slow). |
| `--modular-no-precond-bottleneck` | (bottleneck on) | Whiten BOTH sides. Not viable on our shapes: one 12288-wide factor takes 7.2 s per step. |

### 5d. Variance-Aware Dynamic Dampening (VADD)

Guards against the latent scale drifting upward (the drone/loud failure of earlier full fine-tunes).
**Everything here is off unless `--var-dampening` is set.**

| flag | default | what it does |
|---|---|---|
| `--var-dampening` | off | Threshold on the latent standard deviation (1.20 tried). Turns on the two tiers below. |
| `--var-barrier-weight` | 0.1 | Tier 1: a training penalty when a latent channel's spread exceeds the threshold. Observed active (small, ~0.002). |
| `--var-damp-opt` / `--var-no-damp-opt` | on (when VADD on) | Tier 2: shrink the optimizer step while the spread is above threshold. Observed inert in the runs we audited. |
| `--var-damp-power` | 1.0 | How hard tier 2 shrinks: factor (threshold/spread)^p. |
| `--var-wd-boost` | 0.0 | Extra weight decay during high-spread episodes. Untested. |
| `--demo-latent-clamp` | off | Render-time only: cap a demo latent's spread before decoding (e.g. 1.20). The crackling clips we scanned had spread 1.3–1.4, so this is the flag aimed at them; untested on them. Does not change training. |
| `--demo-cfg-rescale` | 0.0 | Render-time CFG rescale φ (0.7 is the literature value) — tames over-saturated guidance. Untested. |

## 6. Length, batch, checkpoints, demos

| flag | default | what it does / range |
|---|---|---|
| `--steps` | 10000 | Total optimizer steps. |
| `--epochs` | none | Alternative to `--steps`; wins if given. |
| `--batch_size` | 8 | Items per step. 32 tested at rank 128 (fits in 16 GB). Out of memory → halve it and double the next one. |
| `--accumulate_grad_batches` | 1 | Add up N batches before each step (effective batch = batch × N) without the memory. Our optimizer's step size does NOT grow with batch, so bigger batches mainly give a cleaner direction and fewer steps per hour. |
| `--base_precision` | bf16 | Precision of the frozen base. Leave it. |
| `--seed` | 42 | Same seed + same data = same data order and noise, so two runs differing in one flag are directly comparable at the same step. |
| `--num_workers` | 8 | Data-loading processes; 10 used. |
| `--eval_demos` | off | **Always on.** Renders the demo clips at each milestone (async decode, ~30 s per milestone). |
| `--eval_milestones` | 100 500 1000 2000 3000 | Steps at which a checkpoint is saved **and** 6 clips rendered. Put them on epoch boundaries: steps per epoch = ⌊items ÷ batch⌋, then ÷ accumulation rounded up (run B: 20316 ÷ 32 = 634). |
| `--eval_num_prompts` | 3 | Prompts per milestone (each rendered at 20 s and 48 s). |
| `--eval_continuations` | off | Also render long continuations. Slow. |
| `--checkpoint_every` | 500 | Lightning's own periodic checkpoint. Set **100000** when using milestones — otherwise two writers produce duplicate ~2.7 GB files. |
| `--demo_every` / `--no_demos` | 2000 / off | The older demo path. Irrelevant with `--eval_demos`. |
| `--loss_guard_threshold` | 1.0 | Abort and save if an epoch's mean loss is above this or not finite. These latents' loss floor is ~0.75–0.80. |
| `--resume_ckpt` | none | Continue a run from a full checkpoint (optimizer state included). |

## 7. Logging, metadata, probes — and reading the log

| flag | default | what it does |
|---|---|---|
| `--name` / `--save_dir` (= `--output-dir`) | `modular_test` / none | Run folder = `<output-dir>/<name>/`. |
| `--logger` | `wandb` | `wandb`, `csv`, or `None`. W&B asks for a project on a terminal, offering the last one; unattended it reuses it. If W&B fails it falls back to CSV in the run folder. |
| `--wandb-project` | remembered | Skip the question. |
| `--log_every` | 1 | Metric logging cadence in steps. |
| `--purpose` / `--hypothesis` / `--run-notes` | asked | Written to `run_meta.json`. Say what question the run answers and what result would end it. |
| `--cov-probe` / `--cov-probe-snaps` / `--cov-probe-every` | off / 64 / 4 | Research probe: measures the gradient covariance spectrum (decides whether a low-rank whitening sketch could work). Leave off for normal runs. |

**What the log tells you:**
- `[captions] ...` at startup (§3), then `[dataset] N samples from K source(s)` — check N.
- `[run_meta] wrote ...` — the run documents itself; `status` becomes `done` or `crashed` by itself.
- `[MECHANISM AUDIT]` every 500 steps and at the end: `ACTIVE` = the mechanism changes the step;
  `INERT` = it is switched on but doing nothing (don't credit it for the sound). Warnings at startup
  flag flags that can never matter (e.g. VADD options without `--var-dampening`). Silence with
  `SA3_MECHANISM_AUDIT=0`.
- `[LOSS MONITOR]` every 10 **epochs** — on a big dataset that is thousands of steps; the per-step loss
  is in W&B.
- `[DEMO WARNING] ... NaN/Inf` = a render diverged. One clip in six can happen on rare prompts; several
  = the LR or a multiplier is too high.
- `HIPBLAS_STATUS_NOT_SUPPORTED ... calling cublas instead` — harmless fallback.

## 8. After the run — do it yourself

All from the SAO root with the SAO venv; no GPU needed, safe while another run trains.

```
# 1. Clip health: crackle (sample jumps), NaN, latent spread per clip
.venv/bin/python eval/demo_clip_scan.py /run/media/kim/Mantu/sa3_lora_runs/MYRUN

# 2. Trajectory: how far and how fast the adapter moved, and whether it kept a direction
.venv/bin/python control/sa3_control/checkpoint_trajectory_stats.py --ckpt-dir /run/media/kim/Mantu/sa3_lora_runs/MYRUN --label MYRUN --epoch-steps STEPS_PER_EPOCH --glob 'step=*.ckpt'
#    -> checkpoint-stats/MYRUN_trajectory.{md,json,png}

# 3. Wasted "sideways" motion of the adapter halves (A/B gauge drift)
.venv/bin/python eval/lora_gauge_drift.py /run/media/kim/Mantu/sa3_lora_runs/MYRUN --out checkpoint-stats/MYRUN_gauge.json
```

**Reading them:**
- **Clip scan:** 0–5 jumps = clean; hundreds = audible crackle. Latent spread (z0std) ~0.9–1.1 is
  healthy; 1.3+ went with every crackling clip so far.
- **Trajectory velocity** (the `velocity` column ÷ steps between checkpoints × 1000): **30–50 per 1000
  steps is the band our good-sounding runs sat in**; the run that collapsed rhythm was at 142. Falling
  velocity + `step_cos` rising toward 0.7+ = settling into a direction.
- **Gauge drift:** `gauge_frac` is the share of each step spent moving A and B in a way that changes
  nothing audible. ~2% is chance; 12% is where our runs end; if it climbs well past that on a long run,
  consider freezing or down-weighting A.

**Record your verdict** in the run's `run_meta.json` (`kim_feedback`), e.g.:
```
python3 -c "import json,sys;p=sys.argv[1];d=json.load(open(p));d['kim_feedback']=sys.argv[2];json.dump(d,open(p,'w'),indent=1)" /run/media/kim/Mantu/sa3_lora_runs/MYRUN/run_meta.json 'step 5072: ...'
```

## 9. Traps, in one place
- `--lr` default is useless for `modular`; always set it.
- No `--eval_demos` ⇒ crash at step 1 (torchcodec).
- `VAR=x && python` does not export; use `export VAR=x && ...`.
- `latents_avp` without its sidecar trains on the artist name; `latents_goa_bigset` without its sidecar
  is rejected item by item (the audit warns).
- `--checkpoint_every` left at 500 with milestones ⇒ duplicate checkpoints.
- The run NAME is free text — `goa3_avp_r256_2026-09-23` is rank 128. Trust `run_meta.json`, not names.
