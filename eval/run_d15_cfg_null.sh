#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_d15_cfg_null.sh -- EXPERIMENTS D15 re-read: the pianoroll full fine-tune with zeros for the stream in CFG's uncond branch, on E24's 24 crops. About 25 min under one GPU lock hold.
set -u
SAO=/home/kim/Projects/SAO
NAME=pianoroll_cfgnull_goa_t256_step2688_20261103
OUT=/home/kim/evals_aac/control_runs/$NAME
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
python3 "$SAO/Misc/run_record.py" snapshot "$OUT" "$SAO/eval/run_d15_cfg_null.sh" "$SAO/eval/e24_eval2.py"
until KIND=batch NOTE="D15 pianoroll with CFG on the stream, about 25 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
ARGS=(--run "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s1" --ckpt "epoch=31-step=2688.ckpt" --step 2688 --pack P --out "$OUT")
for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/e24_eval2.py" --stage render "${ARGS[@]}"
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 144 ] && break
  sleep 20
done
"$SAO/.venv/bin/python" -u "$SAO/eval/e24_eval2.py" --stage score "${ARGS[@]}"
rc=$?
echo "$(date '+%F %T') score rc=$rc"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots "control_runs/$NAME" --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern "$NAME"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
"$MIRPY" "$SAO/eval/e24_eval2.py" --stage gate "${ARGS[@]}"
rc=$?
echo "$(date '+%F %T') gate rc=$rc"
echo "$(date '+%F %T') ALL DONE"
