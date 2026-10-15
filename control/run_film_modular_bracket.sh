#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-15)
# FiLM density adapter retrained under the ModularOptimizer: LR bracket (EXPERIMENTS E12, project direction 2026-10-15).
# The shipped FiLM (onset_Fusion_lr1e-4_randomcrop, FusionOpt lr 1e-4, 54k steps) is the reference. TRAINING.md D4: an lr
# never transfers across optimizer or net, and the modular optimizer has never trained a control adapter, so this is a
# short bracket that may only PRUNE losers (D25): lr 3e-4 / 1e-3 / 3e-3, 6000 steps each, saves every 2000 with EMA AND
# online weights (D6). The survivor gets the full 54k run (separate launch).
# Recipe = the shipped FiLM's own args (riffer_final.pt) except optimizer/lr/steps; env = control/run_control_train.sh's
# five fixes (that launcher is stale: venv path, Mantu mount, --encoded_dir flag, and it detaches each run).
# Waits for GHOST-NOTE's air queue to finish (/tmp/air_nosf.done), then needs the GPU lock AND free VRAM.
#   bash control/run_film_modular_bracket.sh        (run in background; exit = done)
set -u
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
MANTU=$(for p in /run/media/kim/Mantu /run/media/kim/Mantu2 /run/media/kim/Mantu1; do [ -d "$p/sa3_control_runs" ] && { echo "$p"; break; }; done)
ROOT=$MANTU/sa3_control_runs/film_modular_bracket_20261015
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO/control" || exit 2          # train.py resolves sa3_control from here (as run_control_train.sh does)
mkdir -p "$ROOT"

until [ -f /tmp/air_nosf.done ]; do echo "$(date +%H:%M) waiting for GHOST-NOTE's air queue"; sleep 300; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE FiLM modular LR bracket (3 x 6000 steps, ~2 h)" \
      "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
echo "$(date +%H:%M) GPU acquired"
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT

COMMON=(--encoded-dirs /home/kim/Projects/latents_sa3 --model medium-base --precision bf16
        --crop-frames 512 --random-crop --batch 1 --optimizer modular --mod-whitening shampoo --ema 0.999
        --warmup-steps 300 --no-checkpoint --no-preencode-text --timestep-sampler logit_normal
        --control-mode scalar --scalar-field onset_density --control-dim 768 --n-tokens 256
        --cfg-dropout 0.1 --num-workers 4 --seed 42 --no-export-onnx-on-finish)

# cheap first: a 3-step smoke run must pass before any arm spends 30 min (D31)
"$PY" sa3_control/train.py "${COMMON[@]}" --lr 1e-3 --steps 3 --save-dir "$ROOT/_smoke" --smoke > "$ROOT/_smoke.log" 2>&1
grep -q "smoke OK" "$ROOT/_smoke.log" || { echo "SMOKE FAILED, see $ROOT/_smoke.log"; exit 3; }
echo "$(date +%H:%M) smoke OK"

for LR in 3e-4 1e-3 3e-3; do
  NAME="film_modular_lr${LR}_s6000"
  DIR="$ROOT/$NAME"
  [ -f "$DIR/riffer_final.pt" ] && { echo "$NAME done, skipping"; continue; }
  mkdir -p "$DIR"
  cat > "$DIR/run_meta.json" <<EOF
{"purpose": "EXPERIMENTS E12: does the FiLM onset-density adapter train better under the ModularOptimizer? LR bracket arm, lr $LR (prune-only, TRAINING.md D25). Asked in session 2026-10-15.",
 "hypothesis": "One of lr 3e-4/1e-3/3e-3 trains stably at 6000 steps and reaches the shipped FiLM's density response with less character drift.",
 "kill": "all three arms diverge or show no density response at 6000 steps -> modular is not a fit for this adapter at these lrs",
 "status": "running", "started": "$(date -Is)",
 "recipe": {"optimizer": "modular", "mod_whitening": "shampoo", "lr": "$LR", "steps": 6000, "save_every": 2000, "ema": 0.999,
            "rest": "identical to the shipped FiLM onset_Fusion_lr1e-4_randomcrop args (batch 1, crop 512, random crop, cfg dropout 0.1, warmup 300, seed 42, logit_normal t, scalar onset_density, control_dim 768, n_tokens 256, bf16)"},
 "dataset": {"encoded_dir": "/home/kim/Projects/latents_sa3", "what": "goa corpus SA3 latents (5400 T=4096 crops + TIMESERIES companions), no augmentation"},
 "reference": "$MANTU/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_final.pt (FusionOpt lr 1e-4, 54k steps)",
 "weights": "riffer_step*.pt / riffer_final.pt: 'state' = EMA, 'state_online' = online (SF-averaged), 'model_train' = raw training iterate",
 "related": ["control/run_film_modular_bracket.sh", "docs/TRAINING.md", "EXPERIMENTS E7/E8"],
 "result": null, "kim_feedback": null}
EOF
  echo "$(date +%H:%M) start $NAME"
  "$PY" sa3_control/train.py "${COMMON[@]}" --lr "$LR" --steps 6000 --save-every 2000 \
      --save-dir "$DIR" --run-name "$NAME" > "$DIR/train.log" 2>&1
  rc=$?
  echo "$(date +%H:%M) $NAME rc=$rc; final: $(ls "$DIR"/riffer_final.pt 2>/dev/null || echo MISSING)"
done
echo "$(date +%H:%M) BRACKET DONE"
