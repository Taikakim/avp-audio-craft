#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-16)
# EXPERIMENTS E12 stage 2: the FiLM onset-density adapter under the ModularOptimizer at the full shipped length (54000 steps).
#   bash control/run_film_modular_full.sh <lr>
# Same recipe as control/run_film_modular_bracket.sh (= the shipped FiLM's args except optimizer/lr), saves every 5400 steps.
# Since 2026-10-16 'state' = EMA (0.999) and 'state_online' = the Schedule-Free average (the trainer's EMA-overwrite fix).
set -u
LR=${1:?usage: run_film_modular_full.sh <lr>}
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
ROOT=/run/media/kim/Mantu/sa3_control_runs/film_modular_full_20261016
NAME="film_modular_lr${LR}_s54000"
DIR="$ROOT/$NAME"
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO/control" || exit 2
mkdir -p "$DIR"
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE FiLM modular full run lr $LR (54k steps, ~6.5 h)" \
      "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
echo "$(date +%H:%M) GPU acquired"
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
cat > "$DIR/run_meta.json" <<EOF
{"purpose": "EXPERIMENTS E12 stage 2: the FiLM onset-density adapter retrained under the ModularOptimizer at the shipped length (54000 steps), lr $LR picked by eval/film_bracket_density_check.py (largest density spread at FiLM gain 1.0 among the bracket arms within the latent-level screen).",
 "hypothesis": "The modular-optimizer FiLM reaches at least the shipped FiLM's density range with less character drift and no extra saturation.",
 "kill": "density spread below the shipped FiLM's at matched gain, or more CLAP drift at matched spread",
 "status": "running", "started": "$(date -Is)",
 "recipe": {"optimizer": "modular", "mod_whitening": "shampoo", "lr": "$LR", "steps": 54000, "save_every": 5400, "ema": 0.999,
            "rest": "identical to the shipped FiLM onset_Fusion_lr1e-4_randomcrop (batch 1, crop 512, random crop, cfg dropout 0.1, warmup 300, seed 42, logit_normal t, scalar onset_density, control_dim 768, n_tokens 256, bf16)"},
 "dataset": {"encoded_dir": "/run/media/kim/Kosmos/latents/latents_sa3", "what": "goa corpus SA3 latents (5400 T=4096 crops), no augmentation"},
 "weights": "'state' = EMA 0.999, 'state_online' = Schedule-Free average, 'model_train' = raw iterate",
 "related": ["control/run_film_modular_bracket.sh", "eval/film_bracket_density_check.py", "EXPERIMENTS E12"],
 "result": null, "kim_feedback": null}
EOF
"$PY" sa3_control/train.py --encoded-dirs /run/media/kim/Kosmos/latents/latents_sa3 --model medium-base --precision bf16 \
    --crop-frames 512 --random-crop --batch 1 --optimizer modular --allow-uniform-lr --mod-whitening shampoo --ema 0.999 \
    --warmup-steps 300 --no-checkpoint --no-preencode-text --timestep-sampler logit_normal \
    --control-mode scalar --scalar-field onset_density --control-dim 768 --n-tokens 256 \
    --cfg-dropout 0.1 --num-workers 4 --seed 42 --no-export-onnx-on-finish \
    --lr "$LR" --steps 54000 --save-every 5400 --save-dir "$DIR" --run-name "$NAME" > "$DIR/train.log" 2>&1
echo "$(date +%H:%M) $NAME rc=$? (teardown aborts after saving are known); final: $(ls "$DIR"/riffer_final.pt 2>/dev/null || echo MISSING)"
