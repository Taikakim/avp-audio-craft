#!/usr/bin/env bash
# Last edited: CONTINUITY 2026-10-27 -- --allow-uniform-lr added to the modular launch (ModularOptimizer now refuses one lr for matrices and 1-D parameters unless told; docs/TRAINING.md D34)
# Owner: WINTERMUTE (created 2026-10-25)
# The best LatCH onset head (Muon_b64 = batch_sweep_20261021/EB64, best val 0.1802) retrained on 20% of the big set, three arms:
#   F20    20% of latents_goa_bigset's train tracks (seeded, whole tracks), lr 1e-3 (the EB64 recipe otherwise)
#   F20X   the same 20% + all four ai-music sets (chill, prog_psytechno, prog_trance_melodic_techno, organic_dance; 710 crops,
#          train-only), lr 1e-3
#   F20L   the same 20%, lr 8e-4 (20% lower)
# All arms keep EB64's held-out set (617 tracks) and its standardization stats (train_latch.py --train-frac /
# --extra-train-dirs leave both untouched), so val losses compare directly with EB64 0.1802 / EB64r 0.1896 / ST64 0.1819.
# Same 40 epochs as EB64, so each arm takes ~1/5 of EB64's optimizer steps (F20X ~1/4). Every epoch saved.
# RUN: setsid nohup bash eval/run_frac20_20261025.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
D=$R/frac20_20261025
AI=/run/media/kim/Kosmos/latents/latents_aimusic4
LOG=/home/kim/sao_runs/frac20_20261025.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
# free = no process holds >= 1 GiB of VRAM (desktop apps such as LibreOffice hold a few hundred MB and are not jobs)
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH onset head on 20% of the big set, 3 arms (~2 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

BASE="--optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups
  --feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --mod-warmup-epochs 0.68
  --mod-radial-brake 0.8 --depth 8 --batch-size 32 --grad-accum 2 --epochs 40 --mod-ns-dtype fp32
  --log-grad-noise 10 --save-best-only --save-every-epoch --save-resume --train-frac 0.2 --train-frac-seed 0"

run_arm() {   # name lr purpose extra-args...
  local name=$1 lr=$2 purpose=$3; shift 3
  local d=$D/$name
  [ -f "$d/DONE" ] && { echo "$name already done"; return; }
  mkdir -p "$d"
  "$LPY" - "$d/run_meta.json" "$name" "$lr" "$purpose" "$*" <<'EOF'
import json, sys
p, name, lr, purpose, extra = sys.argv[1:6]
json.dump({"purpose": purpose,
           "hypothesis": "EB64 (Muon_b64) was suspected to learn little after epoch 10-15 by ear (listening 2026-10-24) while val kept "
                         "falling; if 20% of the tracks reach a val near EB64's, data volume is not what limits this head, and adding "
                         "other genres (F20X) or a lower lr (F20L) shows which way the head responds.",
           "kill": "Compare best val with EB64 0.1802 / EB64r 0.1896 (same seed and recipe: ~0.01 is run-to-run noise).",
           "arm": name, "lr": float(lr), "extra_args": extra,
           "recipe": "eval/run_eb64_epochs_20261024.sh EB64r recipe (UNITS + ONSET, micro-batch 32 x accum 2, --mod-ns-dtype fp32, "
                     "40 epochs, seed 0) + --train-frac 0.2 --train-frac-seed 0; no epoch hook",
           "reference": ["batch_sweep_20261021/EB64 (best val 0.1802 @ep27)", "eb64_epochs_20261024/EB64r (0.1896 @ep25)",
                         "strat_t_20261025/ST64 (0.1819 @ep40)"],
           "dataset": "latents_goa_bigset: 20% of the 95% train tracks (seeded, whole tracks); val = EB64's 617 held-out tracks; "
                      "standardization stats from the full train split (as EB64). F20X adds latents_aimusic4 chill 115 + "
                      "prog_psytechno 371 + prog_trance_melodic_techno 192 + organic_dance 32 crops, train-only.",
           "code": "stable-audio-3 scripts/latch/train_latch.py --train-frac / --extra-train-dirs; tests/test_latch_train_frac.py",
           "script": "eval/run_frac20_20261025.sh", "result": {}, "kim_feedback": None}, open(p, "w"), indent=1)
EOF
  echo "$(date +%H:%M) $name: lr $lr $*"
  local t0; t0=$(date +%s)
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $BASE --lr "$lr" "$@" --save-dir "$d" > "$d/train.log" 2>&1 )
  local rc=$?
  echo "$(date +%H:%M) $name rc=$rc; $(( ($(date +%s) - t0) / 60 )) min"
  "$LPY" - "$d" <<'EOF'
import json, os, re, sys
d = sys.argv[1]
vn = [float(x) for x in re.findall(r"val=([0-9.]+)", open(os.path.join(d, "train.log")).read())]
m = json.load(open(os.path.join(d, "run_meta.json")))
m["result"] = {"epochs_trained": len(vn), "val_by_epoch": vn}
if vn:
    m["result"].update(best_val=min(vn), best_epoch=vn.index(min(vn)) + 1)
json.dump(m, open(os.path.join(d, "run_meta.json"), "w"), indent=1)
print(os.path.basename(d), "best", m["result"].get("best_val"), "at epoch", m["result"].get("best_epoch"))
EOF
  [ $rc -eq 0 ] && touch "$d/DONE"
}

run_arm F20 1e-3 "LatCH onset head (EB64 recipe) on 20% of the big set's train tracks: how much of EB64's val does a fifth of the data reach?"
run_arm F20X 1e-3 "The F20 subset plus all four ai-music sets (chill, prog psytechno, prog trance / melodic techno, organic dance) as train-only data: does other-genre data help or hurt the goa val?" \
  --extra-train-dirs $AI/chill $AI/prog_psytechno $AI/prog_trance_melodic_techno $AI/organic_dance
run_arm F20L 8e-4 "The F20 subset at a 20% lower lr (8e-4 vs 1e-3): does the smaller data want a gentler step?"
echo "$(date +%H:%M) ALL DONE"
