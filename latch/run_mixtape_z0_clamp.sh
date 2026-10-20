#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-20)
# Waits for the GPU lock, decodes orig / clamp 1.4 / clamp 1.15 / soft-limited for every shortlist clip with a saved z0 and std > 1.15, releases, writes /tmp/mixtape_z0_clamp.done.
SAO=/home/kim/Projects/SAO; PY=$SAO/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
rm -f /tmp/mixtape_z0_clamp.done
until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 60; done
cd /tmp && $PY "$SAO/eval/mixtape_z0_clamp.py" --caps 1.4,1.15 --only-over --device cuda > /tmp/mixtape_z0_clamp.log 2>&1
rc=$?
"$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
grep -q "CLAMP DONE" /tmp/mixtape_z0_clamp.log && echo "DONE rc=$rc" > /tmp/mixtape_z0_clamp.done
