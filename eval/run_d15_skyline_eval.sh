#!/usr/bin/env bash
set -euo pipefail
SAO=/home/kim/Projects/SAO
NAME=d15_skyline_cfgnull_goa_t256_step2688_20261105
OUT=/home/kim/evals_aac/control_runs/$NAME
PREV=/home/kim/evals_aac/control_runs/pianoroll_cfgnull_goa_t256_step2688_20261103
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"

# Pre-populate ref and zero from the previous D15 run
echo "Pre-populating ref and zero from previous D15 run..."
python3 -c "
import json, shutil, os
prev = '$PREV'
out = '$OUT'
if os.path.exists(f'{prev}/cells.jsonl'):
    done = []
    with open(f'{out}/cells.jsonl', 'w') as fout:
        for line in open(f'{prev}/cells.jsonl'):
            d = json.loads(line)
            if d.get('arm') in ('ref', 'zero'):
                fout.write(line)
                for ext in ('.wav', '.m4a'):
                    src = f'{prev}/{d[\"id\"]}{ext}'
                    dst = f'{out}/{d[\"id\"]}{ext}'
                    if os.path.exists(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)
"

exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1

until KIND=batch NOTE="D15 pianoroll with skyline highest line input" "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do sleep 5; done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

ARGS=(--run "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s1" --ckpt "epoch=31-step=2688.ckpt" --step 2688 --pack PS --out "$OUT")

for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/e24_eval2.py" --stage render "${ARGS[@]}" || true
  n_cells=$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)
  echo "$(date '+%F %T') render attempt $attempt: n_cells=$n_cells"
  [ "$n_cells" -ge 144 ] && break
  sleep 10
done

"$SAO/.venv/bin/python" -u "$SAO/eval/e24_eval2.py" --stage score "${ARGS[@]}"
rc=$?
echo "$(date '+%F %T') score rc=$rc"

"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1
trap - EXIT

"$MIRPY" "$SAO/eval/e24_eval2.py" --stage gate "${ARGS[@]}" || true
echo "$(date '+%F %T') ALL DONE"
