#!/bin/bash
# Owner: CONTINUITY (created 2026-10-29)
# EXPERIMENTS E21 follow-up (E21c, Kim 2026-10-29 "E21 after that"): is same_chroma's weak steering in E21b only a GAIN problem,
# and does the E13-retrained same_chroma head (C3 lr 1e-3 ep10, W's winner) fix it at the usual gains? Same 14 canonical prompts,
# seeds and onset-leg settings as E21b; the 14 unguided renders are reused from E21b (identical payloads).
#   production same_chroma @ 4096, 8192   (E13: it reaches at 6144-8192 what C3 reaches at 512; gate-clean through 8192)
#   E13 C3 same_chroma     @ 512, 2048
# 14 x 2 heads x 4 keys x 2 gains = 224 renders (~45 min at ~12 s) + bungee positive control + score.
#   setsid nohup bash eval/run_e21c_20261029.sh </dev/null >/dev/null 2>&1 &
set -u
SAO=/home/kim/Projects/SAO; cd "$SAO" || exit 2
OUT=/run/media/kim/Mantu/sa3_control_runs/e21c_same_chroma_gain_20261029
BASE=/run/media/kim/Mantu/sa3_control_runs/e21b_transposition_canon_20261028
C3=/run/media/kim/Mantu/latch_sweep/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt
LOG=/home/kim/sao_runs/e21c_20261029.log
exec >>"$LOG" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
ARGS=(--out "$OUT" --base-from "$BASE"
      --head "same_chroma=latch_sa3_same_chroma_best.pt@4096,8192"
      --head "same_chroma_e13=$C3@512,2048"
      --purpose "EXPERIMENTS E21c (Kim 2026-10-29): E21b found same_chroma steers toward the right chord but too weakly to rotate the output. Is that only gain (production head at 4096/8192) and does the E13-retrained head (C3 lr 1e-3 ep10) fix it at 512/2048? Same prompts/seeds/settings as E21b; unguided reused from it.")
# free = no process holds >= 1 GiB of VRAM (W's E18 rule) AND the team guard lets us in (see run_e21b_20261028.sh).
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
until vram_free && KIND=batch NOTE="CONTINUITY E21c: own :8056 + 224 chroma renders (~45 min)" \
      Misc/gpu_guard.sh acquire CONTINUITY $$ >/dev/null 2>&1; do sleep 60; done
SRV=
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1; }
trap cleanup EXIT
echo "$(date +%H:%M) GPU acquired"
if ! curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; then
    setsid nohup .venv/bin/python eval/explorer_render_server.py > /home/kim/sao_runs/e21c_render_server.log 2>&1 &
    SRV=$!
    for _ in $(seq 90); do curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null && break; sleep 10; done
fi
curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null || { echo "server not up"; exit 1; }
echo "$(date +%H:%M) server up (pid ${SRV:-external})"
.venv/bin/python eval/e21b_transposition_server.py render "${ARGS[@]}"
echo "$(date +%H:%M) render done; cells: $(wc -l < "$OUT/cells.jsonl") / 238"
[ -n "$SRV" ] && kill "$SRV" && SRV=
Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1
/home/kim/Projects/mir/pitch_venv/bin/python eval/e21_bungee_posctl.py --out "$OUT" --glob "*same_chroma__k0__g8192.wav" | tail -1
.venv/bin/python eval/e21b_transposition_server.py score "${ARGS[@]}"
echo "$(date +%H:%M) ALL DONE"
