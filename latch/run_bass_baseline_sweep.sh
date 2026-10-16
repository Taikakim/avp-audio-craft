#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-17)
# Owner 2026-10-17: "render a sweep [of the baselines] before running the other stuff". Renders the bass baselines (M3/M4 pure Muon, A3/A4 AdamW; every epoch) into the punch clip's bass slot
# (eval/bass_epoch_sweep.py), then the page (Misc/build_bass_baselines_page.py). run_bass_decorr.sh waits for /tmp/bass_baseline_sweep.done (written only if the sweep finished).
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/bass_baselines_2026-10-16
cd /tmp || exit 1
until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 60; done
"$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
until curl -s localhost:8056/info >/dev/null 2>&1; do sleep 15; done
"$SAO/.venv/bin/python" "$SAO/eval/bass_epoch_sweep.py" --dirs "$OUT"/M3_* "$OUT"/M4_* "$OUT"/A3_* "$OUT"/A4_* --out "$OUT/epoch_sweep" > "$OUT/sweep.log" 2>&1
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
grep -q "SWEEP DONE" "$OUT/sweep.log" && echo SWEEP DONE > /tmp/bass_baseline_sweep.done
python3 "$SAO/Misc/build_bass_baselines_page.py" >> "$OUT/sweep.log" 2>&1
