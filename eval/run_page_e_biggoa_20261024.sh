#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-24)
# Page E (latch_opt_grid_e.html: MuonG / Muon512 / KS512 continued to 40 epochs, plus Muon_b64 and KSc075) rendered again on
# the biggoa DoRA finetune -> latch_opt_grid_e_biggoa.html (project call 2026-10-24: head evals on the finetune from now on;
# page E itself stays on medium-base for like-for-like comparison with pages C and D).
# Waits for eval/run_eb64_epochs_20261024.sh (EB64r retrain + its per-epoch page) to finish, then takes the GPU lock.
# RUN: setsid nohup bash eval/run_page_e_biggoa_20261024.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
FT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/epoch=63-step=12480.ckpt
LOG=/home/kim/sao_runs/page_e_biggoa_20261024.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
echo "$(date +%H:%M) waiting for the EB64r queue to finish"
while pgrep -f '^bash eval/run_eb64_epochs_20261024\.sh' >/dev/null; do sleep 120; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE page E on the biggoa finetune (~1.5 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired; eval E on biggoa"
FT=$FT FT_TAG=biggoa FT_DESC="our DoRA finetune trained on the same goa set as the heads (rank 128, 64 epochs, final epoch, strength 1)" \
  bash eval/run_opt_grid_eval.sh E
rc=$?
echo "$(date +%H:%M) eval E biggoa rc=$rc"
