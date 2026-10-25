#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-25)
# Second-seed check of the gain-128/512 ringing on the biggoa finetune (eval/ring_score.py, 2026-10-24).
# On seed 1234 several heads rang at the SAME frequency (~0.92 kHz: AdamW_const, AEMc_ademamix, AWc, C1_switch), which
# could be a note of that prompt + seed pushed forward when the drums go down, not something the heads make. This renders
# the same 8 heads, prompt, cfg, steps and finetune on seed 77, at gains 128/512 x 2/4/6 onsets/s (where the seed-1234
# rings sat), then scores ringing against seed 77's own unguided render.
#   head-made ringing:  the same heads ring again (AdamW_const / AEMc / KSc high, Muon_b64 / AWcG low) at a stable frequency
#   seed artefact:      the 0.92 kHz ring moves or vanishes with the seed, and the head ranking does not hold
# RUN: setsid nohup bash eval/run_ring_seed2_20261025.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
MIR=/home/kim/Projects/mir/mir/bin/python
OUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
OLD=/run/media/kim/Mantu/sa3_control_runs/onset_eval_optcmpFT_biggoa_
PFX=onset_eval_ringS77FT_biggoa_
FT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/epoch=63-step=12480.ckpt
LOG=/home/kim/sao_runs/ring_seed2_20261025.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
until vram_free && KIND=batch NOTE="WINTERMUTE second-seed ringing check, 8 biggoa heads (~1 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

HEADS=""
for d in "$OLD"*; do
  arm=${d#"$OLD"}
  ck=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['head_checkpoint'])" "$d/run_meta.json")
  HEADS="${HEADS:+$HEADS,}$arm=$ck"
done
echo "heads: $HEADS"

"$PY" eval/latch_onset_eval.py --finetune "$FT" --heads "$HEADS" --prefix "$PFX" --out-root "$OUT" \
  --gains 128,512 --densities 2,4,6 --seed 77 \
  --notes "Second-seed ringing check (eval/run_ring_seed2_20261025.sh): the 8 biggoa heads of latch_opt_grid_biggoa on seed 77 instead of 1234, gains 128/512 x 2/4/6 onsets/s. Hypothesis: if the ~0.92 kHz ring heard on seed 1234 is head-made, the same heads ring again at a stable frequency; if it is a note of that seed, it moves or vanishes. Kill: ring ranking across heads at gain 512, d2-4, does not repeat (Spearman < 0.5) -> the ring score is seed-bound and stays advisory."
echo "$(date +%H:%M) render done"
"$MIR" eval/ring_score.py --workers 6 "$OUT/$PFX"* | tail -3

"$PY" - "$OUT" "$PFX" "$OLD" <<'EOF'
import glob, json, os, sys
out, pfx, old = sys.argv[1:4]
rows = []
for d in sorted(glob.glob(f"{out}/{pfx}*")):
    arm = d[len(f"{out}/{pfx}"):]
    p, q = f"{d}/ring_score.json", f"{old}{arm}/ring_score.json"
    if not (os.path.exists(p) and os.path.exists(q)):
        continue
    new = {(c["gain"], c["requested"]): c for c in json.load(open(p))["cells"]}
    ref = {(c["gain"], c["requested"]): c for c in json.load(open(q))["cells"]}
    cells = [{"gain": k[0], "requested": k[1], "ring_s77": new[k]["ring"], "hz_s77": new[k]["ring_hz"],
              "ring_s1234": ref[k]["ring"], "hz_s1234": ref[k]["ring_hz"]} for k in sorted(new) if k in ref]
    rows.append({"arm": arm, "cells": cells})
    m = json.load(open(f"{d}/run_meta.json"))
    m["purpose"] = "Second-seed ringing check: same head, prompt, finetune and grid as onset_eval_optcmpFT_biggoa_" + arm + ", seed 77."
    m["result"] = {"ring_vs_seed1234": cells}
    json.dump(m, open(f"{d}/run_meta.json", "w"), indent=2)
    print(arm, " ".join(f"g{c['gain']:g}d{c['requested']:g} {c['ring_s1234']:.2f}@{c['hz_s1234']:.0f}->{c['ring_s77']:.2f}@{c['hz_s77']:.0f}" for c in cells))
json.dump(rows, open(f"{out}/{pfx}SUMMARY.json", "w"), indent=1)
EOF
echo "$(date +%H:%M) ALL DONE"
