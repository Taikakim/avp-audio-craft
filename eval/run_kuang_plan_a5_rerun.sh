#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-19)
# run_kuang_plan_a5_rerun.sh -- reruns test-plan arm A5 (FiLM fp32 optimizer state, lr 1e-3), which died at its step-4000 save on
# 2026-10-19 23:46 when Mantu filled (truncated riffer_step4000.pt). Waits for eval/run_kuang_plan_stream.sh to exit, keeps the dead
# attempt as A5_..._diskfull, links a fresh A5 folder to the UUID drive (fp32-state checkpoints are 2.4 GB each), drops A5's line
# from SUMMARY.tsv, and reruns the stream script: every other arm is skipped by SUMMARY, P0 by its DONE file; P1 (read-only) reruns.
#   setsid nohup bash eval/run_kuang_plan_a5_rerun.sh > <A>/a5_rerun.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
A=/run/media/kim/Mantu/sa3_control_runs/film_precision_A_20261017
U=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
N=A5_fp32state_lr1e-3
cd "$SAO" || exit 2
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_kuang_plan_stream\.sh$" >/dev/null; do sleep 120; done
echo "$(date +%H:%M) stream done; rerunning $N"
[ -d "$A/$N" ] && [ ! -L "$A/$N" ] && mv "$A/$N" "$A/${N}_diskfull"
mkdir -p "$U/$N"; [ -e "$A/$N" ] || ln -s "$U/$N" "$A/$N"
grep -v "^${N}	" "$A/SUMMARY.tsv" > "$A/SUMMARY.tsv.tmp" && mv "$A/SUMMARY.tsv.tmp" "$A/SUMMARY.tsv"
bash eval/run_kuang_plan_stream.sh
echo "$(date +%H:%M) A5 RERUN DONE"
