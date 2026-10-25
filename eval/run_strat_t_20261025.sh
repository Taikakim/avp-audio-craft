#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-25)
# E14 first arm: stratified training t on the LatCH onset head (Muon_b64 recipe), against EB64 / EB64r.
#   1 waits for the Granite caption pass (eval/granite_local_pass.py, GPU lock holder) to finish and the card to be free
#   2 trains ST64 = eval/run_eb64_epochs_20261024.sh's EB64r recipe (seed 0, micro-batch 32 x 2, 40 epochs) with
#     --t-sampling stratified, no per-epoch ringing hook, into strat_t_20261025/ST64
#   3 writes the val curve, best val and the per-t held-out loss next to EB64 (0.1802) and EB64r (0.1896) into run_meta.json
# RUN: setsid nohup bash eval/run_strat_t_20261025.sh </dev/null >/dev/null 2>&1 &
SAO=/home/kim/Projects/SAO
LPY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
d=$R/strat_t_20261025/ST64
LOG=/home/kim/sao_runs/strat_t_20261025.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export PYTORCH_TUNABLEOP_ENABLED=0 PYTORCH_TUNABLEOP_TUNING=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1
echo "$(date +%H:%M) waiting for the Granite pass to finish"
while pgrep -f '^/home/kim/Projects/mir/mir/bin/python eval/granite_local_pass\.py|granite_local_pass\.py --captions' >/dev/null; do sleep 60; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE LatCH onset head, stratified-t arm (E14), ~3 h" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date +%H:%M) GPU acquired"

UNITS="--optimizer modular --mod-whitening shampoo --mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95
  --lr-watchdog 2 --grad-clip 1.0 --log-opt-groups --lr 1e-3"
ONSET="--feature onset_per_beat_ts --latent-dir /run/media/kim/Kosmos/latents/latents_goa_bigset --val-group-by relpath
  --val-frac 0.05 --val-seed 0 --seed 0 --standardize --num-workers 16 --mod-warmup-epochs 0.68
  --mod-radial-brake 0.8 --depth 8"
mkdir -p "$d"
"$LPY" - "$d/run_meta.json" <<'EOF'
import json, sys
json.dump({"purpose": "E14 first arm: does stratified training t (one draw per 1/32 bin in every micro-batch) lower the held-out "
                      "loss or the gradient noise of the LatCH onset head, against the iid-t Muon_b64 recipe?",
           "hypothesis": "About half of the held-out loss sits at t > 0.7 and iid t clumps within a batch (the DoRA spike batches "
                         "were high-t clumps). Stratifying keeps the marginal U(0,1) but removes the batch-to-batch variance of the "
                         "t mix, so gradient noise should fall (higher half-batch cosine in grad_noise.jsonl) and val may improve.",
           "kill": "best val not below the iid pair's range (EB64 0.1802, EB64r 0.1896: same seed and recipe, so ~0.01 is run-to-run "
                   "noise) AND no rise of the half-batch gradient cosine -> stratified t buys nothing here.",
           "recipe": "eval/run_eb64_epochs_20261024.sh EB64r (UNITS + ONSET, lr 1e-3, micro-batch 32 x accum 2, --mod-ns-dtype fp32, "
                     "40 epochs, --log-grad-noise 10) + --t-sampling stratified; no epoch hook",
           "reference": ["batch_sweep_20261021/EB64 (best val 0.1802 @ep27)", "eb64_epochs_20261024/EB64r (0.1896 @ep25)"],
           "dataset": "latents_goa_bigset (12,524 crops of 4096 frames, goa corpus, no augmentation)",
           "code": "stable-audio-3 scripts/latch/train_latch.py sample_t / --t-sampling; tests/test_latch_t_sampling.py",
           "script": "eval/run_strat_t_20261025.sh", "result": {}, "kim_feedback": None}, open(sys.argv[1], "w"), indent=1)
EOF
echo "$(date +%H:%M) ST64: stratified t"
t0=$(date +%s)
# shellcheck disable=SC2086
( cd /tmp && "$LPY" "$TRAIN" $UNITS $ONSET --batch-size 32 --grad-accum 2 --epochs 40 --mod-ns-dtype fp32 \
    --t-sampling stratified --log-grad-noise 10 --save-best-only --save-every 10 --save-resume \
    --save-dir "$d" > "$d/train.log" 2>&1 )
rc=$?
echo "$(date +%H:%M) ST64 rc=$rc; $(( ($(date +%s) - t0) / 60 )) min"
"$LPY" - "$d" "$R/batch_sweep_20261021/EB64/train.log" "$R/eb64_epochs_20261024/EB64r/train.log" <<'EOF'
import json, os, re, sys
d, o, r = sys.argv[1:4]
val = lambda p: [float(x) for x in re.findall(r"val=([0-9.]+)", open(p).read())] if os.path.exists(p) else []
vn = val(os.path.join(d, "train.log"))
m = json.load(open(os.path.join(d, "run_meta.json")))
res = {"epochs_trained": len(vn), "val_by_epoch": vn, "EB64_val_by_epoch": val(o), "EB64r_val_by_epoch": val(r)}
if vn:
    res.update(best_val=min(vn), best_epoch=vn.index(min(vn)) + 1)
m["result"] = res
json.dump(m, open(os.path.join(d, "run_meta.json"), "w"), indent=1)
print("ST64 best", res.get("best_val"), "at epoch", res.get("best_epoch"))
EOF
