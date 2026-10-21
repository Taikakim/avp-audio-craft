#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-21)
# run_overnight_dpo_batch_20261021.sh -- two queued jobs for the ~5-6 h window, in order:
#
# A. ON-POLICY FLOW-DPO ROUNDS on the synth inverter (V6_C). Round 1 = dpo_v6c_b100 (KUANG, 2026-10-20). Its log
#    shows the held-out DPO loss RISING over its 2000 steps (val_loss 0.91 -> 1.00) while val accuracy stays near
#    0.70: one fixed pair set is already used up, so simply training round 1 longer would over-fit those pairs.
#    "Longer training" is done instead the way iterative DPO does it: each round renders FRESH pairs from the
#    current policy (new seed), and trains from it with the current policy as the reference. Each round's leash
#    (beta 100) is local, and the drift adds up over rounds. Everything else is round 1's recipe (one change).
#    Then: held-out synthetic audio eval (all rounds) and the 24 real stems (listening page).
# B. BATCH-SCALED LatCH ONSET ARMS. The batch sweep held lr at 1e-3 for every batch, so bigger batches also took
#    smaller total steps. Here the optimizer is scaled from EB64 (batch 64) by kappa = B / 64 with the rule for
#    normalised updates (Muon's orthogonalised step and Adam both have a size set by lr, not by the gradient):
#      lr x sqrt(kappa); every per-step EMA keeps its horizon in SAMPLES, 1 - beta x kappa (Muon momentum, NorMuon
#      row stats, Shampoo stats, Adam beta2); Shampoo refresh period / kappa; decoupled wd x sqrt(kappa) (keeps the
#      decay per epoch). Schedule-Free's interpolation beta is a mixing weight, not an EMA: unchanged. Warmup is
#      already in epochs. Prediction: per-epoch held-out curves overlay EB64 while kappa*64 is below the noise scale.
#      30 epochs (EB64's best was epoch 27).
#   setsid nohup bash eval/run_overnight_dpo_batch_20261021.sh > /home/kim/sao_runs/overnight_20261021.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
GUARD=$SAO/Misc/gpu_guard.sh
RUNS=/home/kim/sao_runs
SI=$SAO/stable-audio-tools/scripts/synth_inversion
PY=$SAO/.venv/bin/python                       # synth-inversion venv (as run_v6_1_pipeline.sh)
LPY=$SAO/.venv-rocm10-amd/bin/python           # LatCH trainer venv (as run_batch_sweep.sh)
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
B=$RUNS/real_manifold_v4_bass.npz; A=$RUNS/real_manifold_v4_all.npz
PLUGIN="$HOME/.vst3/Surge XT.vst3"
V6C=$RUNS/v6_C/flow_ema_latest.pt
R1=$RUNS/dpo_v6c_b100/flow_dpo_latest.pt
OUTB=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow/batch_scaled_20261021
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2

while pgrep -f '^bash eval/run_batch_sweep\.sh' >/dev/null; do sleep 60; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE overnight: synth DPO rounds, then batch-scaled LatCH arms (~6 h)" \
      "$GUARD" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$GUARD" release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

# ---------------- A. DPO rounds 2..4 ----------------
prev=$R1
for r in 2 3 4; do
  P=$RUNS/dpo_pairs_v6c_r$r; O=$RUNS/dpo_v6c_b100_r$r
  if [ ! -f "$O/flow_dpo_latest.pt" ]; then
    echo "$(date +%H:%M) round $r: pairs from $(basename "$(dirname "$prev")")"
    ( cd "$SI" && $PY render_pairs_dpo_v6.py --flow "$prev" --bass_manifold "$B" --all_manifold "$A" --plugin "$PLUGIN" \
        --n 8192 --k_passive 4 --workers 14 --seed "$r" --square_shape 0.0 --device cuda:0 --out "$P" ) > "$RUNS/dpo_pairs_v6c_r$r.log" 2>&1 \
      || { echo "$(date +%H:%M) round $r pairs FAILED (see dpo_pairs_v6c_r$r.log); DPO stops here"; break; }
    ( cd "$SI" && $PY train_flow_dpo_v5.py --flow "$prev" --pairs "$P" --out "$O" --metric "mss=1,logmel_l1=0.5" \
        --beta 100 --lr 1e-5 --steps 2000 --batch 64 --seed "$r" --device cuda:0 ) > "$O.log" 2>&1 \
      || { echo "$(date +%H:%M) round $r DPO FAILED (see $O.log)"; break; }
    cat > "$O/run_meta.json" <<EOF
{"purpose": "Flow-DPO round $r on V6_C (on-policy: fresh pairs from round $((r-1)), that round as the reference). Tests whether more DPO (the 2026-10-21 listening verdict: creative, not uniformly better, would benefit from longer training) keeps improving.",
 "recipe": "render_pairs_dpo_v6 n 8192 k_passive 4 seed $r square_shape 0; train_flow_dpo_v5 metric mss=1,logmel_l1=0.5 beta 100 lr 1e-5 steps 2000 batch 64 (= round 1 recipe)",
 "init_and_reference": "$prev", "pairs": "$P", "script": "eval/run_overnight_dpo_batch_20261021.sh", "kim_feedback": null}
EOF
  fi
  echo "$(date +%H:%M) round $r done: last val $(tail -1 "$O/dpo_log.jsonl" | grep -oE '"val_(loss|acc)": [0-9.]+' | paste -sd' ')"
  prev=$O/flow_dpo_latest.pt
done

FLOWS=(--flow V6C="$V6C" --flow R1="$R1")
MODELS=(--model V6_C "$V6C" --model V6_C_DPO_r1 "$R1")
for r in 2 3 4; do
  f=$RUNS/dpo_v6c_b100_r$r/flow_dpo_latest.pt
  [ -f "$f" ] && FLOWS+=(--flow R$r="$f")
  [ -f "$f" ] && { [ $r -eq 2 ] || [ $r -eq 4 ]; } && MODELS+=(--model V6_C_DPO_r$r "$f")
done
echo "$(date +%H:%M) held-out synthetic eval: ${FLOWS[*]}"
( cd "$SI" && $PY audio_eval_v5.py --bass_manifold "$B" --all_manifold "$A" --plugin "$PLUGIN" --n 256 --k 8 --workers 14 \
    --device cuda:0 "${FLOWS[@]}" --metrics logmel_l1 mss modspec_dist --out "$RUNS/audio_eval_v6c_dpo_rounds" ) \
    > "$RUNS/audio_eval_v6c_dpo_rounds.log" 2>&1; echo "$(date +%H:%M) held-out eval rc=$?"
echo "$(date +%H:%M) real stems: ${MODELS[*]}"
( cd "$SI" && $PY eval_real_stems_consensus_v6.py "${MODELS[@]}" --max_midi 60 --drop_polyphony --occam_tol 0.02 \
    --square_shape 0.0 --device cuda:0 --out_dir "$RUNS/stems_v6_c_dpo_rounds" \
  && $PY stem_stats_v6.py "$RUNS/stems_v6_c_dpo_rounds/consensus_eval_summary.json" --ref V6_C --metric mel_ssim \
       --out "$RUNS/stems_v6_c_dpo_rounds/stats_ssim.md" \
  && $PY build_interactive_model_eval_page.py "$RUNS/stems_v6_c_dpo_rounds" ) > "$RUNS/stems_v6_c_dpo_rounds.log" 2>&1
echo "$(date +%H:%M) real stems rc=$?"

# ---------------- B. batch-scaled LatCH onset arms ----------------
mkdir -p "$OUTB"
best_val() { grep -oE 'val=[0-9.]+' "$1/train.log" 2>/dev/null | cut -d= -f2 | sort -g | head -1; }
COMMON="--optimizer modular --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups --mod-ns-dtype fp32
  --feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --mod-warmup-epochs 0.68
  --mod-radial-brake 0.8 --depth 8 --batch-size 32 --epochs 30 --log-grad-noise 10 --save-best-only"
# arm   accum  lr        momentum normuon precond adam_b2 refresh wd
ARMS="EB256s 8     2.0e-3    0.6      0.8     0.8     0.96    3       0.02
EB128s 4     1.414e-3  0.8      0.9     0.9     0.98    5       0.01414"
while read -r arm acc lr mom nb pb ab2 freq wd; do
  d="$OUTB/$arm"; [ -f "$d/DONE" ] && continue; mkdir -p "$d"
  cat > "$d/run_meta.json" <<EOF
{"purpose": "Batch $((acc*32)) with the optimizer scaled from EB64 (batch_sweep_20261021) by the square-root rule for normalised-update optimizers (lr x sqrt(kappa), per-step EMA horizons fixed in samples, Shampoo refresh / kappa, wd x sqrt(kappa)). Tests whether larger batches lost in the unscaled sweep only because their total step was smaller.",
 "hypothesis": "Muon's orthogonalised step and Adam's step have a size set by lr. In the noise-dominated regime their mean progress per step grows ~sqrt(batch) and their noise per step is ~lr^2, so lr ~ sqrt(batch) keeps progress and noise per sample unchanged (Malladi et al. 2022 SDE argument; same as Adam). Prediction: held-out loss per epoch overlays EB64 until the batch passes the gradient-noise scale (measured 80 early -> 330 late on EB64); beyond it the larger batch falls behind.",
 "reference": "batch_sweep_20261021/EB64 (lr 1e-3, momentum 0.9, NorMuon 0.95, Shampoo 0.95, Adam b2 0.99, refresh 10, wd 0.01)",
 "scaled": {"lr": "$lr", "momentum": $mom, "normuon_beta": $nb, "precond_beta": $pb, "adam_beta2": $ab2, "precond_freq": $freq, "wd": $wd, "sf_beta": "unchanged (mixing weight)"},
 "script": "eval/run_overnight_dpo_batch_20261021.sh", "kim_feedback": null}
EOF
  echo "$(date +%H:%M) $arm: accum $acc lr $lr momentum $mom normuon $nb precond $pb adam_b2 $ab2 refresh $freq wd $wd"
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $COMMON --grad-accum "$acc" --lr "$lr" --mod-momentum "$mom" --mod-normuon-beta "$nb" \
      --mod-precond-beta "$pb" --mod-adam-beta2 "$ab2" --mod-precond-freq "$freq" --mod-wd "$wd" \
      --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) $arm rc=$rc; best val $(best_val "$d"); last: $(grep -E 'val=' "$d/train.log" | tail -1 | tr -s ' ')"
  [ "$rc" -eq 0 ] && touch "$d/DONE"
done <<< "$ARMS"
echo "$(date +%H:%M) overnight done"
