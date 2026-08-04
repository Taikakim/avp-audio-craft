#!/bin/bash
# Runs the CPU-only de-risking test batch for the frozen-codec clarity plan
# (docs/clarity-recovery-plan-2026-08-02.md). All GPU-free. CONTINUITY 2026-08-02.
cd /home/kim/Projects/SAO
PY=.venv/bin/python
pass=0; fail=0
for t in test_phase_coherence_metric test_adaa_snake_aliasing test_regression_phase_ceiling \
         test_adaa_snake_module test_vpred_ztsnr test_phase_fusion; do
  echo "===== $t ====="
  if $PY eval/$t.py >/tmp/clr_$t.log 2>&1; then echo "  PASS"; pass=$((pass+1)); else echo "  FAIL (see /tmp/clr_$t.log)"; fail=$((fail+1)); fi
done
echo "===== latent_whitening_probe (analysis, no assert-exit) ====="
$PY eval/latent_whitening_probe.py >/tmp/clr_whiten.log 2>&1 && grep -q "PREMISE + MATH HOLD" /tmp/clr_whiten.log && { echo "  PASS"; pass=$((pass+1)); } || { echo "  CHECK"; fail=$((fail+1)); }
echo ""; echo "TOTAL: $pass pass, $fail fail"
