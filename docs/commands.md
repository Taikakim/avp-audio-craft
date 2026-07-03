# Commands that actually get run

Copy-paste reference. All venv paths absolute (see `venvs.md`).

## mir — feature extraction

```bash
MIR=/home/kim/Projects/mir; PY=$MIR/mir/bin/python
# Full pipeline (config-driven)
$PY $MIR/src/master_pipeline.py --config $MIR/config/master_pipeline.yaml
# Whole-track 100 Hz timeseries → /run/media/kim/Lehto/timeseries/<track>.TIMESERIES.npz
$PY $MIR/src/spectral/whole_track_timeseries.py /run/media/kim/Mantu/ai-music/Goa_Separated --workers 4
# Audiobox aesthetics on a render dir (single-file mode; batch OOMs WavLM on 16 GB)
$PY -c "import sys; sys.path.insert(0,'$MIR/src'); from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics as a; print(a('clip.flac'))"
```

## stable-audio-tools — LatCH

```bash
SAT=/home/kim/Projects/SAO/stable-audio-tools; PY=$SAT/sat-venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE   # activate native CK flash-attn (SDPA→CK on sat-venv); MASTER §5
# Train a LatCH head (ship recipe — see training-findings.md)
$PY $SAT/scripts/train_latch.py --feature rms_energy_bass \
  --optimizer fusion --components ns5,normuon,sf --t-injection adaln_zero \
  --compile --hot-dtype bf16 --dim 256 --depth 4 --batch-size 64 --lr 3e-4 \
  --epochs 40 --seed 1 --save-best-only
#   whole-track targets:  --target-source whole_track --npz-root /run/media/kim/Lehto/timeseries
# Audition renders → renders/<set>/ (+ manifest.json + index.html)
$PY $SAT/scripts/render_audition.py
$PY $SAT/scripts/build_manifest.py        # regenerate manifest after adding clips
```

## stable-audio-3 — encode + LoRA

```bash
SA3=/home/kim/Projects/SAO/stable-audio-3; PY=$SA3/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE   # activate native CK flash-attn (30–100% faster); torch-2.10/2.12 venvs only — MASTER §5
# Pre-encode a flat dir (clip.flac + clip.txt prompts) with the SAME-L VAE
$PY $SA3/scripts/pre_encode_dataset.py --model same-l --data_dir DIR --output_path OUT --model_half
# Beat-aligned T=4096 dataset (the real one): manifest then encode
$PY /tmp/sa3_beat_manifest.py            # → /tmp/sa3_crop_manifest.csv (drops <380s)
$PY /tmp/sa3_encode_from_manifest.py     # → /home/kim/Projects/latents_sa3/ (.npy/.json/.TIMESERIES.npz — NVMe is now the sole copy, Lehto/latents_sa3 was removed 2026-07-03)
# LoRA finetune (MIOPEN_FIND_MODE=2 — mode 6 crashes the DiT!)
# Read latents from the NVMe mirror, not Lehto (removable drive starves the dataloader — MASTER §5).
MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=1 PYTORCH_TUNABLEOP_TUNING=1 \
  $PY $SA3/scripts/train_lora.py --model medium-base \
  --encoded_dir /home/kim/Projects/latents_sa3 \
  --rank 16 --adapter_type dora-rows --base_precision bf16 \
  --batch_size 1 --lr 1e-4 --steps 5000 --compile --demo_every 1500
#   tuning runs: add --steps 10 --no_demos
# Gradio UI (FA escape hatches if varlen misbehaves)
$PY $SA3/run_gradio.py            # --no-flash-attn / --no-flash-varlen
```

## GPU / system

```bash
rocm-smi --showmeminfo vram        # VRAM held (a job >12 GB blocks parallel work)
rocm-smi --showuse                 # util (misleading for IO-bound encodes)
pgrep -af train_                   # what's running
```
