# MP3-bitrate training A/B — experiment design + staging runbook

Status: **staged, not launched.** Provenance scan done, corpus-staging script +
training sbatch written. Kim runs the staging commands (agents don't rsync); nothing
here launches training.

## Question
Does the *source bitrate* of the training audio measurably affect SA3 full-FT
generation quality? Train five identical models on the SAME tracks encoded at
FLAC / 320 / 256 / 192 / 128 kbps and listen for where source degradation (HF loss,
transient smear) starts showing up in generations — and where it stops mattering.

For a clean A/B the FLAC arm must be genuine lossless. **Source = Tidal `Goa Dataset`
FLAC** — Kim confirms it's pulled from Tidal, i.e. genuine lossless, NOT FLAC
transcoded from MP3. So the corpus is trusted by provenance; the scan's job is only
to flag the rare lossy-master exception (a remaster sourced from lossy, a hard
mastering lowpass), not to distrust the set. The verified-LOSSLESS subset of Goa
Dataset IS the reference.

## Prerequisite — verified-lossless subset (done)
`sa3_control_runs/analysis/goa_flac_provenance_2026-08-05/` (Mantu eval drive) scans
every FLAC, decodes 30 s from the track middle, computes a Welch power spectrum,
finds the HF brickwall cutoff + rolloff sharpness, and classifies each file
LOSSLESS / MP3-LIKE / DARK-INCONCLUSIVE. Method distinguishes a hard MP3 cliff-to-a-
deep-floor from a genuinely dark psytrance mix (gradual rolloff, shallow floor).
Conservative: a sharp cliff to a deep floor below ~21.3 kHz (the MP3-320 lowpass
zone) is rejected as lossy even at a high cutoff — a false positive silently ruins
the reference arm. (Limitation: a lossy encoder that does NOT lowpass — rare
Fraunhofer / older 320 CBR — is spectrally indistinguishable from lossless and can't
be caught this way. With a Tidal origin this risk is negligible.)

Outputs (primary corpus = Goa Dataset):
- `goa_dataset_verified_lossless.txt` — the reference filelist (feeds the A/B).
- `goa_dataset_provenance.json` — per-file {path, cutoff_khz, class, rolloff, stopband}.
Secondary corpus (Goa_Separated full_mix.flac) also scanned for comparison:
- `goa_flac_verified_lossless.txt`, `provenance.json` / `goa_flac_provenance.json`.

## The five corpus versions
Built by `eval/flac_bitrate_transcode.py` from the verified-lossless filelist:

| arm      | source encode              | dir        |
|----------|----------------------------|------------|
| flac     | verbatim copy (lossless)   | `flac/`    |
| mp3_320  | libmp3lame CBR 320k        | `mp3_320/` |
| mp3_256  | libmp3lame CBR 256k        | `mp3_256/` |
| mp3_192  | libmp3lame CBR 192k        | `mp3_192/` |
| mp3_128  | libmp3lame CBR 128k        | `mp3_128/` |

All five hold the SAME tracks in the SAME relative layout; **source bitrate is the
only variable.** MP3 arms are decoded back to PCM at train time (never fed as MP3) —
the point is that lossy encoding has permanently removed detail before the model
sees the audio. Each clip gets an identical caption `.txt` sibling (below), so
train_lora's `--data_dir` caption lookup is uniform across arms.

## Resolved decisions
- **(a) Learning rate = `8e-5`** (Kim confirmed; the earlier "4e1"/"lr4e1" was a
  typo). Our validated full-FT rate; identical across all five arms.
- **(b) N = full verified-lossless subset by default**, but this is a controlled
  A/B so a subset is fine. `flac_bitrate_transcode.py --limit N` caps it; **DESIGN
  cap ≈ 1200 tracks** to keep the 5× transcode + LUMI transfer manageable. The
  filelist is deterministically ordered, so `--limit 1200` is a stable prefix (same
  1200 tracks every arm).
- **(c) Captions = one consistent generic prompt.** `flac_bitrate_transcode.py`
  writes `"goa trance, psychedelic"` (override with `--caption`) into a `.txt`
  sibling of every clip in every arm. Since bitrate is the only variable under test,
  captions only need to be *identical across arms*, not individually accurate —
  train_lora's `--data_dir` `caption_metadata_fn` reads the per-clip `.txt`.

## Arm training config (in the sbatch)
Full fine-tune, fusion (SF-NorMuon), EMA, T256, bs4, **20 epochs**, fp32, seed 1,
`--checkpoint_every_epochs 4`, `--no_demos --logger csv`. Identical for all arms;
only `--data_dir` (the bitrate corpus) differs. See
`lumi/sbatch/flac_bitrate_ab.sbatch` — 1 node / 8 GCD, 5 arms one per GCD (GCDs 5-7
idle), copied from the `precision_ladder.sbatch` independent-trainer pattern
(SLURM_JOB_NAME=bash + distinct MASTER_PORT per GCD so arms don't collide on the DDP
port; per-GCD /tmp MIOpen/Triton dirs).

## Staging runbook — commands FOR KIM (agents don't rsync)
Let `BIGSET_LOCAL` = local staging root, `VL` = the verified-lossless filelist.
```bash
# 0. paths
VL=/run/media/kim/Mantu/sa3_control_runs/analysis/goa_flac_provenance_2026-08-05/goa_dataset_verified_lossless.txt
BIGSET_LOCAL=/run/media/kim/Mantu/sa3_control_runs/data/goa_bitrate_ab

# 1. build the 5 corpus arms locally (idempotent; ~1200-track cap; generic captions)
/home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/eval/flac_bitrate_transcode.py \
    --filelist "$VL" --out-root "$BIGSET_LOCAL" \
    --limit 1200 --workers 12 --caption "goa trance, psychedelic"
#    -> $BIGSET_LOCAL/{flac,mp3_320,mp3_256,mp3_192,mp3_128}/ each with .mp3/.flac + .txt

# 2. rsync the 5 arms to LUMI scratch (the sbatch's BIGSET_DIR default)
rsync -aP "$BIGSET_LOCAL"/ \
    akekim@efp.lumi.csc.fi:/scratch/project_465003186/data/goa_bitrate_ab/

# 3. make sure the repo on LUMI (/project/.../code) is current (train_lora.py + sbatch)
#    then submit — 5 arms, one per GCD, on one 8-GCD node:
ssh akekim@efp.lumi.csc.fi \
    'cd /project/project_465003186/code && sbatch lumi/sbatch/flac_bitrate_ab.sbatch'
#    override knobs if needed: BIGSET_DIR=... EPOCHS=... LR=... ARMS="mp3_192 mp3_128" sbatch ...
```
After the job: 5 run dirs under `/scratch/.../runs/flac_bitrate_ab/` with
`epoch=*.ckpt` (EMA rides as `diffusion_ema.ema_model.*`). Then render matched
(prompt, seed, cfg) cells from all 5 and build a same-playhead A/B/X audition page.

## Files
- `eval/flac_bitrate_transcode.py` — builds the 5 corpus arms + caption sidecars (idempotent, `--limit`).
- `lumi/sbatch/flac_bitrate_ab.sbatch` — the 5-arm training job (NOT launched).
- `eval/flac_bitrate_ab_DESIGN.md` — this file.
- provenance outputs — `sa3_control_runs/analysis/goa_flac_provenance_2026-08-05/`.
