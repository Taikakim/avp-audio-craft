#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-28)
# E13b, second half. The shared stable-audio-3 checkout was switched from feature/sa3-drum-sep to main (June, 247 commits behind)
# at 07:38 while S0 was training, so S1/S2 and the eval must not import stable_audio_3 from it. This waits for the first runner
# (S0 only; S1/S2 were marked "deferred" in SUMMARY.tsv), removes those markers, and reruns latch/run_chroma_size.sh and the eval
# chain with PYTHONPATH on the worktree (feature/sa3-drum-sep + the grad-noise-by-t commit), which takes precedence over the
# editable install in both venvs (checked 2026-10-28).
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_size_2026-10-28
export PYTHONPATH=/home/kim/Projects/SAO-worktrees/sa3-latch-gn
while pgrep -f "^/bin/bash latch/run_chroma_size.sh" > /dev/null; do sleep 60; done
grep -v "	deferred$" "$OUT/SUMMARY.tsv" > "$OUT/SUMMARY.tsv.tmp" && mv "$OUT/SUMMARY.tsv.tmp" "$OUT/SUMMARY.tsv"
echo "$(date '+%F %T') first runner done; S1/S2 with PYTHONPATH=$PYTHONPATH"
cd "$SAO" || exit 1
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True bash latch/run_chroma_size.sh
"$SAO/eval/run_chroma_e13.sh" --stages size
python3 "$SAO/eval/grad_noise_by_t_report.py" "$OUT"/S*_*/ > "$OUT/grad_noise_by_t_report.txt" 2>&1
echo "$(date '+%F %T') E13b done"
