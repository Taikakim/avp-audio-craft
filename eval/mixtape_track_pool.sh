#!/bin/bash
# Owner: GHOST-NOTE (created 2026-11-03) -- unattended wrapper: waits for the GPU lock per arm, releases between arms.
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
cd /home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_2026-11-03; mkdir -p $OUT
for ARM in soup_mean soup_ep7_ep14 fullft_avp_t256_ep80 goa5k_dora_3e-3_3033st goa5k_r128_shampoo_k5_8088 fp32cmp_avp_bs4_lr1e4_ep28; do
  until Misc/gpu_guard.sh acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 120; done
  ONLY_ARM=$ARM .venv/bin/python eval/mixtape_track_pool.py >> $OUT/pool.log 2>&1
  rc=$?; echo "$ARM rc=$rc $(date +%T)" >> $OUT/arms.log
  Misc/gpu_guard.sh release GHOST-NOTE >/dev/null 2>&1
done
n=$(grep -c '"seed"' $OUT/cells.jsonl); echo "pool tracks written: $n" >> $OUT/arms.log; touch $OUT/ALL_ARMS_DONE
