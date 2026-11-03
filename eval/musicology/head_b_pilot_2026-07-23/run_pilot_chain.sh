#!/bin/bash
# Head B (melody_contour) local pilot chain — CONTINUITY, 2026-07-23.
# Spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md §2/§8.
#
# Phases: [wait+acquire .gpu.lock] -> VRAM guard -> GPU integration smoke (6 steps)
#   -> pilot train (T=512, ~799 melody crops, r128 dora-rows + melody conditioning,
#      lr 1e-4, 4 epochs, per-epoch saves) -> 8 pilot renders (4 motif-conditioned +
#      4 seed-matched null/rest) -> muscriptor transcription -> RELEASE lock ->
#   CPU scoring: clap (sat-venv) + mood (mir venv) + contour-adoption analyze (.venv).
#
# Doctrine notes (MASTER §5): rc captured on its OWN line everywhere ($(date) clobbers
# $?); artifact-count verification after every phase (never trust rc alone); measured
# free-VRAM gate, not pgrep; canonical absolute lock path; pid-aware with the chain's
# own long-lived $$.
set -u
cd /home/kim/Projects/SAO
D=eval/musicology/head_b_pilot_2026-07-23
LOG=$D/chain.log
VENV=/home/kim/Projects/SAO/.venv/bin/python
SAT_VENV=/home/kim/Projects/SAO/stable-audio-tools/sat-venv/bin/python
MIR_VENV=/home/kim/Projects/mir/mir/bin/python
SAVE_DIR=/run/media/kim/Mantu/sa3_control_runs/headb_melody_pilot_2026-07-23
LOCK=/home/kim/Projects/SAO/.gpu.lock
HANDLE=CONTINUITY-headb

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0
export MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4

release_lock () {
  python3 Misc/filelock.py release "$LOCK" --handle "$HANDLE" >> "$LOG" 2>&1
}

echo "=== $(date -Is) chain start (pid $$); waiting for $LOCK ===" >> "$LOG"
python3 Misc/filelock.py acquire "$LOCK" --handle "$HANDLE" --pid-aware --pid $$ --timeout 28800 >> "$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  echo "LOCK-FAIL rc=$rc" >> "$LOG"
  exit 3
fi
echo "=== $(date -Is) lock acquired ===" >> "$LOG"

# --- VRAM guard: proceed only when >9 GiB free, 3 consecutive 20 s polls (max 6 h) ---
# (6 h, not 30 min: observed 2026-07-23 — ghost-note released the lock while its
# model_matrix render campaign still held 11 GiB; the guard must outwait an unlocked
# GPU job, and holding the lock meanwhile is the safe posture.)
vram_free_gib () {
  rocm-smi --showmeminfo vram --json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)["card0"]
print((int(d["VRAM Total Memory (B)"])-int(d["VRAM Total Used Memory (B)"]))/2**30)'
}
ok=0; polls=0
while [ $ok -lt 3 ] && [ $polls -lt 1080 ]; do
  f=$(vram_free_gib || echo 0)
  if python3 -c "exit(0 if float('$f')>9.0 else 1)"; then ok=$((ok+1)); else ok=0; fi
  polls=$((polls+1))
  sleep 20
done
if [ $ok -lt 3 ]; then
  echo "VRAM-GUARD-FAIL: free VRAM never held >9GiB (last=$f GiB)" >> "$LOG"
  release_lock
  exit 5
fi
echo "=== $(date -Is) VRAM guard passed (free ${f} GiB) ===" >> "$LOG"

# --- Phase 1: GPU integration smoke — 6 steps, exact pilot config, bf16 ---
SMOKE_DIR=/tmp/headb_smoke_$$
mkdir -p "$SMOKE_DIR"
"$VENV" control/sa3_control/train.py \
  --encoded_dir /run/media/kim/Kosmos/latents/latents_sa3 --model medium-base --precision bf16 \
  --control-mode melody_contour --melody-dir /run/media/kim/Lehto/latents-all-backup/latents_sa3_melody \
  --melody-dropout 0.1 --cfg-dropout 0.1 --dora-rank 128 \
  --subset-tracks 0.02 --crop-frames 512 --batch 1 --grad-accum 2 --lr 1e-4 \
  --optimizer adamw --steps 6 --max-epochs 1 --save-every 999999 \
  --num-workers 2 --seed 42 --no-preencode-text --no-export-onnx-on-finish \
  --save-dir "$SMOKE_DIR" >> "$LOG" 2>&1
rc_smoke=$?
echo "gpu-smoke rc=$rc_smoke" >> "$LOG"
if [ $rc_smoke -ne 0 ] || [ ! -f "$SMOKE_DIR/riffer_final.pt" ]; then
  echo "GPU-SMOKE-FAIL (rc=$rc_smoke, final ckpt present: $(ls "$SMOKE_DIR" 2>/dev/null | wc -l) files)" >> "$LOG"
  release_lock
  exit 4
fi
rm -rf "$SMOKE_DIR"
echo "=== $(date -Is) GPU smoke passed ===" >> "$LOG"

# --- Phase 2: pilot training (4 epochs x ~799 crops = ~3196 steps, per-epoch saves) ---
mkdir -p "$SAVE_DIR"
"$VENV" control/sa3_control/train.py \
  --encoded_dir /run/media/kim/Kosmos/latents/latents_sa3 --model medium-base --precision bf16 \
  --control-mode melody_contour --melody-dir /run/media/kim/Lehto/latents-all-backup/latents_sa3_melody \
  --melody-dropout 0.1 --cfg-dropout 0.1 --dora-rank 128 \
  --subset-tracks 0.3 --crop-frames 512 --batch 1 --grad-accum 2 --lr 1e-4 \
  --optimizer adamw --warmup-steps 100 --steps 4000 --max-epochs 4 \
  --save-every 799 --num-workers 4 --seed 42 --no-export-onnx-on-finish \
  --save-dir "$SAVE_DIR" > "$SAVE_DIR/train.log" 2>&1
rc_train=$?
echo "train rc=$rc_train" >> "$LOG"
n_ckpt=$(ls "$SAVE_DIR"/riffer_step*.pt 2>/dev/null | wc -l)
if [ $rc_train -ne 0 ] || [ ! -f "$SAVE_DIR/riffer_final.pt" ] || [ "$n_ckpt" -lt 3 ]; then
  echo "TRAIN-FAIL rc=$rc_train ckpts=$n_ckpt final=$([ -f "$SAVE_DIR/riffer_final.pt" ] && echo yes || echo no)" >> "$LOG"
  release_lock
  exit 4
fi
echo "=== $(date -Is) training done ($n_ckpt epoch ckpts + final) ===" >> "$LOG"

# --- Phase 3: 8 pilot renders (resumable) ---
"$VENV" control/sa3_control/melody_pilot_eval.py render --ckpt "$SAVE_DIR/riffer_final.pt" >> "$LOG" 2>&1
rc_render=$?
echo "render rc=$rc_render" >> "$LOG"
n_wav=$(ls $D/renders/*.wav 2>/dev/null | wc -l)
n_z0=$(ls $D/renders/*.z0.npy 2>/dev/null | wc -l)
if [ $rc_render -ne 0 ] || [ "$n_wav" -lt 8 ] || [ "$n_z0" -lt 8 ]; then
  echo "RENDER-FAIL rc=$rc_render wavs=$n_wav z0=$n_z0" >> "$LOG"
  release_lock
  exit 4
fi
echo "=== $(date -Is) renders done ($n_wav wavs, $n_z0 z0) ===" >> "$LOG"

# --- Phase 4: muscriptor transcription (GPU) ---
"$VENV" eval/hook_eval_renders.py \
  --wavs "$D/renders/*.wav" --out $D/hook_scores.jsonl \
  --midi-dir $D/hook_scores_midi --bpm 143 >> "$LOG" 2>&1
rc_tr=$?
echo "transcribe rc=$rc_tr" >> "$LOG"
n_mid=$(ls $D/hook_scores_midi/*.mid 2>/dev/null | wc -l)

release_lock
echo "=== $(date -Is) lock released; mids=$n_mid/$n_wav ===" >> "$LOG"
if [ $rc_tr -ne 0 ] || [ "$n_mid" -lt "$n_wav" ]; then
  echo "TRANSCRIBE-FAIL rc=$rc_tr mids=$n_mid" >> "$LOG"
  exit 4
fi

# --- Phase 5: CPU scoring (no lock needed) ---
"$SAT_VENV" control/sa3_control/melody_pilot_eval.py clap >> "$LOG" 2>&1
rc_clap=$?
echo "clap rc=$rc_clap" >> "$LOG"
"$MIR_VENV" control/sa3_control/melody_pilot_eval.py mood >> "$LOG" 2>&1
rc_mood=$?
echo "mood rc=$rc_mood" >> "$LOG"
"$VENV" control/sa3_control/melody_pilot_eval.py analyze > $D/results_table.tsv 2>> "$LOG"
rc_an=$?
echo "analyze rc=$rc_an" >> "$LOG"
if [ $rc_an -ne 0 ] || [ ! -s $D/results.json ]; then
  echo "ANALYZE-FAIL rc=$rc_an" >> "$LOG"
  exit 4
fi
echo "=== $(date -Is) CHAIN COMPLETE (clap=$rc_clap mood=$rc_mood analyze=$rc_an) ===" >> "$LOG"
exit 0
