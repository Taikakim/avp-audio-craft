#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-24)
# Last edited: WINTERMUTE 2026-10-24 -- render epoch by epoch with the ringing cut (gain 256, ring >= 0.5, two consecutive epochs)
# Muon_b64 epoch by epoch (listening pass on latch_opt_grid_biggoa.html, 2026-10-24): Muon_b64 already sounds spectral at gain 512
# and is suspected to learn little after epoch 10-15, while its val kept falling to epoch 27. Its run (batch_sweep_20261021/EB64)
# saved only the best epoch, so:
#   1 waits for eval/run_cont40_20261024.sh (KS512 epochs 21-40) to finish and release the GPU
#   2 retrains EB64 with the exact recipe of eval/run_batch_sweep.sh (seed 0, micro-batch 32 x 2, Newton-Schulz fp32, 40 epochs)
#     plus --save-every-epoch, into eb64_epochs_20261024/EB64r; compares its val curve with the original (same seed -> should match)
#   3 renders every epoch on the biggoa DoRA finetune, gains 64/128/192/256/384/512 x requested 0.5/1/2/4/8/16 onsets/s
#     (bash eval/run_opt_grid_eval.sh EPS) -> latch_eb64_epochs_biggoa.html
# RUN: setsid nohup bash eval/run_eb64_epochs_20261024.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
ORIG=$R/batch_sweep_20261021/EB64
d=$R/eb64_epochs_20261024/EB64r
FT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/epoch=63-step=12480.ckpt
LOG=/home/kim/sao_runs/eb64_epochs_20261024.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
echo "$(date +%H:%M) waiting for the cont40 queue (KS512) to finish"
while pgrep -f '^bash eval/run_cont40_20261024\.sh' >/dev/null; do sleep 120; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE Muon_b64 retrain (every epoch saved, ~3 h) then per-epoch render (~3-4 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

# 2 retrain: eval/run_batch_sweep.sh's UNITS + ONSET with LR=1e-3, NS=fp32 (bf16 was not 10% faster), EB64 = 32 x 2; + every epoch
UNITS="--optimizer modular --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups --lr 1e-3"
ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --mod-warmup-epochs 0.68
  --mod-radial-brake 0.8 --depth 8"
if [ ! -f "$d/DONE" ]; then
  mkdir -p "$d"
  "$LPY" - "$d/run_meta.json" <<'EOF'
import json, sys
json.dump({"purpose": "Muon_b64 (batch_sweep_20261021/EB64) retrained with the same recipe and seed, every epoch saved, to render each "
                      "epoch: where does the head stop learning by ear, and where does the spectral / ringing sound begin?",
           "hypothesis": "Listening pass 2026-10-24 on the biggoa page: Muon_b64 already sounds spectral at gain 512 (overtrained) and "
                         "probably learns very little after epoch 10-15, though val keeps falling to epoch 27.",
           "recipe": "eval/run_batch_sweep.sh UNITS + ONSET, lr 1e-3, micro-batch 32 x accum 2, --mod-ns-dtype fp32, 40 epochs, "
                     "--log-grad-noise 10 --save-best-only --save-every-epoch",
           "reference": "batch_sweep_20261021/EB64 (best val 0.1802 at epoch 27)",
           "dataset": "latents_goa_bigset (12,524 crops of 4096 frames, goa corpus, no augmentation)",
           "script": "eval/run_eb64_epochs_20261024.sh", "result": {}, "kim_feedback": None}, open(sys.argv[1], "w"), indent=1)
EOF
  echo "$(date +%H:%M) EB64r: retrain, every epoch saved"
  t0=$(date +%s)
  # shellcheck disable=SC2086
  ( cd /tmp && "$LPY" "$TRAIN" $UNITS $ONSET --batch-size 32 --grad-accum 2 --epochs 40 --mod-ns-dtype fp32 \
      --log-grad-noise 10 --save-best-only --save-every-epoch --save-dir "$d" > "$d/train.log" 2>&1 )
  rc=$?
  echo "$(date +%H:%M) EB64r rc=$rc; $(( ($(date +%s) - t0) / 60 )) min"
  [ $rc -eq 0 ] || { echo "EB64r failed, no render"; exit 1; }
  touch "$d/DONE"
fi
# same seed and recipe -> the val curve should overlay the original's; record how closely
"$LPY" - "$ORIG/train.log" "$d/train.log" "$d/run_meta.json" <<'EOF'
import json, re, sys
o, n, p = sys.argv[1:4]
vo = [float(x) for x in re.findall(r"val=([0-9.]+)", open(o).read())]
vn = [float(x) for x in re.findall(r"val=([0-9.]+)", open(n).read())]
diff = max(abs(a - b) for a, b in zip(vo, vn)) if vo and vn else None
m = json.load(open(p))
m["result"] = {"val_by_epoch": vn, "best_val": min(vn), "best_epoch": vn.index(min(vn)) + 1,
               "original_val_by_epoch": vo, "max_abs_val_diff_vs_original": diff}
json.dump(m, open(p, "w"), indent=1)
print(f"val curve vs original: max |diff| {diff}; best {min(vn):.4f} at epoch {vn.index(min(vn)) + 1} (original 0.1802 at 27)")
EOF

# 3 per-epoch grid on the biggoa finetune, one epoch at a time with the ringing cut: stop the series once a gain-256 cell
#   rings >= 0.5 (eval/ring_score.py) in two consecutive epochs at the same requested density
SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
PFX=onset_eval_eb64epFT_biggoa_
last=0; cut=""
for e in $(seq 1 40); do
  n=$(printf 'ep%02d' "$e")
  ( cd "$SAO" && "$SAO/.venv/bin/python" eval/latch_onset_eval.py --finetune "$FT" \
      --heads "$n=$d/latch_sa3_onset_per_beat_ts_ep$e.pt" --prefix "$PFX" --out-root "$SRC" \
      --gains 64,128,192,256,384,512 --densities 0.5,1,2,4,8,16 \
      --notes "Every epoch of the Muon_b64 onset head (retrained, same recipe and seed): where does it stop learning, and where does the spectral / ringing sound begin?" ) \
      2>&1 | grep -E "^  $n g" | cut -c1-160
  /home/kim/Projects/mir/mir/bin/python eval/ring_score.py --workers 6 "$SRC/$PFX$n" | tail -1
  last=$e
  cut=$("$LPY" - "$SRC" "$PFX" "$e" <<'EOF'
import json, os, sys
src, pfx, e = sys.argv[1], sys.argv[2], int(sys.argv[3])
def hot(k):
    p = f"{src}/{pfx}ep{k:02d}/ring_score.json"
    return {c["requested"] for c in json.load(open(p))["cells"] if c["gain"] == 256 and c["ring"] >= 0.5} if os.path.exists(p) else set()
both = sorted(hot(e - 1) & hot(e)) if e > 1 else []
print(f"epochs {e - 1}-{e} ring >= 0.5 at gain 256, requested {', '.join(f'{q:g}' for q in both)}/s" if both else "")
EOF
)
  [ -n "$cut" ] && { echo "$(date +%H:%M) RINGING CUT after epoch $e: $cut"; break; }
done
"$LPY" - "$d/run_meta.json" "$last" "$cut" <<'EOF'
import json, sys
p, last, cut = sys.argv[1], int(sys.argv[2]), sys.argv[3]
m = json.load(open(p))
m["render_series"] = {"epochs_rendered": f"1-{last}", "ringing_cut": cut or None,
                      "rule": "stop when a gain-256 cell rings >= 0.5 (eval/ring_score.py) in two consecutive epochs at the same requested density"}
json.dump(m, open(p, "w"), indent=1)
EOF
echo "$(date +%H:%M) eval EPS (epochs 1-$last): scoring + page"
EPS_MAX=$last FT=$FT FT_TAG=biggoa FT_DESC="our DoRA finetune trained on the same goa set as the heads (rank 128, 64 epochs, final epoch, strength 1)" \
  bash eval/run_opt_grid_eval.sh EPS
rc=$?
echo "$(date +%H:%M) eval EPS rc=$rc"
echo "$(date +%H:%M) queue done"
