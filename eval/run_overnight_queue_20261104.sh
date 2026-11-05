#!/usr/bin/env bash
# run_overnight_queue_20261104.sh -- Autonomous 8-10 hour overnight execution queue (2026-11-04 -> 2026-11-05).
# Prepared for Kim's 8-hour sleep window.
#
# STAGES:
# 1. Kuang's Melody Probe Map (latch/melody_probe_map.py):
#    - GPU extraction (real DiT activations, 160 crops x 6 sigmas)
#    - GPU extraction (random-init control, 160 crops x 2 sigmas)
#    - CPU 5-fold cross-validation ridge regression (--stride 2)
# 2. Batch Generation of Full 10-Track Mixtape Pool V3 (90s Islands + 4-Bar Bridge & A2A):
#    - 90s parents + two 12-bar div4 islands + Mode A direct bridge + Mode B A2A 0.60 bridge
#    - AAC 192k encoding + live board upload
# 3. E24 Arm B Fine-tune (latch/run_e24_contourB.sh):
#    - K&P L3 contour shapes from MuScriptor notes (blocks 12-23), 2400 steps (~2.4 h GPU)
# 4. E24 Arm B Evaluation (eval/run_e24_eval2.sh):
#    - 24 crops x 5 arms, MuScriptor transcription, Audiobox metrics, gate check (~35 min GPU)
# 5. E24 Arm A Fine-tune (latch/run_e24_contourA.sh):
#    - Interval-from-previous-note stream (26 ch), 2400 steps (~2.4 h GPU)
# 6. E24 Arm A Evaluation (eval/run_e24_eval2.sh):
#    - 24 crops x 5 arms, MuScriptor transcription, Audiobox metrics, gate check (~35 min GPU)
# 7. E24 Multi-Arm Listening Page & Handover:
#    - Updates e24_contour.html featuring Arms C, B, and A side-by-side
#    - Syncs to DreamHost and files handover report

set -u
SAO=/home/kim/Projects/SAO
cd "$SAO" || exit 1

LOG_DIR="/run/media/kim/Mantu/sa3_lora_runs/overnight_20261104_logs"
mkdir -p "$LOG_DIR"
MASTER_LOG="$LOG_DIR/master_queue.log"

exec > >(tee -a "$MASTER_LOG") 2>&1

echo "================================================================="
echo "=== OVERNIGHT QUEUE LAUNCHED: $(date '+%F %T') ==="
echo "================================================================="

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0
export MIOPEN_FIND_MODE=2
export WANDB_PROJECT=sa3-lora-dev
export WANDB_MODE=offline

# Safety trap to guarantee lock release
cleanup() {
    echo "[$(date '+%F %T')] Caught signal or EXIT, ensuring GPU lock is released..."
    "$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1 || true
    "$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1 || true
}
trap cleanup EXIT

# -----------------------------------------------------------------------------
# STAGE 1: Kuang's Melody Probe Map
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 1: Kuang's Melody Probe Map (latch/melody_probe_map.py)"
echo "#################################################################"
PROBE_LAT="/run/media/kim/Kosmos/latents/latents_sa3"
PROBE_OUT="/run/media/kim/Mantu/sa3_lora_runs/melody_probe_2026-11-04"
PROBE_HEAD="$SAO/stable-audio-3/latch_weights_sa3_medium/val30_f0_other_ema0.999/latch_sa3_f0_other_best.pt"
mkdir -p "$PROBE_OUT"

echo "[$(date '+%F %T')] Acquiring GPU lock for Stage 1a (Real DiT extraction)..."
until KIND=batch NOTE="Stage 1a: Melody probe extract real, ~20 min" "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do sleep 30; done

echo "[$(date '+%F %T')] Extracting real DiT activations (160 crops x 6 sigmas)..."
"$SAO/.venv/bin/python" "$SAO/latch/melody_probe_map.py" extract \
    --latent-dir "$PROBE_LAT" \
    --out-dir "$PROBE_OUT/acts" \
    --f0-head "$PROBE_HEAD" \
    > "$LOG_DIR/stage1a_extract_real.log" 2>&1
echo "[$(date '+%F %T')] Real DiT extraction complete (rc=$?)."

echo "[$(date '+%F %T')] Extracting random-init control activations (160 crops x 2 sigmas)..."
"$SAO/.venv/bin/python" "$SAO/latch/melody_probe_map.py" extract \
    --latent-dir "$PROBE_LAT" \
    --out-dir "$PROBE_OUT/acts_random" \
    --random-init \
    --sigmas 0.5,0.137 \
    > "$LOG_DIR/stage1b_extract_random.log" 2>&1
echo "[$(date '+%F %T')] Random-init extraction complete (rc=$?)."

echo "[$(date '+%F %T')] Releasing GPU lock for CPU ridge regression analysis..."
"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1

echo "[$(date '+%F %T')] Starting 5-fold cross-validation ridge regression on CPU (stride 2)..."
"$SAO/.venv/bin/python" "$SAO/latch/melody_probe_map.py" analyze \
    --latent-dir "$PROBE_LAT" \
    --acts-dir "$PROBE_OUT/acts" \
    --random-acts-dir "$PROBE_OUT/acts_random" \
    --out-json "$PROBE_OUT/melody_probe_map.json" \
    --stride 2 \
    > "$LOG_DIR/stage1c_analyze_cpu.log" 2>&1
echo "[$(date '+%F %T')] Stage 1 Analysis Complete! Results written to $PROBE_OUT/melody_probe_map.json and .md"

# -----------------------------------------------------------------------------
# STAGE 2: Batch Generation of Full 10-Track Mixtape Pool V3 (90s Islands + 4-Bar Bridge)
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 2: Mixtape Track Pool V3 (90s Islands + 4-Bar Bridge)"
echo "#################################################################"
echo "[$(date '+%F %T')] Acquiring GPU lock for Stage 2..."
until KIND=batch NOTE="Stage 2: Mixtape V3 10-track 90s islands batch, ~15 min" "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do sleep 30; done

echo "[$(date '+%F %T')] Generating 10 tracks with 90s parents, Island A/B crops, 4-bar bridges, and A2A..."
"$SAO/.venv/bin/python" "$SAO/eval/generate_mixtape_v3_islands.py" > "$LOG_DIR/stage2_mixtape_v3.log" 2>&1
echo "[$(date '+%F %T')] Stage 2 Generation complete (rc=$?). Releasing GPU lock..."
"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1

echo "[$(date '+%F %T')] Publishing updated Mixtape Pool V3 to DreamHost..."
"$SAO/.venv/bin/python" "$SAO/Misc/build_mixtape_trackpool_v3_page.py" > "$LOG_DIR/stage2_build_page.log" 2>&1 || true
bash "$SAO/eval/publish_mixtape_v3.sh" > "$LOG_DIR/stage2_publish.log" 2>&1 || true
echo "[$(date '+%F %T')] Stage 2 published successfully."

# -----------------------------------------------------------------------------
# STAGE 3: E24 Arm B Fine-tune (K&P L3 contour shapes from MuScriptor notes)
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 3: E24 Arm B Fine-tune (latch/run_e24_contourB.sh)"
echo "#################################################################"
echo "[$(date '+%F %T')] Launching E24 Arm B fine-tune (2400 steps, ~2.4 h)..."
bash "$SAO/latch/run_e24_contourB.sh"
echo "[$(date '+%F %T')] E24 Arm B fine-tune finished."

# -----------------------------------------------------------------------------
# STAGE 4: E24 Arm B Evaluation
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 4: E24 Arm B Evaluation (eval/run_e24_eval2.sh)"
echo "#################################################################"
RUN_DIR_B="/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_lora_runs/e24_contourB_r128_2026-11-03"
if [ -d "$RUN_DIR_B" ]; then
    echo "[$(date '+%F %T')] Running eval2 on Arm B checkpoint..."
    bash "$SAO/eval/run_e24_eval2.sh" "$RUN_DIR_B" B e24_contourB_eval2_20261103
    echo "[$(date '+%F %T')] E24 Arm B evaluation finished."
else
    echo "[$(date '+%F %T')] WARNING: $RUN_DIR_B not found, skipping Stage 4."
fi

# -----------------------------------------------------------------------------
# STAGE 5: E24 Arm A Fine-tune (Interval-from-previous-note melody stream)
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 5: E24 Arm A Fine-tune (latch/run_e24_contourA.sh)"
echo "#################################################################"
echo "[$(date '+%F %T')] Launching E24 Arm A fine-tune (2400 steps, ~2.4 h)..."
bash "$SAO/latch/run_e24_contourA.sh"
echo "[$(date '+%F %T')] E24 Arm A fine-tune finished."

# -----------------------------------------------------------------------------
# STAGE 6: E24 Arm A Evaluation
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 6: E24 Arm A Evaluation (eval/run_e24_eval2.sh)"
echo "#################################################################"
RUN_DIR_A="/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_lora_runs/e24_contourA_r128_2026-11-04"
if [ -d "$RUN_DIR_A" ]; then
    echo "[$(date '+%F %T')] Running eval2 on Arm A checkpoint..."
    bash "$SAO/eval/run_e24_eval2.sh" "$RUN_DIR_A" A e24_contourA_eval2_20261104
    echo "[$(date '+%F %T')] E24 Arm A evaluation finished."
else
    echo "[$(date '+%F %T')] WARNING: $RUN_DIR_A not found, skipping Stage 6."
fi

# -----------------------------------------------------------------------------
# STAGE 7: Build E24 Multi-Arm Listening Page & Final Handover
# -----------------------------------------------------------------------------
echo ""
echo "#################################################################"
echo "### STAGE 7: Build E24 Listening Page & Final Handover"
echo "#################################################################"
echo "[$(date '+%F %T')] Building E24 listening page combining Arms C, B, and A..."
"$SAO/.venv/bin/python" "$SAO/Misc/build_e24_contour_page.py" > "$LOG_DIR/stage7_build_e24_page.log" 2>&1 || true

echo "[$(date '+%F %T')] Syncing E24 page to DreamHost..."
rsync -avz --exclude '*.wav' --exclude '*.pt' "$HOME/evals_aac/e24_contour*" "aavepyor@aavepyora.online:~/aavepyora.online/files/evals/" > "$LOG_DIR/stage7_rsync.log" 2>&1 || true

echo ""
echo "================================================================="
echo "=== ALL OVERNIGHT JOBS COMPLETED SUCCESSFULLY: $(date '+%F %T') ==="
echo "================================================================="
