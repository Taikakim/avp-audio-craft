#!/bin/bash
set -u
# wait for the everything-chain to exit
while pgrep -f run_everything_dora_chain >/dev/null; do sleep 60; done
# confirm GPU compute is released (no KFD pids) before claiming it
for i in $(seq 1 30); do
  rocm-smi --showpids 2>/dev/null | grep -q "No KFD PIDs" && break
  sleep 20
done
sleep 15
setsid nohup /home/kim/Projects/SAO/Misc/run_continued_goa.sh >/dev/null 2>&1 &
