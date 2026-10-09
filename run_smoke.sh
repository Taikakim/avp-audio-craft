#!/bin/bash
source .venv/bin/activate
export V7_ORDER="/run/media/kim/Mantu2/sa3_lora_runs/mixtape_v7c/order_used.json"
export V7_STEMS="/run/media/kim/Mantu2/sa3_lora_runs/mixtape_v7_stems"
export V7_DOWNBEATS="/run/media/kim/Mantu2/sa3_lora_runs/mixtape_v7c/downbeats_native.json"
export V7_SMOKE_OUT="/home/kim/staging/kone-mixtape/smoke/kuang_smoke_4clips"
export V7_CKPT_A="/run/media/kim/Mantu2/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"
export V7_CKPT_B="/run/media/kim/Mantu2/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt"
export V7_CHROMA_HEAD="/run/media/kim/Mantu2/sa3_lora_runs/cu_reward_renders/analysis/chroma_heads/latch_sa3_chroma_other_best.pt"

python eval/render_v7_smoketest.py \
    --bounds /tmp/bounds_structural.json \
    --clips 0:4 \
    --no-generate \
    --drum-inpaint-bars 2 4 \
    --other-inpaint-bars 2 4 \
    --other-slerp \
    --kick-ramp auto \
    --drum-split zero_phase \
    --assemble-mix "$@"
