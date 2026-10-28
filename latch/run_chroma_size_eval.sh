#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-28)
# E13b follow-up: wait for latch/run_chroma_size.sh to finish, then render + score the new heads (eval/run_chroma_e13.sh --stages size,
# which waits for the GPU lock itself) and summarise the gradient noise by t and part for every arm.
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_size_2026-10-28
while pgrep -f "^/bin/bash latch/run_chroma_size.sh" > /dev/null; do sleep 120; done
echo "$(date '+%F %T') training chain finished: $(tail -1 "$OUT/SUMMARY.tsv" 2>/dev/null)"
"$SAO/eval/run_chroma_e13.sh" --stages size
python3 "$SAO/eval/grad_noise_by_t_report.py" "$OUT"/S*_*/ > "$OUT/grad_noise_by_t_report.txt" 2>&1
echo "$(date '+%F %T') E13b eval done"
