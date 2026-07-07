#!/bin/bash
# Night sequence 2026-07-07 (Kim: transitions before the training chain).
# g175 grid (already running) -> transition_lab -> familiarity smoke -> overnight chain.
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SA3/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
cd "$SA3" || exit 1
note() { "$SAO/Misc/worklog_note.sh" night-0707 "$1 ($(date +%H:%M))"; }

# 1. wait for the g175 grid ([done] marker; ~4h timeout)
for i in $(seq 1 480); do
  grep -q "^\[done\]" "$SAO/logs/density_control_g175.log" 2>/dev/null && break
  sleep 30
done
grep -q "^\[done\]" "$SAO/logs/density_control_g175.log" || { note "ABORT: g175 never finished"; exit 1; }
note "g175 grid done; starting transition_lab"

# 2. transitions (Kim listens in the morning)
$PY ../eval/transition_lab.py \
  --out-dir /run/media/kim/Mantu1/sa3_lora_runs/newcap8_transitions \
  > "$SAO/logs/transition_lab.log" 2>&1
note "transition_lab done (exit $?) -> newcap8_transitions"

# 3. familiarity smoke: 12 steps on avp, must exit 0 AND log familiarity weights
rm -f "$SAO/.familiarity_ready"
timeout 1800 $PY scripts/train_lora.py \
  --model medium-base --encoded_dir /home/kim/Projects/latents_avp \
  --adapter_type dora-rows --rank 16 --lora_alpha 16 \
  --optimizer fusion --lr 2e-4 --steps 12 --batch_size 4 --duration 47 \
  --beat-aware-crop --familiarity_beta 1.0 --log_every 1 \
  --base_precision bf16 --no_demos --num_workers 4 --seed 42 \
  --save_dir /tmp/claude-1000/fam_smoke --name fam_smoke --logger csv \
  > "$SAO/logs/familiarity_smoke.log" 2>&1
SMOKE=$?
if [ "$SMOKE" -eq 0 ] && grep -rq "familiarity_w" /tmp/claude-1000/fam_smoke/lightning_logs/*/metrics.csv 2>/dev/null; then
  touch "$SAO/.familiarity_ready"
  note "familiarity smoke PASS -> stage D armed"
else
  note "familiarity smoke FAIL (exit $SMOKE) -> stage D will be skipped"
fi
rm -rf /tmp/claude-1000/fam_smoke

# 4. the training chain (A goa-r16-newstack, B avp-r16, C avp-r128adj, D gated)
bash "$SAO/Misc/run_overnight_20260707.sh"
