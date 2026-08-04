#!/bin/bash
# night_campaign_20260719.sh — Kim away ~20h, big GPU runs OK. Chains the high-value GPU
# work behind the running EMA retrain, all GPU-serialized (each phase owns the card).
#
#   A. wait for the EMA retrain (7 heads x {ema20,ema40}) to fully finish
#   B. FULL chroma grid — hpcp + same_chroma x 12 prompts x 8 targets x 3 seeds x 4 gains
#      (chroma_other head missing -> skipped). Populates the extended chroma page.
#   C. EMA-hpcp BEFORE/AFTER — render the chroma pilot with the EMA-retrained hpcp head
#      (ema20 and ema40), so Δcos12 vs the shipped hpcp answers "did EMA fix hpcp's uneven
#      / backfiring steering". Clean, self-contained (no MERT needed — the chroma metric is
#      the verdict for a chroma head).
#
# DEFERRED (flagged for Kim, NOT run autonomously):
#   - same_chroma EMA retrain: needs the per-crop SAME-chroma corpus (gen_same_chroma_ts.py,
#     ONNX decoder, UNTESTED end-to-end) — a prerequisite pass I won't fire unattended.
#   - scalar/activation EMA heads "did it help" MERT-Δ verdict: the renders are cheap but the
#     measurement (mert_selector) needs care — left as a measurement pass, not an autonomous claim.
# Launch: setsid bash eval/night_campaign_20260719.sh >/tmp/night_campaign.log 2>&1 &
set -uo pipefail
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 \
       OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
PY=/home/kim/Projects/SAO/.venv/bin/python
EMA_OUT=/run/media/kim/Mantu/sa3_control_runs/latch_ema_retrain_20260719
log(){ echo "[night $(date +%H:%M)] $*"; }

# ── PHASE A: wait for the EMA retrain to FULLY finish (all 14 runs) ──────────────────
log "PHASE A — waiting for EMA retrain to finish"
sleep 30
while pgrep -f latch_ema_retrain_driver.sh >/dev/null 2>&1; do sleep 60; done
log "PHASE A done — EMA retrain finished"
grep -E "DONE|FAIL" /tmp/latch_ema_retrain.log | tail -20

# ── PHASE B: full chroma grid (populate the page) ───────────────────────────────────
log "PHASE B — full chroma grid START"
${PY} eval/chroma_steer_render.py --full >/tmp/night_chroma_full.log 2>&1 && \
  log "PHASE B done — $(grep -c '/g' /tmp/night_chroma_full.log 2>/dev/null || echo '?') cells" || \
  log "PHASE B FAILED (see /tmp/night_chroma_full.log)"

# ── PHASE C: EMA-hpcp before/after ──────────────────────────────────────────────────
log "PHASE C — EMA-hpcp before/after"
for pair in ema20:20 ema40:40; do
  a=${pair%%:*}; ep=${pair##*:}
  src="$EMA_OUT/hpcp_${a}/latch_sa3_hpcp_ep${ep}.pt"
  if [ -f "$src" ]; then
    cmp="$EMA_OUT/heads_${a}"; mkdir -p "$cmp"
    ln -sf "$src" "$cmp/latch_sa3_hpcp_best.pt"
    log "PHASE C — hpcp $a pilot render START"
    ${PY} eval/chroma_steer_render.py --pilot --models hpcp --heads-dir "$cmp" --tag hpcp_$a \
      >/tmp/night_hpcp_$a.log 2>&1 && log "PHASE C — hpcp $a DONE" || log "PHASE C — hpcp $a FAILED"
  else
    log "PHASE C — $a hpcp head missing ($src) — skipped"
  fi
done

log "CAMPAIGN COMPLETE — chroma page populated + EMA-hpcp comparison rendered."
log "Δcos12 tables: compare Mantu/.../chroma_steer_20260719{,_hpcp_ema20,_hpcp_ema40}/chroma_steer_manifest.json"
